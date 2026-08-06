"""Quality phase data models."""

import uuid
from dataclasses import dataclass, field
from enum import Enum


class CheckStatus(Enum):
    """Status of a quality check."""
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"


class CheckType(Enum):
    """Types of quality checks."""
    PROMPT_ALIGNMENT = "prompt_alignment"
    ARTIFACT_DETECTION = "artifact_detection"
    FACE_BODY_LOGIC = "face_body_logic"
    COMPOSITION = "composition"
    STYLE_CONSISTENCY = "style_consistency"
    TECHNICAL_QUALITY = "technical_quality"
    STRUCTURAL_SIMILARITY = "structural_similarity"
    TEXT_READABILITY = "text_readability"
    AI_QUALITY = "ai_quality"


@dataclass
class MLCheckResult:
    """Result of a machine learning-based quality check."""
    check_type: CheckType
    score: float = 0.0
    status: CheckStatus = CheckStatus.INCONCLUSIVE
    details: dict = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "check_type": self.check_type.value,
            "score": self.score,
            "status": self.status.value,
            "details": self.details,
            "issues": self.issues,
            "confidence": self.confidence,
        }


@dataclass
class AICheckResult:
    """Result of an AI-based quality check."""
    check_type: CheckType
    score: float = 0.0
    status: CheckStatus = CheckStatus.INCONCLUSIVE
    details: dict = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    tokens_used: int = 0
    model_used: str = ""
    
    def to_dict(self) -> dict:
        return {
            "check_type": self.check_type.value,
            "score": self.score,
            "status": self.status.value,
            "details": self.details,
            "issues": self.issues,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
        }


@dataclass
class QualityReport:
    """Complete quality assessment report."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    overall_score: float = 0.0
    passed: bool = False
    tier_used: str = "ml_only"  # "ml_only" or "ml+ai"
    ml_checks: list[MLCheckResult] = field(default_factory=list)
    ai_checks: list[AICheckResult] = field(default_factory=list)
    tokens_consumed: int = 0
    refinement_notes: list[str] = field(default_factory=list)
    iteration_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "overall_score": self.overall_score,
            "passed": self.passed,
            "tier_used": self.tier_used,
            "ml_checks": [c.to_dict() for c in self.ml_checks],
            "ai_checks": [c.to_dict() for c in self.ai_checks],
            "tokens_consumed": self.tokens_consumed,
            "refinement_notes": self.refinement_notes,
            "iteration_count": self.iteration_count,
            "warnings": self.warnings,
            "errors": self.errors,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "QualityReport":
        ml_checks = [
            MLCheckResult(
                check_type=CheckType(c["check_type"]),
                score=c.get("score", 0.0),
                status=CheckStatus(c.get("status", "inconclusive")),
                details=c.get("details", {}),
                issues=c.get("issues", []),
                confidence=c.get("confidence", 0.0),
            )
            for c in data.get("ml_checks", [])
        ]
        ai_checks = [
            AICheckResult(
                check_type=CheckType(c["check_type"]),
                score=c.get("score", 0.0),
                status=CheckStatus(c.get("status", "inconclusive")),
                details=c.get("details", {}),
                issues=c.get("issues", []),
                tokens_used=c.get("tokens_used", 0),
                model_used=c.get("model_used", ""),
            )
            for c in data.get("ai_checks", [])
        ]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            overall_score=data.get("overall_score", 0.0),
            passed=data.get("passed", False),
            tier_used=data.get("tier_used", "ml_only"),
            ml_checks=ml_checks,
            ai_checks=ai_checks,
            tokens_consumed=data.get("tokens_consumed", 0),
            refinement_notes=data.get("refinement_notes", []),
            iteration_count=data.get("iteration_count", 0),
            warnings=data.get("warnings", []),
            errors=data.get("errors", []),
        )
