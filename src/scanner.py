"""
File scanner module.
"""

import os
import time
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict
from datetime import datetime

from .config import Config
from .parser import FilenameParser

class FileScanner:
    """Scan directories for media files and check for existing covers."""

    def __init__(self, config: Config):
        self.config = config

    def scan_directory(self, directory: str) -> Dict:
        """
        Scan a directory for media files without covers.

        Returns:
            Dict with directory info and list of movies
        """
        movies = []
        total_files = 0
        last_scan = datetime.now().strftime('%Y-%m-%d %H:%M')

        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    # Check if file has valid extension
                    ext = Path(file).suffix[1:].lower()  # Remove the dot
                    if ext not in self.config.file_extensions:
                        continue

                    total_files += 1
                    filepath = os.path.join(root, file)

                    # Check if cover exists
                    cover_path = str(Path(filepath).with_suffix('.jpg'))
                    if os.path.exists(cover_path):
                        continue  # Skip files with existing covers

                    # Parse filename
                    title, year = FilenameParser.parse(file)

                    movies.append({
                        'filepath': filepath,
                        'filename': file,
                        'title': title,
                        'year': year,
                        'cover_path': cover_path
                    })

            return {
                'directory': directory,
                'total_files': total_files,
                'missing_covers': len(movies),
                'movies': movies,
                'last_scan': last_scan,
                'status': 'ok'
            }

        except Exception as e:
            return {
                'directory': directory,
                'error': str(e),
                'status': 'error'
            }

    def get_directory_stats(self, directory: str) -> Dict:
        """Get statistics for a directory without full scan."""
        total_files = 0
        missing_covers = 0
        last_modified = None

        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    ext = Path(file).suffix[1:].lower()
                    if ext not in self.config.file_extensions:
                        continue

                    total_files += 1
                    filepath = os.path.join(root, file)
                    cover_path = str(Path(filepath).with_suffix('.jpg'))

                    if not os.path.exists(cover_path):
                        missing_covers += 1

                    # Track most recent modification
                    mtime = os.path.getmtime(filepath)
                    if last_modified is None or mtime > last_modified:
                        last_modified = mtime

            # Detect if directory is local or network mount
            location_type = self._detect_location_type(directory)

            # Check if directory is writable
            is_writable = os.access(directory, os.W_OK)

            return {
                'directory': directory,
                'total_files': total_files,
                'missing_covers': missing_covers,
                'last_modified': datetime.fromtimestamp(last_modified).strftime('%Y-%m-%d %H:%M') if last_modified else None,
                'status': 'ok' if missing_covers == 0 else 'action_needed',
                'location_type': location_type,
                'is_writable': is_writable
            }

        except Exception as e:
            return {
                'directory': directory,
                'error': str(e),
                'status': 'error',
                'location_type': 'unknown',
                'is_writable': False
            }

    def _detect_location_type(self, directory: str) -> str:
        """Detect if directory is local or network mount."""
        import platform

        system = platform.system()

        if system == 'Windows':
            # Check if it's a network drive (UNC path or mapped network drive)
            if directory.startswith('\\\\'):
                return 'network'
            # Check if drive letter is a network drive
            try:
                import subprocess
                drive = directory[:2]  # e.g., 'C:'
                result = subprocess.run(
                    ['net', 'use'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'  # Ignore encoding errors
                )
                if drive.upper() in result.stdout.upper():
                    return 'network'
            except Exception:
                # If detection fails, assume local
                pass
            return 'local'

        elif system in ('Linux', 'Darwin'):  # Linux or macOS
            # Read mount information
            try:
                with open('/proc/mounts' if system == 'Linux' else '/etc/mtab', 'r') as f:
                    mounts = f.read()

                # Common network filesystem types
                network_fs = ['nfs', 'cifs', 'smb', 'smbfs', 'fuse.sshfs', 'ftp', 'davfs']

                for line in mounts.split('\n'):
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[1]
                        fs_type = parts[2]

                        # Check if directory is under this mount point
                        if directory.startswith(mount_point):
                            if fs_type in network_fs:
                                return 'network'

                            return 'local'
            except Exception:
                return 'local'

        return 'local'

# ============================================================================
# Directory Stats Cache
# ============================================================================

class DirectoryStatsCache:
    """
    Thread-safe cache for get_directory_stats(). Returns cached stats immediately
    and refreshes them in the background when stale or missing.
    """
    def __init__(self, scanner: FileScanner, max_workers: int = 4):
        self.scanner = scanner
        self._cache: Dict[str, Dict] = {}  # directory -> {'stats': dict, 'ts': float, 'inflight': bool}
        self._lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def _placeholder(self, directory: str, status: str = 'refreshing') -> Dict:
        return {
            'directory': directory,
            'total_files': None,
            'missing_covers': None,
            'last_modified': None,
            'status': status,
            'location_type': self.scanner._detect_location_type(directory),
            'is_writable': os.access(directory, os.W_OK),
        }

    def _refresh_async(self, directory: str):
        def _task():
            new_stats = self.scanner.get_directory_stats(directory)
            with self._lock:
                self._cache[directory] = {'stats': new_stats, 'ts': time.time(), 'inflight': False}
        self.executor.submit(_task)

    def peek(self, directory: str) -> Dict:
        """
        Return current cached stats without triggering a refresh.
        If not present, return a lightweight placeholder with status 'unknown'.
        """
        with self._lock:
            entry = self._cache.get(directory)
            return entry['stats'] if entry else self._placeholder(directory, status='unknown')

    def get(self, directory: str, ttl_seconds: int = 300) -> Dict:
        """
        Return cached stats if fresh. If stale/missing, mark inflight and trigger
        background refresh, then return last cached or a placeholder.
        """
        now = time.time()
        with self._lock:
            entry = self._cache.get(directory)
            if entry and (now - entry['ts'] < ttl_seconds):
                return entry['stats']  # fresh

            # Already refreshing? Return whatever we have.
            if entry and entry.get('inflight'):
                return entry['stats']

            # Prepare placeholder or existing stats, mark inflight, then refresh.
            stats = entry['stats'] if entry else self._placeholder(directory, status='refreshing')
            self._cache[directory] = {'stats': stats, 'ts': entry['ts'] if entry else 0.0, 'inflight': True}

        self._refresh_async(directory)
        return stats
