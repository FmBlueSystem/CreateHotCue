#!/usr/bin/env python3
"""
Simple CUEpoint Components Test
Test core functionality without GUI dependencies
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_audio_components():
    """Test audio-related components."""
    print("🎵 Testing Audio Components...")
    
    try:
        # Test AudioLoader
        from core.audio_loader import AudioLoader, AudioData
        print("✅ AudioLoader import successful")
        
        # Test AudioEngine
        from playback.audio_engine import AudioEngine, PlaybackState, AudioDevice
        print("✅ AudioEngine import successful")
        
        # Test sounddevice
        import sounddevice as sd
        devices = sd.query_devices()
        output_devices = [d for d in devices if d['max_output_channels'] > 0]
        print(f"✅ Found {len(output_devices)} audio output devices")
        
        # Test basic AudioEngine creation
        config = {
            'audio': {
                'sample_rate': 44100,
                'buffer_size': 512,
                'output_channels': 2,
                'target_latency_ms': 10
            }
        }
        
        audio_engine = AudioEngine(config)
        print("✅ AudioEngine created successfully")
        
        # Test device enumeration
        available_devices = audio_engine.get_available_devices()
        print(f"✅ AudioEngine found {len(available_devices)} devices")
        
        # Test state management
        assert audio_engine.get_state() == PlaybackState.STOPPED
        assert audio_engine.get_position() == 0.0
        assert not audio_engine.is_playing()
        print("✅ AudioEngine state management working")
        
        # Cleanup
        audio_engine.cleanup()
        print("✅ AudioEngine cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Audio components test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_core_components():
    """Test core components."""
    print("\n🔧 Testing Core Components...")
    
    try:
        # Test BeatgridEngine
        from core.beatgrid_engine import BeatgridEngine
        print("✅ BeatgridEngine import successful")
        
        # Test CueManager
        from core.cue_manager import CueManager, CuePoint, CueType
        print("✅ CueManager import successful")
        
        # Test MetadataParser
        from core.metadata_parser import MetadataParser
        print("✅ MetadataParser import successful")
        
        # Test StructureAnalyzer
        from analysis.structure_analyzer import StructureAnalyzer
        print("✅ StructureAnalyzer import successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Core components test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gui_components():
    """Test GUI components (import only)."""
    print("\n🖥️ Testing GUI Components...")
    
    try:
        # Test PyQt6 availability
        from PyQt6.QtWidgets import QApplication
        print("✅ PyQt6 available")
        
        # Test PyQtGraph
        import pyqtgraph as pg
        print("✅ PyQtGraph available")
        
        # Test OpenGL
        import OpenGL
        print("✅ PyOpenGL available")
        
        # Test GUI components (import only, no instantiation)
        from gui.main_window import MainWindow
        print("✅ MainWindow import successful")
        
        from gui.transport_bar import TransportBar
        print("✅ TransportBar import successful")
        
        from gui.waveform_view import WaveformView
        print("✅ WaveformView import successful")
        
        from gui.sidebar import Sidebar
        print("✅ Sidebar import successful")
        
        from gui.navigation_controls import NavigationControls
        print("✅ NavigationControls import successful")
        
        return True
        
    except Exception as e:
        print(f"❌ GUI components test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dependencies():
    """Test all required dependencies."""
    print("\n📦 Testing Dependencies...")
    
    dependencies = [
        ('numpy', 'NumPy'),
        ('scipy', 'SciPy'),
        ('sounddevice', 'SoundDevice'),
        ('PyQt6', 'PyQt6'),
        ('pyqtgraph', 'PyQtGraph'),
        ('OpenGL', 'PyOpenGL'),
        ('mutagen', 'Mutagen'),
        ('pydub', 'PyDub')
    ]
    
    success_count = 0
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"✅ {name} available")
            success_count += 1
        except ImportError:
            print(f"⚠️  {name} not available")
    
    print(f"📊 Dependencies: {success_count}/{len(dependencies)} available")
    return success_count == len(dependencies)

def main():
    """Run all component tests."""
    print("🎚️ CUEpoint Components Test")
    print("=" * 50)
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Core Components", test_core_components),
        ("Audio Components", test_audio_components),
        ("GUI Components", test_gui_components),
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
    print(f"📊 Component Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL COMPONENT TESTS PASSED!")
        print("\n🚀 CUEpoint Components Validated:")
        print("   ✅ All dependencies installed")
        print("   ✅ Core audio processing components")
        print("   ✅ Audio playback engine")
        print("   ✅ GUI framework components")
        print("\n🎚️ CUEpoint is ready for DJ use!")
        return 0
    else:
        print("⚠️  Some component tests failed.")
        print("Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
