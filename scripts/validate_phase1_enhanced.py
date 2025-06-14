#!/usr/bin/env python3
"""
Phase 1 Enhanced Validation Script
Comprehensive testing of strengthened Phase 1 implementation
"""

import sys
import os
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_enhanced_audio_loader():
    """Test enhanced AudioLoader with robust error handling."""
    print("\n🎵 Testing Enhanced AudioLoader...")
    
    try:
        from core.audio_loader import AudioLoader, AudioData
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        loader = AudioLoader(config)
        print("✅ AudioLoader created successfully")
        
        # Test validation
        import numpy as np
        valid_data = np.random.random((2, 44100)).astype(np.float32) * 0.5
        assert loader._validate_audio_data(valid_data, 44100) is True
        print("✅ Audio validation working")
        
        # Test memory optimization
        audio_data = AudioData(
            data=valid_data.astype(np.float64),  # Start with float64
            sample_rate=44100,
            duration=1.0,
            channels=2,
            file_path=Path("test.wav"),
            format="wav",
            bit_depth=16,
            file_size=1000,
            load_time=0.1
        )
        
        optimized = loader.optimize_memory_usage(audio_data)
        assert optimized.data.dtype == np.float32
        print("✅ Memory optimization working")
        
        # Test enhanced waveform generation
        waveform_data = loader.generate_waveform_data(audio_data, zoom_levels=[1, 4])
        assert isinstance(waveform_data, dict)
        for zoom_data in waveform_data.values():
            assert 'peaks' in zoom_data
            assert 'rms' in zoom_data
        print("✅ Enhanced waveform generation working")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced AudioLoader test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_beatgrid_engine():
    """Test enhanced BeatgridEngine with improved algorithms."""
    print("\n🥁 Testing Enhanced BeatgridEngine...")
    
    try:
        from core.beatgrid_engine import BeatgridEngine
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        engine = BeatgridEngine(config)
        print("✅ BeatgridEngine created successfully")
        
        # Test beat filtering
        import numpy as np
        beats = np.array([0.0, 0.1, 0.5, 0.51, 1.0, 1.05, 1.5])
        filtered = engine._filter_close_beats(beats, min_interval=0.2)
        assert len(filtered) < len(beats)
        print("✅ Beat filtering working")
        
        # Test BPM calculation
        regular_beats = np.arange(0, 5, 0.5)  # 120 BPM
        bpm, confidence = engine._calculate_bpm_and_confidence(regular_beats)
        assert abs(bpm - 120.0) < 5.0
        assert confidence > 0.5
        print("✅ Enhanced BPM calculation working")
        
        # Test beat interpolation
        original_beats = np.array([0.0, 1.0, 2.0, 3.0])
        interpolated = engine._interpolate_beats(original_beats)
        assert len(interpolated) == 2 * len(original_beats) - 1
        print("✅ Beat interpolation working")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced BeatgridEngine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_monitor():
    """Test PerformanceMonitor functionality."""
    print("\n📊 Testing PerformanceMonitor...")
    
    try:
        from core.performance_monitor import PerformanceMonitor
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        monitor = PerformanceMonitor(config)
        print("✅ PerformanceMonitor created successfully")
        
        # Test FPS recording
        fps = monitor.record_frame()
        assert fps >= 0
        print("✅ FPS recording working")
        
        # Test memory monitoring
        memory_usage = monitor.get_memory_usage()
        assert 'rss_mb' in memory_usage
        assert memory_usage['rss_mb'] > 0
        print("✅ Memory monitoring working")
        
        # Test callbacks
        callback_called = False
        def test_callback(value):
            nonlocal callback_called
            callback_called = True
        
        monitor.add_fps_callback(test_callback)
        monitor.record_frame()
        assert callback_called
        print("✅ Callbacks working")
        
        # Test performance report
        report = monitor.get_performance_report()
        assert 'performance_score' in report
        assert 'current_fps' in report
        print("✅ Performance reporting working")
        
        # Test monitoring start/stop
        monitor.start_monitoring()
        time.sleep(0.1)  # Brief monitoring
        monitor.stop_monitoring()
        print("✅ Background monitoring working")
        
        return True
        
    except Exception as e:
        print(f"❌ PerformanceMonitor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_gui_integration():
    """Test enhanced GUI integration with performance monitoring."""
    print("\n🖥️ Testing Enhanced GUI Integration...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from gui.main_window import MainWindow
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
            app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Create MainWindow with performance monitoring
        window = MainWindow(config)
        print("✅ Enhanced MainWindow created successfully")
        
        # Check performance monitor integration
        assert hasattr(window, 'performance_monitor')
        assert window.performance_monitor is not None
        print("✅ PerformanceMonitor integrated")
        
        # Check callbacks are set up
        assert len(window.performance_monitor.fps_callbacks) > 0
        assert len(window.performance_monitor.memory_callbacks) > 0
        print("✅ Performance callbacks configured")
        
        # Test performance display update
        window._update_performance_display()
        print("✅ Performance display updates working")
        
        # Test performance report generation
        report = window.get_performance_report()
        assert isinstance(report, dict)
        print("✅ Performance report generation working")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced GUI integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling_robustness():
    """Test error handling and robustness improvements."""
    print("\n🛡️ Testing Error Handling & Robustness...")
    
    try:
        from core.audio_loader import AudioLoader, AudioLoadError
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        loader = AudioLoader(config)
        
        # Test handling of non-existent file
        try:
            loader.load_audio("nonexistent_file.mp3")
            assert False, "Should have raised AudioLoadError"
        except AudioLoadError:
            print("✅ Non-existent file error handling working")
        
        # Test handling of invalid audio data
        import numpy as np
        
        # Empty data
        assert loader._validate_audio_data(np.array([]), 44100) is False
        print("✅ Empty data validation working")
        
        # NaN data
        nan_data = np.full((2, 1000), np.nan)
        assert loader._validate_audio_data(nan_data, 44100) is False
        print("✅ NaN data validation working")
        
        # Infinite data
        inf_data = np.full((2, 1000), np.inf)
        assert loader._validate_audio_data(inf_data, 44100) is False
        print("✅ Infinite data validation working")
        
        # Invalid sample rate
        valid_data = np.random.random((2, 1000))
        assert loader._validate_audio_data(valid_data, 0) is False
        assert loader._validate_audio_data(valid_data, -1) is False
        print("✅ Invalid sample rate validation working")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_performance_benchmark():
    """Run a quick performance benchmark."""
    print("\n⚡ Running Performance Benchmark...")
    
    try:
        from core.performance_monitor import PerformanceMonitor
        from core.audio_loader import AudioLoader, AudioData
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Create components
        monitor = PerformanceMonitor(config)
        loader = AudioLoader(config)
        
        # Generate test audio
        import numpy as np
        duration = 10.0  # 10 seconds
        sample_rate = 44100
        samples = int(duration * sample_rate)
        
        print(f"Generating {duration}s test audio...")
        start_time = time.time()
        
        # Generate complex audio
        t = np.linspace(0, duration, samples)
        left = (np.sin(2 * np.pi * 440 * t) + 
                0.5 * np.sin(2 * np.pi * 880 * t) +
                0.3 * np.random.normal(0, 0.1, samples))
        right = (np.sin(2 * np.pi * 660 * t) + 
                 0.4 * np.sin(2 * np.pi * 1320 * t) +
                 0.3 * np.random.normal(0, 0.1, samples))
        
        stereo_data = np.array([left, right])
        generation_time = time.time() - start_time
        print(f"✅ Audio generated in {generation_time:.3f}s")
        
        # Create AudioData
        audio_data = AudioData(
            data=stereo_data,
            sample_rate=sample_rate,
            duration=duration,
            channels=2,
            file_path=Path("benchmark_test.wav"),
            format="wav",
            bit_depth=16,
            file_size=samples * 4,
            load_time=generation_time
        )
        
        # Test waveform generation performance
        print("Testing waveform generation performance...")
        start_time = time.time()
        
        waveform_data = loader.generate_waveform_data(
            audio_data, 
            zoom_levels=[1, 2, 4, 8, 16, 32]
        )
        
        waveform_time = time.time() - start_time
        print(f"✅ Waveform data generated in {waveform_time:.3f}s")
        
        # Test memory usage
        memory_usage = monitor.get_memory_usage()
        print(f"✅ Memory usage: {memory_usage['rss_mb']:.1f}MB")
        
        # Performance summary
        print("\n📊 Performance Summary:")
        print(f"   Audio Generation: {generation_time:.3f}s for {duration}s audio")
        print(f"   Waveform Generation: {waveform_time:.3f}s for 6 zoom levels")
        print(f"   Memory Usage: {memory_usage['rss_mb']:.1f}MB")
        print(f"   Data Size: {audio_data.data.nbytes / (1024*1024):.1f}MB")
        
        # Performance targets
        if waveform_time < 1.0:
            print("✅ Waveform generation meets performance target (<1s)")
        else:
            print("⚠️  Waveform generation slower than target")
        
        if memory_usage['rss_mb'] < 200:
            print("✅ Memory usage within reasonable limits (<200MB)")
        else:
            print("⚠️  Memory usage higher than expected")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all enhanced Phase 1 validation tests."""
    print("🎚️ CUEpoint Phase 1 Enhanced - Validation Suite")
    print("=" * 60)
    
    tests = [
        ("Enhanced AudioLoader", test_enhanced_audio_loader),
        ("Enhanced BeatgridEngine", test_enhanced_beatgrid_engine),
        ("PerformanceMonitor", test_performance_monitor),
        ("Enhanced GUI Integration", test_enhanced_gui_integration),
        ("Error Handling & Robustness", test_error_handling_robustness),
        ("Performance Benchmark", run_performance_benchmark),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 60)
    print(f"📊 Enhanced Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All enhanced tests passed! Phase 1 is robust and ready.")
        print("\n🚀 Phase 1 Strengthening Complete:")
        print("   ✅ Robust error handling and validation")
        print("   ✅ Enhanced performance monitoring")
        print("   ✅ Improved algorithms and optimizations")
        print("   ✅ Memory management and optimization")
        print("   ✅ Comprehensive testing and validation")
        print("\nReady to proceed to Phase 2! 🎯")
        return 0
    else:
        print("⚠️  Some enhanced tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
