"""
Enhanced Navigation Controls - Advanced zoom and navigation for Phase 3
Includes mini-map, zoom controls, and smart navigation features
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, Tuple, List

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QSlider, QPushButton, QFrame, QSpinBox,
                            QComboBox, QCheckBox, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPainter, QPen, QBrush, QColor

import pyqtgraph as pg

from ..core.audio_loader import AudioData


class MiniMapWidget(QWidget):
    """Mini-map widget showing full track overview with current view indicator."""
    
    # Signals
    view_changed = pyqtSignal(float, float)  # start_time, end_time
    position_clicked = pyqtSignal(float)     # clicked_time
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        
        # Data
        self.audio_data: Optional[AudioData] = None
        self.waveform_overview: Optional[np.ndarray] = None
        self.current_view_start = 0.0
        self.current_view_end = 0.0
        self.track_duration = 0.0
        
        # Visual settings
        self.setFixedHeight(80)
        self.setMinimumWidth(200)
        
        # Colors
        self.waveform_color = QColor(100, 150, 255)
        self.view_indicator_color = QColor(255, 255, 255, 100)
        self.background_color = QColor(30, 30, 30)
        
        # Interaction
        self.dragging = False
        self.drag_start_x = 0
        
        self.logger.debug("MiniMapWidget initialized")
    
    def set_audio_data(self, audio_data: AudioData) -> None:
        """Set audio data and generate overview waveform."""
        self.audio_data = audio_data
        self.track_duration = audio_data.duration
        
        # Generate overview waveform (downsampled)
        self._generate_overview_waveform()
        self.update()
    
    def _generate_overview_waveform(self) -> None:
        """Generate downsampled waveform for overview."""
        if not self.audio_data:
            return
        
        # Use mono audio for overview
        if self.audio_data.channels > 1:
            mono_audio = np.mean(self.audio_data.data, axis=0)
        else:
            mono_audio = self.audio_data.data[0]
        
        # Downsample to fit widget width
        target_samples = self.width() * 2  # 2 samples per pixel
        if len(mono_audio) > target_samples:
            # Downsample by taking RMS of chunks
            chunk_size = len(mono_audio) // target_samples
            chunks = mono_audio[:target_samples * chunk_size].reshape(-1, chunk_size)
            self.waveform_overview = np.sqrt(np.mean(chunks**2, axis=1))
        else:
            self.waveform_overview = np.abs(mono_audio)
        
        # Normalize
        if np.max(self.waveform_overview) > 0:
            self.waveform_overview = self.waveform_overview / np.max(self.waveform_overview)
    
    def set_view_range(self, start_time: float, end_time: float) -> None:
        """Set current view range indicator."""
        self.current_view_start = start_time
        self.current_view_end = end_time
        self.update()
    
    def paintEvent(self, event) -> None:
        """Paint the mini-map."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), self.background_color)
        
        if self.waveform_overview is None or self.track_duration == 0:
            painter.setPen(QPen(QColor(100, 100, 100)))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No audio loaded")
            return
        
        # Draw waveform overview
        self._draw_waveform_overview(painter)
        
        # Draw view indicator
        self._draw_view_indicator(painter)
        
        # Draw time markers
        self._draw_time_markers(painter)
    
    def _draw_waveform_overview(self, painter: QPainter) -> None:
        """Draw the overview waveform."""
        if self.waveform_overview is None:
            return
        
        width = self.width()
        height = self.height()
        center_y = height // 2
        
        painter.setPen(QPen(self.waveform_color, 1))
        painter.setBrush(QBrush(self.waveform_color))
        
        # Draw waveform as filled polygon
        points = []
        for i, amplitude in enumerate(self.waveform_overview):
            x = int(i * width / len(self.waveform_overview))
            y_top = int(center_y - amplitude * center_y * 0.8)
            y_bottom = int(center_y + amplitude * center_y * 0.8)
            
            if i == 0:
                points.append((x, center_y))
            
            points.append((x, y_top))
        
        # Add bottom points in reverse
        for i in reversed(range(len(self.waveform_overview))):
            x = int(i * width / len(self.waveform_overview))
            amplitude = self.waveform_overview[i]
            y_bottom = int(center_y + amplitude * center_y * 0.8)
            points.append((x, y_bottom))
        
        # Draw polygon
        if len(points) > 2:
            from PyQt6.QtGui import QPolygon
            from PyQt6.QtCore import QPoint
            
            polygon = QPolygon([QPoint(int(x), int(y)) for x, y in points])
            painter.drawPolygon(polygon)
    
    def _draw_view_indicator(self, painter: QPainter) -> None:
        """Draw current view range indicator."""
        if self.track_duration == 0:
            return
        
        width = self.width()
        height = self.height()
        
        # Calculate view indicator position
        start_x = int(self.current_view_start / self.track_duration * width)
        end_x = int(self.current_view_end / self.track_duration * width)
        
        # Draw view indicator rectangle
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(self.view_indicator_color))
        painter.drawRect(start_x, 0, end_x - start_x, height)
    
    def _draw_time_markers(self, painter: QPainter) -> None:
        """Draw time markers."""
        if self.track_duration == 0:
            return
        
        width = self.width()
        height = self.height()
        
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.setFont(QFont("Arial", 8))
        
        # Draw markers every 30 seconds
        marker_interval = 30.0  # seconds
        num_markers = int(self.track_duration / marker_interval)
        
        for i in range(num_markers + 1):
            time_pos = i * marker_interval
            x = int(time_pos / self.track_duration * width)
            
            # Draw marker line
            painter.drawLine(x, height - 10, x, height)
            
            # Draw time label
            minutes = int(time_pos // 60)
            seconds = int(time_pos % 60)
            time_text = f"{minutes}:{seconds:02d}"
            painter.drawText(x - 15, height - 12, time_text)
    
    def mousePressEvent(self, event) -> None:
        """Handle mouse press for navigation."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_x = event.position().x()
            
            # Calculate clicked time
            clicked_time = event.position().x() / self.width() * self.track_duration
            self.position_clicked.emit(clicked_time)
    
    def mouseMoveEvent(self, event) -> None:
        """Handle mouse drag for view adjustment."""
        if self.dragging and self.track_duration > 0:
            # Calculate new view range based on drag
            current_view_width = self.current_view_end - self.current_view_start
            
            # Calculate time offset
            pixel_offset = event.position().x() - self.drag_start_x
            time_offset = pixel_offset / self.width() * self.track_duration
            
            # Update view range
            new_start = max(0, self.current_view_start + time_offset)
            new_end = min(self.track_duration, new_start + current_view_width)
            
            # Adjust start if end hits boundary
            if new_end == self.track_duration:
                new_start = max(0, new_end - current_view_width)
            
            self.view_changed.emit(new_start, new_end)
            self.drag_start_x = event.position().x()
    
    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release."""
        self.dragging = False


class ZoomControls(QWidget):
    """Advanced zoom controls with presets and smart zoom features."""
    
    # Signals
    zoom_changed = pyqtSignal(float)  # zoom_level
    zoom_to_selection = pyqtSignal()
    zoom_to_cue_range = pyqtSignal(int, int)  # start_cue_id, end_cue_id
    
    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Zoom settings
        self.min_zoom = config.get('waveform', {}).get('min_zoom', 0.1)
        self.max_zoom = config.get('waveform', {}).get('max_zoom', 100.0)
        self.zoom_step = config.get('waveform', {}).get('zoom_step', 1.5)
        
        # Current state
        self.current_zoom = 1.0
        
        self._setup_ui()
        self.logger.debug("ZoomControls initialized")
    
    def _setup_ui(self) -> None:
        """Setup zoom controls UI."""
        layout = QVBoxLayout(self)
        
        # Zoom level group
        zoom_group = QGroupBox("Zoom Level")
        zoom_layout = QVBoxLayout(zoom_group)
        
        # Zoom slider
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(int(np.log10(self.min_zoom) * 10))
        self.zoom_slider.setMaximum(int(np.log10(self.max_zoom) * 10))
        self.zoom_slider.setValue(0)  # 1.0x zoom
        self.zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        zoom_layout.addWidget(self.zoom_slider)
        
        # Zoom level display
        self.zoom_label = QLabel("1.0x")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_layout.addWidget(self.zoom_label)
        
        # Zoom buttons
        zoom_buttons_layout = QHBoxLayout()
        
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_in_button.clicked.connect(self._zoom_in)
        zoom_buttons_layout.addWidget(self.zoom_in_button)
        
        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_out_button.clicked.connect(self._zoom_out)
        zoom_buttons_layout.addWidget(self.zoom_out_button)
        
        self.zoom_fit_button = QPushButton("Fit All")
        self.zoom_fit_button.clicked.connect(self._zoom_fit)
        zoom_buttons_layout.addWidget(self.zoom_fit_button)
        
        zoom_layout.addLayout(zoom_buttons_layout)
        layout.addWidget(zoom_group)
        
        # Smart zoom group
        smart_zoom_group = QGroupBox("Smart Zoom")
        smart_zoom_layout = QVBoxLayout(smart_zoom_group)
        
        # Zoom presets
        presets_layout = QHBoxLayout()
        
        self.zoom_preset_combo = QComboBox()
        self.zoom_preset_combo.addItems([
            "Overview (0.1x)",
            "Wide (0.5x)", 
            "Normal (1x)",
            "Detail (2x)",
            "Fine (5x)",
            "Ultra (10x)"
        ])
        self.zoom_preset_combo.currentTextChanged.connect(self._on_preset_changed)
        presets_layout.addWidget(QLabel("Preset:"))
        presets_layout.addWidget(self.zoom_preset_combo)
        
        smart_zoom_layout.addLayout(presets_layout)
        
        # Smart zoom features
        self.auto_zoom_checkbox = QCheckBox("Auto-zoom to cues")
        smart_zoom_layout.addWidget(self.auto_zoom_checkbox)
        
        self.follow_playback_checkbox = QCheckBox("Follow playback")
        smart_zoom_layout.addWidget(self.follow_playback_checkbox)
        
        layout.addWidget(smart_zoom_group)
    
    def _on_zoom_slider_changed(self, value: int) -> None:
        """Handle zoom slider change."""
        # Convert slider value to zoom level (logarithmic scale)
        zoom_level = 10 ** (value / 10.0)
        self._set_zoom_level(zoom_level)
    
    def _set_zoom_level(self, zoom_level: float) -> None:
        """Set zoom level and update UI."""
        self.current_zoom = max(self.min_zoom, min(self.max_zoom, zoom_level))
        
        # Update label
        self.zoom_label.setText(f"{self.current_zoom:.1f}x")
        
        # Update slider (without triggering signal)
        self.zoom_slider.blockSignals(True)
        slider_value = int(np.log10(self.current_zoom) * 10)
        self.zoom_slider.setValue(slider_value)
        self.zoom_slider.blockSignals(False)
        
        # Emit signal
        self.zoom_changed.emit(self.current_zoom)
    
    def _zoom_in(self) -> None:
        """Zoom in by zoom step."""
        new_zoom = self.current_zoom * self.zoom_step
        self._set_zoom_level(new_zoom)
    
    def _zoom_out(self) -> None:
        """Zoom out by zoom step."""
        new_zoom = self.current_zoom / self.zoom_step
        self._set_zoom_level(new_zoom)
    
    def _zoom_fit(self) -> None:
        """Zoom to fit entire track."""
        self._set_zoom_level(0.1)  # Overview zoom
    
    def _on_preset_changed(self, preset_text: str) -> None:
        """Handle zoom preset selection."""
        preset_map = {
            "Overview (0.1x)": 0.1,
            "Wide (0.5x)": 0.5,
            "Normal (1x)": 1.0,
            "Detail (2x)": 2.0,
            "Fine (5x)": 5.0,
            "Ultra (10x)": 10.0
        }
        
        if preset_text in preset_map:
            self._set_zoom_level(preset_map[preset_text])
    
    def get_zoom_level(self) -> float:
        """Get current zoom level."""
        return self.current_zoom
    
    def set_zoom_level(self, zoom_level: float) -> None:
        """Set zoom level externally."""
        self._set_zoom_level(zoom_level)


class NavigationControls(QWidget):
    """Complete navigation controls combining mini-map and zoom controls."""
    
    # Signals
    view_changed = pyqtSignal(float, float)  # start_time, end_time
    zoom_changed = pyqtSignal(float)         # zoom_level
    position_changed = pyqtSignal(float)     # position
    
    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        self._setup_ui()
        self._connect_signals()
        
        self.logger.info("NavigationControls initialized")
    
    def _setup_ui(self) -> None:
        """Setup navigation controls UI."""
        layout = QVBoxLayout(self)
        
        # Mini-map
        minimap_group = QGroupBox("Track Overview")
        minimap_layout = QVBoxLayout(minimap_group)
        
        self.mini_map = MiniMapWidget()
        minimap_layout.addWidget(self.mini_map)
        
        layout.addWidget(minimap_group)
        
        # Zoom controls
        self.zoom_controls = ZoomControls(self.config)
        layout.addWidget(self.zoom_controls)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Mini-map signals
        self.mini_map.view_changed.connect(self.view_changed.emit)
        self.mini_map.position_clicked.connect(self.position_changed.emit)
        
        # Zoom control signals
        self.zoom_controls.zoom_changed.connect(self.zoom_changed.emit)
    
    def set_audio_data(self, audio_data: AudioData) -> None:
        """Set audio data for navigation."""
        self.mini_map.set_audio_data(audio_data)
    
    def set_view_range(self, start_time: float, end_time: float) -> None:
        """Update view range indicator."""
        self.mini_map.set_view_range(start_time, end_time)
    
    def set_zoom_level(self, zoom_level: float) -> None:
        """Set zoom level."""
        self.zoom_controls.set_zoom_level(zoom_level)
    
    def get_zoom_level(self) -> float:
        """Get current zoom level."""
        return self.zoom_controls.get_zoom_level()
