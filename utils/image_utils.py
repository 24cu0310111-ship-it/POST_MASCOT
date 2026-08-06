"""Image processing utilities for the MAO system."""

import base64
import hashlib
from pathlib import Path

try:
    from PIL import Image, ImageOps, ImageStat
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


class ImageUtils:
    """Utility class for image operations."""
    
    @staticmethod
    def validate_image_path(path: str) -> bool:
        """Validate that a path points to a valid image file."""
        if not Path(path).exists():
            return False
        
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff']
        return Path(path).suffix.lower() in valid_extensions
    
    @staticmethod
    def get_image_info(path: str) -> dict:
        """Get basic information about an image."""
        if not PIL_AVAILABLE:
            return {"error": "PIL not available"}
        
        try:
            with Image.open(path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                    "size_bytes": Path(path).stat().st_size
                }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def calculate_image_hash(path: str) -> str:
        """Calculate a hash of an image file for uniqueness."""
        with open(path, 'rb') as f:
            content = f.read()
        return hashlib.sha256(content).hexdigest()
    
    @staticmethod
    def image_to_base64(path: str) -> str | None:
        """Convert image file to base64 string."""
        try:
            with open(path, 'rb') as f:
                content = f.read()
            return base64.b64encode(content).decode('utf-8')
        except Exception:
            return None
    
    @staticmethod
    def base64_to_image(base64_str: str, output_path: str) -> bool:
        """Save base64 string as image file."""
        try:
            content = base64.b64decode(base64_str)
            with open(output_path, 'wb') as f:
                f.write(content)
            return True
        except Exception:
            return False
    
    @staticmethod
    def resize_image(path: str, output_path: str, width: int, height: int) -> bool:
        """Resize an image."""
        if not PIL_AVAILABLE:
            return False
        
        try:
            with Image.open(path) as img:
                img = img.resize((width, height), Image.Resampling.LANCZOS)
                img.save(output_path)
            return True
        except Exception:
            return False
    
    @staticmethod
    def detect_blur(image_path: str, threshold: float = 100.0) -> float:
        """
        Detect blur in an image using OpenCV.
        Returns blur score (higher = more blurry).
        """
        if not OPENCV_AVAILABLE:
            return 0.0
        
        try:
            img = cv2.imread(image_path)
            if img is None:
                return 0.0
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            return float(blur_score)
        except Exception:
            return 0.0
    
    @staticmethod
    def detect_edges(image_path: str) -> float:
        """Detect edge density in an image."""
        if not OPENCV_AVAILABLE:
            return 0.0
        
        try:
            img = cv2.imread(image_path)
            if img is None:
                return 0.0
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            edge_pixels = cv2.countNonZero(edges)
            total_pixels = gray.size
            return edge_pixels / total_pixels if total_pixels > 0 else 0.0
        except Exception:
            return 0.0
    
    @staticmethod
    def get_average_color(image_path: str) -> tuple[float, float, float]:
        """Get average RGB color of an image."""
        if not PIL_AVAILABLE:
            return (0, 0, 0)
        
        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                width, height = img.size
                pixels = img.load()
                
                r, g, b = 0, 0, 0
                count = 0
                
                # Sample a subset of pixels for performance
                step = max(1, width // 100, height // 100)
                for x in range(0, width, step):
                    for y in range(0, height, step):
                        pixel = pixels[x, y]
                        r += pixel[0]
                        g += pixel[1]
                        b += pixel[2]
                        count += 1
                
                if count > 0:
                    return (r / count, g / count, b / count)
                return (0, 0, 0)
        except Exception:
            return (0, 0, 0)
    
    @staticmethod
    def is_valid_image_file(path: str) -> bool:
        """Check if a file is a valid image."""
        if not Path(path).exists():
            return False
        
        try:
            if PIL_AVAILABLE:
                with Image.open(path) as img:
                    img.verify()
                    return True
            elif OPENCV_AVAILABLE:
                img = cv2.imread(path)
                return img is not None
            else:
                # Fallback: check file extension
                valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff']
                return Path(path).suffix.lower() in valid_extensions
        except Exception:
            return False
    
    @staticmethod
    def create_thumbnail(image_path: str, output_path: str, size: int = 256) -> bool:
        """Create a thumbnail of an image."""
        if not PIL_AVAILABLE:
            return False
        
        try:
            with Image.open(image_path) as img:
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                img.save(output_path)
            return True
        except Exception:
            return False
