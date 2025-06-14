# 🎚️ CUEpoint - DJ Waveform & Analysis Suite v2.1

Professional DJ application for macOS that rivals Serato DJ Pro in waveform quality, beatgrid precision, and musical analysis. Built with PyQt6 and optimized for Apple Silicon and Intel Macs.

## ✨ Features

- **GPU-Accelerated Waveform**: 60 FPS rendering with Metal backend
- **Precision Beatgrid**: ±10ms accuracy with madmom + aubio algorithms  
- **Serato Compatibility**: Full cue point and metadata compatibility
- **Structure Detection**: AI-powered intro/verse/chorus identification
- **Low-Latency Playback**: < 10ms audio latency with Core Audio
- **Multi-Format Support**: MP3, M4A, FLAC, WAV up to 192kHz

## 🖥️ System Requirements

- **macOS**: 12.0+ (Monterey, Ventura, Sonoma)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 2GB free space
- **Audio**: Core Audio compatible interface recommended
- **Display**: 13" (2560×1600) or larger, Retina preferred

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/cuepoint/cuepoint.git
cd cuepoint

# Install dependencies (requires Homebrew)
brew install ffmpeg portaudio python@3.11
pip install -r requirements.txt

# Run application
python src/main.py
```

### First Use

1. **Drag & Drop** audio files (MP3/M4A/FLAC/WAV)
2. **Auto-analysis** detects BPM and structure
3. **Set cue points** with ⌘+1-9 shortcuts
4. **Zoom waveform** with trackpad pinch or ⌘+/-
5. **Export metadata** compatible with Serato DJ

## 🎛️ Interface Overview

```
┌─────────────────────────────────────────────────────────────┐
│ File  Edit  View  Analysis                    🔊 ⏯️ ⏹️ ⏭️    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🌊 GPU Waveform (OpenGL/Metal)                            │
│     ├─ Stereo L/R channels                                 │
│     ├─ Beatgrid overlay                                    │
│     ├─ Structure regions                                   │
│     └─ Cue point markers                                   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Cues & Structure │                                          │
│ 🔴 Cue 1: Intro  │         Transport Controls              │
│ 🔵 Cue 2: Drop   │    ⏮️ ⏯️ ⏭️  🔊────────  ⏱️ 2:34      │
│ 🟡 Cue 3: Break  │                                          │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Configuration

Edit `config/config.json` to customize:

- **Colors**: Waveform, beatgrid, cue point colors
- **Performance**: Buffer sizes, FPS targets, memory limits
- **Shortcuts**: Keyboard and trackpad gestures
- **Analysis**: BPM detection algorithms and thresholds

## 🧪 Development

### Setup Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest --cov=src

# Code formatting
black src/ tests/
ruff check src/ tests/
mypy src/
```

### Project Structure

```
CUEpoint/
├── src/
│   ├── core/           # Audio processing & analysis
│   ├── gui/            # PyQt6 interface components  
│   ├── analysis/       # AI structure detection
│   └── playback/       # Low-latency audio engine
├── tests/              # Unit & integration tests
├── config/             # Configuration files
├── assets/             # Icons, test tracks
└── docs/               # Documentation
```

### Performance Benchmarks

```bash
# FPS measurement
python tests/benchmarks/fps_test.py

# Audio latency test  
python tests/benchmarks/latency_test.py

# Memory profiling
python -m memory_profiler src/main.py
```

## 📊 Quality Metrics

- **Waveform Rendering**: 60 FPS sustained
- **Audio Latency**: < 10ms round-trip
- **BPM Accuracy**: ±10ms vs manual annotation
- **Memory Usage**: ≤ 100MB per loaded track
- **Load Time**: ≤ 2s for 5-minute track
- **Test Coverage**: ≥ 90%

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Code Standards

- **Python**: 3.11+ with type hints
- **Style**: Black formatting, Ruff linting
- **Tests**: pytest-qt for GUI components
- **Documentation**: Docstrings for all public APIs

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **madmom**: Beat tracking algorithms
- **PyQtGraph**: High-performance plotting
- **Serato**: Metadata format inspiration
- **DJ Community**: Feature requests and testing

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/cuepoint/cuepoint/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cuepoint/cuepoint/discussions)
- **Email**: support@cuepoint.app

---

**Made with ❤️ for the DJ community**
