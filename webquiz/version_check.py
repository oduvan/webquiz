import asyncio
import aiohttp
import json
import logging
from typing import Optional, Tuple, List

from webquiz import __version__ as current_package_version

logger = logging.getLogger(__name__)

PYPI_API_URL = "https://pypi.org/pypi/webquiz/json"
UPDATE_URL = "https://github.com/oduvan/webquiz/releases"

async def get_latest_version_from_pypi() -> Optional[str]:
    """
    Fetch the latest release version from PyPI API.
    
    Returns:
        Latest version string (e.g., "1.0.8") or None if unable to fetch
    """
    try:
        timeout = aiohttp.ClientTimeout(total=5)  # 5 second timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(PYPI_API_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    info = data.get('info', {})
                    latest_version = info.get('version', '')
                    return latest_version
                else:
                    logger.debug(f"PyPI API returned status {response.status}")
                    return None
    except asyncio.TimeoutError:
        logger.debug("Timeout while checking for updates")
        return None
    except Exception as e:
        logger.debug(f"Error checking for updates: {e}")
        return None

def get_current_version() -> str:
    """
    Get the currently installed version of webquiz.
    
    Returns:
        Current version string or "unknown" if unable to determine
    """
    try:
        return current_package_version
    except Exception:
        return 'unknown'

def parse_version(version_str: str) -> List[int]:
    """
    Parse version string into list of integers for comparison.
    
    Args:
        version_str: Version string like "1.0.5"
        
    Returns:
        List of integers like [1, 0, 5]
    """
    try:
        # Remove any 'v' prefix and split by dots
        clean_version = version_str.lstrip('v').strip()
        parts = clean_version.split('.')
        return [int(part) for part in parts if part.isdigit()]
    except (ValueError, AttributeError):
        return [0]

def is_newer_version(current: str, latest: str) -> bool:
    """
    Compare version strings to determine if latest is newer than current.
    
    Args:
        current: Current version string
        latest: Latest version string from PyPI
        
    Returns:
        True if latest version is newer than current
    """
    if current == 'unknown' or not latest:
        return False
        
    try:
        current_parts = parse_version(current)
        latest_parts = parse_version(latest)
        
        # Pad shorter version with zeros for comparison
        max_len = max(len(current_parts), len(latest_parts))
        current_parts.extend([0] * (max_len - len(current_parts)))
        latest_parts.extend([0] * (max_len - len(latest_parts)))
        
        return latest_parts > current_parts
    except Exception as e:
        logger.debug(f"Error comparing versions {current} vs {latest}: {e}")
        return False

async def check_for_updates() -> Tuple[bool, Optional[str], str]:
    """
    Check if a newer version is available.
    
    Returns:
        Tuple of (update_available, latest_version, current_version)
    """
    current_version = get_current_version()
    latest_version = await get_latest_version_from_pypi()
    
    if latest_version and is_newer_version(current_version, latest_version):
        return True, latest_version, current_version
    else:
        return False, latest_version, current_version

def print_update_notification(current_version: str, latest_version: str):
    """
    Print a user-friendly update notification.
    
    Args:
        current_version: Current installed version
        latest_version: Latest available version
    """
    print()
    print("🔔 UPDATE AVAILABLE")
    print("=" * 50)
    print(f"Current version: {current_version}")
    print(f"Latest version:  {latest_version}")
    print()
    print("A newer version of WebQuiz is available!")
    print(f"More info: {UPDATE_URL}")
    print("=" * 50)
    print()

async def check_and_notify_updates(show_up_to_date: bool = False):
    """
    Check for updates and notify user if available.
    
    Args:
        show_up_to_date: Whether to show message when already up to date
    """
    try:
        update_available, latest_version, current_version = await check_for_updates()
        
        if update_available and latest_version:
            print_update_notification(current_version, latest_version)
        elif show_up_to_date and latest_version:
            print(f"✅ WebQuiz is up to date (version {current_version})")
    except Exception as e:
        logger.debug(f"Error during update check: {e}")
        # Silently fail - don't interrupt the user experience