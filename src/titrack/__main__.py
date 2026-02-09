"""Entry point for running as module: python -m titrack

Supports --overlay mode for running the overlay as a subprocess.
This avoids creating Win32 windows in the main pywebview process,
which would break easy_drag functionality.
"""

import sys

# Check for overlay subprocess mode BEFORE importing heavy dependencies.
# This way the overlay process only loads ctypes + urllib (no FastAPI, SQLite, etc.)
if len(sys.argv) > 1 and sys.argv[1] == "--overlay":
    from titrack.win32.overlay_manager import run_overlay_main
    sys.exit(run_overlay_main())

from titrack.cli.commands import main

if __name__ == "__main__":
    sys.exit(main())
