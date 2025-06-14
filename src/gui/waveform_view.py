"""
Waveform View Widget - GPU Accelerated
OpenGL/Metal rendering for 60 FPS performance using PyQtGraph
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
import threading

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QWheelEvent, QMouseEvent, QPainter
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

import pyqtgraph as pg
from pyqtgraph.opengl import GLViewWidget, GLLinePlotItem, GLGridItem

from ..core.audio_loader import AudioData
from ..core.beatgrid_engine import BeatgridData


class WaveformView(QWidget):
    """
    GPU-accelerated waveform display widget.
    Renders audio waveform with beatgrid, cues, and structure overlays.
    Uses PyQtGraph with OpenGL backend for 60 FPS performance.
    """

    # Signals
    zoom_changed = pyqtSignal(float)  # Emitted when zoom level changes
    position_changed = pyqtSignal(float)  # Emitted when playback position changes
    beat_clicked = pyqtSignal(float)  # Emitted when beat is clicked
    cue_clicked = pyqtSignal(int)  # Emitted when cue point is clicked
    structure_clicked = pyqtSignal(str)  # Emitted when structure section is clicked

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.config = config
        self.logger = logging.getLogger(__name__)

        # Waveform data
        self.audio_data: Optional[AudioData] = None
        self.beatgrid_data: Optional[BeatgridData] = None
        self.waveform_cache: Dict[int, np.ndarray] = {}

        # Phase 3: Visual overlays
        self.cue_points: List[Any] = []  # Will be CuePoint objects
        self.structure_sections: List[Any] = []  # Will be StructureSection objects
        self.cue_overlay_items: List[Any] = []
        self.structure_overlay_items: List[Any] = []
        self.show_cue_overlays = config.get('waveform', {}).get('show_cue_overlays', True)
        self.show_structure_overlays = config.get('waveform', {}).get('show_structure_overlays', True)

        # Display settings
        self.zoom_level = config.get('waveform', {}).get('zoom', {}).get('default', 4)
        self.zoom_min = config.get('waveform', {}).get('zoom', {}).get('min', 1)
        self.zoom_max = config.get('waveform', {}).get('zoom', {}).get('max', 128)
        self.stereo_mode = True  # True for stereo, False for mono

        # Colors from config
        colors = config.get('waveform', {}).get('colors', {})
        self.color_background = QColor(colors.get('background', '#1A1A1A'))
        self.color_peaks = QColor(colors.get('peaks', '#00FF88'))
        self.color_rms = QColor(colors.get('rms', '#004422'))
        self.color_beatgrid = QColor(colors.get('beatgrid', '#FF6B35'))
        self.color_downbeat = QColor(colors.get('downbeat', '#FF6B35'))

        # Rendering settings
        rendering = config.get('waveform', {}).get('rendering', {})
        self.use_opengl = rendering.get('use_opengl', True)
        self.target_fps = rendering.get('target_fps', 60)
        self.line_width = rendering.get('line_width', 1)
        self.rms_alpha = rendering.get('rms_alpha', 0.6)

        # Playback state
        self.playback_position = 0.0  # Current position in seconds
        self.is_playing = False

        # Mouse interaction
        self.mouse_pressed = False
        self.last_mouse_pos = QPointF()

        # Performance monitoring
        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.current_fps = 0.0

        # Setup UI
        self._setup_ui()
        self._setup_performance_timer()

        self.logger.info(f"WaveformView initialized - OpenGL: {self.use_opengl}")

    def _setup_ui(self) -> None:
        """Setup the waveform display UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Info bar
        info_layout = QHBoxLayout()
        self.info_label = QLabel("No audio loaded")
        self.fps_label = QLabel("FPS: --")
        self.zoom_label = QLabel(f"Zoom: {self.zoom_level}x")

        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        info_layout.addWidget(self.zoom_label)
        info_layout.addWidget(self.fps_label)

        layout.addLayout(info_layout)

        # Main waveform display
        if self.use_opengl:
            self._setup_opengl_view()
        else:
            self._setup_cpu_view()

        layout.addWidget(self.plot_widget)

    def _setup_opengl_view(self) -> None:
        """Setup OpenGL-accelerated waveform view."""
        try:
            # Configure PyQtGraph for OpenGL
            pg.setConfigOptions(
                antialias=True,
                useOpenGL=True,
                enableExperimental=True
            )

            # Create plot widget with OpenGL
            self.plot_widget = pg.PlotWidget(
                background=self.color_background,
                enableMenu=False
            )

            # Configure plot
            self.plot_widget.setLabel('left', 'Amplitude')
            self.plot_widget.setLabel('bottom', 'Time (s)')
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

            # Remove default mouse interaction
            self.plot_widget.setMouseEnabled(x=False, y=False)

            # Setup custom mouse handling
            self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

            # Plot items for waveform data
            self.waveform_items = []
            self.beatgrid_items = []
            self.position_line = None

            self.logger.info("OpenGL waveform view initialized")

        except Exception as e:
            self.logger.warning(f"OpenGL setup failed, falling back to CPU: {e}")
            self.use_opengl = False
            self._setup_cpu_view()

    def _setup_cpu_view(self) -> None:
        """Setup CPU-based waveform view as fallback."""
        # Create standard plot widget
        self.plot_widget = pg.PlotWidget(
            background=self.color_background,
            enableMenu=False
        )

        # Configure plot
        self.plot_widget.setLabel('left', 'Amplitude')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Remove default mouse interaction
        self.plot_widget.setMouseEnabled(x=False, y=False)

        # Setup custom mouse handling
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        # Plot items
        self.waveform_items = []
        self.beatgrid_items = []
        self.position_line = None

        self.logger.info("CPU waveform view initialized")

    def _setup_performance_timer(self) -> None:
        """Setup FPS monitoring timer."""
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self._update_fps)
        self.fps_timer.start(1000)  # Update every second

    def load_audio_data(self, audio_data: AudioData) -> None:
        """Load audio data for waveform display."""
        self.audio_data = audio_data
        self.waveform_cache.clear()

        # Update info
        self.info_label.setText(
            f"{audio_data.file_path.name} - "
            f"{audio_data.duration:.1f}s, "
            f"{audio_data.channels}ch, "
            f"{audio_data.sample_rate}Hz"
        )

        # Generate waveform data for current zoom level
        self._generate_waveform_display()

        # Reset view
        self.fit_to_window()

        self.logger.info(f"Audio data loaded: {audio_data.file_path.name}")

    def load_beatgrid_data(self, beatgrid_data: BeatgridData) -> None:
        """Load beatgrid data for display."""
        self.beatgrid_data = beatgrid_data
        self._update_beatgrid_display()

        self.logger.info(f"Beatgrid loaded: {beatgrid_data.bpm:.1f} BPM")

    def _generate_waveform_display(self) -> None:
        """Generate waveform display for current zoom level with optimizations."""
        if not self.audio_data:
            return

        # Performance timing
        start_time = time.time()

        # Clear existing waveform items
        for item in self.waveform_items:
            self.plot_widget.removeItem(item)
        self.waveform_items.clear()

        # Get current view range for optimization
        view_range = self.plot_widget.viewRange()
        x_min, x_max = view_range[0]

        # Only render visible portion at high zoom levels
        if self.zoom_level > 16:
            visible_start = max(0, x_min)
            visible_end = min(self.audio_data.duration, x_max)
            visible_duration = visible_end - visible_start

            # If we're viewing a small portion, only process that
            if visible_duration < self.audio_data.duration * 0.1:
                self._render_visible_portion(visible_start, visible_end)
                render_time = time.time() - start_time
                self.logger.debug(f"Rendered visible portion in {render_time:.3f}s")
                return

        # Full waveform rendering
        widget_width = self.plot_widget.width() or 1920
        total_samples = self.audio_data.data.shape[-1]
        samples_per_pixel = max(1, total_samples // (widget_width * self.zoom_level))

        # Use cached waveform data if available
        if hasattr(self, 'waveform_cache') and self.zoom_level in self.waveform_cache:
            cached_data = self.waveform_cache[self.zoom_level]
            self._render_cached_waveform(cached_data)
        else:
            # Generate new waveform data
            time_axis = np.linspace(0, self.audio_data.duration,
                                   total_samples // samples_per_pixel)

            if self.stereo_mode and self.audio_data.channels == 2:
                # Display stereo channels separately
                self._render_stereo_waveform(time_axis, samples_per_pixel)
            else:
                # Display mono or mixed waveform
                self._render_mono_waveform(time_axis, samples_per_pixel)

        render_time = time.time() - start_time
        self.logger.debug(f"Waveform rendered in {render_time:.3f}s at zoom {self.zoom_level}x")

    def _render_visible_portion(self, start_time: float, end_time: float) -> None:
        """Render only the visible portion of the waveform for performance."""
        if not self.audio_data:
            return

        # Calculate sample range
        start_sample = int(start_time * self.audio_data.sample_rate)
        end_sample = int(end_time * self.audio_data.sample_rate)
        start_sample = max(0, start_sample)
        end_sample = min(self.audio_data.data.shape[-1], end_sample)

        if start_sample >= end_sample:
            return

        # Extract visible audio data
        visible_data = self.audio_data.data[:, start_sample:end_sample]
        visible_duration = (end_sample - start_sample) / self.audio_data.sample_rate

        # Calculate downsampling for this portion
        widget_width = self.plot_widget.width() or 1920
        samples_per_pixel = max(1, visible_data.shape[-1] // widget_width)

        # Generate time axis for visible portion
        time_axis = np.linspace(start_time, end_time,
                               visible_data.shape[-1] // samples_per_pixel)

        # Render the visible portion
        if self.stereo_mode and self.audio_data.channels == 2:
            self._render_stereo_portion(visible_data, time_axis, samples_per_pixel)
        else:
            self._render_mono_portion(visible_data, time_axis, samples_per_pixel)

    def _render_cached_waveform(self, cached_data: Dict[str, np.ndarray]) -> None:
        """Render waveform from cached data."""
        peaks = cached_data['peaks']
        rms = cached_data['rms']

        # Generate time axis
        time_axis = np.linspace(0, self.audio_data.duration, peaks.shape[-1])

        if self.stereo_mode and peaks.shape[0] == 2:
            self._render_stereo_cached(peaks, rms, time_axis)
        else:
            self._render_mono_cached(peaks, rms, time_axis)

    def _render_stereo_waveform(self, time_axis: np.ndarray, samples_per_pixel: int) -> None:
        """Render stereo waveform with L/R channels stacked."""
        for channel_idx in range(self.audio_data.channels):
            channel_data = self.audio_data.data[channel_idx]

            # Downsample for display
            if samples_per_pixel > 1:
                n_pixels = len(channel_data) // samples_per_pixel
                reshaped = channel_data[:n_pixels * samples_per_pixel].reshape(n_pixels, samples_per_pixel)
                peaks = np.max(np.abs(reshaped), axis=1)
                rms = np.sqrt(np.mean(reshaped**2, axis=1))
            else:
                peaks = np.abs(channel_data)
                rms = np.abs(channel_data)  # For single samples, RMS = abs

            # Adjust for stereo display (stack channels)
            y_offset = 0.5 - channel_idx  # L: +0.5, R: -0.5
            y_scale = 0.4  # Scale to fit in half the display

            # Create positive and negative peaks for stereo display
            peaks_pos = y_offset + peaks * y_scale
            peaks_neg = y_offset - peaks * y_scale

            # RMS envelope
            rms_pos = y_offset + rms * y_scale
            rms_neg = y_offset - rms * y_scale

            # Plot RMS fill (background)
            rms_color = QColor(self.color_rms)
            rms_color.setAlphaF(self.rms_alpha)

            rms_item = pg.FillBetweenItem(
                pg.PlotCurveItem(time_axis[:len(rms_pos)], rms_pos),
                pg.PlotCurveItem(time_axis[:len(rms_neg)], rms_neg),
                brush=rms_color
            )
            self.plot_widget.addItem(rms_item)
            self.waveform_items.append(rms_item)

            # Plot peak waveform (foreground)
            peak_pen = pg.mkPen(color=self.color_peaks, width=self.line_width)

            # Positive peaks
            peak_pos_item = pg.PlotCurveItem(
                time_axis[:len(peaks_pos)], peaks_pos,
                pen=peak_pen
            )
            self.plot_widget.addItem(peak_pos_item)
            self.waveform_items.append(peak_pos_item)

            # Negative peaks
            peak_neg_item = pg.PlotCurveItem(
                time_axis[:len(peaks_neg)], peaks_neg,
                pen=peak_pen
            )
            self.plot_widget.addItem(peak_neg_item)
            self.waveform_items.append(peak_neg_item)

    def _render_mono_waveform(self, time_axis: np.ndarray, samples_per_pixel: int) -> None:
        """Render mono waveform (single channel or mixed)."""
        # Mix channels if stereo
        if self.audio_data.channels > 1:
            mono_data = np.mean(self.audio_data.data, axis=0)
        else:
            mono_data = self.audio_data.data[0]

        # Downsample for display
        if samples_per_pixel > 1:
            n_pixels = len(mono_data) // samples_per_pixel
            reshaped = mono_data[:n_pixels * samples_per_pixel].reshape(n_pixels, samples_per_pixel)
            peaks = np.max(np.abs(reshaped), axis=1)
            rms = np.sqrt(np.mean(reshaped**2, axis=1))
        else:
            peaks = np.abs(mono_data)
            rms = np.abs(mono_data)

        # Create positive and negative waveform
        peaks_pos = peaks
        peaks_neg = -peaks
        rms_pos = rms
        rms_neg = -rms

        # Plot RMS fill
        rms_color = QColor(self.color_rms)
        rms_color.setAlphaF(self.rms_alpha)

        rms_item = pg.FillBetweenItem(
            pg.PlotCurveItem(time_axis[:len(rms_pos)], rms_pos),
            pg.PlotCurveItem(time_axis[:len(rms_neg)], rms_neg),
            brush=rms_color
        )
        self.plot_widget.addItem(rms_item)
        self.waveform_items.append(rms_item)

        # Plot peak waveform
        peak_pen = pg.mkPen(color=self.color_peaks, width=self.line_width)

        peak_pos_item = pg.PlotCurveItem(
            time_axis[:len(peaks_pos)], peaks_pos,
            pen=peak_pen
        )
        self.plot_widget.addItem(peak_pos_item)
        self.waveform_items.append(peak_pos_item)

        peak_neg_item = pg.PlotCurveItem(
            time_axis[:len(peaks_neg)], peaks_neg,
            pen=peak_pen
        )
        self.plot_widget.addItem(peak_neg_item)
        self.waveform_items.append(peak_neg_item)

    def _render_stereo_portion(self, visible_data: np.ndarray, time_axis: np.ndarray, samples_per_pixel: int) -> None:
        """Render stereo waveform for visible portion only."""
        for channel_idx in range(min(2, visible_data.shape[0])):
            channel_data = visible_data[channel_idx]

            # Downsample for display
            if samples_per_pixel > 1:
                n_pixels = len(channel_data) // samples_per_pixel
                if n_pixels > 0:
                    reshaped = channel_data[:n_pixels * samples_per_pixel].reshape(n_pixels, samples_per_pixel)
                    peaks = np.max(np.abs(reshaped), axis=1)
                    rms = np.sqrt(np.mean(reshaped**2, axis=1))
                else:
                    peaks = np.abs(channel_data)
                    rms = np.abs(channel_data)
            else:
                peaks = np.abs(channel_data)
                rms = np.abs(channel_data)

            # Adjust for stereo display
            y_offset = 0.5 - channel_idx
            y_scale = 0.4

            peaks_pos = y_offset + peaks * y_scale
            peaks_neg = y_offset - peaks * y_scale
            rms_pos = y_offset + rms * y_scale
            rms_neg = y_offset - rms * y_scale

            # Plot RMS fill
            rms_color = QColor(self.color_rms)
            rms_color.setAlphaF(self.rms_alpha)

            if len(time_axis) == len(rms_pos):
                rms_item = pg.FillBetweenItem(
                    pg.PlotCurveItem(time_axis, rms_pos),
                    pg.PlotCurveItem(time_axis, rms_neg),
                    brush=rms_color
                )
                self.plot_widget.addItem(rms_item)
                self.waveform_items.append(rms_item)

            # Plot peak waveform
            peak_pen = pg.mkPen(color=self.color_peaks, width=self.line_width)

            if len(time_axis) == len(peaks_pos):
                peak_pos_item = pg.PlotCurveItem(time_axis, peaks_pos, pen=peak_pen)
                self.plot_widget.addItem(peak_pos_item)
                self.waveform_items.append(peak_pos_item)

                peak_neg_item = pg.PlotCurveItem(time_axis, peaks_neg, pen=peak_pen)
                self.plot_widget.addItem(peak_neg_item)
                self.waveform_items.append(peak_neg_item)

    def _render_mono_portion(self, visible_data: np.ndarray, time_axis: np.ndarray, samples_per_pixel: int) -> None:
        """Render mono waveform for visible portion only."""
        # Mix channels if stereo
        if visible_data.shape[0] > 1:
            mono_data = np.mean(visible_data, axis=0)
        else:
            mono_data = visible_data[0]

        # Downsample for display
        if samples_per_pixel > 1:
            n_pixels = len(mono_data) // samples_per_pixel
            if n_pixels > 0:
                reshaped = mono_data[:n_pixels * samples_per_pixel].reshape(n_pixels, samples_per_pixel)
                peaks = np.max(np.abs(reshaped), axis=1)
                rms = np.sqrt(np.mean(reshaped**2, axis=1))
            else:
                peaks = np.abs(mono_data)
                rms = np.abs(mono_data)
        else:
            peaks = np.abs(mono_data)
            rms = np.abs(mono_data)

        peaks_pos = peaks
        peaks_neg = -peaks
        rms_pos = rms
        rms_neg = -rms

        # Plot RMS fill
        rms_color = QColor(self.color_rms)
        rms_color.setAlphaF(self.rms_alpha)

        if len(time_axis) == len(rms_pos):
            rms_item = pg.FillBetweenItem(
                pg.PlotCurveItem(time_axis, rms_pos),
                pg.PlotCurveItem(time_axis, rms_neg),
                brush=rms_color
            )
            self.plot_widget.addItem(rms_item)
            self.waveform_items.append(rms_item)

        # Plot peak waveform
        peak_pen = pg.mkPen(color=self.color_peaks, width=self.line_width)

        if len(time_axis) == len(peaks_pos):
            peak_pos_item = pg.PlotCurveItem(time_axis, peaks_pos, pen=peak_pen)
            self.plot_widget.addItem(peak_pos_item)
            self.waveform_items.append(peak_pos_item)

            peak_neg_item = pg.PlotCurveItem(time_axis, peaks_neg, pen=peak_pen)
            self.plot_widget.addItem(peak_neg_item)
            self.waveform_items.append(peak_neg_item)

    def _render_stereo_cached(self, peaks: np.ndarray, rms: np.ndarray, time_axis: np.ndarray) -> None:
        """Render stereo waveform from cached data."""
        for channel_idx in range(min(2, peaks.shape[0])):
            channel_peaks = peaks[channel_idx]
            channel_rms = rms[channel_idx]

            # Adjust for stereo display
            y_offset = 0.5 - channel_idx
            y_scale = 0.4

            peaks_pos = y_offset + channel_peaks * y_scale
            peaks_neg = y_offset - channel_peaks * y_scale
            rms_pos = y_offset + channel_rms * y_scale
            rms_neg = y_offset - channel_rms * y_scale

            # Plot RMS fill
            rms_color = QColor(self.color_rms)
            rms_color.setAlphaF(self.rms_alpha)

            rms_item = pg.FillBetweenItem(
                pg.PlotCurveItem(time_axis, rms_pos),
                pg.PlotCurveItem(time_axis, rms_neg),
                brush=rms_color
            )
            self.plot_widget.addItem(rms_item)
            self.waveform_items.append(rms_item)

            # Plot peak waveform
            peak_pen = pg.mkPen(color=self.color_peaks, width=self.line_width)

            peak_pos_item = pg.PlotCurveItem(time_axis, peaks_pos, pen=peak_pen)
            self.plot_widget.addItem(peak_pos_item)
            self.waveform_items.append(peak_pos_item)

            peak_neg_item = pg.PlotCurveItem(time_axis, peaks_neg, pen=peak_pen)
            self.plot_widget.addItem(peak_neg_item)
            self.waveform_items.append(peak_neg_item)

    def _render_mono_cached(self, peaks: np.ndarray, rms: np.ndarray, time_axis: np.ndarray) -> None:
        """Render mono waveform from cached data."""
        # Use first channel or mix if multiple
        if peaks.shape[0] > 1:
            channel_peaks = np.mean(peaks, axis=0)
            channel_rms = np.mean(rms, axis=0)
        else:
            channel_peaks = peaks[0]
            channel_rms = rms[0]

        peaks_pos = channel_peaks
        peaks_neg = -channel_peaks
        rms_pos = channel_rms
        rms_neg = -channel_rms

        # Plot RMS fill
        rms_color = QColor(self.color_rms)
        rms_color.setAlphaF(self.rms_alpha)

        rms_item = pg.FillBetweenItem(
            pg.PlotCurveItem(time_axis, rms_pos),
            pg.PlotCurveItem(time_axis, rms_neg),
            brush=rms_color
        )
        self.plot_widget.addItem(rms_item)
        self.waveform_items.append(rms_item)

        # Plot peak waveform
        peak_pen = pg.mkPen(color=self.color_peaks, width=self.line_width)

        peak_pos_item = pg.PlotCurveItem(time_axis, peaks_pos, pen=peak_pen)
        self.plot_widget.addItem(peak_pos_item)
        self.waveform_items.append(peak_pos_item)

        peak_neg_item = pg.PlotCurveItem(time_axis, peaks_neg, pen=peak_pen)
        self.plot_widget.addItem(peak_neg_item)
        self.waveform_items.append(peak_neg_item)

    def _update_beatgrid_display(self) -> None:
        """Update beatgrid overlay display."""
        if not self.beatgrid_data or not self.audio_data:
            return

        # Clear existing beatgrid items
        for item in self.beatgrid_items:
            self.plot_widget.removeItem(item)
        self.beatgrid_items.clear()

        # Get plot range
        view_range = self.plot_widget.viewRange()
        y_min, y_max = view_range[1]

        # Draw beat lines
        beat_pen = pg.mkPen(color=self.color_beatgrid, width=1, style=Qt.PenStyle.DashLine)
        for beat_time in self.beatgrid_data.beats:
            if 0 <= beat_time <= self.audio_data.duration:
                beat_line = pg.InfiniteLine(
                    pos=beat_time,
                    angle=90,
                    pen=beat_pen
                )
                self.plot_widget.addItem(beat_line)
                self.beatgrid_items.append(beat_line)

        # Draw downbeat lines (thicker)
        downbeat_pen = pg.mkPen(color=self.color_downbeat, width=2, style=Qt.PenStyle.SolidLine)
        for downbeat_time in self.beatgrid_data.downbeats:
            if 0 <= downbeat_time <= self.audio_data.duration:
                downbeat_line = pg.InfiniteLine(
                    pos=downbeat_time,
                    angle=90,
                    pen=downbeat_pen
                )
                self.plot_widget.addItem(downbeat_line)
                self.beatgrid_items.append(downbeat_line)

    def _update_playback_position(self) -> None:
        """Update playback position indicator."""
        if self.position_line:
            self.plot_widget.removeItem(self.position_line)

        if self.audio_data and 0 <= self.playback_position <= self.audio_data.duration:
            position_pen = pg.mkPen(color='white', width=2)
            self.position_line = pg.InfiniteLine(
                pos=self.playback_position,
                angle=90,
                pen=position_pen
            )
            self.plot_widget.addItem(self.position_line)

    def set_playback_position(self, position: float) -> None:
        """Set current playback position."""
        self.playback_position = position
        self._update_playback_position()
        self.position_changed.emit(position)

    def zoom_in(self) -> None:
        """Zoom in on waveform."""
        new_zoom = min(self.zoom_max, self.zoom_level * 2)
        if new_zoom != self.zoom_level:
            self.zoom_level = new_zoom
            self.zoom_label.setText(f"Zoom: {self.zoom_level}x")
            self._generate_waveform_display()
            self.zoom_changed.emit(self.zoom_level)

    def zoom_out(self) -> None:
        """Zoom out on waveform."""
        new_zoom = max(self.zoom_min, self.zoom_level / 2)
        if new_zoom != self.zoom_level:
            self.zoom_level = new_zoom
            self.zoom_label.setText(f"Zoom: {self.zoom_level}x")
            self._generate_waveform_display()
            self.zoom_changed.emit(self.zoom_level)

    def fit_to_window(self) -> None:
        """Fit waveform to window width."""
        if self.audio_data:
            self.plot_widget.setXRange(0, self.audio_data.duration, padding=0.02)
            self.plot_widget.setYRange(-1.1, 1.1, padding=0.02)

    def toggle_stereo_mono(self) -> None:
        """Toggle between stereo and mono display."""
        self.stereo_mode = not self.stereo_mode
        if self.audio_data:
            self._generate_waveform_display()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zooming."""
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()

    def _on_mouse_clicked(self, event) -> None:
        """Handle mouse clicks on waveform."""
        if not self.audio_data:
            return

        # Get click position in plot coordinates
        pos = event.scenePos()
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            click_time = mouse_point.x()

            # Clamp to audio duration
            click_time = max(0, min(click_time, self.audio_data.duration))

            # Check if click is near a beat
            if self.beatgrid_data:
                for beat_time in self.beatgrid_data.beats:
                    if abs(click_time - beat_time) < 0.1:  # 100ms tolerance
                        self.beat_clicked.emit(beat_time)
                        return

            # Set playback position
            self.set_playback_position(click_time)

    def _update_fps(self) -> None:
        """Update FPS counter."""
        current_time = time.time()
        elapsed = current_time - self.last_fps_time

        if elapsed >= 1.0:
            self.current_fps = self.fps_counter / elapsed
            self.fps_label.setText(f"FPS: {self.current_fps:.1f}")

            self.fps_counter = 0
            self.last_fps_time = current_time

        self.fps_counter += 1

    def paintEvent(self, event) -> None:
        """Override paint event for FPS counting."""
        super().paintEvent(event)
        self.fps_counter += 1

    def get_current_fps(self) -> float:
        """Get current FPS for performance monitoring."""
        return self.current_fps

    def clear_display(self) -> None:
        """Clear all waveform and beatgrid display."""
        # Clear waveform
        for item in self.waveform_items:
            self.plot_widget.removeItem(item)
        self.waveform_items.clear()

        # Clear beatgrid
        for item in self.beatgrid_items:
            self.plot_widget.removeItem(item)
        self.beatgrid_items.clear()

        # Clear position line
        if self.position_line:
            self.plot_widget.removeItem(self.position_line)
            self.position_line = None

        # Reset data
        self.audio_data = None
        self.beatgrid_data = None
        self.waveform_cache.clear()

        # Update info
        self.info_label.setText("No audio loaded")

    def set_cue_points(self, cue_points: List[Any]) -> None:
        """Set cue points for visual overlay."""
        self.cue_points = cue_points
        self._update_cue_overlays()

    def set_structure_sections(self, structure_sections: List[Any]) -> None:
        """Set structure sections for visual overlay."""
        self.structure_sections = structure_sections
        self._update_structure_overlays()

    def _update_cue_overlays(self) -> None:
        """Update cue point visual overlays."""
        # Clear existing cue overlays
        for item in self.cue_overlay_items:
            self.plot_widget.removeItem(item)
        self.cue_overlay_items.clear()

        if not self.show_cue_overlays or not self.cue_points or not self.audio_data:
            return

        # Get plot range for positioning
        view_range = self.plot_widget.viewRange()
        y_min, y_max = view_range[1]

        for cue_point in self.cue_points:
            # Create cue line
            cue_time = getattr(cue_point, 'position_seconds', 0.0)
            cue_color = getattr(cue_point, 'color', '#FF3366')
            cue_label = getattr(cue_point, 'label', f'Cue {getattr(cue_point, "id", "?")}')

            # Create vertical line for cue
            cue_line = pg.InfiniteLine(
                pos=cue_time,
                angle=90,
                pen=pg.mkPen(color=cue_color, width=2),
                movable=False
            )

            # Add click detection
            cue_line.sigClicked.connect(
                lambda line, cue_id=getattr(cue_point, 'id', 0): self.cue_clicked.emit(cue_id)
            )

            self.plot_widget.addItem(cue_line)
            self.cue_overlay_items.append(cue_line)

            # Add cue label (text item)
            cue_text = pg.TextItem(
                text=cue_label,
                color=cue_color,
                anchor=(0.5, 1.0)  # Center horizontally, bottom vertically
            )
            cue_text.setPos(cue_time, y_max * 0.9)  # Position near top

            self.plot_widget.addItem(cue_text)
            self.cue_overlay_items.append(cue_text)

    def _update_structure_overlays(self) -> None:
        """Update structure section visual overlays."""
        # Clear existing structure overlays
        for item in self.structure_overlay_items:
            self.plot_widget.removeItem(item)
        self.structure_overlay_items.clear()

        if not self.show_structure_overlays or not self.structure_sections or not self.audio_data:
            return

        # Get plot range for positioning
        view_range = self.plot_widget.viewRange()
        y_min, y_max = view_range[1]

        for section in self.structure_sections:
            start_time = getattr(section, 'start_time', 0.0)
            end_time = getattr(section, 'end_time', 0.0)
            section_color = getattr(section, 'color', '#888888')
            section_label = getattr(section, 'label', 'Unknown')
            section_type = getattr(section, 'type', None)

            # Create background region for structure section
            section_region = pg.LinearRegionItem(
                values=[start_time, end_time],
                brush=pg.mkBrush(color=section_color + '40'),  # Semi-transparent
                pen=pg.mkPen(color=section_color, width=1),
                movable=False
            )

            # Add click detection
            section_region.sigClicked.connect(
                lambda region, s_type=section_type: self.structure_clicked.emit(str(s_type))
            )

            self.plot_widget.addItem(section_region)
            self.structure_overlay_items.append(section_region)

            # Add structure label
            section_text = pg.TextItem(
                text=section_label,
                color=section_color,
                anchor=(0.5, 0.0)  # Center horizontally, top vertically
            )
            section_text.setPos((start_time + end_time) / 2, y_min * 0.9)  # Position near bottom

            self.plot_widget.addItem(section_text)
            self.structure_overlay_items.append(section_text)

    def toggle_cue_overlays(self, show: bool) -> None:
        """Toggle visibility of cue point overlays."""
        self.show_cue_overlays = show
        self._update_cue_overlays()

    def toggle_structure_overlays(self, show: bool) -> None:
        """Toggle visibility of structure overlays."""
        self.show_structure_overlays = show
        self._update_structure_overlays()

    def highlight_cue_point(self, cue_id: int) -> None:
        """Highlight a specific cue point."""
        # Find and highlight the cue point
        for i, cue_point in enumerate(self.cue_points):
            if getattr(cue_point, 'id', 0) == cue_id:
                # Temporarily change the cue line appearance
                if i * 2 < len(self.cue_overlay_items):  # Each cue has line + text
                    cue_line = self.cue_overlay_items[i * 2]
                    if hasattr(cue_line, 'setPen'):
                        # Make line thicker and brighter
                        highlight_color = getattr(cue_point, 'color', '#FF3366')
                        cue_line.setPen(pg.mkPen(color=highlight_color, width=4))

                        # Reset after delay
                        def reset_highlight():
                            if hasattr(cue_line, 'setPen'):
                                cue_line.setPen(pg.mkPen(color=highlight_color, width=2))

                        QTimer.singleShot(1000, reset_highlight)  # Reset after 1 second
                break

    def jump_to_cue(self, cue_id: int) -> None:
        """Jump view to a specific cue point."""
        for cue_point in self.cue_points:
            if getattr(cue_point, 'id', 0) == cue_id:
                cue_time = getattr(cue_point, 'position_seconds', 0.0)
                self.set_playback_position(cue_time)

                # Center view on cue point
                current_range = self.plot_widget.viewRange()[0]
                range_width = current_range[1] - current_range[0]
                new_start = cue_time - range_width / 2
                new_end = cue_time + range_width / 2

                # Ensure we don't go outside track bounds
                if new_start < 0:
                    new_start = 0
                    new_end = range_width
                elif new_end > self.audio_data.duration:
                    new_end = self.audio_data.duration
                    new_start = new_end - range_width

                self.plot_widget.setXRange(new_start, new_end, padding=0)
                break

        self.logger.info("Waveform display cleared")
