"""
Enhanced Integration Tests for Phase 1 - Robustness and Performance
Tests the strengthened implementation with error handling and optimizations
"""

import pytest
import numpy as np
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.audio_loader import AudioLoader, AudioData, AudioLoadError
from src.core.beatgrid_engine import BeatgridEngine, BeatgridData, BeatgridError
from src.core.performance_monitor import PerformanceMonitor, PerformanceMetrics
from src.gui.main_window import MainWindow


class TestEnhancedAudioLoader:
    """Test enhanced AudioLoader with robust error handling."""
    
    def test_multiple_loading_methods(self, test_config, temp_audio_file):
        """Test that AudioLoader tries multiple methods for loading."""
        loader = AudioLoader(test_config)
        
        # Should successfully load with fallback methods
        audio_data = loader.load_audio(temp_audio_file)
        
        assert isinstance(audio_data, AudioData)
        assert audio_data.duration > 0
        assert audio_data.data.shape[0] > 0
    
    def test_audio_validation(self, test_config):
        """Test audio data validation."""
        loader = AudioLoader(test_config)
        
        # Test valid audio data
        valid_data = np.random.random((2, 44100)).astype(np.float32) * 0.5
        assert loader._validate_audio_data(valid_data, 44100) is True
        
        # Test invalid audio data
        assert loader._validate_audio_data(np.array([]), 44100) is False  # Empty
        assert loader._validate_audio_data(valid_data, 0) is False  # Invalid sample rate
        assert loader._validate_audio_data(np.full((2, 44100), np.nan), 44100) is False  # NaN values
        assert loader._validate_audio_data(np.full((2, 44100), np.inf), 44100) is False  # Inf values
    
    def test_enhanced_waveform_generation(self, test_config, sample_audio_data):
        """Test enhanced waveform data generation with peaks and RMS."""
        loader = AudioLoader(test_config)
        
        # Create AudioData
        audio_data = AudioData(
            data=sample_audio_data['data'].T,
            sample_rate=sample_audio_data['sample_rate'],
            duration=sample_audio_data['duration'],
            channels=sample_audio_data['channels'],
            file_path=Path("test.wav"),
            format="wav",
            bit_depth=16,
            file_size=1000,
            load_time=0.1
        )
        
        waveform_data = loader.generate_waveform_data(audio_data, zoom_levels=[1, 4, 16])
        
        # Check structure
        assert isinstance(waveform_data, dict)
        for zoom in [1, 4, 16]:
            if zoom in waveform_data:
                zoom_data = waveform_data[zoom]
                assert 'peaks' in zoom_data
                assert 'rms' in zoom_data
                assert 'samples_per_pixel' in zoom_data
                
                # Check that peaks and RMS have same shape
                assert zoom_data['peaks'].shape == zoom_data['rms'].shape
    
    def test_memory_optimization(self, test_config, sample_audio_data):
        """Test memory optimization features."""
        loader = AudioLoader(test_config)
        
        # Create AudioData with float64 (should be optimized to float32)
        audio_data = AudioData(
            data=sample_audio_data['data'].T.astype(np.float64),
            sample_rate=sample_audio_data['sample_rate'],
            duration=sample_audio_data['duration'],
            channels=sample_audio_data['channels'],
            file_path=Path("test.wav"),
            format="wav",
            bit_depth=16,
            file_size=1000,
            load_time=0.1
        )
        
        # Optimize memory usage
        optimized_data = loader.optimize_memory_usage(audio_data)
        
        # Should convert to float32
        assert optimized_data.data.dtype == np.float32
    
    def test_audio_chunking(self, test_config):
        """Test audio chunking for large files."""
        loader = AudioLoader(test_config)
        
        # Create large audio data (2 minutes)
        duration = 120.0
        sample_rate = 44100
        samples = int(duration * sample_rate)
        large_audio_data = AudioData(
            data=np.random.random((2, samples)).astype(np.float32),
            sample_rate=sample_rate,
            duration=duration,
            channels=2,
            file_path=Path("large_test.wav"),
            format="wav",
            bit_depth=16,
            file_size=samples * 4,
            load_time=1.0
        )
        
        # Chunk into 60-second pieces
        chunks = loader.create_audio_chunks(large_audio_data, chunk_duration=60.0)
        
        assert len(chunks) == 2  # Should be split into 2 chunks
        assert all(chunk.duration <= 60.0 for chunk in chunks)
        
        # Total duration should be preserved
        total_duration = sum(chunk.duration for chunk in chunks)
        assert abs(total_duration - duration) < 0.1


class TestEnhancedBeatgridEngine:
    """Test enhanced BeatgridEngine with improved algorithms."""
    
    def test_beat_filtering(self, test_config):
        """Test filtering of beats that are too close together."""
        engine = BeatgridEngine(test_config)
        
        # Create beats with some too close together
        beats = np.array([0.0, 0.1, 0.5, 0.51, 1.0, 1.05, 1.5])  # Some beats < 200ms apart
        
        filtered_beats = engine._filter_close_beats(beats, min_interval=0.2)
        
        # Should remove beats that are too close
        assert len(filtered_beats) < len(beats)
        
        # Check that remaining beats are properly spaced
        if len(filtered_beats) > 1:
            intervals = np.diff(filtered_beats)
            assert np.all(intervals >= 0.2)
    
    def test_bpm_confidence_calculation(self, test_config):
        """Test improved BPM and confidence calculation."""
        engine = BeatgridEngine(test_config)
        
        # Create regular beats (120 BPM = 0.5s intervals)
        regular_beats = np.arange(0, 10, 0.5)
        bpm, confidence = engine._calculate_bpm_and_confidence(regular_beats)
        
        assert abs(bpm - 120.0) < 1.0  # Should detect 120 BPM
        assert confidence > 0.8  # Should have high confidence
        
        # Create irregular beats
        irregular_beats = np.array([0.0, 0.3, 0.8, 1.4, 2.1])  # Irregular intervals
        bpm, confidence = engine._calculate_bpm_and_confidence(irregular_beats)
        
        assert confidence < 0.8  # Should have lower confidence
    
    def test_beat_interpolation(self, test_config):
        """Test beat interpolation for BPM correction."""
        engine = BeatgridEngine(test_config)
        
        original_beats = np.array([0.0, 1.0, 2.0, 3.0])
        interpolated_beats = engine._interpolate_beats(original_beats)
        
        # Should double the number of beats
        assert len(interpolated_beats) == 2 * len(original_beats) - 1
        
        # Check that interpolated beats are in correct positions
        expected = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
        np.testing.assert_array_almost_equal(interpolated_beats, expected)


class TestPerformanceMonitor:
    """Test PerformanceMonitor functionality."""
    
    def test_performance_monitor_creation(self, test_config):
        """Test PerformanceMonitor creation and basic functionality."""
        monitor = PerformanceMonitor(test_config)
        
        assert monitor.target_fps == test_config['waveform']['rendering']['target_fps']
        assert monitor.memory_limit_mb == test_config['audio']['memory_limit_mb']
    
    def test_fps_recording(self, test_config):
        """Test FPS recording and calculation."""
        monitor = PerformanceMonitor(test_config)
        
        # Simulate frames at 60 FPS
        frame_interval = 1.0 / 60.0
        
        for i in range(10):
            time.sleep(frame_interval)
            fps = monitor.record_frame()
            
            if i > 0:  # Skip first frame (no previous frame time)
                assert 50 < fps < 70  # Should be around 60 FPS (with some tolerance)
        
        # Check metrics
        metrics = monitor.get_current_metrics()
        assert metrics.avg_fps > 0
        assert len(monitor.fps_history) > 0
    
    def test_memory_monitoring(self, test_config):
        """Test memory usage monitoring."""
        monitor = PerformanceMonitor(test_config)
        
        memory_usage = monitor.get_memory_usage()
        
        assert 'rss_mb' in memory_usage
        assert 'vms_mb' in memory_usage
        assert 'percent' in memory_usage
        assert memory_usage['rss_mb'] > 0
    
    def test_performance_callbacks(self, test_config):
        """Test performance monitoring callbacks."""
        monitor = PerformanceMonitor(test_config)
        
        fps_values = []
        memory_values = []
        optimization_suggestions = []
        
        def fps_callback(fps):
            fps_values.append(fps)
        
        def memory_callback(memory_mb):
            memory_values.append(memory_mb)
        
        def optimization_callback(suggestion):
            optimization_suggestions.append(suggestion)
        
        monitor.add_fps_callback(fps_callback)
        monitor.add_memory_callback(memory_callback)
        monitor.add_optimization_callback(optimization_callback)
        
        # Trigger some events
        monitor.record_frame()
        monitor.get_memory_usage()
        
        # Callbacks should have been called
        assert len(fps_values) > 0
        assert len(memory_values) > 0
    
    def test_performance_score(self, test_config):
        """Test performance score calculation."""
        monitor = PerformanceMonitor(test_config)
        
        # Simulate some performance data
        monitor.current_metrics.avg_fps = 60.0
        monitor.current_metrics.memory_mb = 50.0
        monitor.current_metrics.frame_drops = 0
        monitor._frame_count = 100
        
        score = monitor._calculate_performance_score()
        
        assert 0 <= score <= 100
        assert score > 80  # Should be high with good performance
    
    def test_performance_report(self, test_config):
        """Test comprehensive performance report generation."""
        monitor = PerformanceMonitor(test_config)
        
        # Record some data
        monitor.record_frame()
        monitor.get_memory_usage()
        
        report = monitor.get_performance_report()
        
        required_fields = [
            'current_fps', 'average_fps', 'fps_range',
            'memory_mb', 'memory_percent', 'cpu_percent',
            'render_time_ms', 'frame_drops', 'total_frames',
            'target_fps', 'memory_limit_mb', 'performance_score'
        ]
        
        for field in required_fields:
            assert field in report


@pytest.mark.integration
class TestEnhancedMainWindow:
    """Test enhanced MainWindow with performance monitoring."""
    
    def test_main_window_with_performance_monitor(self, qapp, test_config):
        """Test MainWindow with integrated performance monitoring."""
        window = MainWindow(test_config)
        
        # Check that performance monitor is initialized
        assert hasattr(window, 'performance_monitor')
        assert window.performance_monitor is not None
        
        # Check that callbacks are set up
        assert len(window.performance_monitor.fps_callbacks) > 0
        assert len(window.performance_monitor.memory_callbacks) > 0
        assert len(window.performance_monitor.optimization_callbacks) > 0
    
    def test_performance_display_update(self, qapp, test_config):
        """Test performance display updates in UI."""
        window = MainWindow(test_config)
        
        # Simulate some performance data
        window.performance_monitor.current_metrics.fps = 60.0
        window.performance_monitor.current_metrics.avg_fps = 58.5
        window.performance_monitor.current_metrics.memory_mb = 75.0
        window.performance_monitor.current_metrics.memory_percent = 5.2
        
        # Update display
        window._update_performance_display()
        
        # Should not raise any exceptions
        assert True
    
    def test_performance_report_generation(self, qapp, test_config):
        """Test performance report generation from MainWindow."""
        window = MainWindow(test_config)
        
        report = window.get_performance_report()
        
        assert isinstance(report, dict)
        assert 'performance_score' in report
        assert 'current_fps' in report
        assert 'memory_mb' in report
