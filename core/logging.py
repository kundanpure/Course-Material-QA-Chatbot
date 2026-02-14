"""
Simple logging configuration for production RAG system
"""
import logging
import sys
from typing import Optional

# Create logger
logger = logging.getLogger("rag_system")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)

# Add handler
if not logger.handlers:
    logger.addHandler(console_handler)


def setup_logging(level: Optional[str] = None):
    """Setup logging configuration"""
    if level:
        logger.setLevel(getattr(logging, level.upper()))
    logger.info("Logging configured")
