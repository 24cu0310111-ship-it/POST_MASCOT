"""Reference Resolver - Part of Phase 1 Input Analyzer."""

from dataclasses import dataclass
from pathlib import Path

from models.input_models import Reference, ReferenceType
from utils.image_utils import ImageUtils
from utils.logger import get_logger

logger = get_logger("phase1.reference_resolver")


@dataclass
class ReferenceResolver:
    """
    Resolves and validates reference files, URLs, and prior outputs.
    
    Responsibilities:
    1. Resolve file paths, URLs, and prior conversation outputs
    2. Download and cache remote references
    3. Extract metadata (dimensions, format, color profile) from image references
    """
    
    download_cache: dict[str, str] = None  # URL -> local path mapping
    
    def __init__(self):
        self.download_cache = {}
        self.temp_dir = Path("./temp_references")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def resolve_batch(self, references: list[dict]) -> list[Reference]:
        """
        Resolve a batch of references from dictionary format.
        
        Args:
            references: List of reference dictionaries with 'type', 'path', 'url', or 'content'
            
        Returns:
            List of resolved Reference objects
        """
        resolved = []
        for ref_data in references:
            ref_type = ref_data.get('type', 'file')
            
            if ref_type == 'file':
                ref = Reference(
                    type=ReferenceType.FILE,
                    path=ref_data.get('path')
                )
                await self._resolve_file(ref)
                resolved.append(ref)
            
            elif ref_type == 'url':
                ref = Reference(
                    type=ReferenceType.URL,
                    url=ref_data.get('url')
                )
                await self._resolve_url(ref)
                resolved.append(ref)
            
            elif ref_type == 'text':
                ref = Reference(
                    type=ReferenceType.TEXT,
                    content=ref_data.get('content')
                )
                await self._resolve_text(ref)
                resolved.append(ref)
            
            elif ref_type == 'previous_output':
                ref = Reference(
                    type=ReferenceType.PREVIOUS_OUTPUT,
                    path=ref_data.get('path'),
                    content=ref_data.get('content')
                )
                await self._resolve_previous_output(ref)
                resolved.append(ref)
        
        return resolved
    
    async def _resolve_file(self, reference: Reference) -> Reference:
        """Resolve a file reference by validating and extracting metadata."""
        if reference.path:
            # Validate file exists
            file_path = Path(reference.path)
            if file_path.exists():
                reference.metadata = self._extract_file_metadata(str(file_path))
            else:
                reference.metadata = {"error": f"File not found: {reference.path}"}
                logger.warning(f"File not found: {reference.path}")
        return reference
    
    async def _resolve_url(self, reference: Reference) -> Reference:
        """Resolve a URL reference."""
        if reference.url:
            # Check if already cached
            if reference.url in self.download_cache:
                reference.path = self.download_cache[reference.url]
                reference.type = ReferenceType.FILE
                reference.metadata = self._extract_file_metadata(reference.path)
            else:
                # Download and cache
                local_path = await self._download_url(reference.url)
                if local_path:
                    self.download_cache[reference.url] = local_path
                    reference.path = local_path
                    reference.type = ReferenceType.FILE
                    reference.metadata = self._extract_file_metadata(local_path)
                else:
                    reference.metadata = {"url": reference.url, "cached": False}
        return reference
    
    async def _resolve_text(self, reference: Reference) -> Reference:
        """Resolve a text reference."""
        if reference.content:
            reference.metadata = {
                "type": "text",
                "length": len(reference.content)
            }
        return reference
    
    async def _resolve_previous_output(self, reference: Reference) -> Reference:
        """Resolve a reference to a previous output."""
        if reference.path:
            # Treat as file
            return await self._resolve_file(reference)
        elif reference.content:
            # Treat as text
            return await self._resolve_text(reference)
        return reference
    
    def _extract_file_metadata(self, file_path: str) -> dict:
        """Extract metadata from a file."""
        metadata = {"path": file_path}
        
        try:
            # Basic file info
            file_path_obj = Path(file_path)
            metadata["exists"] = file_path_obj.exists()
            metadata["size_bytes"] = file_path_obj.stat().st_size
            metadata["extension"] = file_path_obj.suffix.lower()
            
            # Image-specific metadata
            if metadata["extension"] in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff']:
                img_info = ImageUtils.get_image_info(file_path)
                metadata.update(img_info)
                
                # Extract color info
                avg_color = ImageUtils.get_average_color(file_path)
                metadata["average_color"] = {
                    "r": avg_color[0],
                    "g": avg_color[1],
                    "b": avg_color[2]
                }
            
        except Exception as e:
            metadata["error"] = str(e)
            logger.error(f"Error extracting metadata from {file_path}: {e}")
        
        return metadata
    
    async def _download_url(self, url: str) -> str | None:
        """
        Download a URL to local storage.
        
        Note: This is a placeholder. In a full implementation, use aiohttp or requests.
        """
        logger.warning(f"URL download not fully implemented: {url}")
        
        # For demonstration, we'll just create a placeholder file
        # In production, implement actual HTTP download
        try:
            import uuid

            import aiohttp
            
            # Generate unique filename
            filename = f"downloaded_{hash(url)}_{uuid.uuid4().hex}{Path(url).suffix}"
            output_path = self.temp_dir / filename
            
            # Download using aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        output_path.write_bytes(content)
                        logger.info(f"Downloaded {url} to {output_path}")
                        return str(output_path)
                    else:
                        logger.warning(f"Failed to download {url}: HTTP {response.status}")
                        return None
        except ImportError:
            # aiohttp not available, try requests
            try:
                import uuid

                import requests
                
                filename = f"downloaded_{hash(url)}_{uuid.uuid4().hex}{Path(url).suffix}"
                output_path = self.temp_dir / filename
                
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    output_path.write_bytes(response.content)
                    logger.info(f"Downloaded {url} to {output_path}")
                    return str(output_path)
                else:
                    logger.warning(f"Failed to download {url}: HTTP {response.status_code}")
                    return None
            except ImportError:
                logger.warning("Neither aiohttp nor requests available for URL download")
                return None
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return None
    
    async def download_reference(self, reference: Reference, output_dir: str = None) -> str | None:
        """
        Download a URL reference to local storage.
        
        Args:
            reference: Reference object with URL
            output_dir: Optional output directory (defaults to temp_dir)
            
        Returns:
            Local path to downloaded file, or None if failed
        """
        if reference.type != ReferenceType.URL:
            return None
        
        if output_dir:
            # Temporarily override temp_dir
            old_temp_dir = self.temp_dir
            self.temp_dir = Path(output_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            result = await self._download_url(reference.url)
            if result:
                # Update reference
                reference.path = result
                reference.type = ReferenceType.FILE
                reference.metadata = self._extract_file_metadata(result)
            return result
        finally:
            if output_dir:
                self.temp_dir = old_temp_dir
    
    def get_cached_path(self, url: str) -> str | None:
        """Get the cached local path for a URL, if available."""
        return self.download_cache.get(url)
    
    def clear_cache(self):
        """Clear all cached downloads."""
        import shutil
        for path in self.download_cache.values():
            try:
                Path(path).unlink()
            except Exception:
                pass
        self.download_cache.clear()
        
        # Remove temp directory
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass
