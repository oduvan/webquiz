#!/usr/bin/env python3
"""
Entry point for PyInstaller binary.
Sets executable directory for relative path resolution.
"""

import sys
import os
from pathlib import Path
import webquiz.cli


def main():
    # Set executable directory for relative path resolution
    # For PyInstaller binaries, we need to detect the correct executable path
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # Running in a PyInstaller bundle
        exe_dir = Path(sys.argv[0]).parent.resolve()
    else:
        # Running normally (should not happen in binary_entry.py, but fallback)
        exe_dir = Path(sys.executable).parent

    os.environ["WEBQUIZ_BINARY_DIR"] = str(exe_dir)

    # Change working directory to binary location (important for macOS)
    os.chdir(exe_dir)

    # Mark this as binary execution for browser auto-opening
    os.environ["WEBQUIZ_IS_BINARY"] = "1"

    # Start the main application
    webquiz.cli.main()


if __name__ == "__main__":
    main()
