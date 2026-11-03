"""PyInstaller entry point (a plain script, so absolute imports work when frozen)."""

import sys

from offline_tools.app import main

sys.exit(main())
