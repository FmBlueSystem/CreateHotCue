#!/bin/bash
# CUEpoint Development Environment Setup Script
# Optimized for macOS

set -e  # Exit on any error

echo "🎚️ CUEpoint Development Environment Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_warning "This script is optimized for macOS. Some features may not work on other platforms."
fi

# Check for Homebrew
print_status "Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    print_error "Homebrew not found. Please install Homebrew first:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi
print_success "Homebrew found"

# Check for Python 3.11+
print_status "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python 3.11+ required, found $PYTHON_VERSION"
        print_status "Installing Python 3.11 via Homebrew..."
        brew install python@3.11
    fi
else
    print_error "Python 3 not found. Installing via Homebrew..."
    brew install python@3.11
fi

# Install system dependencies
print_status "Installing system dependencies..."

# FFmpeg for audio processing
if ! command -v ffmpeg &> /dev/null; then
    print_status "Installing FFmpeg..."
    brew install ffmpeg
else
    print_success "FFmpeg already installed"
fi

# PortAudio for low-latency audio
if ! pkg-config --exists portaudio-2.0; then
    print_status "Installing PortAudio..."
    brew install portaudio
else
    print_success "PortAudio already installed"
fi

# pkg-config for dependency detection
if ! command -v pkg-config &> /dev/null; then
    print_status "Installing pkg-config..."
    brew install pkg-config
else
    print_success "pkg-config already installed"
fi

# Optional: create-dmg for building DMG packages
if ! command -v create-dmg &> /dev/null; then
    print_status "Installing create-dmg (for building DMG packages)..."
    brew install create-dmg
else
    print_success "create-dmg already installed"
fi

# Create virtual environment
print_status "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install -r requirements.txt

# Install development dependencies
print_status "Installing development dependencies..."
pip install -e ".[dev,profiling]"

# Verify installations
print_status "Verifying installations..."

# Check PyQt6
python -c "import PyQt6; print('PyQt6:', PyQt6.PYQT_VERSION_STR)" 2>/dev/null && print_success "PyQt6 installed" || print_error "PyQt6 installation failed"

# Check PyQtGraph
python -c "import pyqtgraph; print('PyQtGraph:', pyqtgraph.__version__)" 2>/dev/null && print_success "PyQtGraph installed" || print_error "PyQtGraph installation failed"

# Check audio libraries
python -c "import librosa; print('librosa:', librosa.__version__)" 2>/dev/null && print_success "librosa installed" || print_error "librosa installation failed"
python -c "import sounddevice; print('sounddevice:', sounddevice.__version__)" 2>/dev/null && print_success "sounddevice installed" || print_error "sounddevice installation failed"

# Check beat detection libraries
python -c "import madmom; print('madmom: OK')" 2>/dev/null && print_success "madmom installed" || print_warning "madmom installation failed (optional)"
python -c "import aubio; print('aubio: OK')" 2>/dev/null && print_success "aubio installed" || print_warning "aubio installation failed (optional)"

# Run basic tests
print_status "Running basic tests..."
if python -m pytest tests/unit/test_main_window.py -v; then
    print_success "Basic tests passed"
else
    print_warning "Some tests failed - this may be normal during development"
fi

# Create sample test audio file
print_status "Creating sample test audio file..."
python -c "
import numpy as np
import wave
import os

# Create assets/test_tracks directory if it doesn't exist
os.makedirs('assets/test_tracks', exist_ok=True)

# Generate 30 seconds of test audio at 128 BPM
sample_rate = 44100
duration = 30.0
bpm = 128.0
beat_interval = 60.0 / bpm

samples = int(sample_rate * duration)
t = np.linspace(0, duration, samples)

# Generate kick drum pattern
kick_pattern = np.zeros(samples)
for beat_time in np.arange(0, duration, beat_interval):
    beat_sample = int(beat_time * sample_rate)
    if beat_sample < samples:
        # Simple kick drum (low frequency sine burst)
        kick_duration = int(0.1 * sample_rate)
        kick_end = min(beat_sample + kick_duration, samples)
        kick_env = np.exp(-np.arange(kick_end - beat_sample) / (0.02 * sample_rate))
        kick_pattern[beat_sample:kick_end] += kick_env * np.sin(2 * np.pi * 60 * np.arange(kick_end - beat_sample) / sample_rate)

# Add some musical content
music = 0.3 * np.sin(2 * np.pi * 440 * t)  # A4 tone
music += 0.2 * np.sin(2 * np.pi * 880 * t)  # A5 harmony

# Combine
audio = kick_pattern + music

# Normalize
audio = audio / np.max(np.abs(audio)) * 0.8

# Convert to 16-bit stereo
audio_16bit = (audio * 32767).astype(np.int16)
stereo_audio = np.column_stack((audio_16bit, audio_16bit))

# Save as WAV
with wave.open('assets/test_tracks/test_128bpm.wav', 'wb') as wav_file:
    wav_file.setnchannels(2)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)
    wav_file.writeframes(stereo_audio.tobytes())

print('Sample test audio created: assets/test_tracks/test_128bpm.wav')
"

print_success "Sample test audio created"

# Final setup
print_status "Final setup..."

# Make scripts executable
chmod +x scripts/*.sh 2>/dev/null || true

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    cat > .env << EOF
# CUEpoint Development Environment Variables
PYTHONPATH=\${PWD}/src
QT_LOGGING_RULES="*.debug=false"
EOF
    print_success ".env file created"
fi

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "To start developing:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Run the application: make run"
echo "  3. Run tests: make test"
echo "  4. Check code quality: make dev-check"
echo ""
echo "Available make commands:"
echo "  make help          - Show all available commands"
echo "  make run           - Run the application"
echo "  make test          - Run all tests"
echo "  make dev-check     - Run formatting, linting, and tests"
echo "  make build-dmg     - Build macOS DMG package"
echo ""
echo "Happy coding! 🎚️"
