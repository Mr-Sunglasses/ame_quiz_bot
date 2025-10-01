from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Dict

class RateLimiter:
    def __init__(self, max_per_hour: int):
        self.max_per_hour = max_per_hour
        self._events: Dict[int, Deque[datetime]] = {}

    def allow(self, user_id: int) -> bool:
        now = datetime.utcnow()
        dq = self._events.setdefault(user_id, deque())
        window_start = now - timedelta(hours=1)
        while dq and dq[0] < window_start:
            dq.popleft()
        if len(dq) >= self.max_per_hour:
            return False
        dq.append(now)
        return True
