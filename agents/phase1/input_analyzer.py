"""Input Analyzer Agent - Phase 1 of the MAO system."""

import re
from dataclasses import dataclass

from config import config
from models.input_models import (
    AnalyzedInput,
    ClarificationRequest,
    InputIntent,
    Reference,
    ReferenceType,
)
from utils.logger import get_logger

from .context_validator import ContextValidator
from .reference_resolver import ReferenceResolver

logger = get_logger("phase1.input_analyzer")


@dataclass
class InputAnalyzer:
    """
    Phase 1: Input Analyzer Agent
    
    Responsibilities:
    1. Parse raw user input
    2. Extract intent, subject, style, constraints
    3. Detect and validate references
    4. Check context sufficiency
    5. Generate clarification questions if needed
    """
    
    def __init__(self, config_override=None):
        self.config = config_override or config.phase1
        self.context_validator = ContextValidator(self.config)
        self.reference_resolver = ReferenceResolver()
    
    async def analyze(self, user_input: str, references: list[dict] = None) -> AnalyzedInput:
        """
        Analyze user input and return structured data.
        
        Args:
            user_input: Raw user input text
            references: Optional list of reference dictionaries
        
        Returns:
            AnalyzedInput with parsed and validated data
        """
        logger.info(f"Analyzing input: {user_input[:100]}...")
        
        # Step 1: Parse input
        parsed = self._parse_input(user_input)
        
        # Step 2: Resolve references
        if references:
            resolved_refs = await self.reference_resolver.resolve_batch(references)
            parsed.references.extend(resolved_refs)
        
        # Step 3: Validate context
        validated = self.context_validator.validate(parsed)
        
        logger.info(f"Input analysis complete. Context score: {validated.context_score:.2f}")
        logger.info(f"Missing fields: {validated.missing_fields}")
        
        return validated
    
    def _parse_input(self, user_input: str) -> AnalyzedInput:
        """
        Parse raw user input into structured components.
        """
        # Extract intent
        intent = self._extract_intent(user_input)
        
        # Extract subject
        subject = self._extract_subject(user_input)
        
        # Extract style
        style = self._extract_style(user_input)
        
        # Extract constraints
        constraints = self._extract_constraints(user_input)
        
        # Extract references from text
        references = self._extract_references_from_text(user_input)
        
        return AnalyzedInput(
            raw_input=user_input,
            intent=intent,
            subject=subject,
            style=style,
            constraints=constraints,
            references=references,
            context_score=0.0,  # Will be set by validator
            missing_fields=[]
        )
    
    def _extract_intent(self, text: str) -> InputIntent:
        """Extract the user's intent from the input text."""
        text_lower = text.lower()
        
        # Check for specific intent keywords first
        if any(word in text_lower for word in ['edit', 'modify', 'change', 'adjust']):
            return InputIntent.EDIT_IMAGE
        if any(word in text_lower for word in ['style transfer', 'transfer style', 'apply style']):
            return InputIntent.STYLE_TRANSFER
        if any(word in text_lower for word in ['variation', 'variant', 'different version']):
            return InputIntent.VARIATION
        if any(word in text_lower for word in ['upscale', 'enlarge', 'higher resolution', 'hd', '4k']):
            return InputIntent.UPSCALE
        if any(word in text_lower for word in ['generate', 'create', 'make', 'design', 'produce']):
            return InputIntent.GENERATE_IMAGE
        
        # Default to generate if we can't determine
        return InputIntent.GENERATE_IMAGE
    
    def _extract_subject(self, text: str) -> str:
        """Extract the main subject from the input text."""
        # Remove common prefixes
        text = re.sub(r'^(generate|create|make|design|produce|a|an|the|for|of)\s+', '', text.lower())
        
        # Extract subject by looking for nouns after intent keywords
        # This is a simplified version - in production, use NLP
        
        # Common subject patterns for mascot generation
        mascot_patterns = [
            r'mascot',
            r'character',
            r'logo',
            r'brand\s+(ambassador|character|representative)',
            r'design',
            r'illustration',
            r'artwork'
        ]
        
        for pattern in mascot_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Extract the part describing what to create
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Get text after the intent keyword
                    words = text.split()
                    for i, word in enumerate(words):
                        if word.lower() in ['generate', 'create', 'make', 'design', 'produce']:
                            if i + 1 < len(words):
                                return ' '.join(words[i+1:i+10])  # Take next 9 words
                    return text[:200]  # Fallback
        
        # Default: return the text after removing intent keywords
        intent_keywords = ['generate', 'create', 'make', 'design', 'produce', 'edit', 'modify']
        for keyword in intent_keywords:
            text = re.sub(rf'\b{keyword}\b', '', text, flags=re.IGNORECASE)
        
        return text.strip()[:200]
    
    def _extract_style(self, text: str) -> str | None:
        """Extract style information from the input text."""
        text_lower = text.lower()
        
        style_keywords = []
        
        # Style categories
        art_styles = [
            'realistic', 'cartoon', 'anime', 'manga', '3d', '2d',
            'vector', 'watercolor', 'oil painting', 'sketch', 'pencil',
            'digital art', 'cyberpunk', 'steampunk', 'fantasy',
            'minimalist', 'modern', 'vintage', 'retro', 'futuristic',
            'illustration', 'comic', 'graphic design', 'flat design'
        ]
        
        for style in art_styles:
            if style in text_lower:
                style_keywords.append(style)
        
        # Cultural styles (important for India Post)
        cultural_styles = [
            'indian', 'bollywood', 'traditional', 'cultural',
            'heritage', 'ethnic', 'folk art', 'madhubani',
            'warli', 'pattachitra', 'rajasthani', 'modern indian'
        ]
        
        for style in cultural_styles:
            if style in text_lower:
                style_keywords.append(style)
        
        # Color schemes
        color_schemes = [
            'vibrant', 'colorful', 'monochrome', 'black and white',
            'pastel', 'neon', 'dark', 'light', 'warm', 'cool',
            'earth tones', 'metallic', 'gradient'
        ]
        
        for scheme in color_schemes:
            if scheme in text_lower:
                style_keywords.append(scheme)
        
        if style_keywords:
            return ', '.join(style_keywords)
        
        return None
    
    def _extract_constraints(self, text: str) -> dict:
        """Extract constraints from the input text."""
        constraints = {}
        text_lower = text.lower()
        
        # Extract dimensions
        width_match = re.search(r'(\d+)x(\d+)', text)
        if width_match:
            constraints['width'] = int(width_match.group(1))
            constraints['height'] = int(width_match.group(2))
        
        # Individual dimensions
        width_match = re.search(r'width[:\s]+(\d+)', text_lower)
        height_match = re.search(r'height[:\s]+(\d+)', text_lower)
        if width_match:
            constraints['width'] = int(width_match.group(1))
        if height_match:
            constraints['height'] = int(height_match.group(1))
        
        # Aspect ratio
        ratio_match = re.search(r'aspect\s+ratio[:\s]+([\d:]+)', text_lower)
        if ratio_match:
            constraints['aspect_ratio'] = ratio_match.group(1)
        
        # Color constraints
        color_matches = re.findall(r'color[:\s]+([^\s,;]+)', text_lower)
        for color in color_matches:
            if 'color' not in constraints:
                constraints['colors'] = []
            constraints['colors'].append(color.strip())
        
        # Format
        format_match = re.search(r'format[:\s]+([^\s,;]+)', text_lower)
        if format_match:
            constraints['format'] = format_match.group(1)
        
        # Quality settings
        quality_matches = re.findall(r'quality[:\s]+([^\s,;]+)', text_lower)
        for quality in quality_matches:
            if 'quality' not in constraints:
                constraints['quality'] = []
            constraints['quality'].append(quality.strip())
        
        return constraints
    
    def _extract_references_from_text(self, text: str) -> list[Reference]:
        """Extract file paths or URLs mentioned in the text."""
        references = []
        
        # URL patterns
        url_pattern = r'https?://[^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp|svg)'
        urls = re.findall(url_pattern, text, re.IGNORECASE)
        for url in urls:
            references.append(Reference(type=ReferenceType.URL, url=url))
        
        # File path patterns (simple detection)
        file_pattern = r'(?:/|\\|\s)(?:[^\s/\\]+/)*[^\s/\\]+\.(?:png|jpg|jpeg|gif|bmp|webp|svg)'
        files = re.findall(file_pattern, text)
        for file_path in files:
            references.append(Reference(type=ReferenceType.FILE, path=file_path.strip()))
        
        return references
    
    def needs_clarification(self, analyzed: AnalyzedInput) -> bool:
        """Check if the analyzed input needs clarification."""
        return not analyzed.is_sufficient
    
    def generate_clarification(self, analyzed: AnalyzedInput) -> ClarificationRequest:
        """Generate clarification questions for insufficient input."""
        questions = []
        suggestions = []
        
        if "subject" in analyzed.missing_fields:
            questions.append("What is the main subject or object you want to generate?")
            suggestions.append("Please describe what you want to create (e.g., 'a mascot', 'a logo', 'a character')")
        
        if "intent" in analyzed.missing_fields:
            questions.append("What do you want to do? (generate, edit, modify, upscale)")
            suggestions.append("Specify your intent: generate new image, edit existing, create variation, or upscale")
        
        if analyzed.subject and "mascot" in analyzed.subject.lower() and not analyzed.style:
            questions.append("What style should the mascot be in? (e.g., cartoon, realistic, vector, traditional Indian)")
            suggestions.append("Popular styles: cartoon, realistic, vector, anime, traditional Indian art")
        
        if not analyzed.constraints:
            questions.append("Are there any specific constraints? (dimensions, colors, format)")
            suggestions.append("Example: '1024x1024', 'red and gold colors', 'PNG format'")
        
        if not analyzed.references:
            questions.append("Do you have any reference images or examples?")
            suggestions.append("You can upload reference images or provide URLs")
        
        return ClarificationRequest(
            missing_fields=analyzed.missing_fields[:self.config.max_clarification_questions],
            questions=questions[:self.config.max_clarification_questions],
            suggestions=suggestions[:self.config.max_clarification_questions]
        )


