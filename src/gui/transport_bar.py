"""
Transport Bar Widget
Playback controls and position display
"""

import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider, QLabel
from PyQt6.QtCore import Qt


class TransportBar(QWidget):
    """
    Transport controls for audio playback.
    Includes play/pause, position slider, and time display.
    """
    
    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self._setup_ui()
        self.logger.info("TransportBar created")
    
    def _setup_ui(self) -> None:
        """Setup transport bar UI."""
        layout = QHBoxLayout(self)
        
        # Play/Pause button
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(40, 30)
        layout.addWidget(self.play_button)
        
        # Position slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        layout.addWidget(self.position_slider)
        
        # Time display
        self.time_label = QLabel("0:00 / 0:00")
        layout.addWidget(self.time_label)
        
        # Set fixed height
        transport_height = self.config.get('ui', {}).get('transport_height', 60)
        self.setFixedHeight(transport_height)
