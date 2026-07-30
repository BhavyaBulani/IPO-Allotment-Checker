import threading
import time

class RateLimiter:
    """
    A simple rate limiter to pace synchronous requests to registrars.
    """
    def __init__(self):
        self._locks = {}
        self._last_request_time = {}
        self.min_delay = 0.5 # 500ms between requests per registrar
        self._global_lock = threading.Lock()

    def wait(self, registrar_id: int):
        with self._global_lock:
            if registrar_id not in self._locks:
                self._locks[registrar_id] = threading.Lock()
                self._last_request_time[registrar_id] = 0.0

        with self._locks[registrar_id]:
            now = time.time()
            elapsed = now - self._last_request_time[registrar_id]
            if elapsed < self.min_delay:
                time.sleep(self.min_delay - elapsed)
            self._last_request_time[registrar_id] = time.time()

# Global instance
rate_limiter = RateLimiter()
