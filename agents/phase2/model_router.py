"""Model Router - Part of Phase 2 Creator Agent."""

from dataclasses import dataclass, field
from enum import Enum

from config import config
from models.generation_models import BackendType
from models.input_models import AnalyzedInput, InputIntent
from utils.logger import get_logger

logger = get_logger("phase2.model_router")


class TaskType(Enum):
    """Types of generation tasks."""
    IMAGE_GENERATION = "image_generation"
    IMAGE_EDITING = "image_editing"
    STYLE_TRANSFER = "style_transfer"
    UPSCALING = "upscaling"
    VARIATION = "variation"


@dataclass
class BackendCandidate:
    """A candidate backend for selection."""
    name: str
    backend_type: BackendType
    priority: float
    cost: float
    speed: float
    quality: float
    supports_task: bool
    available: bool
    needs_api_key: bool = False
    
    def score(self, task_type: TaskType, quality_needs: str = "standard") -> float:
        """Calculate selection score for this backend."""
        score = 0.0
        
        # Priority weight
        score += self.priority * 0.4
        
        # Task support (must support task to be selected)
        if self.supports_task:
            score += 0.3
        
        # Quality adjustment
        quality_multiplier = {
            "draft": 0.7,
            "standard": 1.0,
            "high": 1.3,
            "premium": 1.5
        }
        score += (self.quality * quality_multiplier.get(quality_needs, 1.0)) * 0.2
        
        # Speed adjustment (for drafts, speed matters more)
        if quality_needs == "draft":
            score += self.speed * 0.2
        else:
            score += self.speed * 0.1
        
        # Cost penalty (for iterations, prefer cheaper)
        score -= self.cost * 0.01
        
        # Prefer free backends when API key not available
        if not self.needs_api_key:
            score += 0.15
        
        return score


@dataclass
class ModelRouter:
    """
    Intelligent model selection engine.
    
    Picks the optimal backend based on:
    - Task Type
    - Quality Needs
    - Available Backends
    - Cost (prefers FREE backends)
    - Speed
    """
    
    backend_candidates: dict[str, BackendCandidate] = field(default_factory=dict)
    task_capabilities: dict[BackendType, list[TaskType]] = field(default_factory=dict)
    
    def __init__(self, config_override=None):
        self.config = config_override or config.phase2
        self.backend_candidates: dict[str, BackendCandidate] = {}
        self.task_capabilities: dict[BackendType, list[TaskType]] = {}
        self._initialize_backend_candidates()
        self._initialize_task_capabilities()
    
    def _initialize_backend_candidates(self):
        """Initialize known backend candidates."""
        # Pollinations.ai (FREE, no key needed) — HIGHEST PRIORITY
        self.backend_candidates["pollinations"] = BackendCandidate(
            name="pollinations",
            backend_type=BackendType.WEB_API,
            priority=1.0,
            cost=0.0,  # FREE!
            speed=0.9,
            quality=0.85,
            supports_task=False,
            available=True,
            needs_api_key=False
        )
        
        # MCP Server (Orshot)
        self.backend_candidates["mcp"] = BackendCandidate(
            name="mcp",
            backend_type=BackendType.MCP_SERVER,
            priority=0.8,
            cost=0.5,
            speed=0.8,
            quality=0.9,
            supports_task=False,
            available=True,
            needs_api_key=True
        )
        
        # CLI Tools (Stable Diffusion)
        self.backend_candidates["cli"] = BackendCandidate(
            name="cli",
            backend_type=BackendType.CLI_TOOL,
            priority=0.7,
            cost=0.1,
            speed=0.6,
            quality=0.8,
            supports_task=False,
            available=True,
            needs_api_key=False
        )
        
        # Web APIs (DALL-E, Flux, Midjourney)
        self.backend_candidates["web_api"] = BackendCandidate(
            name="web_api",
            backend_type=BackendType.WEB_API,
            priority=0.6,
            cost=2.0,
            speed=0.7,
            quality=0.95,
            supports_task=False,
            available=True,
            needs_api_key=True
        )
        
        # Local Models
        self.backend_candidates["local"] = BackendCandidate(
            name="local",
            backend_type=BackendType.LOCAL_MODEL,
            priority=0.5,
            cost=0.0,
            speed=0.9,
            quality=0.75,
            supports_task=False,
            available=True,
            needs_api_key=False
        )
        
        # Opencode CLI Model
        self.backend_candidates["opencode"] = BackendCandidate(
            name="opencode",
            backend_type=BackendType.CLI_TOOL,
            priority=0.85,
            cost=0.2,
            speed=0.85,
            quality=0.9,
            supports_task=False,
            available=True,
            needs_api_key=True
        )
        
        # Omniroute CLI Model
        self.backend_candidates["omniroute"] = BackendCandidate(
            name="omniroute",
            backend_type=BackendType.CLI_TOOL,
            priority=0.85,
            cost=0.2,
            speed=0.9,
            quality=0.85,
            supports_task=False,
            available=True,
            needs_api_key=True
        )

        # Omniroute-Org CLI Model
        self.backend_candidates["omniroute-org"] = BackendCandidate(
            name="omniroute-org",
            backend_type=BackendType.CLI_TOOL,
            priority=0.85,
            cost=0.2,
            speed=0.9,
            quality=0.85,
            supports_task=False,
            available=True,
            needs_api_key=True
        )
    
    def _initialize_task_capabilities(self):
        """Initialize task capabilities for each backend type."""
        self.task_capabilities = {
            BackendType.WEB_API: [
                TaskType.IMAGE_GENERATION,
                TaskType.UPSCALING
            ],
            BackendType.MCP_SERVER: [
                TaskType.IMAGE_GENERATION,
                TaskType.IMAGE_EDITING,
                TaskType.STYLE_TRANSFER
            ],
            BackendType.CLI_TOOL: [
                TaskType.IMAGE_GENERATION,
                TaskType.IMAGE_EDITING,
                TaskType.STYLE_TRANSFER,
                TaskType.UPSCALING,
                TaskType.VARIATION
            ],
            BackendType.LOCAL_MODEL: [
                TaskType.IMAGE_GENERATION,
                TaskType.UPSCALING
            ]
        }
    
    def _update_backend_supports(self, task_type: TaskType):
        """Update which backends support the current task."""
        for backend_name, candidate in self.backend_candidates.items():
            backend_type = candidate.backend_type
            if backend_type in self.task_capabilities:
                candidate.supports_task = task_type in self.task_capabilities[backend_type]
            else:
                candidate.supports_task = False
    
    def select_backend(
        self,
        analyzed: AnalyzedInput,
        quality_needs: str = "standard"
    ) -> str:
        """
        Select the best backend for the given input.
        
        Args:
            analyzed: AnalyzedInput from Phase 1
            quality_needs: Quality level ("draft", "standard", "high", "premium")
        
        Returns:
            Name of the selected backend
        """
        # Determine task type from intent
        task_type = self._intent_to_task_type(analyzed.intent)
        self._update_backend_supports(task_type)
        
        # Filter available backends that support the task
        available_backends = []
        for name, candidate in self.backend_candidates.items():
            if candidate.supports_task and candidate.available:
                available_backends.append((name, candidate))
        
        if not available_backends:
            logger.warning(f"No backends available for task type: {task_type}")
            return "pollinations"  # Default fallback
        
        # Score each backend
        scored_backends = []
        for name, candidate in available_backends:
            score = candidate.score(task_type, quality_needs)
            scored_backends.append((score, name, candidate))
        
        # Sort by score (highest first)
        scored_backends.sort(reverse=True, key=lambda x: x[0])
        
        # Select the best
        best_name = scored_backends[0][1]
        logger.info(f"Selected backend: {best_name} (score: {scored_backends[0][0]:.2f})")
        
        return best_name
    
    def _intent_to_task_type(self, intent) -> TaskType:
        """Convert InputIntent to TaskType."""
        mapping = {
            InputIntent.GENERATE_IMAGE: TaskType.IMAGE_GENERATION,
            InputIntent.EDIT_IMAGE: TaskType.IMAGE_EDITING,
            InputIntent.STYLE_TRANSFER: TaskType.STYLE_TRANSFER,
            InputIntent.VARIATION: TaskType.VARIATION,
            InputIntent.UPSCALE: TaskType.UPSCALING,
            InputIntent.UNKNOWN: TaskType.IMAGE_GENERATION
        }
        return mapping.get(intent, TaskType.IMAGE_GENERATION)
    
    def get_backend_info(self, backend_name: str) -> BackendCandidate | None:
        """Get information about a specific backend."""
        return self.backend_candidates.get(backend_name)
    
    def list_available_backends(self, task_type: TaskType = None) -> list[str]:
        """List available backends, optionally filtered by task type."""
        available = []
        for name, candidate in self.backend_candidates.items():
            if candidate.available:
                if task_type is None or candidate.supports_task:
                    available.append(name)
        return available
    
    def set_backend_available(self, backend_name: str, available: bool):
        """Update backend availability."""
        if backend_name in self.backend_candidates:
            self.backend_candidates[backend_name].available = available
