#!/usr/bin/env python3

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Build a binary executable using PyInstaller."""
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    
    # Check if PyInstaller is available
    try:
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("PyInstaller is not installed or not in PATH. Install it with: poetry install")
        sys.exit(1)
    
    # PyInstaller command - use the binary entry point
    binary_entry = project_root / "webquiz" / "binary_entry.py"
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "webquiz",
        "--add-data", f"{project_root / 'webquiz' / 'templates'}:webquiz/templates",
        "--add-data", f"{project_root / 'webquiz' / 'server_config.yaml.example'}:webquiz/",
        "--hidden-import", "webquiz.server",
        str(binary_entry)
    ]
    
    print(f"Building binary with PyInstaller...")
    print(f"Working directory: {project_root}")
    
    # Run PyInstaller
    try:
        result = subprocess.run(cmd, cwd=project_root, check=True)
        print("\n✅ Build completed successfully!")
        print(f"📁 Binary location: {project_root}/dist/webquiz")
        print("\n🚀 To run the binary:")
        print("   ./dist/webquiz")
        print("   ./dist/webquiz --help")
        print("   ./dist/webquiz --master-key secret123")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with exit code {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    main()