"""
Minidlna integration module.
"""

import time
import requests
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

class MinidlnaClient:
    """
    Client for checking Minidlna status with caching.
    """
    def __init__(self, url: str):
        self.url = url
        self._cache = {'status': None, 'ts': 0.0, 'inflight': False}
        self._lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=1)

    def _refresh_async(self):
        def _task():
            status = False
            try:
                response = requests.get(self.url, timeout=5)
                status = (response.status_code == 200)
            except Exception:
                status = False

            with self._lock:
                self._cache = {'status': status, 'ts': time.time(), 'inflight': False}

        self.executor.submit(_task)

    def get_status(self, ttl_seconds: int = 60) -> Optional[bool]:
        """
        Get Minidlna status. Returns cached status if fresh.
        Triggers background refresh if stale or missing.
        """
        if not self.url:
            return None

        now = time.time()
        with self._lock:
            cached_status = self._cache['status']
            ts = self._cache['ts']
            inflight = self._cache['inflight']

            if cached_status is not None and (now - ts < ttl_seconds):
                return cached_status  # Fresh

            if inflight:
                return cached_status if cached_status is not None else False # Return what we have or False

            # Mark inflight
            self._cache['inflight'] = True

        # Trigger refresh
        self._refresh_async()

        # Return current cache (even if stale) or False if first run
        return cached_status if cached_status is not None else False
