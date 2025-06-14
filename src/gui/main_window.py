"""
Main Window for CUEpoint Application
Optimized for macOS 13" displays (2560×1600)
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QMenuBar, QStatusBar, QFileDialog,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QDragEnterEvent, QDropEvent

from .waveform_view import WaveformView
from .transport_bar import TransportBar
from .sidebar import Sidebar
from ..core.audio_loader import AudioLoader, AudioData, AudioLoadError
from ..core.beatgrid_engine import BeatgridEngine, BeatgridData, BeatgridError
from ..core.performance_monitor import PerformanceMonitor
from ..core.cue_manager import CueManager, CuePoint, CueType
from ..core.metadata_parser import MetadataParser, TrackMetadata
from ..core.serato_bridge import SeratoBridge
from ..analysis.structure_analyzer import StructureAnalyzer, StructureAnalysisResult
from .navigation_controls import NavigationControls
from ..playback.audio_engine import AudioEngine, PlaybackState


class MainWindow(QMainWindow):
    """
    Main application window with waveform display, transport controls,
    and sidebar for cues and structure analysis.
    """
    
    # Signals
    file_loaded = pyqtSignal(str)  # Emitted when audio file is loaded
    
    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.current_file: Optional[Path] = None

        # Initialize audio processing components
        self.audio_loader = AudioLoader(config)
        self.beatgrid_engine = BeatgridEngine(config)
        self.performance_monitor = PerformanceMonitor(config)

        # Initialize Phase 2 components
        self.cue_manager = CueManager(config)
        self.metadata_parser = MetadataParser(config)
        self.serato_bridge = SeratoBridge(config)

        # Initialize Phase 3 components
        self.structure_analyzer = StructureAnalyzer(config)

        # Initialize Audio Playback (Critical)
        self.audio_engine = AudioEngine(config)

        # Current audio and analysis data
        self.current_audio_data: Optional[AudioData] = None
        self.current_beatgrid_data: Optional[BeatgridData] = None
        self.current_metadata: Optional[TrackMetadata] = None
        self.current_structure_data: Optional[StructureAnalysisResult] = None
        
        # Initialize UI
        self._setup_window()
        self._create_menu_bar()
        self._create_central_widget()
        self._create_status_bar()
        self._setup_drag_drop()
        self._connect_signals()
        
        # Performance monitoring
        self._setup_performance_monitoring()

        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
        self.logger.info("MainWindow initialized")
    
    def _setup_window(self) -> None:
        """Configure main window properties."""
        window_config = self.config.get('app', {}).get('window', {})
        
        # Set window title and size
        self.setWindowTitle(f"{self.config.get('app', {}).get('name', 'CUEpoint')} v{self.config.get('app', {}).get('version', '2.1.0')}")
        
        # Window dimensions optimized for 13" MacBook (2560×1600)
        width = window_config.get('width', 1400)
        height = window_config.get('height', 900)
        self.resize(width, height)
        
        # Set minimum size
        min_width = window_config.get('min_width', 1200)
        min_height = window_config.get('min_height', 700)
        self.setMinimumSize(min_width, min_height)
        
        # Center window on screen
        self._center_on_screen()
        
        # Enable unified title and toolbar on macOS
        self.setUnifiedTitleAndToolBarOnMac(True)
    
    def _center_on_screen(self) -> None:
        """Center the window on the primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())
    
    def _create_menu_bar(self) -> None:
        """Create application menu bar with macOS-style menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        # Open action
        open_action = QAction("Open Track...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)
        
        # Recent files submenu (placeholder)
        recent_menu = file_menu.addMenu("Recent Files")
        recent_menu.setEnabled(False)  # Will be enabled when we have recent files
        
        file_menu.addSeparator()
        
        # Export action
        export_action = QAction("Export Analysis...", self)
        export_action.setShortcut(QKeySequence("Cmd+E"))
        export_action.triggered.connect(self._export_analysis)
        export_action.setEnabled(False)  # Enabled when file is loaded
        file_menu.addAction(export_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        # Cue point actions
        for i in range(1, 10):
            cue_action = QAction(f"Set Cue Point {i}", self)
            cue_action.setShortcut(QKeySequence(f"Cmd+{i}"))
            cue_action.triggered.connect(lambda checked, num=i: self._set_cue_point(num))
            edit_menu.addAction(cue_action)
        
        edit_menu.addSeparator()
        
        # Clear cues action
        clear_cues_action = QAction("Clear All Cues", self)
        clear_cues_action.triggered.connect(self._clear_all_cues)
        edit_menu.addAction(clear_cues_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        # Zoom actions
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)
        
        fit_window_action = QAction("Fit to Window", self)
        fit_window_action.setShortcut(QKeySequence("Cmd+0"))
        fit_window_action.triggered.connect(self._fit_to_window)
        view_menu.addAction(fit_window_action)
        
        view_menu.addSeparator()
        
        # Toggle stereo/mono
        toggle_stereo_action = QAction("Toggle Stereo/Mono", self)
        toggle_stereo_action.setShortcut(QKeySequence("Cmd+M"))
        toggle_stereo_action.triggered.connect(self._toggle_stereo_mono)
        view_menu.addAction(toggle_stereo_action)
        
        # Analysis menu
        analysis_menu = menubar.addMenu("Analysis")
        
        detect_bpm_action = QAction("Detect BPM", self)
        detect_bpm_action.triggered.connect(self._detect_bpm)
        analysis_menu.addAction(detect_bpm_action)
        
        find_structure_action = QAction("Find Structure", self)
        find_structure_action.triggered.connect(self._find_structure)
        analysis_menu.addAction(find_structure_action)
        
        analysis_menu.addSeparator()
        
        export_serato_action = QAction("Export to Serato", self)
        export_serato_action.triggered.connect(self._export_to_serato)
        analysis_menu.addAction(export_serato_action)
    
    def _create_central_widget(self) -> None:
        """Create the main central widget with splitter layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create horizontal splitter for main content
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create waveform view (main area)
        self.waveform_view = WaveformView(self.config, self)
        
        # Create sidebar for cues and structure
        self.sidebar = Sidebar(self.config, self)
        self.sidebar.set_cue_manager(self.cue_manager)
        self.sidebar.set_structure_analyzer(self.structure_analyzer)
        self.sidebar.cue_jump_requested.connect(self._jump_to_position)
        self.sidebar.cue_selected.connect(self._on_cue_selected)

        # Create navigation controls (Phase 3)
        self.navigation_controls = NavigationControls(self.config, self)
        self.navigation_controls.view_changed.connect(self._on_view_changed)
        self.navigation_controls.zoom_changed.connect(self._on_zoom_changed)
        self.navigation_controls.position_changed.connect(self._jump_to_position)

        # Add widgets to splitter
        main_splitter.addWidget(self.waveform_view)
        main_splitter.addWidget(self.sidebar)
        main_splitter.addWidget(self.navigation_controls)
        
        # Set splitter proportions (waveform gets most space)
        sidebar_width = self.config.get('ui', {}).get('sidebar_width', 300)
        main_splitter.setSizes([1000, sidebar_width])
        
        # Add splitter to main layout
        main_layout.addWidget(main_splitter)
        
        # Create transport bar
        self.transport_bar = TransportBar(self.config, self)
        self.transport_bar.set_audio_engine(self.audio_engine)
        main_layout.addWidget(self.transport_bar)
    
    def _create_status_bar(self) -> None:
        """Create status bar with performance indicators."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add permanent widgets for performance monitoring
        self.fps_label = self.status_bar.addPermanentWidget(None)
        self.memory_label = self.status_bar.addPermanentWidget(None)
        
        # Initial status
        self.status_bar.showMessage("Ready - Drag and drop audio files to begin")
    
    def _setup_drag_drop(self) -> None:
        """Enable drag and drop for audio files."""
        self.setAcceptDrops(True)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Connect file loaded signal
        self.file_loaded.connect(self._on_file_loaded)

        # Connect waveform view signals
        if hasattr(self.waveform_view, 'zoom_changed'):
            self.waveform_view.zoom_changed.connect(self._on_zoom_changed)
        if hasattr(self.waveform_view, 'position_clicked'):
            self.waveform_view.position_clicked.connect(self._jump_to_position)
        if hasattr(self.waveform_view, 'cue_requested'):
            self.waveform_view.cue_requested.connect(self._set_cue_point)

        # Connect transport bar signals
        self.transport_bar.play_requested.connect(self._play_audio)
        self.transport_bar.pause_requested.connect(self._pause_audio)
        self.transport_bar.stop_requested.connect(self._stop_audio)
        self.transport_bar.seek_requested.connect(self._seek_audio)
        self.transport_bar.volume_changed.connect(self._set_volume)
        self.transport_bar.speed_changed.connect(self._set_speed)
        self.transport_bar.device_changed.connect(self._set_audio_device)

        # Connect audio engine signals
        self.audio_engine.position_changed.connect(self._on_playback_position_changed)
    
    def _setup_performance_monitoring(self) -> None:
        """Setup performance monitoring with enhanced callbacks."""
        # Setup performance monitor callbacks
        self.performance_monitor.add_fps_callback(self._on_fps_update)
        self.performance_monitor.add_memory_callback(self._on_memory_update)
        self.performance_monitor.add_optimization_callback(self._on_optimization_suggestion)

        # Setup UI update timer
        self.performance_timer = QTimer()
        self.performance_timer.timeout.connect(self._update_performance_display)
        self.performance_timer.start(1000)  # Update every second

    def _on_fps_update(self, fps: float) -> None:
        """Handle FPS updates from performance monitor."""
        # This runs in background thread, so we just store the value
        # UI updates happen in _update_performance_display
        pass

    def _on_memory_update(self, memory_mb: float) -> None:
        """Handle memory updates from performance monitor."""
        # Check for memory warnings
        if memory_mb > self.audio_loader.memory_limit_mb * 0.9:
            self.logger.warning(f"Memory usage high: {memory_mb:.1f}MB")

    def _on_optimization_suggestion(self, suggestion: str) -> None:
        """Handle optimization suggestions from performance monitor."""
        self.logger.info(f"Performance suggestion: {suggestion}")
        # Could show user notification here in future
    
    # Event handlers
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter events for file drops."""
        if event.mimeData().hasUrls():
            # Check if any URLs are audio files
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = Path(url.toLocalFile())
                    if self._is_supported_audio_file(file_path):
                        event.acceptProposedAction()
                        return
        event.ignore()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """Handle file drop events."""
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = Path(url.toLocalFile())
                if self._is_supported_audio_file(file_path):
                    self._load_audio_file(file_path)
                    break  # Load only the first supported file
    
    # Utility methods
    def _is_supported_audio_file(self, file_path: Path) -> bool:
        """Check if file is a supported audio format."""
        supported_formats = self.config.get('audio', {}).get('supported_formats', [])
        return file_path.suffix.lower().lstrip('.') in supported_formats
    
    def _load_audio_file(self, file_path: Path) -> None:
        """Load an audio file for analysis with metadata and cues."""
        try:
            self.current_file = file_path
            self.status_bar.showMessage(f"Loading: {file_path.name}...")

            # Load audio data
            self.current_audio_data = self.audio_loader.load_audio(file_path)

            # Load metadata
            self._load_metadata_async(file_path)

            # Setup cue manager for this track
            self.cue_manager.set_track(file_path, self.current_audio_data.duration * 1000)

            # Load existing cues from metadata
            self._load_existing_cues_async(file_path)

            # Load into waveform view
            self.waveform_view.load_audio_data(self.current_audio_data)

            # Load into navigation controls (Phase 3)
            self.navigation_controls.set_audio_data(self.current_audio_data)

            # Load into audio engine for playback (Critical)
            self.audio_engine.load_audio(self.current_audio_data)
            self.transport_bar.set_duration(self.current_audio_data.duration)

            # Start beat analysis in background
            self._analyze_beats_async()

            # Start structure analysis in background (Phase 3)
            self._analyze_structure_async()

            self.file_loaded.emit(str(file_path))
            self.status_bar.showMessage(f"Loaded: {file_path.name} - Analyzing...")
            self.logger.info(f"Loaded audio file: {file_path}")

        except AudioLoadError as e:
            self.logger.error(f"Failed to load audio file: {e}")
            QMessageBox.critical(self, "Audio Load Error", str(e))
        except Exception as e:
            self.logger.error(f"Unexpected error loading audio file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load audio file:\n{e}")

    def _load_metadata_async(self, file_path: Path) -> None:
        """Load metadata in background thread."""
        def load_task():
            try:
                metadata = self.metadata_parser.read_metadata(file_path)
                self._on_metadata_loaded(metadata)
            except Exception as e:
                self.logger.warning(f"Failed to load metadata: {e}")
                self._on_metadata_loaded(None)

        import threading
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()

    def _load_existing_cues_async(self, file_path: Path) -> None:
        """Load existing cues from metadata in background thread."""
        def load_task():
            try:
                # Try to load Serato cues first
                import mutagen
                audio_file = mutagen.File(str(file_path))

                if audio_file:
                    serato_cues = self.serato_bridge.read_serato_cues(audio_file)
                    if serato_cues:
                        self._on_cues_loaded(serato_cues)
                        return

                # TODO: Try to load from JSON sidecar file
                # json_file = file_path.with_suffix('.cuepoint.json')
                # if json_file.exists():
                #     with open(json_file) as f:
                #         cue_data = json.load(f)
                #         self.cue_manager.import_from_json(cue_data)

            except Exception as e:
                self.logger.warning(f"Failed to load existing cues: {e}")

        import threading
        thread = threading.Thread(target=load_task, daemon=True)
        thread.start()

    def _on_metadata_loaded(self, metadata: Optional[TrackMetadata]) -> None:
        """Handle loaded metadata."""
        self.current_metadata = metadata

        if metadata:
            # Update window title with track info
            title_parts = []
            if metadata.artist:
                title_parts.append(metadata.artist)
            if metadata.title:
                title_parts.append(metadata.title)

            if title_parts:
                track_info = " - ".join(title_parts)
                self.setWindowTitle(f"CUEpoint - {track_info}")

            # Update status with BPM if available
            if metadata.bpm:
                self.status_bar.showMessage(f"Loaded: {metadata.bpm:.1f} BPM detected in metadata", 3000)

            self.logger.info(f"Metadata loaded: {metadata.artist} - {metadata.title}")

    def _on_cues_loaded(self, cues: List[CuePoint]) -> None:
        """Handle loaded cue points."""
        for cue in cues:
            try:
                self.cue_manager.cue_points[cue.id] = cue
            except Exception as e:
                self.logger.warning(f"Failed to load cue {cue.id}: {e}")

        # Update sidebar display
        cue_points = self.cue_manager.get_all_cue_points()
        self.sidebar.update_cue_points(cue_points)

        self.logger.info(f"Loaded {len(cues)} existing cue points")

    def _analyze_structure_async(self) -> None:
        """Analyze musical structure in background thread."""
        if not self.current_audio_data:
            return

        def analyze_task():
            try:
                # Perform structure analysis
                structure_result = self.structure_analyzer.analyze_structure(
                    self.current_audio_data,
                    self.current_beatgrid_data
                )

                # Update UI in main thread
                self._on_structure_analyzed(structure_result)

            except Exception as e:
                self.logger.error(f"Structure analysis failed: {e}")
                self._on_structure_analyzed(None)

        import threading
        thread = threading.Thread(target=analyze_task, daemon=True)
        thread.start()

    def _on_structure_analyzed(self, structure_result: Optional[StructureAnalysisResult]) -> None:
        """Handle completed structure analysis."""
        self.current_structure_data = structure_result

        if structure_result and structure_result.sections:
            # Update sidebar with structure sections
            self.sidebar.update_structure_sections(structure_result.sections)

            # Update waveform view with structure overlays
            self.waveform_view.set_structure_sections(structure_result.sections)

            # Update status
            section_count = len(structure_result.sections)
            confidence = structure_result.confidence
            self.status_bar.showMessage(
                f"Structure analysis complete: {section_count} sections "
                f"({confidence:.1%} confidence)", 3000
            )

            self.logger.info(f"Structure analysis complete: {section_count} sections, "
                           f"{confidence:.1%} confidence")
        else:
            self.logger.warning("Structure analysis failed or returned no sections")

    def _on_view_changed(self, start_time: float, end_time: float) -> None:
        """Handle view range change from navigation controls."""
        # Update waveform view range
        if hasattr(self.waveform_view, 'set_view_range'):
            self.waveform_view.set_view_range(start_time, end_time)

        self.logger.debug(f"View changed: {start_time:.2f}s - {end_time:.2f}s")

    def _on_zoom_changed(self, zoom_level: float) -> None:
        """Handle zoom level change from navigation controls."""
        # Update waveform view zoom
        if hasattr(self.waveform_view, 'set_zoom_level'):
            self.waveform_view.set_zoom_level(zoom_level)

        self.logger.debug(f"Zoom changed: {zoom_level:.1f}x")

    def _update_visual_overlays(self) -> None:
        """Update all visual overlays on waveform view."""
        if not self.current_audio_data:
            return

        # Update cue point overlays
        cue_points = self.cue_manager.get_all_cue_points()
        self.waveform_view.set_cue_points(cue_points)

        # Update structure overlays
        if self.current_structure_data and self.current_structure_data.sections:
            self.waveform_view.set_structure_sections(self.current_structure_data.sections)

        # Update navigation view range
        if hasattr(self.waveform_view, 'get_view_range'):
            start_time, end_time = self.waveform_view.get_view_range()
            self.navigation_controls.set_view_range(start_time, end_time)

    # Audio Playback Methods (Critical Implementation)
    def _play_audio(self) -> None:
        """Start audio playback."""
        if not self.current_audio_data:
            QMessageBox.information(self, "No Audio", "Please load an audio file first.")
            return

        success = self.audio_engine.play()
        if not success:
            QMessageBox.warning(self, "Playback Error", "Failed to start audio playback.")
            self.logger.error("Failed to start audio playback")

    def _pause_audio(self) -> None:
        """Pause audio playback."""
        success = self.audio_engine.pause()
        if not success:
            self.logger.error("Failed to pause audio playback")

    def _stop_audio(self) -> None:
        """Stop audio playback."""
        success = self.audio_engine.stop()
        if not success:
            self.logger.error("Failed to stop audio playback")

    def _seek_audio(self, position_seconds: float) -> None:
        """Seek to specific position in audio."""
        success = self.audio_engine.seek(position_seconds)
        if success:
            # Update waveform view position
            self.waveform_view.set_playback_position(position_seconds)
            self.logger.debug(f"Seeked to {position_seconds:.2f}s")
        else:
            self.logger.error(f"Failed to seek to {position_seconds:.2f}s")

    def _set_volume(self, volume: float) -> None:
        """Set audio playback volume."""
        self.audio_engine.set_volume(volume)
        self.logger.debug(f"Volume set to {volume:.2f}")

    def _set_speed(self, speed: float) -> None:
        """Set audio playback speed."""
        self.audio_engine.set_speed(speed)
        self.logger.debug(f"Speed set to {speed:.2f}")

    def _set_audio_device(self, device_id: int) -> None:
        """Set audio output device."""
        success = self.audio_engine.set_audio_device(device_id)
        if not success:
            QMessageBox.warning(self, "Device Error", "Failed to set audio device.")
            self.logger.error(f"Failed to set audio device {device_id}")

    def _on_playback_position_changed(self, position: float) -> None:
        """Handle playback position updates from audio engine."""
        # Update waveform view
        self.waveform_view.set_playback_position(position)

        # Update navigation controls
        if hasattr(self.navigation_controls, 'set_current_position'):
            self.navigation_controls.set_current_position(position)

    def _analyze_beats_async(self) -> None:
        """Analyze beats in background thread."""
        if not self.current_audio_data:
            return

        def analyze_task():
            try:
                beatgrid_data = self.beatgrid_engine.analyze_beats(self.current_audio_data)
                # Update UI in main thread
                self._on_beats_analyzed(beatgrid_data)
            except BeatgridError as e:
                self.logger.warning(f"Beat analysis failed: {e}")
                self._on_beats_analysis_failed(str(e))
            except Exception as e:
                self.logger.error(f"Unexpected error in beat analysis: {e}")
                self._on_beats_analysis_failed(str(e))

        # Run in background thread
        import threading
        thread = threading.Thread(target=analyze_task, daemon=True)
        thread.start()

    def _on_beats_analyzed(self, beatgrid_data: BeatgridData) -> None:
        """Handle successful beat analysis."""
        self.current_beatgrid_data = beatgrid_data

        # Load into waveform view
        self.waveform_view.load_beatgrid_data(beatgrid_data)

        # Update status
        self.status_bar.showMessage(
            f"Analysis complete: {beatgrid_data.bpm:.1f} BPM "
            f"({beatgrid_data.confidence:.0%} confidence)"
        )

        self.logger.info(f"Beat analysis complete: {beatgrid_data.bpm:.1f} BPM")

    def _on_beats_analysis_failed(self, error_msg: str) -> None:
        """Handle failed beat analysis."""
        self.status_bar.showMessage(f"Beat analysis failed: {error_msg}")
        self.logger.warning(f"Beat analysis failed: {error_msg}")
    
    # Menu action handlers (placeholders for now)
    def _open_file_dialog(self) -> None:
        """Open file dialog to select audio file."""
        supported_formats = self.config.get('audio', {}).get('supported_formats', [])
        filter_str = "Audio Files (" + " ".join(f"*.{fmt}" for fmt in supported_formats) + ")"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Audio File", "", filter_str
        )
        
        if file_path:
            self._load_audio_file(Path(file_path))
    
    def _export_analysis(self) -> None:
        """Export analysis data."""
        # Placeholder - will be implemented in later phases
        pass
    
    def _set_cue_point(self, number: int) -> None:
        """Set cue point at current position."""
        if not self.current_audio_data:
            QMessageBox.information(self, "No Audio", "Please load an audio file first.")
            return

        # Get current playback position from audio engine
        current_position = self.audio_engine.get_position()

        try:
            position_ms = current_position * 1000.0
            cue_point = self.cue_manager.add_cue_point(number, position_ms)

            # Update sidebar display
            cue_points = self.cue_manager.get_all_cue_points()
            self.sidebar.update_cue_points(cue_points)

            # Update waveform visual overlays (Phase 3)
            self._update_visual_overlays()

            self.status_bar.showMessage(f"Cue {number} set at {current_position:.2f}s", 2000)
            self.logger.info(f"Cue {number} set at {current_position:.2f}s")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to set cue point: {e}")
            self.logger.error(f"Failed to set cue point {number}: {e}")

    def _jump_to_position(self, position_seconds: float) -> None:
        """Jump to specific position in track."""
        if not self.current_audio_data:
            return

        # Clamp position to track duration
        position_seconds = max(0, min(position_seconds, self.current_audio_data.duration))

        # Seek audio engine to position
        self.audio_engine.seek(position_seconds)

        # Update waveform view position
        self.waveform_view.set_playback_position(position_seconds)

        self.status_bar.showMessage(f"Jumped to {position_seconds:.2f}s", 1000)
        self.logger.debug(f"Jumped to position {position_seconds:.2f}s")

    def _on_cue_selected(self, cue_id: int) -> None:
        """Handle cue selection from sidebar."""
        # Highlight cue in sidebar
        self.sidebar.highlight_cue(cue_id)

        # TODO: Highlight cue in waveform view

        self.logger.debug(f"Cue {cue_id} selected")
    
    def _clear_all_cues(self) -> None:
        """Clear all cue points."""
        # Placeholder - will be implemented in Phase 2
        pass
    
    def _zoom_in(self) -> None:
        """Zoom in on waveform."""
        if hasattr(self.waveform_view, 'zoom_in'):
            self.waveform_view.zoom_in()
    
    def _zoom_out(self) -> None:
        """Zoom out on waveform."""
        if hasattr(self.waveform_view, 'zoom_out'):
            self.waveform_view.zoom_out()
    
    def _fit_to_window(self) -> None:
        """Fit waveform to window."""
        if hasattr(self.waveform_view, 'fit_to_window'):
            self.waveform_view.fit_to_window()
    
    def _toggle_stereo_mono(self) -> None:
        """Toggle between stereo and mono display."""
        if hasattr(self.waveform_view, 'toggle_stereo_mono'):
            self.waveform_view.toggle_stereo_mono()
    
    def _detect_bpm(self) -> None:
        """Detect BPM of current track."""
        if not self.current_audio_data:
            QMessageBox.information(self, "No Audio", "Please load an audio file first.")
            return

        self.status_bar.showMessage("Re-analyzing beats...")
        self._analyze_beats_async()
    
    def _find_structure(self) -> None:
        """Find musical structure of current track."""
        # Placeholder - will be implemented in Phase 3
        pass
    
    def _export_to_serato(self) -> None:
        """Export analysis to Serato format."""
        # Placeholder - will be implemented in Phase 2
        pass
    
    # Signal handlers
    def _on_file_loaded(self, file_path: str) -> None:
        """Handle file loaded signal."""
        # Enable menu actions that require a loaded file
        for action in self.menuBar().actions():
            if action.text() == "File":
                for sub_action in action.menu().actions():
                    if "Export" in sub_action.text():
                        sub_action.setEnabled(True)
    
    def _on_zoom_changed(self, zoom_level: float) -> None:
        """Handle zoom level changes."""
        self.status_bar.showMessage(f"Zoom: {zoom_level:.1f}x", 2000)
    
    # Performance monitoring
    def _update_performance_display(self) -> None:
        """Update performance display in status bar."""
        try:
            # Get current metrics from performance monitor
            metrics = self.performance_monitor.get_current_metrics()

            # Update FPS display
            if hasattr(self, 'fps_label') and self.fps_label:
                if metrics.fps > 0:
                    fps_text = f"FPS: {metrics.fps:.1f}"
                    if metrics.avg_fps > 0:
                        fps_text += f" (avg: {metrics.avg_fps:.1f})"
                else:
                    fps_text = "FPS: --"
                self.fps_label.setText(fps_text)

            # Update memory display
            if hasattr(self, 'memory_label') and self.memory_label:
                if metrics.memory_mb > 0:
                    memory_text = f"RAM: {metrics.memory_mb:.1f}MB"
                    if metrics.memory_percent > 0:
                        memory_text += f" ({metrics.memory_percent:.1f}%)"
                else:
                    memory_text = "RAM: --"
                self.memory_label.setText(memory_text)

            # Record frame for FPS calculation if waveform is active
            if hasattr(self, 'waveform_view') and self.waveform_view:
                self.performance_monitor.record_frame()

        except Exception as e:
            self.logger.warning(f"Failed to update performance display: {e}")

    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        return self.performance_monitor.get_performance_report()

    def cleanup_performance_monitoring(self) -> None:
        """Clean up performance monitoring resources."""
        if hasattr(self, 'performance_monitor'):
            self.performance_monitor.cleanup()

        if hasattr(self, 'performance_timer'):
            self.performance_timer.stop()
