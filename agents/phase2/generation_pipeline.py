"""Generation Pipeline - Part of Phase 2 Creator Agent."""

import time
from dataclasses import dataclass, field
from pathlib import Path

from config import config
from models.generation_models import GenerationResult
from models.input_models import AnalyzedInput, ReferenceType
from utils.file_utils import FileUtils
from utils.logger import get_logger

logger = get_logger("phase2.generation_pipeline")


@dataclass
class GenerationPipeline:
    """
    Manages the generation pipeline.
    
    Responsibilities:
    1. Translate AnalyzedInput into backend-specific prompts
    2. Handle prompt engineering per-backend
    3. Manage generation parameters
    4. Return GenerationResult with output image + metadata
    """
    
    default_params: dict = field(default_factory=dict)
    backend_params: dict[str, dict] = field(default_factory=dict)
    
    def __init__(self, config_override=None):
        self.config = config_override or config.phase2
        self.default_params: dict = {}
        self.backend_params: dict[str, dict] = {}
        self._initialize_defaults()
    
    def _initialize_defaults(self):
        """Initialize default generation parameters."""
        self.default_params = {
            "width": 1024,
            "height": 1024,
            "steps": 50,
            "cfg_scale": 7.0,
            "sampler": "DPM++ 2M Karras",
            "seed": -1  # Random seed
        }
        
        # Backend-specific parameters
        self.backend_params = {
            "mcp": {
                "width": 1024,
                "height": 1024,
                "format": "png"
            },
            "cli": {
                "width": 512,
                "height": 512,
                "steps": 30,
                "cfg_scale": 7.0,
                "sampler": "Euler a"
            },
            "web_api": {
                "width": 1024,
                "height": 1024,
                "n": 1,
                "size": "1024x1024"
            },
            "local": {
                "width": 512,
                "height": 512,
                "steps": 20
            }
        }
    
    def build_prompt(
        self,
        analyzed: AnalyzedInput,
        refinement: GenerationResult = None
    ) -> str:
        """
        Build a generation prompt from analyzed input.
        
        Args:
            analyzed: AnalyzedInput from Phase 1
            refinement: Optional previous GenerationResult for refinement
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = []
        
        # Start with the subject
        if analyzed.subject:
            prompt_parts.append(analyzed.subject)
        
        # Add style
        if analyzed.style:
            prompt_parts.append(f"in {analyzed.style} style")
        
        # Add constraints
        if analyzed.constraints:
            for key, value in analyzed.constraints.items():
                if key == "colors" and isinstance(value, list):
                    prompt_parts.append(f"using colors: {', '.join(value)}")
                elif key not in ["width", "height", "format"]:
                    prompt_parts.append(f"{key}: {value}")
        
        # Add refinement notes if available
        if refinement and refinement.refinement_notes:
            prompt_parts.append("Refinements:")
            for note in refinement.refinement_notes[:3]:  # Limit to 3 refinements
                prompt_parts.append(f"  - {note}")
        
        # Special formatting for India Post mascot
        if analyzed.subject and "mascot" in analyzed.subject.lower():
            prompt_parts.append("")
            prompt_parts.append("Characteristics to include:")
            characteristics = [
                "Trust & Reliability",
                "Public Service",
                "Inclusivity",
                "Indian Culture & Heritage",
                "Digital Innovation",
                "Friendly Personality",
                "Nationwide Connectivity"
            ]
            prompt_parts.append(", ".join(characteristics))
        
        # Join all parts
        prompt = " ".join(prompt_parts)
        
        # Clean up
        prompt = prompt.replace("  ", " ").strip()
        
        logger.info(f"Built prompt: {prompt[:200]}...")
        
        return prompt
    
    def get_parameters(
        self,
        analyzed: AnalyzedInput,
        backend: str = "mcp"
    ) -> dict:
        """
        Get generation parameters for a specific backend.
        
        Args:
            analyzed: AnalyzedInput
            backend: Backend name
        
        Returns:
            Dictionary of generation parameters
        """
        # Start with defaults
        params = self.default_params.copy()
        
        # Apply backend-specific parameters
        if backend in self.backend_params:
            params.update(self.backend_params[backend])
        
        # Apply constraints from analyzed input
        if analyzed.constraints:
            if "width" in analyzed.constraints:
                params["width"] = analyzed.constraints["width"]
            if "height" in analyzed.constraints:
                params["height"] = analyzed.constraints["height"]
        
        # Add seed for reproducibility
        params["seed"] = int(time.time()) % 1000000
        
        return params
    
    def format_prompt_for_backend(
        self,
        prompt: str,
        backend: str,
        analyzed: AnalyzedInput
    ) -> str:
        """
        Format prompt for a specific backend's requirements.
        
        Args:
            prompt: Base prompt
            backend: Backend name
            analyzed: AnalyzedInput
        
        Returns:
            Backend-specific formatted prompt
        """
        if backend == "mcp":
            # Orshot MCP format
            return self._format_for_mcp(prompt, analyzed)
        elif backend == "cli":
            return self._format_for_cli(prompt, analyzed)
        elif backend == "web_api":
            return self._format_for_web_api(prompt, analyzed)
        else:
            return prompt
    
    def _format_for_mcp(self, prompt: str, analyzed: AnalyzedInput) -> str:
        """Format prompt for MCP backend (Orshot)."""
        # Orshot uses template-based generation
        # We'll create a comprehensive template
        
        template = f"""
Design Task: {analyzed.subject or 'Mascot Design'}

Description: {prompt}

Style Requirements:
- {analyzed.style or 'Professional and friendly'}
- High quality, detailed
- Suitable for official use

Technical Requirements:
- Format: PNG
- Transparent background preferred
- High resolution: 1024x1024
        """
        return template.strip()
    
    def _format_for_cli(self, prompt: str, analyzed: AnalyzedInput) -> str:
        """Format prompt for CLI backend (Stable Diffusion)."""
        # Add negative prompt
        negative_prompt = "blurry, low quality, deformed, ugly, distorted"
        
        # Format: positive prompt + negative prompt
        return f"{prompt}, high quality, detailed --neg {negative_prompt}"
    
    def _format_for_web_api(self, prompt: str, analyzed: AnalyzedInput) -> str:
        """Format prompt for Web API backend (DALL-E, etc.)."""
        # Most web APIs just need the prompt as-is
        return prompt
    
    def extract_references(self, analyzed: AnalyzedInput) -> list[str]:
        """
        Extract reference paths/URLs from analyzed input.
        
        Args:
            analyzed: AnalyzedInput
        
        Returns:
            List of reference file paths or URLs
        """
        references = []
        for ref in analyzed.references:
            if ref.type == ReferenceType.FILE and ref.path:
                references.append(ref.path)
            elif ref.type == ReferenceType.URL and ref.url:
                references.append(ref.url)
        return references
    
    async def post_process(
        self,
        result: GenerationResult,
        backend: str
    ) -> GenerationResult:
        """
        Post-process a generation result.
        
        Args:
            result: GenerationResult from backend
            backend: Backend name
        
        Returns:
            Post-processed GenerationResult
        """
        # Ensure output directory exists
        output_dir = Path(config.output_dir if hasattr(config, 'output_dir') else "./output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # If result has image_path, ensure it's in the right location
        if result.image_path:
            file_utils = FileUtils()
            if not Path(result.image_path).is_absolute():
                # Make it absolute
                result.image_path = str(Path(result.image_path).absolute())
            
            # Copy to output directory
            output_path = output_dir / Path(result.image_path).name
            file_utils.copy_file(result.image_path, str(output_path))
            result.image_path = str(output_path)
        
        return result
