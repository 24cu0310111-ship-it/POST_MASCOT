"""MCP Backend - Uses MCP protocol for image generation (Orshot)."""

import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import config_manager
from models.generation_models import BackendType, GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from utils.logger import get_logger

from .base_backend import BackendHealth, BaseBackend

logger = get_logger("backends.mcp")


@dataclass
class MCPBackend(BaseBackend):
    """
    MCP Server Backend - Uses MCP protocol for image generation.
    
    Connects to MCP servers like Orshot for image generation.
    """
    
    mcp_url: str = "https://mcp.orshot.com/mcp"
    api_key: str | None = None
    
    @property
    def name(self) -> str:
        return "mcp"
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.MCP_SERVER
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_image_generation": True,
            "supports_image_editing": True,
            "supports_style_transfer": True,
            "max_resolution": "2048x2048",
            "formats": ["png", "jpg", "svg"],
            "needs_api_key": True
        }
    
    def __init__(self):
        super().__init__()
        self._load_config()
    
    def _load_config(self):
        """Load configuration from config manager."""
        self.mcp_url = os.getenv("MCP_URL") or config_manager.get_api_key("MCP_URL") or self.mcp_url
        self.api_key = (
            self.api_key
            or os.getenv("ORSHOT_API_KEY")
            or config_manager.get_api_key("ORSHOT_API_KEY")
            or config_manager.get_api_key("orshot")
            or os.getenv("OPENCODE_API_KEY")
            or config_manager.get_api_key("opencode")
        )
        
        logger.info(f"MCP Backend initialized. URL: {self.mcp_url}")
    
    async def initialize(self) -> bool:
        """Initialize the MCP backend."""
        # Check if we can connect
        try:
            await self.health_check()
            return True
        except Exception as e:
            logger.error(f"MCP backend initialization failed: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        analyzed: AnalyzedInput = None,
        refinement: GenerationResult = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate an image using MCP server (Orshot).
        
        Args:
            prompt: The text prompt
            analyzed: Optional AnalyzedInput for additional context
            refinement: Optional previous GenerationResult for refinement
            **kwargs: Additional parameters (size, format, etc.)
        
        Returns:
            GenerationResult with the generated image
        """
        import time
        start_time = time.time()
        
        output_path = self._create_output_path(prompt, ".png")
        
        try:
            # Try to import mcp client
            try:
                from mcp import ClientSession
                from mcp.client.sse import sse_client
            except ImportError as e:
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error=f"MCP client not available: {e}"
                )
            
            # Get API key
            api_key = self.api_key
            if not api_key:
                logger.warning("No ORSHOT_API_KEY configured — generating placeholder image")
                self._create_placeholder_image(output_path, prompt)
                prompt_file = output_path.with_suffix(".txt")
                prompt_file.write_text(prompt)
                generation_time_ms = int((time.time() - start_time) * 1000)
                return GenerationResult(
                    image_path=str(output_path),
                    backend_used=self.name,
                    model_version="placeholder",
                    generation_params={"prompt": prompt, "size": kwargs.get("size", "1080x1080")},
                    generation_time_ms=generation_time_ms,
                    cost_estimate=0.0,
                    prompt_used=prompt,
                    status=GenerationStatus.COMPLETED,
                    metadata={
                        "note": "No ORSHOT_API_KEY set — placeholder image generated. Set ORSHOT_API_KEY in .env for real generation.",
                        "mcp_server": self.mcp_url,
                    }
                )
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json, text/event-stream"
            }
            
            # Connect to MCP server
            logger.info(f"Connecting to MCP server at {self.mcp_url}...")
            
            try:
                async with sse_client(url=self.mcp_url, headers=headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        logger.info("Connected to MCP server")
                        
                        # Prepare generation parameters
                        size = kwargs.get("size", "1080x1080")
                        image_format = kwargs.get("format", "png")
                        
                        # Call Orshot tool
                        result = await session.call_tool(
                            "orshot_create_template_design",
                            arguments={
                                "name": analyzed.subject or "Generated Image",
                                "size": size,
                                "pages_data": [
                                    {
                                        "elements": [
                                            {
                                                "id": "prompt_text",
                                                "type": "text",
                                                "text": prompt,
                                                "position": {"x": 50, "y": 50},
                                                "size": {"width": 980, "height": 980},
                                                "style": {
                                                    "fontSize": "30px",
                                                    "color": "#000000"
                                                }
                                            }
                                        ],
                                        "backgroundColor": "#ffffff"
                                    }
                                ],
                                "includeThumbnails": True
                            }
                        )
                        
                        logger.info("MCP generation completed")
                        
                        # Extract image from response
                        response_metadata = result.model_dump() if hasattr(result, 'model_dump') else {"response": str(result)}
                        image_saved = await self._extract_image_from_response(result, output_path)
                        
                        # Save prompt to file
                        prompt_file = output_path.with_suffix(".txt")
                        prompt_file.write_text(prompt)
                        
                        generation_time_ms = int((time.time() - start_time) * 1000)
                        
                        if image_saved:
                            return GenerationResult(
                                image_path=str(output_path),
                                backend_used=self.name,
                                model_version="orshot-v1",
                                generation_params={
                                    "prompt": prompt,
                                    "size": size,
                                    "format": image_format
                                },
                                generation_time_ms=generation_time_ms,
                                cost_estimate=self._estimate_cost(),
                                prompt_used=prompt,
                                status=GenerationStatus.COMPLETED,
                                metadata={
                                    "mcp_server": self.mcp_url,
                                    "tool": "orshot_create_template_design",
                                    "response": response_metadata
                                }
                            )
                        else:
                            # No image data found — return completed with URL if available
                            image_url = self._extract_url_from_response(response_metadata)
                            if image_url:
                                return GenerationResult(
                                    image_path=None,
                                    image_url=image_url,
                                    backend_used=self.name,
                                    model_version="orshot-v1",
                                    generation_params={
                                        "prompt": prompt,
                                        "size": size,
                                        "format": image_format
                                    },
                                    generation_time_ms=generation_time_ms,
                                    cost_estimate=self._estimate_cost(),
                                    prompt_used=prompt,
                                    status=GenerationStatus.COMPLETED,
                                    metadata={
                                        "mcp_server": self.mcp_url,
                                        "tool": "orshot_create_template_design",
                                        "response": response_metadata,
                                        "note": "Image URL returned but not downloaded locally"
                                    }
                                )
                            else:
                                # Fall back to placeholder
                                self._create_placeholder_image(output_path, prompt)
                                return GenerationResult(
                                    image_path=str(output_path),
                                    backend_used=self.name,
                                    model_version="orshot-v1",
                                    generation_params={
                                        "prompt": prompt,
                                        "size": size,
                                        "format": image_format
                                    },
                                    generation_time_ms=generation_time_ms,
                                    cost_estimate=self._estimate_cost(),
                                    prompt_used=prompt,
                                    status=GenerationStatus.COMPLETED,
                                    metadata={
                                        "mcp_server": self.mcp_url,
                                        "tool": "orshot_create_template_design",
                                        "response": response_metadata,
                                        "note": "Placeholder image — no image data in Orshot response"
                                    }
                                )
                        
            except Exception as e:
                logger.error(f"MCP generation error: {e}")
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error=str(e),
                    prompt_used=prompt
                )
            
        except Exception as e:
            logger.error(f"MCP backend error: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e),
                prompt_used=prompt
            )
    
    async def _extract_image_from_response(self, result, output_path: Path) -> bool:
        """Try to extract an image from the MCP tool result.
        
        Checks for:
        1. Base64-encoded image data in text content
        2. Image URLs in text content
        3. Thumbnail data if includeThumbnails was set
        
        Returns True if an image was saved.
        """
        try:
            # MCP CallToolResult has a .content list of content blocks
            content_items = getattr(result, 'content', [])
            if not content_items and hasattr(result, 'result'):
                content_items = getattr(result.result, 'content', [])
            
            for item in content_items:
                text = getattr(item, 'text', '') or ''
                
                # Check for base64 data URI: data:image/...;base64,...
                b64_match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', text)
                if b64_match:
                    img_data = base64.b64decode(b64_match.group(1))
                    output_path.write_bytes(img_data)
                    logger.info(f"Saved base64 image to {output_path}")
                    return True
                
                # Check for direct base64 block (no data URI prefix)
                clean = text.strip()
                if len(clean) > 500 and re.match(r'^[A-Za-z0-9+/=\s]+$', clean):
                    try:
                        img_data = base64.b64decode(clean.replace('\n', '').replace(' ', ''))
                        if img_data[:4] in [b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1', b'RIFF']:
                            output_path.write_bytes(img_data)
                            logger.info(f"Saved raw base64 image to {output_path}")
                            return True
                    except Exception:
                        pass
                
                # Check for image URL
                url_match = re.search(r'(https?://[^\s"\'<>]+\.(?:png|jpg|jpeg|webp|gif))', text, re.IGNORECASE)
                if url_match:
                    url = url_match.group(1)
                    if await self._download_url(url, output_path):
                        return True
            
            # Check result.data or result.result for nested structures
            for obj in [result, getattr(result, 'result', None)]:
                if obj is None:
                    continue
                data = getattr(obj, 'data', None)
                if isinstance(data, dict):
                    for key in ['image', 'imageUrl', 'url', 'thumbnail', 'output', 'png', 'jpg', 'renderedUrl', 'downloadUrl', 'designUrl']:
                        val = data.get(key)
                        if isinstance(val, str) and val.startswith('http'):
                            if await self._download_url(val, output_path):
                                return True
                        elif isinstance(val, str) and len(val) > 100:
                            try:
                                img_data = base64.b64decode(val)
                                if len(img_data) > 100:
                                    output_path.write_bytes(img_data)
                                    return True
                            except Exception:
                                pass
                    # Check nested 'result' dict
                    nested = data.get('result', {})
                    if isinstance(nested, dict):
                        for key in ['imageUrl', 'url', 'thumbnail', 'output', 'renderedUrl', 'downloadUrl']:
                            val = nested.get(key)
                            if isinstance(val, str) and val.startswith('http'):
                                if await self._download_url(val, output_path):
                                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")
            return False
    
    def _extract_url_from_response(self, response_metadata: dict) -> str | None:
        """Extract an image URL from the response metadata."""
        if not isinstance(response_metadata, dict):
            return None
        
        # Check common URL keys at top level
        for key in ['url', 'imageUrl', 'image_url', 'thumbnail', 'output_url', 'design_url', 'renderedUrl', 'downloadUrl']:
            val = response_metadata.get(key)
            if isinstance(val, str) and val.startswith('http'):
                return val
        
        # Check nested content
        content = response_metadata.get('content', response_metadata.get('result', {}))
        if isinstance(content, dict):
            return self._extract_url_from_response(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    url = self._extract_url_from_response(item)
                    if url:
                        return url
                elif isinstance(item, str) and item.startswith('http'):
                    return item
        
        return None
    
    async def _download_url(self, url: str, output_path: Path) -> bool:
        """Download a URL to a local file."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if len(data) > 100:
                            output_path.write_bytes(data)
                            logger.info(f"Downloaded image from {url} to {output_path}")
                            return True
        except ImportError:
            try:
                import requests
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 100:
                    output_path.write_bytes(resp.content)
                    logger.info(f"Downloaded image from {url} to {output_path}")
                    return True
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to download {url}: {e}")
        return False
    
    async def health_check(self) -> BackendHealth:
        """Check if the MCP server is accessible."""
        try:
            # Try to import
            try:
                from mcp import ClientSession
                from mcp.client.sse import sse_client
            except ImportError:
                logger.warning("MCP client not installed")
                return BackendHealth.UNHEALTHY
            
            # Try to connect
            api_key = self.api_key or os.getenv("OPENCODE_API_KEY")
            if not api_key:
                logger.warning("No API key for MCP health check")
                return BackendHealth.UNHEALTHY
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json"
            }
            
            # Quick connection test
            try:
                async with sse_client(url=self.mcp_url, headers=headers) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        return BackendHealth.HEALTHY
            except Exception as e:
                logger.warning(f"MCP health check failed: {e}")
                return BackendHealth.UNHEALTHY
                
        except Exception as e:
            logger.error(f"MCP health check error: {e}")
            return BackendHealth.UNHEALTHY
    
    def _create_placeholder_image(self, path: Path, prompt: str):
        """Create a placeholder image showing the prompt (for when no API key is available)."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.new('RGB', (1024, 1024), color=(240, 244, 248))
            draw = ImageDraw.Draw(img)

            try:
                font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
                font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
                font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
            except Exception:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
                font_title = ImageFont.load_default()

            # Header bar
            draw.rectangle([0, 0, 1024, 80], fill=(25, 118, 210))
            draw.text((30, 18), "MAO — Multi-Agent Orchestrator", fill=(255, 255, 255), font=font_large)

            # Center icon area
            draw.rectangle([362, 140, 662, 440], outline=(25, 118, 210), width=3)
            draw.text((410, 260), "IMAGE", fill=(25, 118, 210), font=font_title)

            # Status badge
            draw.rounded_rectangle([340, 470, 684, 520], radius=10, fill=(255, 193, 7))
            draw.text((370, 478), "PLACEHOLDER — No API Key Set", fill=(0, 0, 0), font=font_small)

            # Prompt text (wrapped)
            y = 550
            words = prompt.split()
            line = ""
            for word in words:
                test = f"{line} {word}".strip()
                if len(test) > 55:
                    draw.text((50, y), line, fill=(50, 50, 50), font=font_small)
                    y += 24
                    line = word
                else:
                    line = test
            if line:
                draw.text((50, y), line, fill=(50, 50, 50), font=font_small)

            # Footer
            draw.rectangle([0, 980, 1024, 1024], fill=(25, 118, 210))
            draw.text((30, 988), "Set ORSHOT_API_KEY in .env for real generation", fill=(200, 220, 255), font=font_small)

            # Border
            draw.rectangle([0, 0, 1023, 1023], outline=(25, 118, 210), width=2)

            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path)
            logger.info(f"Created placeholder image at {path}")

        except ImportError:
            logger.warning("PIL not available, cannot create placeholder image")
            path.with_suffix(".txt").write_text(f"MAO Generated Image\nPrompt: {prompt}\n\nSet ORSHOT_API_KEY in .env for real generation.")
        except Exception as e:
            logger.error(f"Error creating placeholder: {e}")
    
    def _estimate_cost(self, width: int = 1024, height: int = 1024) -> float:
        """Estimate cost for MCP generation."""
        # Orshot is free for basic usage
        return 0.0
