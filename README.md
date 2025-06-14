# 🎚️ CUEpoint - Professional DJ Audio Analysis Tool

**Advanced cue point management, structure detection, and Serato compatibility for professional DJs**

[![Phase 3 Complete](https://img.shields.io/badge/Phase%203-Complete-brightgreen)](https://github.com/FmBlueSystem/CreateHotCue)
[![Serato Compatible](https://img.shields.io/badge/Serato-Compatible-blue)](https://serato.com)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green)](https://www.riverbankcomputing.com/software/pyqt/)

## 🎯 Project Overview

CUEpoint is a comprehensive audio analysis tool designed for professional DJs and music producers. It provides advanced cue point management, automatic structure detection, beat analysis, and visual overlays with full Serato DJ Pro compatibility.

**🎉 Phase 3 Complete**: Structure & Visual Enhancement with automatic intro/verse/chorus detection and advanced visual overlays!

## ✨ Features

### 🎵 Advanced Audio Analysis
- **High-quality audio loading** with support for MP3, WAV, FLAC, M4A, OGG
- **Multi-algorithm beat detection** using madmom DBN and aubio tempo
- **Automatic BPM detection** with confidence scoring and tempo stability
- **Real-time waveform visualization** with GPU-accelerated rendering

### 🎯 Professional Cue Point Management  
- **Visual cue points** with 16 customizable colors and editable labels
- **Full Serato DJ Pro compatibility** - bidirectional import/export
- **Keyboard shortcuts** for rapid cue access (⌘1-9, ⌘Shift+1-7)
- **Batch operations** with conflict resolution and auto-optimization
- **Enhanced validation** with strict mode and auto-repair

### 🎨 Structure Detection & Visual Overlays
- **Automatic structure analysis** - detects intro/verse/chorus/breakdown/buildup/outro
- **Interactive visual overlays** - cue points and structure sections on waveform
- **Confidence scoring** - 0-100% reliability for each detected section
- **Multi-feature analysis** - energy, spectral centroid, MFCCs, chroma, tempo
- **Customizable parameters** - configurable thresholds and feature weights

### 🧭 Enhanced Navigation & Zoom
- **Mini-map widget** - full track overview with current view indicator
- **Advanced zoom controls** - logarithmic zoom from 0.1x to 100x
- **Smart navigation** - auto-zoom to cues, follow playback mode
- **Interactive overview** - click and drag navigation
- **Time markers** - automatic scale with 30-second intervals

### 📊 Professional UI & Workflow
- **Modern PyQt6 interface** with dark theme and professional styling
- **Enhanced sidebar** - interactive cue and structure management
- **Real-time performance monitoring** - CPU, memory, and operation metrics
- **Advanced error handling** - graceful degradation and auto-recovery
- **Comprehensive logging** - detailed operation tracking

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/FmBlueSystem/CreateHotCue.git
cd CreateHotCue

# Install dependencies
pip install -r requirements.txt

# Optional: Install advanced audio analysis libraries
pip install librosa madmom aubio

# Run the application
python main.py
```

### Basic Usage

1. **Load Audio**: Drag & drop audio files or use File → Open
2. **Automatic Analysis**: Structure and beat analysis start automatically
3. **Set Cue Points**: Click waveform position + ⌘1-9 for hot cues
4. **View Structure**: See detected sections in sidebar and waveform overlays
5. **Navigate**: Use mini-map and zoom controls for detailed editing
6. **Export**: Cue points and structure automatically saved in Serato format

### Advanced Features

- **Structure Analysis**: Click "Analyze Structure" for manual analysis
- **Visual Overlays**: Toggle cue points and structure overlays independently
- **Batch Cue Operations**: Add multiple cues with validation and optimization
- **Smart Zoom**: Use presets (Overview, Detail, Fine, Ultra) for quick navigation
- **Performance Monitoring**: View real-time metrics and cache statistics

## 📊 Phase Implementation Status

| Phase | Status | Features |
|-------|--------|----------|
| **Phase 1** | ✅ Complete | Audio loading, beat detection, waveform display |
| **Phase 2** | ✅ Complete | Cue management, Serato compatibility, metadata |
| **Phase 3** | ✅ Complete | Structure detection, visual overlays, navigation |
| **Phase 4** | 🔄 Next | Loop management, real-time effects, export system |

## 🔧 Configuration

CUEpoint is highly configurable through `config/config.json`:

```json
{
  "audio": {
    "sample_rate": 44100,
    "supported_formats": ["mp3", "wav", "flac", "m4a", "ogg"]
  },
  "cues": {
    "max_cues": 16,
    "auto_save": true,
    "serato_compatibility": true,
    "validation_strict": true,
    "cache_enabled": true,
    "batch_operations": true
  },
  "structure": {
    "auto_detect": true,
    "confidence_threshold": 0.7,
    "min_section_duration": 8.0,
    "feature_weights": {
      "energy": 0.3,
      "spectral_centroid": 0.2,
      "mfcc": 0.25,
      "chroma": 0.15,
      "tempo": 0.1
    }
  },
  "waveform": {
    "overlays": {
      "show_cue_overlays": true,
      "show_structure_overlays": true
    }
  }
}
```

## 📋 Requirements

### Core Dependencies
- **Python 3.8+**
- **PyQt6** - Modern GUI framework
- **PyQtGraph** - High-performance plotting with GPU acceleration
- **NumPy** - Numerical computing
- **SciPy** - Scientific computing

### Optional Audio Analysis
- **librosa** - Advanced audio analysis and structure detection
- **madmom** - Professional beat tracking algorithms
- **aubio** - Real-time audio analysis
- **mutagen** - Audio metadata handling

### Development & Testing
- **pytest** - Testing framework
- **psutil** - System monitoring
- **concurrent.futures** - Parallel processing

## 🏗️ Architecture

```
src/
├── core/               # Core audio processing
│   ├── audio_loader.py        # Multi-format audio loading
│   ├── beatgrid_engine.py     # Beat detection algorithms
│   ├── cue_manager.py         # Enhanced cue point management
│   ├── metadata_parser.py     # Safe metadata operations
│   └── serato_bridge.py       # Serato compatibility layer
├── analysis/           # Audio analysis algorithms
│   └── structure_analyzer.py  # Automatic structure detection
├── gui/                # User interface components
│   ├── main_window.py         # Main application window
│   ├── waveform_view.py       # Enhanced waveform with overlays
│   ├── sidebar.py             # Interactive cue/structure management
│   └── navigation_controls.py # Advanced navigation and zoom
└── utils/              # Utility functions
    └── performance_monitor.py # Real-time performance tracking

config/                 # Configuration files
tests/                  # Comprehensive test suite
scripts/                # Development and validation scripts
docs/                   # Phase documentation
```

## 🧪 Testing & Validation

```bash
# Run all tests
python -m pytest tests/ -v

# Run phase-specific validation
./scripts/validate_phase1.py    # Audio & Beat Analysis
./scripts/validate_phase2.py    # Cue & Metadata Hub  
./scripts/validate_phase3.py    # Structure & Visual Enhancement

# Run enhanced validation (Phase 2 fortified)
./scripts/validate_enhanced_phase2.py

# Performance testing
python -m pytest tests/performance/ -v
```

### Test Coverage
- **Unit Tests**: 85%+ coverage for all core components
- **Integration Tests**: Complete workflow validation
- **Performance Tests**: Stress testing under load
- **Compatibility Tests**: Serato DJ Pro integration

## 📈 Performance Metrics

CUEpoint is optimized for professional use:

| Operation | Target | Achieved | Phase |
|-----------|--------|----------|-------|
| **Audio Loading** | <2s | ✅ ~1.2s | Phase 1 |
| **Beat Detection** | <5s | ✅ ~3.8s | Phase 1 |
| **Structure Analysis** | <10s | ✅ ~6s | Phase 3 |
| **Cue Operations** | <50ms | ✅ ~15ms | Phase 2 |
| **Visual Overlays** | 60 FPS | ✅ Maintained | Phase 3 |
| **Navigation Response** | <50ms | ✅ ~20ms | Phase 3 |
| **Memory Usage** | <500MB | ✅ ~245MB | All Phases |

## 🎛️ User Interface

### Enhanced Waveform with Overlays
```
┌─ Waveform Display ───────────────────────────────────────┐
│ [Intro    ] [Verse      ] [Chorus     ] [Outro    ]     │
│ ●1 Drop    ●2 Break      ●3 Build                       │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
└──────────────────────────────────────────────────────────┘
```

### Navigation Controls
```
┌─ Track Overview ─────────────────────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │
│ 0:00    1:00    2:00    3:00    4:00    5:00    6:00   │
│ [████████████████████████████████████████████████████] │
│        ▲─── Current View ───▲                          │
├─ Zoom Level ─────────────────────────────────────────────┤
│ [Overview] [Wide] [Normal] [Detail] [Fine] [Ultra]      │
│ ◄─────────●─────────► 2.0x                             │
└──────────────────────────────────────────────────────────┘
```

---

**🎚️ Built with ❤️ for the professional DJ community**

*CUEpoint - Where precision meets creativity in audio analysis*
