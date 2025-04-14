import logging
import os
from datetime import datetime

def setup_logger(name: str = "SimpleBankingSystem", level=logging.INFO):
    """Setup and configure a single logger for the entire system"""
    logger = logging.getLogger(name)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(level)
    
    # Create formatter
    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # TODO: Implement file logging functionality
    
    return logger

logger = setup_logger() 