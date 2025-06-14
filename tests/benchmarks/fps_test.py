#!/usr/bin/env python3
"""
FPS Performance Benchmark for WaveformView
Tests GPU rendering performance and measures sustained FPS
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt
import numpy as np

from gui.waveform_view import WaveformView
from core.audio_loader import AudioData, AudioLoader
from core.beatgrid_engine import BeatgridEngine, BeatgridData


class FPSBenchmark:
    """FPS benchmark for waveform rendering."""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        
        # Test configuration
        self.config = {
            'waveform': {
                'theme': 'dark',
                'colors': {
                    'background': '#1A1A1A',
                    'peaks': '#00FF88',
                    'rms': '#004422',
                    'beatgrid': '#FF6B35',
                    'downbeat': '#FF6B35'
                },
                'zoom': {
                    'min': 1,
                    'max': 128,
                    'default': 4
                },
                'rendering': {
                    'target_fps': 60,
                    'use_opengl': True,
                    'fallback_to_cpu': True,
                    'line_width': 1,
                    'rms_alpha': 0.6
                }
            },
            'audio': {
                'sample_rate': 44100,
                'supported_formats': ['wav']
            },
            'beatgrid': {
                'algorithms': ['madmom_dbn'],
                'confidence_threshold': 0.8,
                'bpm_range': [60, 200]
            }
        }
        
        self.waveform_view = None
        self.fps_samples = []
        self.test_duration = 10.0  # seconds
        self.start_time = None
        
    def generate_test_audio(self, duration: float = 30.0) -> AudioData:
        """Generate synthetic audio for testing."""
        sample_rate = 44100
        samples = int(sample_rate * duration)
        
        # Generate complex waveform with multiple frequencies
        t = np.linspace(0, duration, samples)
        
        # Left channel: mix of frequencies
        left = (np.sin(2 * np.pi * 440 * t) +  # A4
                0.5 * np.sin(2 * np.pi * 880 * t) +  # A5
                0.3 * np.sin(2 * np.pi * 220 * t))   # A3
        
        # Right channel: slightly different mix
        right = (np.sin(2 * np.pi * 440 * t) +
                 0.4 * np.sin(2 * np.pi * 660 * t) +  # E5
                 0.2 * np.sin(2 * np.pi * 110 * t))   # A2
        
        # Add some noise for realism
        left += 0.1 * np.random.normal(0, 1, samples)
        right += 0.1 * np.random.normal(0, 1, samples)
        
        # Normalize
        left = left / np.max(np.abs(left))
        right = right / np.max(np.abs(right))
        
        # Combine to stereo
        stereo_data = np.array([left, right])
        
        return AudioData(
            data=stereo_data,
            sample_rate=sample_rate,
            duration=duration,
            channels=2,
            file_path=Path("synthetic_test.wav"),
            format="wav",
            bit_depth=16,
            file_size=samples * 4,  # 16-bit stereo
            load_time=0.1
        )
    
    def generate_test_beatgrid(self, audio_data: AudioData, bpm: float = 128.0) -> BeatgridData:
        """Generate synthetic beatgrid for testing."""
        beat_interval = 60.0 / bpm
        n_beats = int(audio_data.duration / beat_interval)
        
        beats = np.arange(n_beats) * beat_interval
        downbeats = beats[::4]  # Every 4th beat
        
        return BeatgridData(
            bpm=bpm,
            confidence=0.95,
            beats=beats,
            downbeats=downbeats,
            time_signature=(4, 4),
            tempo_changes=[],
            algorithm_used='synthetic',
            analysis_time=0.0,
            manual_override=False
        )
    
    def setup_waveform_view(self):
        """Setup waveform view for testing."""
        self.waveform_view = WaveformView(self.config)
        self.waveform_view.resize(1920, 400)  # Typical waveform size
        self.waveform_view.show()
        
        # Generate test data
        print("Generating test audio data...")
        audio_data = self.generate_test_audio(30.0)
        beatgrid_data = self.generate_test_beatgrid(audio_data)
        
        # Load into waveform view
        print("Loading data into waveform view...")
        self.waveform_view.load_audio_data(audio_data)
        self.waveform_view.load_beatgrid_data(beatgrid_data)
        
        print(f"Waveform view setup complete - OpenGL: {self.waveform_view.use_opengl}")
    
    def run_fps_test(self):
        """Run FPS performance test."""
        print(f"Starting FPS test for {self.test_duration} seconds...")
        
        self.start_time = time.time()
        self.fps_samples = []
        
        # Setup timer to collect FPS samples
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.collect_fps_sample)
        self.fps_timer.start(100)  # Collect every 100ms
        
        # Setup timer to end test
        self.end_timer = QTimer()
        self.end_timer.timeout.connect(self.end_test)
        self.end_timer.start(int(self.test_duration * 1000))
        
        # Start zoom animation to stress test rendering
        self.zoom_timer = QTimer()
        self.zoom_timer.timeout.connect(self.animate_zoom)
        self.zoom_timer.start(50)  # Change zoom every 50ms
        
        # Run event loop
        self.app.exec()
    
    def collect_fps_sample(self):
        """Collect FPS sample."""
        if self.waveform_view:
            fps = self.waveform_view.get_current_fps()
            self.fps_samples.append(fps)
            
            elapsed = time.time() - self.start_time
            print(f"Time: {elapsed:.1f}s, FPS: {fps:.1f}")
    
    def animate_zoom(self):
        """Animate zoom level to stress test rendering."""
        if not self.waveform_view:
            return
        
        # Cycle through zoom levels
        elapsed = time.time() - self.start_time
        zoom_cycle = 4.0  # 4 second cycle
        phase = (elapsed % zoom_cycle) / zoom_cycle * 2 * np.pi
        
        # Zoom between 1x and 16x
        zoom_level = 1 + 15 * (np.sin(phase) + 1) / 2
        
        # Apply zoom (simplified - would need proper implementation)
        # self.waveform_view.set_zoom_level(zoom_level)
    
    def end_test(self):
        """End the FPS test and report results."""
        self.fps_timer.stop()
        self.end_timer.stop()
        self.zoom_timer.stop()
        
        if self.fps_samples:
            avg_fps = np.mean(self.fps_samples)
            min_fps = np.min(self.fps_samples)
            max_fps = np.max(self.fps_samples)
            std_fps = np.std(self.fps_samples)
            
            print("\n" + "="*50)
            print("FPS BENCHMARK RESULTS")
            print("="*50)
            print(f"Test Duration: {self.test_duration:.1f} seconds")
            print(f"OpenGL Enabled: {self.waveform_view.use_opengl}")
            print(f"Average FPS: {avg_fps:.1f}")
            print(f"Minimum FPS: {min_fps:.1f}")
            print(f"Maximum FPS: {max_fps:.1f}")
            print(f"FPS Std Dev: {std_fps:.1f}")
            print(f"Target FPS: {self.config['waveform']['rendering']['target_fps']}")
            
            # Performance assessment
            target_fps = self.config['waveform']['rendering']['target_fps']
            if avg_fps >= target_fps * 0.9:
                print("✅ PASS: Performance meets target")
            elif avg_fps >= target_fps * 0.7:
                print("⚠️  WARN: Performance below target but acceptable")
            else:
                print("❌ FAIL: Performance significantly below target")
            
            print("="*50)
        
        self.app.quit()


def main():
    """Run FPS benchmark."""
    print("CUEpoint Waveform FPS Benchmark")
    print("Testing GPU-accelerated waveform rendering performance")
    print()
    
    benchmark = FPSBenchmark()
    
    try:
        benchmark.setup_waveform_view()
        benchmark.run_fps_test()
    except Exception as e:
        print(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
