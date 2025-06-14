#!/usr/bin/env python3
"""
CUEpoint - Main Application Entry Point
Optimized for macOS 13" displays
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QIcon, QPalette, QColor

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('cuepoint.log')
        ]
    )


def load_config() -> dict:
    """Load application configuration."""
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in config file: {e}")
        return {}


def setup_app_style(app: QApplication, config: dict) -> None:
    """Configure application styling for macOS."""
    # Enable high DPI scaling
    app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    
    # Set application properties
    app.setApplicationName(config.get('app', {}).get('name', 'CUEpoint'))
    app.setApplicationVersion(config.get('app', {}).get('version', '2.1.0'))
    app.setOrganizationName("CUEpoint Team")
    app.setOrganizationDomain("cuepoint.app")
    
    # Set application icon
    icon_path = Path(__file__).parent.parent / "assets" / "icons" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Apply dark theme if configured
    if config.get('ui', {}).get('theme') == 'dark':
        apply_dark_theme(app)


def apply_dark_theme(app: QApplication) -> None:
    """Apply dark theme styling."""
    palette = QPalette()
    
    # Window colors
    palette.setColor(QPalette.ColorRole.Window, QColor(26, 26, 26))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    
    # Base colors (input fields)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    
    # Text colors
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    
    # Button colors
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    
    # Highlight colors
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    
    app.setPalette(palette)


def check_system_requirements() -> bool:
    """Check if system meets minimum requirements."""
    import platform
    
    # Check macOS version
    if platform.system() != "Darwin":
        logging.warning("CUEpoint is optimized for macOS")
        return True  # Allow running on other platforms
    
    # Check macOS version (12.0+)
    version = platform.mac_ver()[0]
    if version:
        major, minor = map(int, version.split('.')[:2])
        if major < 12:
            logging.error(f"macOS 12.0+ required, found {version}")
            return False
    
    # Check Python version
    if sys.version_info < (3, 11):
        logging.error(f"Python 3.11+ required, found {sys.version}")
        return False
    
    return True


def main() -> int:
    """Main application entry point."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting CUEpoint v2.1.0")
    
    # Check system requirements
    if not check_system_requirements():
        logger.error("System requirements not met")
        return 1
    
    # Load configuration
    config = load_config()
    if not config:
        logger.error("Failed to load configuration")
        return 1
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Setup application styling
    setup_app_style(app, config)
    
    # Create and show main window
    try:
        main_window = MainWindow(config)
        main_window.show()
        
        logger.info("Application started successfully")
        return app.exec()
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
