"""Backend Registry - Part of Phase 2 Creator Agent."""

import asyncio
from dataclasses import dataclass, field

from backends.base_backend import BackendHealth
from config import config
from models.generation_models import BackendType
from utils.logger import get_logger

logger = get_logger("phase2.backend_registry")


@dataclass
class BackendConfig:
    """Configuration for a specific backend."""
    backend_type: BackendType
    api_key: str | None = None
    endpoint: str | None = None
    model_name: str | None = None
    timeout: int = 300
    max_retries: int = 3
    health: BackendHealth = BackendHealth.UNKNOWN


@dataclass
class BackendRegistry:
    """
    Registry of all available generation backends.
    
    Responsibilities:
    1. Maintain list of all available backends
    2. Health checking and availability monitoring
    3. Capability matrix (what each backend can do)
    4. Configuration: API keys, endpoints, model versions
    """
    
    backends: dict[str, any] = field(default_factory=dict)
    configs: dict[str, BackendConfig] = field(default_factory=dict)
    health_status: dict[str, BackendHealth] = field(default_factory=dict)
    
    def __init__(self, config_override=None):
        self.config = config_override or config.phase2
        self.backends: dict[str, any] = {}
        self.configs: dict[str, BackendConfig] = {}
        self.health_status: dict[str, BackendHealth] = {}
        self._initialize_backends()
        self._load_configurations()
    
    def _initialize_backends(self):
        """Initialize all backend adapters."""
        from backends.cli_backend import CLIBackend
        from backends.local_backend import LocalBackend
        from backends.mcp_backend import MCPBackend
        from backends.pollinations_backend import PollinationsBackend
        from backends.web_api_backend import WebAPIBackend
        
        # Initialize backend instances
        self.backends = {
            "mcp": MCPBackend(),
            "cli": CLIBackend(),
            "web_api": WebAPIBackend(),
            "pollinations": PollinationsBackend(),
            "local": LocalBackend()
        }
    
    def _load_configurations(self):
        """Load backend configurations from config."""
        backend_configs = self.config.backend_configs if hasattr(self.config, 'backend_configs') else {}
        
        for name, backend_config in backend_configs.items():
            if name in self.backends:
                self.configs[name] = BackendConfig(
                    backend_type=BackendType(backend_config.get('type', 'mcp')),
                    api_key=backend_config.get('api_key'),
                    endpoint=backend_config.get('endpoint'),
                    model_name=backend_config.get('model_name'),
                    timeout=backend_config.get('timeout', 300),
                    max_retries=backend_config.get('max_retries', 3)
                )
    
    def get_backend(self, backend_name: str) -> any:
        """Get a backend instance by name."""
        return self.backends.get(backend_name)
    
    def get_backend_config(self, backend_name: str) -> BackendConfig | None:
        """Get configuration for a backend."""
        return self.configs.get(backend_name)
    
    async def check_health(self, backend_name: str) -> BackendHealth:
        """
        Check the health of a backend.
        
        Args:
            backend_name: Name of the backend to check
        
        Returns:
            Health status of the backend
        """
        backend = self.backends.get(backend_name)
        if not backend:
            return BackendHealth.UNHEALTHY
        
        try:
            result = await backend.health_check()
            self.health_status[backend_name] = result
            return result
        except Exception as e:
            logger.error(f"Health check failed for {backend_name}: {e}")
            self.health_status[backend_name] = BackendHealth.UNHEALTHY
            return BackendHealth.UNHEALTHY
    
    async def check_all_health(self) -> dict[str, BackendHealth]:
        """Check health of all backends."""
        results = {}
        tasks = []
        
        for name in self.backends.keys():
            task = self.check_health(name)
            tasks.append(task)
        
        health_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, result in zip(self.backends.keys(), health_results):
            if isinstance(result, Exception):
                results[name] = BackendHealth.UNHEALTHY
                logger.error(f"Health check error for {name}: {result}")
            else:
                results[name] = result
        
        return results
    
    def is_available(self, backend_name: str) -> bool:
        """Check if a backend is available."""
        if backend_name not in self.backends:
            return False
        
        # Check health status
        if backend_name in self.health_status:
            return self.health_status[backend_name] in [BackendHealth.HEALTHY, BackendHealth.DEGRADED]
        
        return True  # Assume available if not checked yet
    
    def get_capabilities(self, backend_name: str) -> dict:
        """Get capabilities of a backend."""
        backend = self.backends.get(backend_name)
        if backend:
            return backend.capabilities
        return {}
    
    def list_backends(self) -> list[str]:
        """List all registered backends."""
        return list(self.backends.keys())
    
    def list_available_backends(self) -> list[str]:
        """List all available backends."""
        return [name for name in self.backends.keys() if self.is_available(name)]
    
    def set_api_key(self, backend_name: str, api_key: str):
        """Set API key for a backend."""
        backend = self.backends.get(backend_name)
        if backend:
            backend.api_key = api_key
        
        # Also update config
        if backend_name not in self.configs:
            self.configs[backend_name] = BackendConfig(
                backend_type=BackendType.WEB_API
            )
        self.configs[backend_name].api_key = api_key
