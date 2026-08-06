"""Configuration management for the Multi-Agent Orchestrator (MAO) system."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Phase1Config:
    """Configuration for Phase 1 (Input Analyzer)."""
    context_threshold: float = 0.7
    required_fields: list[str] = field(default_factory=lambda: [
        "subject",
        "intent"
    ])
    optional_fields: list[str] = field(default_factory=lambda: [
        "style",
        "constraints",
        "references"
    ])
    max_clarification_questions: int = 3


@dataclass
class Phase2Config:
    """Configuration for Phase 2 (Creator Agent)."""
    default_backend: str = "mcp"
    max_retries: int = 3
    timeout_seconds: int = 300
    preferred_backends: list[str] = field(default_factory=lambda: [
        "mcp",
        "cli",
        "web_api"
    ])
    # Backend-specific configurations
    backend_configs: dict[str, dict] = field(default_factory=dict)
    # Cost tracking
    track_costs: bool = True
    max_cost_per_generation: float = 10.0  # USD


@dataclass
class Phase3Config:
    """Configuration for Phase 3 (Quality Checker)."""
    # ML Validators (Tier 1)
    enable_ml_validators: bool = True
    ml_checks: list[str] = field(default_factory=lambda: [
        "prompt_alignment",
        "artifact_detection",
        "technical_quality",
        "composition"
    ])
    # AI Validators (Tier 2)
    enable_ai_validators: bool = True
    ai_model: str = "omniroute:free-fast vision auto"
    ai_checks: list[str] = field(default_factory=lambda: [
        "ai_quality"
    ])
    # Quality thresholds
    pass_threshold: float = 0.7
    inconclusive_threshold: float = 0.5
    # Refinement
    max_iterations: int = 3
    auto_refine: bool = True


@dataclass
class OrchestratorConfig:
    """Main configuration for the MAO system."""
    phase1: Phase1Config = field(default_factory=Phase1Config)
    phase2: Phase2Config = field(default_factory=Phase2Config)
    phase3: Phase3Config = field(default_factory=Phase3Config)
    # General settings
    output_dir: str = "./output"
    log_level: str = "INFO"
    debug: bool = False
    # Storage
    storage_dir: str = "./storage"
    keep_intermediate_files: bool = True
    # API keys (loaded from environment)
    api_keys: dict[str, str] = field(default_factory=dict)


class ConfigManager:
    """Manages configuration loading and saving."""
    
    DEFAULT_CONFIG = {
        "phase1": {
            "context_threshold": 0.7,
            "required_fields": ["subject", "intent"],
            "optional_fields": ["style", "constraints", "references"],
            "max_clarification_questions": 3
        },
        "phase2": {
            "default_backend": "mcp",
            "max_retries": 3,
            "timeout_seconds": 300,
            "preferred_backends": ["mcp", "cli", "web_api"],
            "track_costs": True,
            "max_cost_per_generation": 10.0
        },
        "phase3": {
            "enable_ml_validators": True,
            "ml_checks": ["prompt_alignment", "artifact_detection", "technical_quality", "composition"],
            "enable_ai_validators": True,
            "ai_model": "omniroute:free-fast vision auto",
            "ai_checks": ["ai_quality"],
            "pass_threshold": 0.7,
            "inconclusive_threshold": 0.5,
            "max_iterations": 3,
            "auto_refine": True
        },
        "output_dir": "./output",
        "log_level": "INFO",
        "debug": False,
        "storage_dir": "./storage",
        "keep_intermediate_files": True
    }
    
    def __init__(self, config_path: str | None = None):
        self.config_path = config_path or self._find_config_path()
        self.config: OrchestratorConfig = OrchestratorConfig()
        self._load_config()
        self._load_api_keys()
    
    def _find_config_path(self) -> str:
        """Find configuration file in standard locations."""
        possible_paths = [
            "./config.yaml",
            "./config.yml",
            "./config.json",
            "~/mao_config.yaml",
            "/etc/mao/config.yaml"
        ]
        for path in possible_paths:
            if Path(path).expanduser().exists():
                return path
        return "./config.yaml"
    
    def _load_config(self):
        """Load configuration from file."""
        config_file = Path(self.config_path).expanduser()
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    if config_file.suffix in ['.yaml', '.yml']:
                        data = yaml.safe_load(f)
                    elif config_file.suffix == '.json':
                        data = json.load(f)
                    else:
                        data = yaml.safe_load(f)
                
                self._update_config(data)
            except Exception as e:
                print(f"Warning: Could not load config from {config_file}: {e}")
                # Use defaults
                self.config = OrchestratorConfig()
        else:
            # Create default config file
            self._save_config(self.DEFAULT_CONFIG)
            self._update_config(self.DEFAULT_CONFIG)
    
    def _update_config(self, data: dict):
        """Update configuration from dictionary."""
        if 'phase1' in data:
            phase1_data = data['phase1']
            self.config.phase1 = Phase1Config(
                context_threshold=phase1_data.get('context_threshold', 0.7),
                required_fields=phase1_data.get('required_fields', ['subject', 'intent']),
                optional_fields=phase1_data.get('optional_fields', ['style', 'constraints', 'references']),
                max_clarification_questions=phase1_data.get('max_clarification_questions', 3)
            )
        
        if 'phase2' in data:
            phase2_data = data['phase2']
            self.config.phase2 = Phase2Config(
                default_backend=phase2_data.get('default_backend', 'mcp'),
                max_retries=phase2_data.get('max_retries', 3),
                timeout_seconds=phase2_data.get('timeout_seconds', 300),
                preferred_backends=phase2_data.get('preferred_backends', ['mcp', 'cli', 'web_api']),
                backend_configs=phase2_data.get('backend_configs', {}),
                track_costs=phase2_data.get('track_costs', True),
                max_cost_per_generation=phase2_data.get('max_cost_per_generation', 10.0)
            )
        
        if 'phase3' in data:
            phase3_data = data['phase3']
            self.config.phase3 = Phase3Config(
                enable_ml_validators=phase3_data.get('enable_ml_validators', True),
                ml_checks=phase3_data.get('ml_checks', ['prompt_alignment', 'artifact_detection', 'technical_quality', 'composition']),
                enable_ai_validators=phase3_data.get('enable_ai_validators', True),
                ai_model=phase3_data.get('ai_model', 'omniroute:free-fast vision auto'),
                ai_checks=phase3_data.get('ai_checks', ['ai_quality']),
                pass_threshold=phase3_data.get('pass_threshold', 0.7),
                inconclusive_threshold=phase3_data.get('inconclusive_threshold', 0.5),
                max_iterations=phase3_data.get('max_iterations', 3),
                auto_refine=phase3_data.get('auto_refine', True)
            )
        
        self.config.output_dir = data.get('output_dir', './output')
        self.config.log_level = data.get('log_level', 'INFO')
        self.config.debug = data.get('debug', False)
        self.config.storage_dir = data.get('storage_dir', './storage')
        self.config.keep_intermediate_files = data.get('keep_intermediate_files', True)
    
    def _load_api_keys(self):
        """Load API keys from environment variables."""
        # Load from .env file if it exists
        env_file = Path('.env').expanduser()
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self.config.api_keys[key.strip()] = value.strip().strip('"\'')
            except Exception as e:
                print(f"Warning: Could not load API keys from .env: {e}")
        
        # Also load from environment
        for key, value in os.environ.items():
            if key.startswith('MAO_') or key in ['OPENCODE_API_KEY', 'ORSHOT_API_KEY', 'MCP_URL', 'VECTORIZER_API_ID', 'VECTORIZER_API_SECRET']:
                self.config.api_keys[key] = value
    
    def _save_config(self, data: dict):
        """Save configuration to file."""
        config_file = Path(self.config_path).expanduser()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def save_config(self):
        """Save current configuration to file."""
        data = {
            "phase1": {
                "context_threshold": self.config.phase1.context_threshold,
                "required_fields": self.config.phase1.required_fields,
                "optional_fields": self.config.phase1.optional_fields,
                "max_clarification_questions": self.config.phase1.max_clarification_questions
            },
            "phase2": {
                "default_backend": self.config.phase2.default_backend,
                "max_retries": self.config.phase2.max_retries,
                "timeout_seconds": self.config.phase2.timeout_seconds,
                "preferred_backends": self.config.phase2.preferred_backends,
                "backend_configs": self.config.phase2.backend_configs,
                "track_costs": self.config.phase2.track_costs,
                "max_cost_per_generation": self.config.phase2.max_cost_per_generation
            },
            "phase3": {
                "enable_ml_validators": self.config.phase3.enable_ml_validators,
                "ml_checks": self.config.phase3.ml_checks,
                "enable_ai_validators": self.config.phase3.enable_ai_validators,
                "ai_model": self.config.phase3.ai_model,
                "ai_checks": self.config.phase3.ai_checks,
                "pass_threshold": self.config.phase3.pass_threshold,
                "inconclusive_threshold": self.config.phase3.inconclusive_threshold,
                "max_iterations": self.config.phase3.max_iterations,
                "auto_refine": self.config.phase3.auto_refine
            },
            "output_dir": self.config.output_dir,
            "log_level": self.config.log_level,
            "debug": self.config.debug,
            "storage_dir": self.config.storage_dir,
            "keep_intermediate_files": self.config.keep_intermediate_files
        }
        self._save_config(data)
    
    def get_config(self) -> OrchestratorConfig:
        """Get the current configuration."""
        return self.config
    
    def get_api_key(self, service: str) -> str | None:
        """Get API key for a service."""
        # Try different key naming conventions
        possible_keys = [
            f"{service}_API_KEY",
            f"API_KEY_{service}",
            service.upper(),
            service
        ]
        for key in possible_keys:
            if key in self.config.api_keys:
                return self.config.api_keys[key]
        return None


# Global configuration instance
config_manager = ConfigManager()
config = config_manager.get_config()
