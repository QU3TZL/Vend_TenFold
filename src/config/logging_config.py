import os
import logging.config
from datetime import datetime

def setup_logging():
    """Configure logging for the application"""
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"app_{timestamp}.log")

    # Logging configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            },
            "detailed": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(filename)s:%(lineno)d"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "default",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": log_file,
                "mode": "a"
            }
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": True
            }
        }
    }

    # Apply the configuration
    logging.config.dictConfig(config)
    
    # Log startup message
    logging.info(f"Logging configured. Log file: {log_file}") 