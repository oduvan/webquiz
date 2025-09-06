#!/usr/bin/env python3
"""
Entry point for PyInstaller binary.
Sets executable directory for relative path resolution.
"""

import sys
import os
from pathlib import Path
import webquiz.cli

# Set executable directory for relative path resolution
exe_dir = Path(sys.executable).parent
os.environ['WEBQUIZ_BINARY_DIR'] = str(exe_dir)

webquiz.cli.main()