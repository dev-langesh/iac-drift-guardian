import logging
import sys
import click

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""
    COLORS = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bright_red',
    }

    def format(self, record):
        level_name = record.levelname
        msg = record.getMessage()
        color = self.COLORS.get(level_name, 'white')
        
        # log type - message
        level_text = click.style(level_name, fg=color, bold=True)
        return f"{level_text} - {msg}"

def setup_logger(name: str = "iac-drift-guardian", level: int = logging.INFO):
    """Sets up a structured logger for the application."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)

    return logger

logger = setup_logger()
