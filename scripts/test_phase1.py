#!/usr/bin/env python3
"""
Phase 1 Quick Test Script
Verifies that all Phase 1 components work correctly
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        # Core modules
        from core.audio_loader import AudioLoader, AudioData, AudioLoadError
        print("✅ AudioLoader imported successfully")
        
        from core.beatgrid_engine import BeatgridEngine, BeatgridData, BeatgridError
        print("✅ BeatgridEngine imported successfully")
        
        # GUI modules
        from gui.waveform_view import WaveformView
        print("✅ WaveformView imported successfully")
        
        from gui.main_window import MainWindow
        print("✅ MainWindow imported successfully")
        
        # External dependencies
        import numpy as np
        print("✅ NumPy imported successfully")
        
        import PyQt6
        print(f"✅ PyQt6 {PyQt6.PYQT_VERSION_STR} imported successfully")
        
        import pyqtgraph as pg
        print(f"✅ PyQtGraph {pg.__version__} imported successfully")
        
        import librosa
        print(f"✅ librosa {librosa.__version__} imported successfully")
        
        # Optional dependencies
        try:
            import madmom
            print("✅ madmom imported successfully")
        except ImportError:
            print("⚠️  madmom not available (optional)")
        
        try:
            import aubio
            print("✅ aubio imported successfully")
        except ImportError:
            print("⚠️  aubio not available (optional)")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_audio_loader():
    """Test AudioLoader functionality."""
    print("\nTesting AudioLoader...")
    
    try:
        # Load config
        import json
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Create AudioLoader
        from core.audio_loader import AudioLoader
        loader = AudioLoader(config)
        print("✅ AudioLoader created successfully")
        
        # Test format detection
        assert loader.is_supported_format("test.mp3") == True
        assert loader.is_supported_format("test.xyz") == False
        print("✅ Format detection working")
        
        # Test synthetic audio generation
        import numpy as np
        sample_rate = 44100
        duration = 1.0
        samples = int(sample_rate * duration)
        
        # Generate stereo test audio
        t = np.linspace(0, duration, samples)
        left = np.sin(2 * np.pi * 440 * t)  # A4
        right = np.sin(2 * np.pi * 880 * t)  # A5
        stereo_data = np.array([left, right])
        
        # Test waveform data generation
        from core.audio_loader import AudioData
        audio_data = AudioData(
            data=stereo_data,
            sample_rate=sample_rate,
            duration=duration,
            channels=2,
            file_path=Path("test.wav"),
            format="wav",
            bit_depth=16,
            file_size=samples * 4,
            load_time=0.1
        )
        
        waveform_data = loader.generate_waveform_data(audio_data, [1, 2, 4])
        assert len(waveform_data) == 3
        print("✅ Waveform data generation working")
        
        # Test RMS calculation
        rms_data = loader.calculate_rms_energy(audio_data)
        assert rms_data.shape[0] == 2  # Two channels
        print("✅ RMS energy calculation working")
        
        return True
        
    except Exception as e:
        print(f"❌ AudioLoader test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_beatgrid_engine():
    """Test BeatgridEngine functionality."""
    print("\nTesting BeatgridEngine...")
    
    try:
        # Load config
        import json
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Create BeatgridEngine
        from core.beatgrid_engine import BeatgridEngine
        engine = BeatgridEngine(config)
        print("✅ BeatgridEngine created successfully")
        
        # Test manual tap tempo
        tap_times = [0.0, 0.5, 1.0, 1.5, 2.0]  # 120 BPM
        bpm = engine.manual_tap_tempo(tap_times)
        assert abs(bpm - 120.0) < 1.0
        print("✅ Manual tap tempo working")
        
        # Test beatgrid adjustment
        import numpy as np
        from core.beatgrid_engine import BeatgridData
        
        original_beatgrid = BeatgridData(
            bpm=128.0,
            confidence=0.9,
            beats=np.array([0.0, 0.46875, 0.9375, 1.40625]),
            downbeats=np.array([0.0, 1.875]),
            time_signature=(4, 4),
            tempo_changes=[],
            algorithm_used='test',
            analysis_time=1.0,
            manual_override=False
        )
        
        adjusted = engine.adjust_beatgrid(original_beatgrid, 0.1, 130.0)
        assert adjusted.bpm == 130.0
        assert adjusted.manual_override == True
        print("✅ Beatgrid adjustment working")
        
        return True
        
    except Exception as e:
        print(f"❌ BeatgridEngine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gui_creation():
    """Test GUI component creation."""
    print("\nTesting GUI components...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
            app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        
        # Load config
        import json
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Test WaveformView creation
        from gui.waveform_view import WaveformView
        waveform_view = WaveformView(config)
        print("✅ WaveformView created successfully")
        
        # Test MainWindow creation
        from gui.main_window import MainWindow
        main_window = MainWindow(config)
        print("✅ MainWindow created successfully")
        
        # Test that components are connected
        assert hasattr(main_window, 'waveform_view')
        assert hasattr(main_window, 'audio_loader')
        assert hasattr(main_window, 'beatgrid_engine')
        print("✅ Component integration working")
        
        return True
        
    except Exception as e:
        print(f"❌ GUI test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        import json
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        
        with open(config_path) as f:
            config = json.load(f)
        
        # Check required sections
        required_sections = ['app', 'audio', 'waveform', 'beatgrid']
        for section in required_sections:
            assert section in config, f"Missing config section: {section}"
        
        print("✅ Configuration loaded successfully")
        print(f"   App: {config['app']['name']} v{config['app']['version']}")
        print(f"   Audio formats: {config['audio']['supported_formats']}")
        print(f"   Target FPS: {config['waveform']['rendering']['target_fps']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def main():
    """Run all Phase 1 tests."""
    print("🎚️ CUEpoint Phase 1 - Quick Test Suite")
    print("=" * 50)
    
    tests = [
        ("Configuration Loading", test_config_loading),
        ("Module Imports", test_imports),
        ("AudioLoader", test_audio_loader),
        ("BeatgridEngine", test_beatgrid_engine),
        ("GUI Components", test_gui_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Phase 1 is ready.")
        print("\nNext steps:")
        print("  1. Run the application: make run")
        print("  2. Load an audio file and test manually")
        print("  3. Run performance benchmarks: make test-benchmark")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
