"""Every task module is imported here; the worker loads this package (no auto-discovery)."""

from app.worker.tasks import feedback, system

__all__ = ["feedback", "system"]
