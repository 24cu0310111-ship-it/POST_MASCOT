"""Backend adapters for the MAO system."""

from .base_backend import BaseBackend, BackendHealth
from .mcp_backend import MCPBackend
from .cli_backend import CLIBackend
from .web_api_backend import WebAPIBackend
from .local_backend import LocalBackend
from .pollinations_backend import PollinationsBackend

__all__ = [
    "BaseBackend",
    "BackendHealth",
    "MCPBackend",
    "CLIBackend",
    "WebAPIBackend",
    "LocalBackend",
    "PollinationsBackend",
]
