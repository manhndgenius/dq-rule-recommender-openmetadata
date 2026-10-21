"""Process-local coordinator for resource-intensive background jobs."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from threading import Lock, RLock
from typing import AsyncIterator, Optional


class HeavyJobCoordinator:
    """Allow only one generation or NT application job per backend process."""

    def __init__(self) -> None:
        self._execution_lock = Lock()
        self._state_lock = RLock()
        self._active_job_id: Optional[str] = None
        self._active_job_type: Optional[str] = None

    @asynccontextmanager
    async def slot(self, job_id: str, job_type: str) -> AsyncIterator[None]:
        # Waiting for another bulk job must not block FastAPI's event loop.
        await asyncio.to_thread(self._execution_lock.acquire)
        with self._state_lock:
            self._active_job_id = job_id
            self._active_job_type = job_type
        try:
            yield
        finally:
            with self._state_lock:
                self._active_job_id = None
                self._active_job_type = None
            self._execution_lock.release()

    def active_job(self) -> dict[str, Optional[str]]:
        with self._state_lock:
            return {
                "job_id": self._active_job_id,
                "job_type": self._active_job_type,
            }


heavy_job_coordinator = HeavyJobCoordinator()
