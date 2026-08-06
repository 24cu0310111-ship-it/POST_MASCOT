"""Logging utilities for the MAO system."""

import logging
import sys
from datetime import datetime
from pathlib import Path


class MAOFormatter(logging.Formatter):
    """Custom formatter for MAO logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        logger_name = record.name
        message = record.getMessage()
        
        # Color coding for different log levels
        if level == "ERROR":
            return f"[{timestamp}] [\033[91m{level}\033[0m] [{logger_name}] {message}"
        elif level == "WARNING":
            return f"[{timestamp}] [\033[93m{level}\033[0m] [{logger_name}] {message}"
        elif level == "INFO":
            return f"[{timestamp}] [\033[92m{level}\033[0m] [{logger_name}] {message}"
        elif level == "DEBUG":
            return f"[{timestamp}] [\033[94m{level}\033[0m] [{logger_name}] {message}"
        else:
            return f"[{timestamp}] [{level}] [{logger_name}] {message}"


def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    console: bool = True
) -> logging.Logger:
    """
    Set up logging for the MAO system.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional path to log file
        console: Whether to log to console
    
    Returns:
        Configured logger
    """
    logger = logging.getLogger("mao")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = MAOFormatter()
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        ))
        logger.addHandler(file_handler)
    
    return logger


# Global logger instance
logger = setup_logging(log_level="INFO", console=True)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(f"mao.{name}")
