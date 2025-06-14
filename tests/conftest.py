"""
Pytest configuration and fixtures for CUEpoint tests
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    yield app
    # Don't quit the app as it might be used by other tests


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Provide test configuration."""
    return {
        "app": {
            "name": "CUEpoint Test",
            "version": "2.1.0-test",
            "window": {
                "width": 800,
                "height": 600,
                "min_width": 600,
                "min_height": 400
            }
        },
        "audio": {
            "sample_rate": 44100,
            "buffer_size": 256,
            "max_latency_ms": 10,
            "supported_formats": ["mp3", "m4a", "flac", "wav"],
            "max_file_size_mb": 100,
            "memory_limit_mb": 50
        },
        "waveform": {
            "theme": "dark",
            "colors": {
                "background": "#1A1A1A",
                "peaks": "#00FF88",
                "rms": "#004422",
                "beatgrid": "#FF6B35",
                "downbeat": "#FF6B35",
                "cue_colors": ["#FF3366", "#33AAFF", "#FFAA33"]
            },
            "zoom": {
                "min": 1,
                "max": 128,
                "default": 4,
                "smooth_factor": 0.1
            },
            "rendering": {
                "target_fps": 60,
                "use_opengl": False,  # Disable for tests
                "fallback_to_cpu": True,
                "line_width": 1,
                "rms_alpha": 0.6
            }
        },
        "ui": {
            "theme": "dark",
            "font_family": "Arial",
            "font_size": 12,
            "sidebar_width": 200,
            "transport_height": 50
        },
        "performance": {
            "enable_profiling": False,
            "log_fps": False,
            "memory_monitoring": False
        }
    }


@pytest.fixture
def temp_config_file(test_config) -> Path:
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f, indent=2)
        return Path(f.name)


@pytest.fixture
def sample_audio_data():
    """Generate sample audio data for testing."""
    import numpy as np
    
    # Generate 5 seconds of test audio (44.1kHz, stereo)
    sample_rate = 44100
    duration = 5.0
    samples = int(sample_rate * duration)
    
    # Generate sine wave with some harmonics
    t = np.linspace(0, duration, samples)
    frequency = 440.0  # A4
    
    # Left channel: fundamental + 3rd harmonic
    left = (np.sin(2 * np.pi * frequency * t) + 
            0.3 * np.sin(2 * np.pi * frequency * 3 * t))
    
    # Right channel: fundamental + 5th harmonic  
    right = (np.sin(2 * np.pi * frequency * t) + 
             0.2 * np.sin(2 * np.pi * frequency * 5 * t))
    
    # Normalize to 16-bit range
    left = (left * 32767).astype(np.int16)
    right = (right * 32767).astype(np.int16)
    
    # Combine to stereo
    stereo = np.column_stack((left, right))
    
    return {
        'data': stereo,
        'sample_rate': sample_rate,
        'duration': duration,
        'channels': 2
    }


@pytest.fixture
def temp_audio_file(sample_audio_data):
    """Create temporary audio file for testing."""
    import wave
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        # Write WAV file
        with wave.open(f.name, 'wb') as wav_file:
            wav_file.setnchannels(sample_audio_data['channels'])
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_audio_data['sample_rate'])
            wav_file.writeframes(sample_audio_data['data'].tobytes())
        
        return Path(f.name)


@pytest.fixture
def mock_beatgrid_data():
    """Generate mock beatgrid data."""
    return {
        'bpm': 128.0,
        'confidence': 0.95,
        'beats': [0.0, 0.46875, 0.9375, 1.40625, 1.875, 2.34375, 2.8125, 3.28125, 3.75, 4.21875, 4.6875],
        'downbeats': [0.0, 1.875, 3.75],
        'time_signature': (4, 4)
    }


@pytest.fixture
def mock_cue_points():
    """Generate mock cue points."""
    return [
        {
            'id': 1,
            'position_ms': 0.0,
            'label': 'Intro',
            'color': '#FF3366',
            'type': 'HOT_CUE'
        },
        {
            'id': 2, 
            'position_ms': 30000.0,
            'label': 'Drop',
            'color': '#33AAFF',
            'type': 'HOT_CUE'
        },
        {
            'id': 3,
            'position_ms': 120000.0,
            'label': 'Break',
            'color': '#FFAA33',
            'type': 'HOT_CUE'
        }
    ]


@pytest.fixture
def mock_structure_data():
    """Generate mock structure analysis data."""
    return {
        'regions': [
            {
                'type': 'intro',
                'start_ms': 0.0,
                'end_ms': 30000.0,
                'confidence': 0.9
            },
            {
                'type': 'verse',
                'start_ms': 30000.0,
                'end_ms': 60000.0,
                'confidence': 0.85
            },
            {
                'type': 'chorus',
                'start_ms': 60000.0,
                'end_ms': 120000.0,
                'confidence': 0.92
            },
            {
                'type': 'breakdown',
                'start_ms': 120000.0,
                'end_ms': 150000.0,
                'confidence': 0.88
            },
            {
                'type': 'outro',
                'start_ms': 150000.0,
                'end_ms': 180000.0,
                'confidence': 0.9
            }
        ]
    }
