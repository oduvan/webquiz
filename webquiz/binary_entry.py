#!/usr/bin/env python3
"""
Entry point for PyInstaller binary.
Sets default paths to executable directory before calling main CLI.
"""

import sys
from pathlib import Path
import webquiz.cli

exe_dir = Path(sys.executable).parent

webquiz.cli.main(
    default_quizzes_dir=str(exe_dir / "quizzes"),
    default_logs_dir=str(exe_dir / "logs"),
    default_csv_dir=str(exe_dir / "data"),
    default_static_dir=str(exe_dir / "static")
)