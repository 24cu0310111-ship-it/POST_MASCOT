"""Generation phase data models."""

import uuid
from dataclasses import dataclass, field
from enum import Enum


class BackendType(Enum):
    """Types of generation backends."""
    CLI_TOOL = "cli"
    MCP_SERVER = "mcp"
    WEB_API = "web_api"
    LOCAL_MODEL = "local"


class GenerationStatus(Enum):
    """Status of a generation task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class GenerationResult:
    """Result of an image generation task."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    image_path: str | None = None
    image_url: str | None = None
    backend_used: str = ""
    model_version: str = ""
    generation_params: dict = field(default_factory=dict)
    generation_time_ms: int = 0
    cost_estimate: float = 0.0
    prompt_used: str = ""
    status: GenerationStatus = GenerationStatus.PENDING
    error: str | None = None
    refinement_notes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "image_path": self.image_path,
            "image_url": self.image_url,
            "backend_used": self.backend_used,
            "model_version": self.model_version,
            "generation_params": self.generation_params,
            "generation_time_ms": self.generation_time_ms,
            "cost_estimate": self.cost_estimate,
            "prompt_used": self.prompt_used,
            "status": self.status.value,
            "error": self.error,
            "refinement_notes": self.refinement_notes,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GenerationResult":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            image_path=data.get("image_path"),
            image_url=data.get("image_url"),
            backend_used=data.get("backend_used", ""),
            model_version=data.get("model_version", ""),
            generation_params=data.get("generation_params", {}),
            generation_time_ms=data.get("generation_time_ms", 0),
            cost_estimate=data.get("cost_estimate", 0.0),
            prompt_used=data.get("prompt_used", ""),
            status=GenerationStatus(data.get("status", "pending")),
            error=data.get("error"),
            refinement_notes=data.get("refinement_notes", []),
            metadata=data.get("metadata", {}),
        )
