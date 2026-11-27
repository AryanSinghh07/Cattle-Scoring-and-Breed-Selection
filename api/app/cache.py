"""Short-lived, in-memory store of side photos for ``/recompute``.

When a user drags the rib-box corners, rib visibility has to be measured
again on the photo. Instead of uploading the photo again, ``/analyze`` keeps a
downscaled copy here for a limited time. Nothing is written to disk, and
entries expire or are evicted (oldest first) automatically.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class CachedPhoto:
    image: np.ndarray  # downscaled RGB
    factor: float  # cached pixels per original pixel
    created: float


class PhotoCache:
    def __init__(self, ttl_seconds: float, max_entries: int, max_side: int, clock=time.monotonic):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self.max_side = max_side
        self._clock = clock
        self._items: OrderedDict[str, CachedPhoto] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, image: np.ndarray) -> str:
        h, w = image.shape[:2]
        factor = min(1.0, self.max_side / max(h, w))
        if factor < 1.0:
            image = cv2.resize(image, (round(w * factor), round(h * factor)), interpolation=cv2.INTER_AREA)
        key = uuid.uuid4().hex
        with self._lock:
            self._expire()
            self._items[key] = CachedPhoto(image, factor, self._clock())
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
        return key

    def get(self, key: str) -> CachedPhoto | None:
        with self._lock:
            self._expire()
            return self._items.get(key)

    def __len__(self) -> int:
        with self._lock:
            self._expire()
            return len(self._items)

    def _expire(self) -> None:
        now = self._clock()
        for k in [k for k, v in self._items.items() if now - v.created > self.ttl]:
            del self._items[k]
