"""Every task module is imported here; the worker loads this package (no auto-discovery)."""

from app.worker.tasks import system

__all__ = ["system"]
