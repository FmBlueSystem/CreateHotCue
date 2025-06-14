"""
Transport Bar Widget - Professional DJ Playback Controls
Complete transport controls with play/pause, seeking, volume, and time display
"""

import logging
from typing import Dict, Any, Optional

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QSlider,
                            QLabel, QVBoxLayout, QGroupBox, QComboBox,
                            QSpinBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ..playback.audio_engine import AudioEngine, PlaybackState


class TransportBar(QWidget):
    """
    Professional transport controls for audio playback.
    Includes play/pause, seeking, volume, speed, and device selection.
    """

    # Signals
    play_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    seek_requested = pyqtSignal(float)  # position in seconds
    volume_changed = pyqtSignal(float)  # volume 0.0-1.0
    speed_changed = pyqtSignal(float)   # speed 0.5-2.0
    device_changed = pyqtSignal(int)    # device ID

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.config = config
        self.logger = logging.getLogger(__name__)

        # State
        self.audio_engine: Optional[AudioEngine] = None
        self.current_duration = 0.0
        self.current_position = 0.0
        self.is_seeking = False
        self.playback_state = PlaybackState.STOPPED

        # UI update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(100)  # Update every 100ms

        self._setup_ui()
        self._connect_signals()

        self.logger.info("TransportBar created")

    def _setup_ui(self) -> None:
        """Setup transport bar UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Main transport controls
        transport_layout = QHBoxLayout()

        # Playback buttons
        self._setup_playback_buttons(transport_layout)

        # Position slider and time display
        self._setup_position_controls(transport_layout)

        # Volume and speed controls
        self._setup_audio_controls(transport_layout)

        main_layout.addLayout(transport_layout)

        # Audio device selection
        self._setup_device_controls(main_layout)

        # Set fixed height
        transport_height = self.config.get('ui', {}).get('transport_height', 80)
        self.setFixedHeight(transport_height)

    def _setup_playback_buttons(self, layout: QHBoxLayout) -> None:
        """Setup playback control buttons."""
        # Stop button
        self.stop_button = QPushButton("⏹")
        self.stop_button.setFixedSize(35, 35)
        self.stop_button.setToolTip("Stop (Space)")
        layout.addWidget(self.stop_button)

        # Play/Pause button
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(45, 35)
        self.play_button.setToolTip("Play/Pause (Space)")
        layout.addWidget(self.play_button)

        # Skip buttons
        self.prev_button = QPushButton("⏮")
        self.prev_button.setFixedSize(30, 35)
        self.prev_button.setToolTip("Previous Cue (Cmd+Left)")
        layout.addWidget(self.prev_button)

        self.next_button = QPushButton("⏭")
        self.next_button.setFixedSize(30, 35)
        self.next_button.setToolTip("Next Cue (Cmd+Right)")
        layout.addWidget(self.next_button)

    def _setup_position_controls(self, layout: QHBoxLayout) -> None:
        """Setup position slider and time display."""
        # Current time
        self.current_time_label = QLabel("0:00")
        self.current_time_label.setFixedWidth(40)
        self.current_time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.current_time_label)

        # Position slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.setMaximum(1000)  # Use 1000 for smooth seeking
        self.position_slider.setValue(0)
        self.position_slider.setToolTip("Seek position")
        layout.addWidget(self.position_slider)

        # Total time
        self.total_time_label = QLabel("0:00")
        self.total_time_label.setFixedWidth(40)
        self.total_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.total_time_label)

    def _setup_audio_controls(self, layout: QHBoxLayout) -> None:
        """Setup volume and speed controls."""
        # Volume control
        volume_label = QLabel("Vol:")
        volume_label.setFixedWidth(25)
        layout.addWidget(volume_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setToolTip("Volume")
        layout.addWidget(self.volume_slider)

        # Speed control
        speed_label = QLabel("Speed:")
        speed_label.setFixedWidth(40)
        layout.addWidget(speed_label)

        self.speed_spinbox = QSpinBox()
        self.speed_spinbox.setMinimum(50)  # 0.5x
        self.speed_spinbox.setMaximum(200)  # 2.0x
        self.speed_spinbox.setValue(100)  # 1.0x
        self.speed_spinbox.setSuffix("%")
        self.speed_spinbox.setFixedWidth(60)
        self.speed_spinbox.setToolTip("Playback speed")
        layout.addWidget(self.speed_spinbox)

    def _setup_device_controls(self, layout: QVBoxLayout) -> None:
        """Setup audio device selection."""
        device_layout = QHBoxLayout()

        device_label = QLabel("Audio Device:")
        device_layout.addWidget(device_label)

        self.device_combo = QComboBox()
        self.device_combo.setToolTip("Select audio output device")
        device_layout.addWidget(self.device_combo)

        # Latency display
        self.latency_label = QLabel("Latency: --ms")
        device_layout.addWidget(self.latency_label)

        device_layout.addStretch()
        layout.addLayout(device_layout)

    def _connect_signals(self) -> None:
        """Connect UI signals."""
        # Playback buttons
        self.play_button.clicked.connect(self._toggle_playback)
        self.stop_button.clicked.connect(self._stop_playback)
        self.prev_button.clicked.connect(self._previous_cue)
        self.next_button.clicked.connect(self._next_cue)

        # Position slider
        self.position_slider.sliderPressed.connect(self._start_seeking)
        self.position_slider.sliderReleased.connect(self._end_seeking)
        self.position_slider.valueChanged.connect(self._on_position_changed)

        # Audio controls
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.speed_spinbox.valueChanged.connect(self._on_speed_changed)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)

    def set_audio_engine(self, audio_engine: AudioEngine) -> None:
        """Set the audio engine reference."""
        self.audio_engine = audio_engine

        # Connect audio engine signals
        audio_engine.playback_started.connect(self._on_playback_started)
        audio_engine.playback_paused.connect(self._on_playback_paused)
        audio_engine.playback_stopped.connect(self._on_playback_stopped)
        audio_engine.position_changed.connect(self._on_position_update)
        audio_engine.state_changed.connect(self._on_state_changed)
        audio_engine.device_changed.connect(self._on_device_update)

        # Update device list
        self._update_device_list()

        self.logger.debug("Audio engine connected to transport bar")

    def _update_device_list(self) -> None:
        """Update audio device list."""
        if not self.audio_engine:
            return

        self.device_combo.clear()
        devices = self.audio_engine.get_available_devices()

        for device in devices:
            device_text = f"{device.name} ({device.channels}ch, {device.latency*1000:.1f}ms)"
            self.device_combo.addItem(device_text, device.id)

            if device.is_default:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)

    def set_duration(self, duration_seconds: float) -> None:
        """Set track duration."""
        self.current_duration = duration_seconds
        self.total_time_label.setText(self._format_time(duration_seconds))

    def _toggle_playback(self) -> None:
        """Toggle play/pause."""
        if self.playback_state == PlaybackState.PLAYING:
            self.pause_requested.emit()
        else:
            self.play_requested.emit()

    def _stop_playback(self) -> None:
        """Stop playback."""
        self.stop_requested.emit()

    def _previous_cue(self) -> None:
        """Jump to previous cue point."""
        # This will be connected to MainWindow cue navigation
        pass

    def _next_cue(self) -> None:
        """Jump to next cue point."""
        # This will be connected to MainWindow cue navigation
        pass

    def _start_seeking(self) -> None:
        """Start seeking mode."""
        self.is_seeking = True

    def _end_seeking(self) -> None:
        """End seeking mode and seek to position."""
        self.is_seeking = False
        if self.current_duration > 0:
            position = (self.position_slider.value() / 1000.0) * self.current_duration
            self.seek_requested.emit(position)

    def _on_position_changed(self, value: int) -> None:
        """Handle position slider change."""
        if self.is_seeking and self.current_duration > 0:
            position = (value / 1000.0) * self.current_duration
            self.current_time_label.setText(self._format_time(position))

    def _on_volume_changed(self, value: int) -> None:
        """Handle volume change."""
        volume = value / 100.0
        self.volume_changed.emit(volume)

    def _on_speed_changed(self, value: int) -> None:
        """Handle speed change."""
        speed = value / 100.0
        self.speed_changed.emit(speed)

    def _on_device_changed(self, index: int) -> None:
        """Handle device change."""
        if index >= 0:
            device_id = self.device_combo.itemData(index)
            if device_id is not None:
                self.device_changed.emit(device_id)

    def _on_playback_started(self) -> None:
        """Handle playback started."""
        self.play_button.setText("⏸")
        self.play_button.setToolTip("Pause (Space)")
        self.playback_state = PlaybackState.PLAYING

    def _on_playback_paused(self) -> None:
        """Handle playback paused."""
        self.play_button.setText("▶")
        self.play_button.setToolTip("Play (Space)")
        self.playback_state = PlaybackState.PAUSED

    def _on_playback_stopped(self) -> None:
        """Handle playback stopped."""
        self.play_button.setText("▶")
        self.play_button.setToolTip("Play (Space)")
        self.playback_state = PlaybackState.STOPPED
        self.current_position = 0.0

    def _on_position_update(self, position: float) -> None:
        """Handle position update from audio engine."""
        self.current_position = position

    def _on_state_changed(self, state: str) -> None:
        """Handle state change from audio engine."""
        self.playback_state = PlaybackState(state)

    def _on_device_update(self, device_name: str) -> None:
        """Handle device change from audio engine."""
        self.latency_label.setText(f"Device: {device_name}")

    def _update_display(self) -> None:
        """Update time display and position slider."""
        if not self.is_seeking:
            # Update time display
            self.current_time_label.setText(self._format_time(self.current_position))

            # Update position slider
            if self.current_duration > 0:
                slider_value = int((self.current_position / self.current_duration) * 1000)
                self.position_slider.setValue(slider_value)

    def _format_time(self, seconds: float) -> str:
        """Format time in MM:SS format."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"
