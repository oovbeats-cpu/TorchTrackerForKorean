"""Update manager - orchestrates update checking and installation."""

import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from titrack.config.paths import is_frozen
from titrack.updater.github_client import GitHubClient, ReleaseInfo, is_newer_version
from titrack.updater.installer import UpdateInstaller
from titrack.version import __version__


class UpdateStatus(Enum):
    """Status of update check/download."""

    IDLE = "idle"
    CHECKING = "checking"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    READY = "ready"
    INSTALLING = "installing"
    ERROR = "error"
    UP_TO_DATE = "up_to_date"


@dataclass
class UpdateInfo:
    """Information about available update."""

    status: UpdateStatus
    current_version: str
    latest_version: Optional[str] = None
    release_notes: Optional[str] = None
    release_url: Optional[str] = None
    download_url: Optional[str] = None
    download_size: Optional[int] = None
    download_progress: int = 0  # Bytes downloaded
    error_message: Optional[str] = None
    checked_at: Optional[datetime] = None


class UpdateManager:
    """
    Manages update checking and installation.

    Handles:
    - Checking GitHub for new releases
    - Downloading updates in background
    - Creating update scripts
    - Triggering restart for update
    """

    GITHUB_OWNER = "oovbeats-cpu"
    GITHUB_REPO = "TorchTrackerForKorean"

    def __init__(
        self,
        on_status_change: Optional[Callable[[UpdateInfo], None]] = None,
    ) -> None:
        """
        Initialize update manager.

        Args:
            on_status_change: Callback when update status changes
        """
        self._github = GitHubClient(self.GITHUB_OWNER, self.GITHUB_REPO)
        self._installer = UpdateInstaller(on_progress=self._on_download_progress)
        self._on_status_change = on_status_change

        self._status = UpdateStatus.IDLE
        self._latest_release: Optional[ReleaseInfo] = None
        self._download_progress = 0
        self._download_total = 0
        self._error_message: Optional[str] = None
        self._checked_at: Optional[datetime] = None
        self._update_script_path: Optional[Path] = None

        self._check_thread: Optional[threading.Thread] = None
        self._download_thread: Optional[threading.Thread] = None

    @property
    def current_version(self) -> str:
        """Get current application version."""
        return __version__

    @property
    def can_update(self) -> bool:
        """Check if updates are possible (frozen mode only)."""
        return is_frozen()

    def get_status(self) -> UpdateInfo:
        """Get current update status."""
        return UpdateInfo(
            status=self._status,
            current_version=self.current_version,
            latest_version=self._latest_release.version if self._latest_release else None,
            release_notes=self._latest_release.body if self._latest_release else None,
            release_url=self._latest_release.html_url if self._latest_release else None,
            download_url=self._latest_release.download_url if self._latest_release else None,
            download_size=self._latest_release.download_size if self._latest_release else None,
            download_progress=self._download_progress,
            error_message=self._error_message,
            checked_at=self._checked_at,
        )

    def _set_status(self, status: UpdateStatus) -> None:
        """Update status and notify callback."""
        self._status = status
        if self._on_status_change:
            self._on_status_change(self.get_status())

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        """Handle download progress updates."""
        self._download_progress = downloaded
        self._download_total = total
        if self._on_status_change:
            self._on_status_change(self.get_status())

    def check_for_updates(self, async_check: bool = True) -> Optional[UpdateInfo]:
        """
        Check for available updates.

        Args:
            async_check: If True, runs in background thread

        Returns:
            UpdateInfo if sync, None if async (use callback)
        """
        if async_check:
            if self._check_thread and self._check_thread.is_alive():
                return None  # Already checking

            self._check_thread = threading.Thread(
                target=self._do_check,
                daemon=True,
                name="update-check",
            )
            self._check_thread.start()
            return None
        else:
            self._do_check()
            return self.get_status()

    def _do_check(self) -> None:
        """Perform the actual update check (disabled for security - no external calls)."""
        self._checked_at = datetime.now()
        self._set_status(UpdateStatus.UP_TO_DATE)
        return
        
        # GitHub API check disabled for security
        self._set_status(UpdateStatus.CHECKING)
        self._error_message = None

        try:
            release = self._github.get_latest_release()
            self._checked_at = datetime.now()

            if not release:
                self._error_message = "Failed to check for updates"
                self._set_status(UpdateStatus.ERROR)
                return

            self._latest_release = release

            if is_newer_version(self.current_version, release.version):
                self._set_status(UpdateStatus.AVAILABLE)
            else:
                self._set_status(UpdateStatus.UP_TO_DATE)

        except Exception as e:
            self._error_message = str(e)
            self._set_status(UpdateStatus.ERROR)

    def download_update(self, async_download: bool = True) -> bool:
        """
        Download the available update.

        Args:
            async_download: If True, runs in background thread

        Returns:
            True if download started/completed, False on error
        """
        if self._status != UpdateStatus.AVAILABLE:
            return False

        if not self._latest_release or not self._latest_release.download_url:
            self._error_message = "No download URL available"
            self._set_status(UpdateStatus.ERROR)
            return False

        if async_download:
            if self._download_thread and self._download_thread.is_alive():
                return False  # Already downloading

            self._download_thread = threading.Thread(
                target=self._do_download,
                daemon=True,
                name="update-download",
            )
            self._download_thread.start()
            return True
        else:
            self._do_download()
            return self._status == UpdateStatus.READY

    def _do_download(self) -> None:
        """Perform the actual download."""
        self._set_status(UpdateStatus.DOWNLOADING)
        self._download_progress = 0
        self._error_message = None

        try:
            # Download ZIP
            zip_path = self._installer.download_update(
                self._latest_release.download_url,
                self._latest_release.download_size,
            )

            if not zip_path:
                self._error_message = "Download failed"
                self._set_status(UpdateStatus.ERROR)
                return

            # Extract and prepare
            update_dir = self._installer.prepare_update(zip_path)
            if not update_dir:
                self._error_message = "Failed to extract update"
                self._set_status(UpdateStatus.ERROR)
                return

            # Create update script
            if self.can_update:
                script_path = self._installer.create_update_script(update_dir)
                if script_path:
                    self._update_script_path = script_path
                else:
                    self._error_message = "Failed to create update script"
                    self._set_status(UpdateStatus.ERROR)
                    return

            self._set_status(UpdateStatus.READY)

        except Exception as e:
            self._error_message = str(e)
            self._set_status(UpdateStatus.ERROR)

    def install_update(self) -> bool:
        """
        Install the downloaded update.

        WARNING: This will exit the application!

        Returns:
            False if installation cannot start (only returns on error)
        """
        if self._status != UpdateStatus.READY:
            return False

        if not self.can_update:
            self._error_message = "Cannot update in development mode"
            return False

        if not self._update_script_path:
            self._error_message = "No update script available"
            return False

        self._set_status(UpdateStatus.INSTALLING)

        # This will not return if successful
        return self._installer.apply_update(self._update_script_path)

    def cancel(self) -> None:
        """Cancel any ongoing update operations and clean up."""
        self._installer.cleanup()
        self._set_status(UpdateStatus.IDLE)
