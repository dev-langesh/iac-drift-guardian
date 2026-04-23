import logging
import sys
import click

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""
    COLORS = {
        'DEBUG': 'bright_black',
        'INFO': 'bright_blue',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bright_red',
    }
    
    ICONS = {
        'INFO': 'ℹ',
        'WARNING': '⚠',
        'ERROR': '✖',
        'CRITICAL': '❗',
        'SUCCESS': '✔'
    }

    def format(self, record):
        level_name = record.levelname
        msg = record.getMessage()
        color = self.COLORS.get(level_name, 'white')
        icon = self.ICONS.get(level_name, ' ')
        
        # Professional format: ICON TYPE - message
        level_text = click.style(f"{icon} {level_name:<7}", fg=color, bold=True)
        return f"\n{level_text} | {msg}"

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

def print_banner():
    """Prints a professional CLI banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════╗
    ║                 IaC DRIFT GUARDIAN v1.0                  ║
    ║        Protecting your Infrastructure from Drift         ║
    ╚══════════════════════════════════════════════════════════╝
    """
    click.echo(click.style(banner, fg='bright_cyan', bold=True))
