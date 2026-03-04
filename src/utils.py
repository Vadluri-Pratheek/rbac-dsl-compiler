"""
Utility functions for RBAC DSL Compiler
"""
import logging

logger = logging.getLogger('rbac_compiler')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(handler)

logger.setLevel(logging.INFO)


def error(message):
    """Log an error message"""
    logger.error(message)


def warning(message):
    """Log a warning message"""
    logger.warning(message)


def info(message):
    """Log an info message"""
    logger.info(message)


def debug(message):
    """Log a debug message"""
    logger.debug(message)


__all__ = ['logger', 'error', 'warning', 'info', 'debug']
