"""File system utilities for the MAO system."""

import shutil
import tempfile
from pathlib import Path


class FileUtils:
    """Utility class for file operations."""
    
    @staticmethod
    def ensure_directory(path: str) -> Path:
        """Ensure a directory exists, create if it doesn't."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_temp_dir(prefix: str = "mao_") -> Path:
        """Get a temporary directory for MAO operations."""
        return Path(tempfile.mkdtemp(prefix=prefix))
    
    @staticmethod
    def cleanup_temp_dir(temp_dir: str | Path) -> None:
        """Remove a temporary directory."""
        temp_dir = Path(temp_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @staticmethod
    def find_files(directory: str, extensions: list[str] = None) -> list[Path]:
        """Find files in a directory with optional extension filtering."""
        directory = Path(directory)
        if not directory.exists():
            return []
        
        files = []
        for file in directory.rglob("*"):
            if file.is_file():
                if extensions:
                    if file.suffix.lower() in [f".{ext}" for ext in extensions]:
                        files.append(file)
                else:
                    files.append(file)
        return files
    
    @staticmethod
    def get_file_size(path: str) -> int:
        """Get file size in bytes."""
        try:
            return Path(path).stat().st_size
        except Exception:
            return 0
    
    @staticmethod
    def read_file_content(path: str) -> str | None:
        """Read content of a text file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None
    
    @staticmethod
    def write_file_content(path: str, content: str) -> bool:
        """Write content to a file."""
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception:
            return False
    
    @staticmethod
    def copy_file(source: str, destination: str) -> bool:
        """Copy a file."""
        try:
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return True
        except Exception:
            return False
    
    @staticmethod
    def move_file(source: str, destination: str) -> bool:
        """Move a file."""
        try:
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, destination)
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete_file(path: str) -> bool:
        """Delete a file."""
        try:
            Path(path).unlink(missing_ok=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_filename_without_extension(path: str) -> str:
        """Get filename without extension."""
        return Path(path).stem
    
    @staticmethod
    def get_file_extension(path: str) -> str:
        """Get file extension."""
        return Path(path).suffix.lower()
    
    @staticmethod
    def change_extension(path: str, new_extension: str) -> str:
        """Change file extension."""
        return str(Path(path).with_suffix(new_extension))
    
    @staticmethod
    def generate_unique_filename(directory: str, prefix: str = "output", extension: str = ".png") -> Path:
        """Generate a unique filename in a directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        counter = 0
        while True:
            filename = f"{prefix}_{counter}{extension}"
            filepath = directory / filename
            if not filepath.exists():
                return filepath
            counter += 1
    
    @staticmethod
    def list_directory_contents(path: str, recursive: bool = False) -> list[Path]:
        """List contents of a directory."""
        path = Path(path)
        if not path.exists():
            return []
        
        if recursive:
            return list(path.rglob("*"))
        else:
            return list(path.iterdir())
