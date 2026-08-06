"""CLI Backend - Uses command-line tools for image generation."""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from models.generation_models import BackendType, GenerationResult, GenerationStatus
from models.input_models import AnalyzedInput
from utils.logger import get_logger

from .base_backend import BackendHealth, BaseBackend

logger = get_logger("backends.cli")


@dataclass
class CLIBackend(BaseBackend):
    """
    CLI Backend - Uses command-line tools for image generation.
    
    Supports tools like:
    - Stable Diffusion CLI
    - ComfyUI
    - Other CLI-based generation tools
    """
    
    cli_command: str = "python scripts/txt2img.py"
    cli_args: list[str] = field(default_factory=list)
    
    @property
    def name(self) -> str:
        return "cli"
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.CLI_TOOL
    
    @property
    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_image_generation": True,
            "supports_image_editing": True,
            "supports_style_transfer": True,
            "supports_upscaling": True,
            "supports_variations": True,
            "max_resolution": "4096x4096",
            "formats": ["png", "jpg", "webp"],
            "needs_api_key": False,
            "requires_local_install": True
        }
    
    def __init__(self):
        super().__init__()
        self._detect_cli_tools()
    
    def _detect_cli_tools(self):
        """Detect available CLI tools."""
        tools = [
            ("Stable Diffusion", ["python", "scripts/txt2img.py"]),
            ("Stable Diffusion XL", ["python", "scripts/sdxl.py"]),
            ("ComfyUI", ["python", "main.py"]),
            ("InvokeAI", ["invoke"]),
            ("Automatic1111", ["python", "launch.py"])
        ]
        
        available_tools = []
        for tool_name, command in tools:
            try:
                # Check if command exists
                result = subprocess.run(
                    ["which"] + command,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    available_tools.append((tool_name, command))
            except Exception:
                pass
        
        logger.info(f"Available CLI tools: {[name for name, _ in available_tools]}")
        
        if available_tools:
            # Use the first available tool
            self.cli_command = available_tools[0][1][0]
            self.cli_args = available_tools[0][1][1:]
    
    async def initialize(self) -> bool:
        """Initialize the CLI backend."""
        try:
            await self.health_check()
            return True
        except Exception as e:
            logger.error(f"CLI backend initialization failed: {e}")
            return False
    
    async def generate(
        self,
        prompt: str,
        analyzed: AnalyzedInput = None,
        refinement: GenerationResult = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate an image using CLI tool.
        
        Args:
            prompt: The text prompt
            analyzed: Optional AnalyzedInput for additional context
            refinement: Optional previous GenerationResult for refinement
            **kwargs: Additional parameters (width, height, steps, etc.)
        
        Returns:
            GenerationResult with the generated image
        """
        import time
        start_time = time.time()
        
        output_path = self._create_output_path(prompt, ".png")
        
        try:
            # Build CLI command
            command = self._build_cli_command(prompt, output_path, kwargs)
            
            if not command:
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error="No CLI tool available",
                    prompt_used=prompt
                )
            
            logger.info(f"Running CLI command: {' '.join(command)}")
            
            # Run the command
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                timeout_val = getattr(self, 'timeout', 300)
                stdout, stderr = process.communicate(timeout=timeout_val)
                
                if process.returncode != 0:
                    logger.error(f"CLI command failed: {stderr}")
                    return GenerationResult(
                        status=GenerationStatus.FAILED,
                        error=f"CLI error: {stderr}",
                        prompt_used=prompt
                    )
                
                # Check if output file was created
                if not output_path.exists():
                    # Try to find output file
                    possible_outputs = list(Path.cwd().glob("*.png")) + \
                                   list(Path.cwd().glob("*.jpg"))
                    if possible_outputs:
                        # Use the most recent file
                        output_path = sorted(possible_outputs, key=lambda p: p.stat().st_mtime)[-1]
                
                if output_path.exists():
                    generation_time_ms = int((time.time() - start_time) * 1000)
                    
                    return GenerationResult(
                        image_path=str(output_path),
                        backend_used=self.name,
                        model_version="stable-diffusion",
                        generation_params={
                            "prompt": prompt,
                            "command": ' '.join(command)
                        },
                        generation_time_ms=generation_time_ms,
                        cost_estimate=0.0,  # Local generation has no cost
                        prompt_used=prompt,
                        status=GenerationStatus.COMPLETED,
                        metadata={
                            "cli_tool": self.cli_command
                        }
                    )
                else:
                    return GenerationResult(
                        status=GenerationStatus.FAILED,
                        error="No output file generated",
                        prompt_used=prompt
                    )
                    
            except subprocess.TimeoutExpired:
                process.kill()
                return GenerationResult(
                    status=GenerationStatus.FAILED,
                    error="CLI command timed out",
                    prompt_used=prompt
                )
            
        except Exception as e:
            logger.error(f"CLI generation error: {e}")
            return GenerationResult(
                status=GenerationStatus.FAILED,
                error=str(e),
                prompt_used=prompt
            )
    
    def _build_cli_command(
        self,
        prompt: str,
        output_path: Path,
        kwargs: dict
    ) -> list[str] | None:
        """Build the CLI command for image generation."""
        
        # For Stable Diffusion CLI
        if "txt2img.py" in self.cli_command or "sdxl.py" in self.cli_command:
            return self._build_sd_command(prompt, output_path, kwargs)
        
        # For ComfyUI
        if "main.py" in self.cli_command:
            return self._build_comfyui_command(prompt, output_path, kwargs)
        
        return None
    
    def _build_sd_command(
        self,
        prompt: str,
        output_path: Path,
        kwargs: dict
    ) -> list[str]:
        """Build command for Stable Diffusion CLI."""
        command = [self.cli_command] + self.cli_args
        
        # Add prompt
        command.extend(["--prompt", prompt])
        
        # Add output path
        command.extend(["--outdir", str(output_path.parent)])
        command.extend(["--output", str(output_path.name)])
        
        # Add parameters
        width = kwargs.get("width", 512)
        height = kwargs.get("height", 512)
        steps = kwargs.get("steps", 50)
        cfg_scale = kwargs.get("cfg_scale", 7.0)
        seed = kwargs.get("seed", -1)
        
        command.extend([
            "--width", str(width),
            "--height", str(height),
            "--steps", str(steps),
            "--cfg_scale", str(cfg_scale),
            "--seed", str(seed)
        ])
        
        return command
    
    def _build_comfyui_command(
        self,
        prompt: str,
        output_path: Path,
        kwargs: dict
    ) -> list[str]:
        """Build command for ComfyUI."""
        # ComfyUI uses a different approach - JSON input
        # For now, return a simple command
        return [
            self.cli_command,
            "--input", str(output_path.parent / "input.json"),
            "--output", str(output_path.parent)
        ]
    
    async def health_check(self) -> BackendHealth:
        """Check if CLI tools are available."""
        try:
            if not self.cli_command:
                return BackendHealth.UNHEALTHY
            
            # Check if the command exists
            result = subprocess.run(
                ["which", self.cli_command],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return BackendHealth.HEALTHY
            else:
                return BackendHealth.UNHEALTHY
                
        except Exception as e:
            logger.error(f"CLI health check error: {e}")
            return BackendHealth.UNHEALTHY
    
    def _estimate_cost(self, width: int = 1024, height: int = 1024) -> float:
        """Estimate cost for CLI generation."""
        # Local generation has no monetary cost
        return 0.0
