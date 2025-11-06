"""GATI SDK - Track AI agent executions and send events to a local backend."""
from gati.version import __version__
from gati.observe import Observe, observe

__version__ = __version__

__all__ = ["__version__", "Observe", "observe"]

