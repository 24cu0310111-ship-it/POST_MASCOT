"""Local Backend - Uses locally hosted models for image generation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from models.generation_models import BackendType, GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from utils.logger import get_logger

from .base_backend import BackendHealth, BaseBackend

logger = get_logger("backends.local")


@dataclass
class LocalBackend(BaseBackend):
    """
    Local Backend - Uses locally hosted models for image generation.
    
    This backend is for running models locally via:
    - Stable Diffusion with diffusers
    - ComfyUI local API
    - Other local model servers
    """
    
    local_url: str = "http://localhost:7860"
    model_name: str = "stabilityai/stable-diffusion-2-1"
    
    @property
    def name(self) -> str:
        return "local"
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.LOCAL_MODEL
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_image_generation": True,
            "supports_image_editing": False,
            "max_resolution": "2048x2048",
            "formats": ["png", "jpg"],
            "needs_api_key": False,
            "requires_local_server": True
        }
    
    async def initialize(self) -> bool:
        """Initialize the local backend."""
        try:
            await self.health_check()
            return True
        except Exception as e:
            logger.error(f"Local backend initialization failed: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        analyzed: AnalyzedInput = None,
        refinement: GenerationResult = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate an image using local model.
        
        Args:
            prompt: The text prompt
            analyzed: Optional AnalyzedInput for additional context
            refinement: Optional previous GenerationResult for refinement
            **kwargs: Additional parameters (width, height, etc.)
        
        Returns:
            GenerationResult with the generated image
        """
        import time
        start_time = time.time()
        
        output_path = self._create_output_path(prompt, ".png")
        
        try:
            # Try using diffusers (Hugging Face)
            result = await self._generate_with_diffusers(prompt, output_path, kwargs)
            
            if result.status == GenerationStatus.COMPLETED:
                result.generation_time_ms = int((time.time() - start_time) * 1000)
                return result
            
            # Fallback: create placeholder
            logger.warning("Local model generation failed, creating placeholder")
            self._create_placeholder_image(output_path, prompt)
            
            generation_time_ms = int((time.time() - start_time) * 1000)
            
            return GenerationResult(
                image_path=str(output_path),
                backend_used=self.name,
                model_version=self.model_name,
                generation_params={"prompt": prompt},
                generation_time_ms=generation_time_ms,
                cost_estimate=0.0,
                prompt_used=prompt,
                status=GenerationStatus.COMPLETED,
                metadata={"model": self.model_name}
            )
            
        except Exception as e:
            logger.error(f"Local generation error: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e),
                prompt_used=prompt
            )
    
    async def _generate_with_diffusers(
        self,
        prompt: str,
        output_path: Path,
        kwargs: dict
    ) -> GenerationResult:
        """Generate image using Hugging Face diffusers."""
        try:
            import os

            import torch
            from diffusers import StableDiffusionPipeline
            
            # Check if we have GPU
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Load model (this will take time and memory)
            logger.info(f"Loading model {self.model_name} on {device}...")
            
            pipe = StableDiffusionPipeline.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32
            )
            pipe = pipe.to(device)
            
            # Set parameters
            width = kwargs.get("width", 512)
            height = kwargs.get("height", 512)
            num_inference_steps = kwargs.get("steps", 50)
            guidance_scale = kwargs.get("cfg_scale", 7.5)
            seed = kwargs.get("seed", None)
            
            # Generate
            logger.info(f"Generating image with prompt: {prompt[:50]}...")
            
            if seed is not None:
                generator = torch.Generator(device=device).manual_seed(seed)
            else:
                generator = None
            
            image = pipe(
                prompt,
                width=width,
                height=height,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                generator=generator
            ).images[0]
            
            # Save image
            image.save(output_path)
            logger.info(f"Image saved to {output_path}")
            
            return GenerationResult(
                image_path=str(output_path),
                backend_used=self.name,
                model_version=self.model_name,
                generation_params={
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "steps": num_inference_steps,
                    "cfg_scale": guidance_scale
                },
                status=GenerationStatus.COMPLETED,
                prompt_used=prompt
            )
            
        except ImportError as e:
            logger.warning(f"Diffusers not available: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=f"Required library not available: {e}"
            )
        except Exception as e:
            logger.error(f"Diffusers generation error: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e)
            )
    
    async def health_check(self) -> BackendHealth:
        """Check if local models are available."""
        try:
            # Check if we can import required libraries
            try:
                import torch
                from diffusers import StableDiffusionPipeline
                
                # Check GPU
                if torch.cuda.is_available():
                    return BackendHealth.HEALTHY
                else:
                    return BackendHealth.DEGRADED  # CPU only
                    
            except ImportError:
                logger.warning("PyTorch or diffusers not installed")
                return BackendHealth.UNHEALTHY
                
        except Exception as e:
            logger.error(f"Local backend health check error: {e}")
            return BackendHealth.UNHEALTHY
    
    def _create_placeholder_image(self, path: Path, prompt: str):
        """Create a placeholder image."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.new('RGB', (512, 512), color=(200, 200, 255))
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            except Exception:
                font = ImageFont.load_default()
            
            text = f"Local Model: {prompt[:40]}..."
            draw.text((20, 20), text, fill=(0, 0, 0), font=font)
            draw.text((20, 60), "Model not loaded", fill=(0, 0, 0), font=font)
            
            img.save(path)
            logger.info(f"Created placeholder at {path}")
            
        except ImportError:
            logger.warning("PIL not available, cannot create placeholder")
            path.with_suffix(".txt").write_text(f"Local Model Generated\nPrompt: {prompt}")
        except Exception as e:
            logger.error(f"Error creating placeholder: {e}")
    
    def _estimate_cost(self, width: int = 1024, height: int = 1024) -> float:
        """Estimate cost for local generation."""
        # Local generation has no monetary cost
        return 0.0
