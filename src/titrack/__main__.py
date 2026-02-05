"""Entry point for running as module: python -m titrack"""

import sys

from titrack.cli.commands import main

if __name__ == "__main__":
    sys.exit(main())
