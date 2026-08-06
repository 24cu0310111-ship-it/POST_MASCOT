"""Web API Backend - Uses REST APIs for image generation (DALL-E, Flux, etc.)."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import config_manager
from models.generation_models import BackendType, GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from utils.logger import get_logger

from .base_backend import BackendHealth, BaseBackend

logger = get_logger("backends.web_api")


@dataclass
class WebAPIBackend(BaseBackend):
    """
    Web API Backend - Uses REST APIs for image generation.
    
    Supports:
    - DALL-E
    - Midjourney (via unofficial APIs)
    - Flux
    - Stable Diffusion APIs
    """
    
    api_provider: str = "dall-e"  # or "flux", "midjourney", "stable-diffusion"
    base_url: str = "https://api.openai.com/v1/images/generations"
    
    @property
    def name(self) -> str:
        return "web_api"
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.WEB_API
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_image_generation": True,
            "supports_image_editing": True,
            "supports_upscaling": True,
            "max_resolution": "4096x4096",
            "formats": ["png", "jpg", "webp"],
            "needs_api_key": True
        }
    
    def __init__(self):
        super().__init__()
        self._load_config()
    
    def _load_config(self):
        """Load configuration."""
        # Try to get API key
        self.api_key = getattr(self, 'api_key', None) or \
                      config_manager.get_api_key("dall-e") or \
                      config_manager.get_api_key("OPENAI_API_KEY") or \
                      os.getenv("OPENAI_API_KEY")
    
    async def initialize(self) -> bool:
        """Initialize the Web API backend."""
        try:
            await self.health_check()
            return True
        except Exception as e:
            logger.error(f"Web API backend initialization failed: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        analyzed: AnalyzedInput = None,
        refinement: GenerationResult = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate an image using Web API.
        
        Args:
            prompt: The text prompt
            analyzed: Optional AnalyzedInput for additional context
            refinement: Optional previous GenerationResult for refinement
            **kwargs: Additional parameters (size, n, model, etc.)
        
        Returns:
            GenerationResult with the generated image
        """
        import time
        start_time = time.time()
        
        output_path = self._create_output_path(prompt, ".png")
        
        try:
            # Get API key
            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error="No API key configured for Web API backend",
                    prompt_used=prompt
                )
            
            # Prepare request
            request_data = self._prepare_request(prompt, kwargs)
            
            # Send request
            result = await self._send_request(request_data, api_key)
            
            if result.get("error"):
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error=result["error"],
                    prompt_used=prompt
                )
            
            # Process response
            if self.api_provider == "dall-e":
                return await self._process_dalle_response(result, output_path, prompt, start_time)
            else:
                return await self._process_generic_response(result, output_path, prompt, start_time)
                
        except Exception as e:
            logger.error(f"Web API generation error: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e),
                prompt_used=prompt
            )
    
    def _prepare_request(self, prompt: str, kwargs: dict) -> dict:
        """Prepare request data for the API."""
        if self.api_provider == "dall-e":
            return {
                "prompt": prompt,
                "n": kwargs.get("n", 1),
                "size": kwargs.get("size", "1024x1024"),
                "model": kwargs.get("model", "dall-e-3"),
                "response_format": kwargs.get("response_format", "url")
            }
        else:
            # Generic request
            return {
                "prompt": prompt,
                "width": kwargs.get("width", 1024),
                "height": kwargs.get("height", 1024),
                "steps": kwargs.get("steps", 50)
            }
    
    async def _send_request(self, data: dict, api_key: str) -> dict:
        """Send request to the API."""
        try:
            import aiohttp
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session, session.post(
                self.base_url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=getattr(self, 'timeout', 300))
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    return {"error": f"HTTP {response.status}: {error_text}"}
        
        except ImportError:
            # Fallback to requests
            import requests
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                self.base_url,
                json=data,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
    
    async def _process_dalle_response(
        self,
        result: dict,
        output_path: Path,
        prompt: str,
        start_time: float
    ) -> GenerationResult:
        """Process DALL-E API response."""
        import time
        
        if "data" not in result or not result["data"]:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error="No data in response",
                prompt_used=prompt
            )
        
        # Get the first image URL
        image_url = result["data"][0].get("url")
        
        if not image_url:
            # Try to get b64_json
            image_b64 = result["data"][0].get("b64_json")
            if image_b64:
                # Decode and save
                import base64
                image_data = base64.b64decode(image_b64)
                output_path.write_bytes(image_data)
            else:
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error="No image URL or data in response",
                    prompt_used=prompt
                )
        else:
            # Download the image
            await self._download_image(image_url, output_path)
        
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        return GenerationResult(
            image_path=str(output_path),
            image_url=image_url,
            backend_used=self.name,
            model_version=result.get("model", "dall-e-3"),
            generation_params={
                "prompt": prompt,
                "provider": self.api_provider
            },
            generation_time_ms=generation_time_ms,
            cost_estimate=self._estimate_cost(),
            prompt_used=prompt,
            status=GenerationStatus.COMPLETED,
            metadata={
                "api_provider": self.api_provider,
                "response_id": result.get("id")
            }
        )
    
    async def _process_generic_response(
        self,
        result: dict,
        output_path: Path,
        prompt: str,
        start_time: float
    ) -> GenerationResult:
        """Process generic API response."""
        import time
        
        # Try to get image data
        image_data = result.get("image") or result.get("images", [None])[0]
        
        if not image_data:
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error="No image data in response",
                prompt_used=prompt
            )
        
        # Save image
        if isinstance(image_data, str):
            # Could be URL or base64
            if image_data.startswith("http"):
                await self._download_image(image_data, output_path)
            else:
                import base64
                image_bytes = base64.b64decode(image_data)
                output_path.write_bytes(image_bytes)
        else:
            # Assume it's bytes
            output_path.write_bytes(image_data)
        
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        return GenerationResult(
            image_path=str(output_path),
            backend_used=self.name,
            model_version=result.get("model", "unknown"),
            generation_params={"prompt": prompt},
            generation_time_ms=generation_time_ms,
            cost_estimate=self._estimate_cost(),
            prompt_used=prompt,
            status=GenerationStatus.COMPLETED
        )
    
    async def _download_image(self, url: str, output_path: Path):
        """Download image from URL."""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        output_path.write_bytes(content)
        except ImportError:
            import requests
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                output_path.write_bytes(response.content)
    
    async def health_check(self) -> BackendHealth:
        """Check if the API is accessible."""
        try:
            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                return BackendHealth.UNHEALTHY
            
            # Try a simple request
            import aiohttp
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Use a small test prompt
            test_data = {
                "prompt": "Test image",
                "n": 1,
                "size": "256x256"
            }
            
            async with aiohttp.ClientSession() as session, session.post(
                self.base_url,
                json=test_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return BackendHealth.HEALTHY
                else:
                    return BackendHealth.DEGRADED
                        
        except Exception as e:
            logger.error(f"Web API health check error: {e}")
            return BackendHealth.UNHEALTHY
    
    def _estimate_cost(self, width: int = 1024, height: int = 1024) -> float:
        """Estimate cost for Web API generation."""
        # DALL-E pricing (approximate)
        if self.api_provider == "dall-e":
            size_category = "standard"
            if width <= 512 and height <= 512:
                size_category = "small"
            elif width <= 1024 and height <= 1024:
                size_category = "standard"
            else:
                size_category = "large"
            
            costs = {
                "small": 0.016,
                "standard": 0.032,
                "large": 0.064
            }
            return costs.get(size_category, 0.032)
        return 0.05  # Default estimate
