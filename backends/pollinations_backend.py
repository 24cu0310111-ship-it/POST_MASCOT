"""Pollinations.ai Backend — FREE, no API key required."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import config_manager
from models.generation_models import BackendType, GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from utils.logger import get_logger

from .base_backend import BackendHealth, BaseBackend

logger = get_logger("backends.pollinations")


@dataclass
class PollinationsBackend(BaseBackend):
    """
    Pollinations.ai Backend — FREE image generation, no API key needed.
    
    Uses: https://pollinations.ai API
    """
    
    api_url: str = "https://image.pollinations.ai/prompt"
    
    @property
    def name(self) -> str:
        return "pollinations"
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.WEB_API
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_image_generation": True,
            "supports_image_editing": False,
            "max_resolution": "1024x1024",
            "formats": ["jpg", "png"],
            "needs_api_key": False,
            "free_tier": True
        }
    
    def __init__(self):
        super().__init__()
        logger.info("Pollinations backend initialized (FREE, no key needed)")
    
    async def initialize(self) -> bool:
        return True
    
    async def generate(
        self,
        prompt: str,
        analyzed: AnalyzedInput = None,
        refinement: GenerationResult = None,
        **kwargs
    ) -> GenerationResult:
        """Generate image using Pollinations.ai"""
        start_time = time.time()
        output_path = self._create_output_path(prompt, ".jpg")
        
        try:
            # Clean prompt for URL
            clean_prompt = prompt.replace(" ", "%20")[:200]
            width = kwargs.get("width", 1024)
            height = kwargs.get("height", 1024)
            seed = kwargs.get("seed", int(time.time() * 1000) % 1000000)
            
            # Build URL
            url = f"{self.api_url}/{clean_prompt}?width={width}&height={height}&seed={seed}&model=flux"
            
            logger.info(f"Pollinations URL: {url[:100]}...")
            
            # Download image
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        output_path.write_bytes(img_data)
                        logger.info(f"Image saved: {output_path} ({len(img_data)} bytes)")
                    else:
                        return GenerationResult(
                            status=GenerationStatus.FAILED,
                            error=f"Pollinations returned {resp.status}",
                            prompt_used=prompt
                        )
            
            generation_time_ms = int((time.time() - start_time) * 1000)
            
            return GenerationResult(
                image_path=str(output_path),
                backend_used=self.name,
                model_version="flux",
                generation_params={
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "seed": seed
                },
                generation_time_ms=generation_time_ms,
                cost_estimate=0.0,
                prompt_used=prompt,
                status=GenerationStatus.COMPLETED,
                metadata={
                    "source": "pollinations.ai",
                    "url": url,
                    "note": "FREE generation - no API key required"
                }
            )
            
        except ImportError:
            # Fallback to requests
            try:
                import requests
                resp = requests.get(url, timeout=60)
                if resp.status_code == 200:
                    output_path.write_bytes(resp.content)
                    logger.info(f"Image saved: {output_path} ({len(resp.content)} bytes)")
                else:
                    return GenerationResult(
                        status=GenerationStatus.FAILED,
                        error=f"Pollinations returned {resp.status_code}",
                        prompt_used=prompt
                    )
            except Exception as e:
                logger.error(f"Pollinations error: {e}")
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error=str(e),
                    prompt_used=prompt
                )
        except Exception as e:
            logger.error(f"Pollinations error: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e),
                prompt_used=prompt
            )
    
    async def health_check(self) -> BackendHealth:
        """Check if Pollinations is accessible"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/test?width=10&height=10",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return BackendHealth.HEALTHY
                    return BackendHealth.DEGRADED
        except Exception:
            return BackendHealth.UNHEALTHY
    
    def _estimate_cost(self, width: int = 1024, height: int = 1024) -> float:
        return 0.0  # FREE!
