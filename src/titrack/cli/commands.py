"""CLI commands for testing and manual operation."""

import argparse
import json
import signal
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

from titrack.collector.collector import Collector
from titrack.config.logging import setup_logging, get_logger
from titrack.config.settings import Settings, find_log_file
from titrack.core.models import ItemDelta, Price, Run
from titrack.core.time_tracker import TimeTracker
from titrack.data.zones import get_zone_display_name
from titrack.db.connection import Database
from titrack.db.repository import Repository
from titrack.parser.patterns import FE_CONFIG_BASE_ID
from titrack.parser.player_parser import get_enter_log_path, get_effective_player_id, parse_enter_log, PlayerInfo
from titrack.sync.manager import SyncManager


def _print_delta(delta: ItemDelta, repo: Repository) -> None:
    """Print a delta to console."""
    item_name = repo.get_item_name(delta.config_base_id)
    sign = "+" if delta.delta > 0 else ""
    context_str = f"[{delta.context.name}]" if delta.proto_name else ""
    print(f"  {sign}{delta.delta} {item_name} {context_str}")


def _print_run_start(run: Run) -> None:
    """Print run start to console."""
    hub_str = " (hub)" if run.is_hub else ""
    zone_name = get_zone_display_name(run.zone_signature, run.level_id)
    print(f"\n=== Entered: {zone_name}{hub_str} ===")


def _print_run_end(run: Run, repo: Repository) -> None:
    """Print run end summary to console."""
    if run.is_hub:
        return

    duration = run.duration_seconds or 0
    minutes = int(duration // 60)
    seconds = int(duration % 60)

    print(f"\n--- Run ended: {minutes}m {seconds}s ---")

    # Get run summary
    summary = repo.get_run_summary(run.id)
    if summary:
        fe_gained = summary.get(FE_CONFIG_BASE_ID, 0)
        print(f"  FE gained: {fe_gained}")

        # Show other items
        for config_id, total in sorted(summary.items()):
            if config_id != FE_CONFIG_BASE_ID and total != 0:
                name = repo.get_item_name(config_id)
                sign = "+" if total > 0 else ""
                print(f"  {sign}{total} {name}")


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize database and optionally seed items and prices."""
    settings = Settings.from_args(
        db_path=args.db,
        portable=args.portable,
        seed_file=args.seed,
    )

    print(f"Initializing database at: {settings.db_path}")

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)

    # Seed items if provided
    if settings.seed_file:
        print(f"Seeding items from: {settings.seed_file}")
        count = _seed_items(repo, settings.seed_file)
        print(f"  Loaded {count} items")
    else:
        existing = repo.get_item_count()
        print(f"  {existing} items in database")

    # Seed prices if provided
    prices_seed = getattr(args, 'prices_seed', None)
    if prices_seed:
        prices_path = Path(prices_seed)
        if prices_path.exists():
            print(f"Seeding prices from: {prices_path}")
            count = _seed_prices(repo, prices_path)
            print(f"  Loaded {count} prices")
        else:
            print(f"  Warning: Price seed file not found: {prices_path}")
    else:
        existing = repo.get_price_count()
        print(f"  {existing} prices in database")

    db.close()
    print("Done.")
    return 0


def _seed_items(repo: Repository, seed_file: Path) -> int:
    """Load items from seed file into database."""
    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    items_data = data.get("items", [])
    items = []

    for item_data in items_data:
        item = Item(
            config_base_id=int(item_data["id"]),
            name_en=item_data.get("name_en"),
            name_cn=item_data.get("name_cn"),
            type_cn=item_data.get("type_cn"),
            icon_url=item_data.get("img"),
            url_en=item_data.get("url_en"),
            url_cn=item_data.get("url_cn"),
        )
        items.append(item)

    repo.upsert_items_batch(items)
    return len(items)


def _seed_prices(repo: Repository, seed_file: Path) -> int:
    """Load prices from seed file into database."""
    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    prices_data = data.get("prices", [])
    prices = []

    for price_data in prices_data:
        price = Price(
            config_base_id=int(price_data["id"]),
            price_fe=float(price_data["price_fe"]),
            source=price_data.get("source", "seed"),
            updated_at=datetime.now(),
        )
        prices.append(price)

    repo.upsert_prices_batch(prices)
    return len(prices)


def cmd_parse_file(args: argparse.Namespace) -> int:
    """Parse a log file (non-blocking)."""
    settings = Settings.from_args(
        log_path=args.file,
        db_path=args.db,
        portable=args.portable,
    )

    if not settings.log_path:
        print("Error: No log file specified and auto-detect failed")
        return 1

    if not settings.log_path.exists():
        print(f"Error: Log file not found: {settings.log_path}")
        return 1

    print(f"Parsing: {settings.log_path}")
    print(f"Database: {settings.db_path}")

    # Parse player info from enter log
    player_info = parse_enter_log(get_enter_log_path(settings.log_path))
    if player_info:
        print(f"Player: {player_info.name} ({player_info.season_name})")
    else:
        print("Warning: Could not detect player info")

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    collector = Collector(
        db=db,
        log_path=settings.log_path,
        on_delta=lambda d: _print_delta(d, repo),
        on_run_start=_print_run_start,
        on_run_end=lambda r: _print_run_end(r, repo),
        player_info=player_info,
    )
    collector.initialize()

    from_beginning = args.from_beginning if hasattr(args,
                                                    "from_beginning") else True
    line_count = collector.process_file(from_beginning=from_beginning)

    print(f"\nProcessed {line_count} lines")

    db.close()
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    """Live tail log file with delta output."""
    settings = Settings.from_args(
        log_path=args.file,
        db_path=args.db,
        portable=args.portable,
    )

    if not settings.log_path:
        print("Error: No log file specified and auto-detect failed")
        detected = find_log_file()
        if detected:
            print(f"  Detected: {detected}")
        return 1

    if not settings.log_path.exists():
        print(f"Error: Log file not found: {settings.log_path}")
        return 1

    print(f"Tailing: {settings.log_path}")
    print(f"Database: {settings.db_path}")

    # Parse player info from enter log
    player_info = parse_enter_log(get_enter_log_path(settings.log_path))
    if player_info:
        print(f"Player: {player_info.name} ({player_info.season_name})")
    else:
        print("Warning: Could not detect player info")

    print("Press Ctrl+C to stop\n")

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    collector = Collector(
        db=db,
        log_path=settings.log_path,
        on_delta=lambda d: _print_delta(d, repo),
        on_run_start=_print_run_start,
        on_run_end=lambda r: _print_run_end(r, repo),
        player_info=player_info,
    )
    collector.initialize()

    def signal_handler(sig, frame):
        print("\nStopping...")
        collector.stop()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        collector.tail(poll_interval=settings.poll_interval)
    except KeyboardInterrupt:
        pass

    db.close()
    return 0


def cmd_show_state(args: argparse.Namespace) -> int:
    """Display current inventory state."""
    settings = Settings.from_args(
        db_path=args.db,
        portable=args.portable,
    )

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    states = repo.get_all_slot_states()

    if not states:
        print("No inventory state recorded")
        db.close()
        return 0

    # Aggregate by item
    totals: dict[int, int] = {}
    for state in states:
        if state.num > 0:
            totals[state.config_base_id] = totals.get(state.config_base_id,
                                                      0) + state.num

    print("Current Inventory:")
    print("-" * 40)

    # Sort by quantity descending
    for config_id, total in sorted(totals.items(), key=lambda x: -x[1]):
        name = repo.get_item_name(config_id)
        fe_marker = " (FE)" if config_id == FE_CONFIG_BASE_ID else ""
        print(f"  {total:>8} {name}{fe_marker}")

    print("-" * 40)
    print(f"Total item types: {len(totals)}")

    db.close()
    return 0


def cmd_show_runs(args: argparse.Namespace) -> int:
    """List recent runs."""
    settings = Settings.from_args(
        db_path=args.db,
        portable=args.portable,
    )

    db = Database(settings.db_path)
    db.connect()

    repo = Repository(db)
    runs = repo.get_recent_runs(limit=args.limit)

    if not runs:
        print("No runs recorded")
        db.close()
        return 0

    print(f"Recent Runs (last {len(runs)}):")
    print("-" * 60)

    for run in runs:
        # Format duration
        if run.duration_seconds:
            minutes = int(run.duration_seconds // 60)
            seconds = int(run.duration_seconds % 60)
            duration_str = f"{minutes}m {seconds}s"
        else:
            duration_str = "active"

        # Get FE for run
        summary = repo.get_run_summary(run.id)
        fe_gained = summary.get(FE_CONFIG_BASE_ID, 0)

        hub_str = "[hub] " if run.is_hub else ""
        zone_name = get_zone_display_name(run.zone_signature, run.level_id)
        print(f"  #{run.id:3} {hub_str}{zone_name[:30]:<30} "
              f"{duration_str:>10} FE: {fe_gained:+d}")

    print("-" * 60)

    db.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the web server with optional background collector."""
    from titrack.config.paths import is_frozen
    from titrack.version import __version__

    # Set up logging early
    portable = getattr(args, 'portable', False) or is_frozen()
    # Show console output only in dev mode or when using --no-window
    console_output = not is_frozen() or getattr(args, 'no_window', False)
    logger = setup_logging(portable=portable, console=console_output)

    logger.info(f"TITrack v{__version__} starting...")

    # Import here to avoid loading FastAPI when not needed
    try:
        import uvicorn
        from titrack.api.app import create_app
    except ImportError:
        logger.error("FastAPI and Uvicorn are required for the serve command.")
        logger.error("Install with: pip install fastapi uvicorn[standard]")
        return 1

    # First, check for saved log_directory in preferences (highest priority)
    from titrack.config.preferences import get_preference
    from titrack.config.settings import find_log_file
    
    saved_log_dir = get_preference("log_directory")
    saved_log_path = None
    
    if saved_log_dir:
        # Try using saved directory first (user's explicit choice)
        found_path = find_log_file(custom_game_dir=saved_log_dir)
        if found_path and found_path.exists():
            saved_log_path = found_path
            logger.info(f"Using saved log directory: {saved_log_dir}")
    
    settings = Settings.from_args(
        log_path=args.file or (str(saved_log_path) if saved_log_path else None),
        db_path=args.db,
        portable=args.portable,
    )

    logger.info(f"Database: {settings.db_path}")

    # If still no log path, try database setting as fallback
    if not settings.log_path or not settings.log_path.exists():
        temp_db = Database(settings.db_path)
        temp_db.connect()
        try:
            temp_repo = Repository(temp_db)
            db_log_dir = temp_repo.get_setting("log_directory")
        finally:
            temp_db.close()

        if db_log_dir and db_log_dir != saved_log_dir:
            found_path = find_log_file(custom_game_dir=db_log_dir)
            if found_path and found_path.exists():
                settings.log_path = found_path
                logger.info(f"Using database log directory: {db_log_dir}")

    # Check if we should use native window mode
    use_window = is_frozen() and not getattr(args, 'no_window', False)

    if use_window:
        # Try window mode - it will fall back to browser mode on failure
        return _serve_with_window(args, settings, logger)
    else:
        args.browser_mode = False
        return _serve_browser_mode(args, settings, logger)


def _serve_browser_mode(args: argparse.Namespace, settings: Settings,
                        logger) -> int:
    """Run server in browser mode (original behavior)."""
    import uvicorn
    from titrack.api.app import create_app

    collector = None
    collector_thread = None
    collector_db = None
    player_info = None
    sync_manager = None
    api_db = None
    time_tracker = TimeTracker()

    try:
        # Start collector in background if log file is available
        if settings.log_path and settings.log_path.exists():
            logger.info(f"Log file: {settings.log_path}")

            # Don't parse player info on startup - wait for live log detection
            # This prevents showing stale data from a previously logged-in character
            player_info = None
            logger.info("Waiting for character login...")

            # Collector gets its own database connection
            collector_db = Database(settings.db_path)
            collector_db.connect()

            collector_repo = Repository(collector_db)

            # Initialize sync manager (uses collector's DB connection)
            # Don't set season context yet - wait for player detection from live log
            sync_manager = SyncManager(collector_db)
            sync_manager.initialize()

            def on_price_update(price):
                item_name = collector_repo.get_item_name(price.config_base_id)
                logger.info(f"[Price] {item_name}: {price.price_fe:.6f} FE")

            # Placeholder for player change callback (set after app is created)
            player_change_callback = [
                None
            ]  # Use list to allow closure modification

            def on_player_change(new_player_info):
                logger.info(
                    f"[Player] Switched to: {new_player_info.name} ({new_player_info.season_name})"
                )
                # Update app state if callback is set
                if player_change_callback[0]:
                    player_change_callback[0](new_player_info)

            collector = Collector(
                db=collector_db,
                log_path=settings.log_path,
                on_delta=lambda d: None,  # Silent operation
                on_run_start=lambda r: None,
                on_run_end=lambda r: None,
                on_price_update=on_price_update,
                on_player_change=on_player_change,
                player_info=player_info,
                sync_manager=sync_manager,
                time_tracker=time_tracker,
            )
            collector.initialize()

            def run_collector():
                try:
                    collector.tail(poll_interval=settings.poll_interval)
                except Exception as e:
                    logger.error(f"Collector error: {e}")

            collector_thread = threading.Thread(target=run_collector,
                                                daemon=True)
            collector_thread.start()
            logger.info("Collector started in background")
        else:
            logger.warning("No log file found - collector not started")
            if settings.log_path:
                logger.warning(f"Expected: {settings.log_path}")

        # API gets its own database connection
        api_db = Database(settings.db_path)
        api_db.connect()

        # Create FastAPI app
        app = create_app(
            db=api_db,
            log_path=settings.log_path,
            collector_running=collector is not None,
            collector=collector,
            player_info=player_info,
            sync_manager=sync_manager,
            browser_mode=getattr(args, 'browser_mode', False),
        )

        # Override the time_tracker with the one connected to the collector
        app.state.time_tracker = time_tracker

        # Set up player change callback to update app state
        if collector is not None:

            def update_app_player(new_player_info):
                app.state.player_info = new_player_info
                # Also update the API repository context with effective player_id
                if hasattr(app.state, 'repo'):
                    effective_id = get_effective_player_id(new_player_info)
                    app.state.repo.set_player_context(
                        new_player_info.season_id, effective_id)
                # Update sync manager season context
                if hasattr(app.state,
                           'sync_manager') and app.state.sync_manager:
                    app.state.sync_manager.set_season_context(
                        new_player_info.season_id)

            player_change_callback[0] = update_app_player

        # Set up graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutting down...")
            if collector:
                collector.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Open browser unless disabled
        url = f"http://127.0.0.1:{args.port}"
        if not args.no_browser:
            logger.info(f"Opening browser at {url}")
            webbrowser.open(url)

        logger.info(f"Starting server on port {args.port}")

        # Run server (log_config=None to avoid frozen mode logging issues)
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="warning",
            log_config=None,
        )
    finally:
        # Ensure proper cleanup of all resources
        if sync_manager:
            try:
                sync_manager.stop_background_sync()
            except Exception as e:
                logger.error(f"Error stopping sync manager: {e}")
        if collector:
            try:
                collector.stop()
            except Exception as e:
                logger.error(f"Error stopping collector: {e}")
        if collector_db:
            try:
                collector_db.close()
            except Exception as e:
                logger.error(f"Error closing collector DB: {e}")
        if api_db:
            try:
                api_db.close()
            except Exception as e:
                logger.error(f"Error closing API DB: {e}")

    return 0


def _serve_with_window(args: argparse.Namespace, settings: Settings,
                       logger) -> int:
    """Run server with native window using pywebview."""
    from titrack.config.paths import is_frozen

    # Test pywebview/pythonnet availability early, before starting any resources
    try:
        import webview
        # Try to initialize the CLR/pythonnet which pywebview uses on Windows
        # This triggers the "Failed to resolve Python.Runtime.Loader.Initialize" error
        # if .NET components are missing, before we start any other resources
        try:
            import clr_loader
            clr_loader.get_coreclr()
        except Exception:
            # clr_loader not available or failed - try direct pythonnet
            try:
                import clr
            except Exception:
                pass  # If both fail, webview.start() will give a clearer error
    except ImportError as e:
        logger.warning(f"pywebview not available: {e}")
        logger.warning("Falling back to browser mode...")
        logger.info(
            "Tip: Install .NET Desktop Runtime or Visual C++ Redistributable for native window mode"
        )
        args.no_browser = False
        args.browser_mode = True  # Flag for UI to show Exit button
        return _serve_browser_mode(args, settings, logger)

    import uvicorn
    from titrack.api.app import create_app

    collector = None
    collector_thread = None
    collector_db = None
    player_info = None
    sync_manager = None
    api_db = None
    server_thread = None
    overlay_process = None
    shutdown_event = threading.Event()
    time_tracker = TimeTracker()

    def cleanup():
        """Clean up all resources."""
        logger.info("Cleaning up resources...")
        shutdown_event.set()

        if overlay_process:
            try:
                overlay_process.terminate()
                overlay_process.wait(timeout=3)
            except Exception:
                try:
                    overlay_process.kill()
                except Exception:
                    pass
        if sync_manager:
            try:
                sync_manager.stop_background_sync()
            except Exception as e:
                logger.error(f"Error stopping sync manager: {e}")
        if collector:
            try:
                collector.stop()
            except Exception as e:
                logger.error(f"Error stopping collector: {e}")
        if collector_db:
            try:
                collector_db.close()
            except Exception as e:
                logger.error(f"Error closing collector DB: {e}")
        if api_db:
            try:
                api_db.close()
            except Exception as e:
                logger.error(f"Error closing API DB: {e}")

    try:
        # Start collector in background if log file is available
        if settings.log_path and settings.log_path.exists():
            logger.info(f"Log file: {settings.log_path}")
            player_info = None
            logger.info("Waiting for character login...")

            collector_db = Database(settings.db_path)
            collector_db.connect()

            collector_repo = Repository(collector_db)

            sync_manager = SyncManager(collector_db)
            sync_manager.initialize()

            def on_price_update(price):
                item_name = collector_repo.get_item_name(price.config_base_id)
                logger.info(f"[Price] {item_name}: {price.price_fe:.6f} FE")

            player_change_callback = [None]

            def on_player_change(new_player_info):
                logger.info(
                    f"[Player] Switched to: {new_player_info.name} ({new_player_info.season_name})"
                )
                if player_change_callback[0]:
                    player_change_callback[0](new_player_info)

            collector = Collector(
                db=collector_db,
                log_path=settings.log_path,
                on_delta=lambda d: None,
                on_run_start=lambda r: None,
                on_run_end=lambda r: None,
                on_price_update=on_price_update,
                on_player_change=on_player_change,
                player_info=player_info,
                sync_manager=sync_manager,
                time_tracker=time_tracker,
            )
            collector.initialize()

            def run_collector():
                try:
                    collector.tail(poll_interval=settings.poll_interval)
                except Exception as e:
                    logger.error(f"Collector error: {e}")

            collector_thread = threading.Thread(target=run_collector,
                                                daemon=True)
            collector_thread.start()
            logger.info("Collector started in background")
        else:
            logger.warning("No log file found - collector not started")
            if settings.log_path:
                logger.warning(f"Expected: {settings.log_path}")

        # API gets its own database connection
        api_db = Database(settings.db_path)
        api_db.connect()

        # Create FastAPI app (window mode, not browser fallback)
        app = create_app(
            db=api_db,
            log_path=settings.log_path,
            collector_running=collector is not None,
            collector=collector,
            player_info=player_info,
            sync_manager=sync_manager,
            browser_mode=False,
        )

        # Override the time_tracker with the one connected to the collector
        app.state.time_tracker = time_tracker

        # Set up player change callback
        if collector is not None:

            def update_app_player(new_player_info):
                app.state.player_info = new_player_info
                if hasattr(app.state, 'repo'):
                    effective_id = get_effective_player_id(new_player_info)
                    app.state.repo.set_player_context(
                        new_player_info.season_id, effective_id)
                if hasattr(app.state, 'sync_manager') and app.state.sync_manager:
                    app.state.sync_manager.set_season_context(new_player_info.season_id)

            player_change_callback[0] = update_app_player

        # Start uvicorn server in a thread
        host = getattr(args, 'host', '127.0.0.1')
        port = getattr(args, 'port', 8000)

        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        def run_server():
            try:
                server.run()
            except Exception as e:
                logger.error(f"Server error: {e}")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        logger.info(f"Server started at http://{host}:{port}")

        # Wait for server to be ready
        import time
        for _ in range(50):
            try:
                import urllib.request
                urllib.request.urlopen(f"http://{host}:{port}/api/status", timeout=0.5)
                break
            except Exception:
                time.sleep(0.1)

        # Create pywebview Api class for JS interop
        class Api:
            def __init__(self):
                self._window = None
                self._api_host = host
                self._api_port = port

            def set_window(self, window):
                self._window = window

            def minimize(self):
                if self._window:
                    self._window.minimize()

            def close(self):
                if self._window:
                    self._window.destroy()

            def browse_folder(self):
                if self._window:
                    result = self._window.create_file_dialog(
                        webview.FOLDER_DIALOG,
                        allow_multiple=False
                    )
                    if result and len(result) > 0:
                        return result[0]
                return None

            def get_window_geometry(self):
                if self._window:
                    return {
                        'x': self._window.x,
                        'y': self._window.y,
                        'width': self._window.width,
                        'height': self._window.height
                    }
                return None

            def set_window_geometry(self, x, y, width, height):
                if self._window:
                    self._window.move(x, y)
                    self._window.resize(width, height)

            def toggle_on_top(self, enabled):
                """Toggle always-on-top window state."""
                if self._window:
                    import threading as _threading
                    def _set():
                        self._window.on_top = enabled
                    _threading.Thread(target=_set, daemon=True).start()
                    return enabled
                return False

            def set_overlay_opacity(self, value):
                """Set overlay opacity via HTTP API (overlay runs as subprocess)."""
                return self._overlay_config_update({"opacity": float(value)})

            def set_overlay_scale(self, scale):
                """Set overlay scale via HTTP API."""
                return self._overlay_config_update({"scale": float(scale)})

            def toggle_overlay(self):
                """Toggle overlay visibility via HTTP API."""
                try:
                    url = f"http://{self._api_host}:{self._api_port}/api/overlay/config"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=1) as resp:
                        config = json.loads(resp.read().decode("utf-8"))
                    new_visible = not config.get("visible", True)
                    self._overlay_config_update({"visible": new_visible})
                    return new_visible
                except Exception:
                    return False

            def _overlay_config_update(self, updates):
                """Send overlay config update to HTTP API."""
                try:
                    url = f"http://{self._api_host}:{self._api_port}/api/overlay/config"
                    data = json.dumps(updates).encode("utf-8")
                    req = urllib.request.Request(url, data=data, method="POST")
                    req.add_header("Content-Type", "application/json")
                    with urllib.request.urlopen(req, timeout=1) as resp:
                        return resp.status == 200
                except Exception:
                    return False

            def set_overlay_lock(self, locked):
                """Set overlay lock state via HTTP API."""
                return self._overlay_config_update({"locked": bool(locked)})

            def set_overlay_columns(self, columns):
                """Set visible overlay columns via HTTP API."""
                return self._overlay_config_update({"visible_columns": list(columns)})

            def set_overlay_text_shadow(self, enabled):
                """Set overlay text shadow via HTTP API."""
                return self._overlay_config_update({"text_shadow": bool(enabled)})


        api = Api()

        # Launch overlay as a SEPARATE PROCESS.
        # WPF overlay (TITrackOverlay.exe) is preferred for clean transparency.
        # Falls back to Python/GDI overlay if WPF exe is not available.
        # Uses Windows Job Object so overlay auto-terminates if main app crashes.
        job_handle = None
        try:
            # Look for WPF overlay executable
            wpf_overlay = None

            if is_frozen():
                # Frozen mode: PyInstaller bundles overlay in _internal/overlay/
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    wpf_overlay = Path(meipass) / "overlay" / "TITrackOverlay.exe"
                else:
                    wpf_overlay = Path(sys.executable).parent / "_internal" / "overlay" / "TITrackOverlay.exe"
            else:
                # Dev mode: check overlay/publish directory relative to project root
                wpf_overlay = Path(__file__).resolve().parent.parent.parent.parent / "overlay" / "publish" / "TITrackOverlay.exe"

            if wpf_overlay and wpf_overlay.exists():
                overlay_cmd = [str(wpf_overlay), "--host", host, "--port", str(port)]
                logger.info(f"Using WPF overlay: {wpf_overlay}")
            elif is_frozen():
                overlay_cmd = [sys.executable, "--overlay",
                               "--host", host, "--port", str(port)]
                logger.info("WPF overlay not found, using GDI fallback")
            else:
                overlay_cmd = [sys.executable, "-m", "titrack", "--overlay",
                               "--host", host, "--port", str(port)]
                logger.info("WPF overlay not found, using GDI fallback")

            overlay_process = subprocess.Popen(
                overlay_cmd,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logger.info(f"Overlay subprocess started (PID: {overlay_process.pid})")

            # Assign overlay to a Windows Job Object so it dies with the parent
            try:
                import ctypes
                import ctypes.wintypes as wt
                kernel32 = ctypes.windll.kernel32
                job_handle = kernel32.CreateJobObjectW(None, None)
                if job_handle:
                    # JOBOBJECT_EXTENDED_LIMIT_INFORMATION with KILL_ON_JOB_CLOSE
                    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", wt.DWORD),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", wt.DWORD),
                            ("Affinity", ctypes.c_size_t),
                            ("PriorityClass", wt.DWORD),
                            ("SchedulingClass", wt.DWORD),
                        ]
                    class IO_COUNTERS(ctypes.Structure):
                        _fields_ = [("v", ctypes.c_uint64 * 6)]
                    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                            ("IoInfo", IO_COUNTERS),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryUsed", ctypes.c_size_t),
                            ("PeakJobMemoryUsed", ctypes.c_size_t),
                        ]
                    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
                    kernel32.SetInformationJobObject(
                        job_handle, 9,  # JobObjectExtendedLimitInformation
                        ctypes.byref(info), ctypes.sizeof(info))
                    kernel32.AssignProcessToJobObject(
                        job_handle, int(overlay_process._handle))
                    logger.info("Overlay assigned to job object (auto-kill on exit)")
            except Exception as e:
                logger.debug(f"Job object setup skipped: {e}")
        except Exception as e:
            logger.warning(f"Could not start overlay subprocess: {e}")
            overlay_process = None

        # Create pywebview window (single window only - no second window!)
        window = webview.create_window(
            title="토치라이트 결정 트래커",
            url=f"http://{host}:{port}",
            width=800,
            height=1000,
            min_size=(580, 400),
            resizable=True,
            frameless=True,
            easy_drag=False,
            js_api=api,
        )
        api.set_window(window)

        # Start webview (blocks until window is closed)
        webview.start()

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        cleanup()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="titrack",
        description="Torchlight Infinite Local Loot Tracker",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Database file path",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Use portable mode (data beside exe)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument(
        "--seed",
        type=str,
        help="Path to item seed JSON file",
    )
    init_parser.add_argument(
        "--prices-seed",
        type=str,
        help="Path to price seed JSON file",
    )

    # parse-file command
    parse_parser = subparsers.add_parser("parse-file", help="Parse a log file")
    parse_parser.add_argument(
        "file",
        type=str,
        nargs="?",
        help="Log file to parse (auto-detects if not specified)",
    )
    parse_parser.add_argument(
        "--from-beginning",
        action="store_true",
        default=True,
        help="Parse from beginning (default)",
    )
    parse_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last position",
    )

    # tail command
    tail_parser = subparsers.add_parser("tail", help="Live tail log file")
    tail_parser.add_argument(
        "file",
        type=str,
        nargs="?",
        help="Log file to tail (auto-detects if not specified)",
    )

    # show-state command
    subparsers.add_parser("show-state", help="Display current inventory")

    # show-runs command
    runs_parser = subparsers.add_parser("show-runs", help="List recent runs")
    runs_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of runs to show (default: 20)",
    )

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start web server")
    serve_parser.add_argument(
        "file",
        type=str,
        nargs="?",
        help="Log file to monitor (auto-detects if not specified)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run server on (default: 8000)",
    )
    serve_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    serve_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )
    serve_parser.add_argument(
        "--no-window",
        action="store_true",
        help=
        "Run in browser mode instead of native window (useful for debugging)",
    )

    return parser


def main() -> int:
    """Main entry point."""
    from titrack.config.paths import is_frozen
    from titrack.version import __version__

    parser = create_parser()
    args = parser.parse_args()

    # Default to serve mode when running as frozen exe with no command
    if args.command is None:
        if is_frozen():
            # Running as packaged EXE - default to serve with portable mode and native window
            args.command = "serve"
            args.file = None
            args.port = 8000
            args.host = "127.0.0.1"
            args.no_browser = True  # Window mode handles its own display
            args.no_window = False  # Use native window by default
            args.portable = True  # Force portable mode for frozen exe
        else:
            parser.print_help()
            return 0

    commands = {
        "init": cmd_init,
        "parse-file": cmd_parse_file,
        "tail": cmd_tail,
        "show-state": cmd_show_state,
        "show-runs": cmd_show_runs,
        "serve": cmd_serve,
    }

    cmd_func = commands.get(args.command)
    if cmd_func is None:
        print(f"Unknown command: {args.command}")
        return 1

    return cmd_func(args)


if __name__ == "__main__":
    sys.exit(main())
