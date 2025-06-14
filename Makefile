# CUEpoint - DJ Waveform & Analysis Suite
# Development Makefile for macOS

.PHONY: help install install-dev test test-unit test-integration test-benchmark
.PHONY: lint format type-check clean run build-dmg
.PHONY: setup-env check-deps profile-memory profile-cpu

# Default target
help:
	@echo "CUEpoint Development Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  setup-env      - Create virtual environment and install dependencies"
	@echo "  install        - Install package in development mode"
	@echo "  install-dev    - Install with development dependencies"
	@echo "  check-deps     - Check system dependencies (ffmpeg, portaudio)"
	@echo ""
	@echo "Development:"
	@echo "  run            - Run the application"
	@echo "  format         - Format code with black"
	@echo "  lint           - Run linting with ruff"
	@echo "  type-check     - Run type checking with mypy"
	@echo ""
	@echo "Testing:"
	@echo "  test           - Run all tests"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-benchmark - Run performance benchmarks"
	@echo ""
	@echo "Profiling:"
	@echo "  profile-memory - Profile memory usage"
	@echo "  profile-cpu    - Profile CPU usage"
	@echo ""
	@echo "Build & Distribution:"
	@echo "  build-dmg      - Build macOS DMG package"
	@echo "  clean          - Clean build artifacts"

# Python and pip executables
PYTHON := python3
PIP := pip3
VENV := venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

# Setup virtual environment
setup-env:
	@echo "Setting up development environment..."
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip setuptools wheel
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PIP) install -e ".[dev,profiling]"
	@echo "Environment setup complete. Activate with: source $(VENV)/bin/activate"

# Check system dependencies
check-deps:
	@echo "Checking system dependencies..."
	@command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg not found. Install with: brew install ffmpeg"; exit 1; }
	@command -v pkg-config >/dev/null 2>&1 || { echo "pkg-config not found. Install with: brew install pkg-config"; exit 1; }
	@pkg-config --exists portaudio-2.0 || { echo "portaudio not found. Install with: brew install portaudio"; exit 1; }
	@echo "All system dependencies found ✓"

# Installation targets
install: check-deps
	$(PIP) install -e .

install-dev: check-deps
	$(PIP) install -e ".[dev,profiling]"

# Run application
run:
	$(PYTHON) src/main.py

# Code formatting and linting
format:
	black src/ tests/
	@echo "Code formatting complete ✓"

lint:
	ruff check src/ tests/
	@echo "Linting complete ✓"

type-check:
	mypy src/
	@echo "Type checking complete ✓"

# Testing targets
test: test-unit test-integration
	@echo "All tests complete ✓"

test-unit:
	pytest tests/unit/ -v --cov=src --cov-report=term-missing

test-integration:
	pytest tests/integration/ -v

test-benchmark:
	@echo "Running performance benchmarks..."
	$(PYTHON) tests/benchmarks/fps_test.py
	$(PYTHON) tests/benchmarks/latency_test.py
	$(PYTHON) tests/benchmarks/memory_test.py

# Profiling
profile-memory:
	@echo "Profiling memory usage..."
	$(PYTHON) -m memory_profiler src/main.py

profile-cpu:
	@echo "Profiling CPU usage..."
	$(PYTHON) -m cProfile -o profile.stats src/main.py
	$(PYTHON) -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"

# Build and distribution
build-dmg: clean
	@echo "Building macOS DMG package..."
	$(PYTHON) setup.py py2app
	@if command -v create-dmg >/dev/null 2>&1; then \
		create-dmg \
			--volname "CUEpoint v2.1" \
			--window-pos 200 120 \
			--window-size 600 400 \
			--icon-size 100 \
			--icon "CUEpoint.app" 175 120 \
			--hide-extension "CUEpoint.app" \
			--app-drop-link 425 120 \
			"CUEpoint-v2.1.dmg" \
			"dist/"; \
	else \
		echo "create-dmg not found. Install with: brew install create-dmg"; \
		exit 1; \
	fi
	@echo "DMG package created: CUEpoint-v2.1.dmg"

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -f profile.stats
	rm -f *.log
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete ✓"

# Development workflow shortcuts
dev-setup: setup-env check-deps
	@echo "Development environment ready!"

dev-check: format lint type-check test-unit
	@echo "Development checks passed ✓"

# CI simulation
ci-test: format lint type-check test
	@echo "CI simulation complete ✓"

# Quick development cycle
quick-test: format lint test-unit
	@echo "Quick development cycle complete ✓"
