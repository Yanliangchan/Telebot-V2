import time

class UserRateLimiter:

    def __init__(self):
        self._events: dict[tuple[int, str], list[float]] = {}

    def allow(self, user_id: int | None, bucket: str, max_requests: int, window_seconds: int) -> bool:
        if user_id is None:
            return False

        now = time.monotonic()
        cutoff = now - window_seconds
        key = (user_id, bucket)
        timestamps = self._events.get(key, [])
        timestamps = [ts for ts in timestamps if ts >= cutoff]

        if len(timestamps) >= max_requests:
            self._events[key] = timestamps
            return False

        timestamps.append(now)
        self._events[key] = timestamps
        return True

user_rate_limiter = UserRateLimiter()