"""Input phase data models."""

import uuid
from dataclasses import dataclass, field
from enum import Enum


class InputIntent(Enum):
    """Types of user intent for image generation."""
    GENERATE_IMAGE = "generate_image"
    EDIT_IMAGE = "edit_image"
    STYLE_TRANSFER = "style_transfer"
    VARIATION = "variation"
    UPSCALE = "upscale"
    UNKNOWN = "unknown"


class ReferenceType(Enum):
    """Types of reference materials."""
    FILE = "file"
    URL = "url"
    PREVIOUS_OUTPUT = "previous_output"
    TEXT = "text"


@dataclass
class Reference:
    """A reference file, URL, or prior output."""
    type: ReferenceType
    path: str | None = None
    url: str | None = None
    content: str | None = None  # For text references
    metadata: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def is_valid(self) -> bool:
        """Check if reference has valid data."""
        if self.type == ReferenceType.FILE:
            return self.path is not None
        elif self.type == ReferenceType.URL:
            return self.url is not None
        elif self.type == ReferenceType.TEXT:
            return self.content is not None
        elif self.type == ReferenceType.PREVIOUS_OUTPUT:
            return self.path is not None or self.content is not None
        return False


@dataclass
class AnalyzedInput:
    """Structured analysis of user input."""
    raw_input: str
    intent: InputIntent = InputIntent.UNKNOWN
    subject: str = ""
    style: str | None = None
    constraints: dict = field(default_factory=dict)
    references: list[Reference] = field(default_factory=list)
    context_score: float = 0.0
    missing_fields: list[str] = field(default_factory=list)
    
    @property
    def is_sufficient(self) -> bool:
        """Check if input has sufficient context."""
        return self.context_score >= 0.7 and len(self.missing_fields) == 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "raw_input": self.raw_input,
            "intent": self.intent.value,
            "subject": self.subject,
            "style": self.style,
            "constraints": self.constraints,
            "references": [
                {"type": r.type.value, "path": r.path, "url": r.url, "content": r.content}
                for r in self.references
            ],
            "context_score": self.context_score,
            "missing_fields": self.missing_fields,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AnalyzedInput":
        """Create from dictionary."""
        references = [
            Reference(
                type=ReferenceType(r["type"]),
                path=r.get("path"),
                url=r.get("url"),
                content=r.get("content"),
            )
            for r in data.get("references", [])
        ]
        return cls(
            raw_input=data["raw_input"],
            intent=InputIntent(data.get("intent", "unknown")),
            subject=data.get("subject", ""),
            style=data.get("style"),
            constraints=data.get("constraints", {}),
            references=references,
            context_score=data.get("context_score", 0.0),
            missing_fields=data.get("missing_fields", []),
        )


@dataclass
class ClarificationRequest:
    """Request for user clarification."""
    missing_fields: list[str]
    questions: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "missing_fields": self.missing_fields,
            "questions": self.questions,
            "suggestions": self.suggestions,
        }
