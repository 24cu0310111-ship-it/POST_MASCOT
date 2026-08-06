"""Base Backend - Abstract base class for all backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from config import config
from models.generation_models import BackendType, GenerationResult
from models.input_models import AnalyzedInput
from utils.logger import get_logger

logger = get_logger("backends.base")


class BackendHealth(Enum):
    """Health status of a backend."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class BaseBackend(ABC):
    """
    Abstract base class for all generation backends.
    
    All backends must implement:
    - generate(): Generate an image from a prompt
    - health_check(): Check if the backend is healthy
    - name: Property returning backend name
    - backend_type: Property returning BackendType
    - capabilities: Property returning dict of capabilities
    """
    
    api_key: str | None = None
    endpoint: str | None = None
    timeout: int = 300
    max_retries: int = 3
    _health: BackendHealth = BackendHealth.UNKNOWN
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the backend."""
    
    @property
    @abstractmethod
    def backend_type(self) -> BackendType:
        """Type of the backend."""
    
    @property
    @abstractmethod
    def capabilities(self) -> dict[str, Any]:
        """Capabilities of this backend."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        analyzed: AnalyzedInput = None,
        refinement: GenerationResult = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate an image from a prompt.
        
        Args:
            prompt: The text prompt
            analyzed: Optional AnalyzedInput for additional context
            refinement: Optional previous GenerationResult for refinement
            **kwargs: Additional backend-specific parameters
        
        Returns:
            GenerationResult with the generated image
        """
    
    @abstractmethod
    async def health_check(self) -> BackendHealth:
        """
        Check the health of this backend.
        
        Returns:
            BackendHealth status
        """
    
    async def initialize(self) -> bool:
        """
        Initialize the backend (optional override).
        
        Returns:
            True if initialization succeeded
        """
        return True
    
    def set_api_key(self, api_key: str):
        """Set the API key for this backend."""
        self.api_key = api_key
    
    def set_endpoint(self, endpoint: str):
        """Set the endpoint for this backend."""
        self.endpoint = endpoint
    
    def set_timeout(self, timeout: int):
        """Set the timeout for this backend."""
        self.timeout = timeout
    
    def set_max_retries(self, max_retries: int):
        """Set the maximum number of retries."""
        self.max_retries = max_retries
    
    def get_health(self) -> BackendHealth:
        """Get the current health status."""
        return self._health
    
    def set_health(self, health: BackendHealth):
        """Set the health status."""
        self._health = health
    
    def is_available(self) -> bool:
        """Check if this backend is available."""
        return self._health in [BackendHealth.HEALTHY, BackendHealth.DEGRADED]
    
    def _create_output_path(
        self,
        prompt: str,
        extension: str = ".png"
    ) -> Path:
        """Create a unique output path for generated image."""
        import hashlib
        import time
        
        # Create a hash of the prompt and timestamp
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        timestamp = str(int(time.time()))[-6:]
        filename = f"{self.name}_{prompt_hash}_{timestamp}{extension}"
        
        output_dir = Path(config.output_dir if hasattr(config, 'output_dir') else "./output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return output_dir / filename
    
    def _estimate_cost(
        self,
        width: int = 1024,
        height: int = 1024,
        steps: int = 50
    ) -> float:
        """Estimate the cost of generation."""
        # Base cost estimation (override in subclasses)
        pixels = width * height
        return (pixels / 1000000) * (steps / 50) * 0.01  # $0.01 per megapixel at 50 steps
