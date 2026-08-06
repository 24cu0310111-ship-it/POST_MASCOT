"""Context Validator - Part of Phase 1 Input Analyzer."""

from dataclasses import dataclass

from models.input_models import AnalyzedInput, Reference
from utils.image_utils import ImageUtils
from utils.logger import get_logger

logger = get_logger("phase1.context_validator")


@dataclass
class ContextValidator:
    """
    Validates that input has sufficient context.
    
    Responsibilities:
    1. Score input completeness against configurable threshold
    2. Identify missing required fields
    3. Validate that referenced files exist and are in supported formats
    """
    
    context_threshold: float = 0.7
    required_fields: list[str] = None
    optional_fields: list[str] = None
    
    def __init__(self, config=None):
        if config:
            self.context_threshold = getattr(config, 'context_threshold', 0.7)
            self.required_fields = getattr(config, 'required_fields', ['subject', 'intent'])
            self.optional_fields = getattr(config, 'optional_fields', ['style', 'constraints', 'references'])
        else:
            self.required_fields = ['subject', 'intent']
            self.optional_fields = ['style', 'constraints', 'references']
    
    def validate(self, analyzed: AnalyzedInput) -> AnalyzedInput:
        """
        Validate the analyzed input and return updated version with scores.
        
        Args:
            analyzed: AnalyzedInput to validate
            
        Returns:
            Updated AnalyzedInput with context_score and missing_fields
        """
        # Score each component
        scores = {}
        missing_fields = []
        
        # Check required fields
        for field in self.required_fields:
            score = self._score_field(field, analyzed)
            scores[field] = score
            if score < 0.5:
                missing_fields.append(field)
        
        # Check optional fields
        for field in self.optional_fields:
            scores[field] = self._score_field(field, analyzed)
        
        # Validate references
        valid_refs = self._validate_references(analyzed.references)
        if len(valid_refs) < len(analyzed.references):
            # Penalize if some references are invalid
            if "references" in scores:
                scores["references"] = max(0, scores["references"] - 0.3)
        
        # Calculate overall context score.
        # Required fields always count; optional fields only count when present,
        # so a plain but valid prompt is not penalized for missing optional context.
        scored_fields = [field for field in self.required_fields]
        scored_fields += [field for field in self.optional_fields if scores[field] > 0]
        total_score = sum(scores[f] for f in scored_fields) / max(len(scored_fields), 1)
        
        # Update and return
        analyzed.context_score = total_score
        analyzed.missing_fields = missing_fields
        
        logger.debug(f"Context validation: score={total_score:.2f}, missing={missing_fields}")
        
        return analyzed
    
    def _score_field(self, field: str, analyzed: AnalyzedInput) -> float:
        """Score a specific field."""
        if field == "subject":
            return self._score_subject(analyzed.subject)
        elif field == "intent":
            return self._score_intent(analyzed.intent)
        elif field == "style":
            return self._score_style(analyzed.style)
        elif field == "constraints":
            return self._score_constraints(analyzed.constraints)
        elif field == "references":
            return self._score_references(analyzed.references)
        else:
            return 0.0
    
    def _score_subject(self, subject: str) -> float:
        """Score the subject field."""
        if not subject or len(subject.strip()) < 3:
            return 0.0
        elif len(subject.strip()) < 10:
            return 0.3
        elif len(subject.strip()) < 50:
            return 0.7
        else:
            return 1.0
    
    def _score_intent(self, intent) -> float:
        """Score the intent field."""
        from models.input_models import InputIntent
        if intent == InputIntent.UNKNOWN:
            return 0.0
        else:
            return 1.0
    
    def _score_style(self, style: str) -> float:
        """Score the style field."""
        if not style:
            return 0.0
        elif len(style.strip()) < 5:
            return 0.3
        else:
            return 1.0
    
    def _score_constraints(self, constraints: dict) -> float:
        """Score the constraints field."""
        if not constraints or len(constraints) == 0:
            return 0.0
        elif len(constraints) == 1:
            return 0.5
        else:
            return 1.0
    
    def _score_references(self, references: list[Reference]) -> float:
        """Score the references field."""
        if not references:
            return 0.0
        valid_count = sum(1 for r in references if r.is_valid())
        return min(1.0, valid_count / 2)  # Max score with 2+ valid references
    
    def _validate_references(self, references: list[Reference]) -> list[Reference]:
        """Validate that references are accessible."""
        valid_refs = []
        for ref in references:
            from models.input_models import ReferenceType
            
            if ref.type == ReferenceType.FILE:
                if ref.path and ImageUtils.is_valid_image_file(ref.path):
                    valid_refs.append(ref)
                else:
                    logger.warning(f"Invalid file reference: {ref.path}")
            elif ref.type == ReferenceType.URL:
                # For now, accept all URLs (validation happens during download)
                valid_refs.append(ref)
            elif ref.type == ReferenceType.TEXT:
                if ref.content:
                    valid_refs.append(ref)
            else:
                valid_refs.append(ref)
        return valid_refs
    
    def is_sufficient(self, context_score: float) -> bool:
        """Check if context score meets threshold."""
        return context_score >= self.context_threshold
    
    def get_missing_fields(self, analyzed: AnalyzedInput) -> list[str]:
        """Get list of missing required fields."""
        self.validate(analyzed)
        return analyzed.missing_fields
