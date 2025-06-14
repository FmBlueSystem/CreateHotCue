#!/usr/bin/env python3
"""
CUEpoint - DJ Waveform & Analysis Suite
Setup script for macOS distribution
"""

import os
import sys
from setuptools import setup, find_packages

# Read version from config
import json
with open('config/config.json', 'r') as f:
    config = json.load(f)
    VERSION = config['app']['version']

# Read requirements
with open('requirements.txt', 'r') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read README for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="cuepoint",
    version=VERSION,
    author="CUEpoint Team",
    author_email="dev@cuepoint.app",
    description="Professional DJ Waveform & Analysis Suite",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cuepoint/cuepoint",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Sound/Audio :: Analysis",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-qt>=4.2.0", 
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "ruff>=0.0.287",
            "mypy>=1.5.0",
        ],
        "profiling": [
            "memory-profiler>=0.61.0",
            "line-profiler>=4.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "cuepoint=cuepoint.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "cuepoint": [
            "config/*.json",
            "assets/*.png",
            "assets/*.icns",
        ],
    },
    # macOS specific options
    options={
        "bdist_dmg": {
            "volume_label": "CUEpoint v2.1",
            "applications_shortcut": True,
        },
        "py2app": {
            "argv_emulation": True,
            "plist": {
                "CFBundleName": "CUEpoint",
                "CFBundleDisplayName": "CUEpoint",
                "CFBundleGetInfoString": "DJ Waveform & Analysis Suite",
                "CFBundleIdentifier": "com.cuepoint.app",
                "CFBundleVersion": VERSION,
                "CFBundleShortVersionString": VERSION,
                "NSHumanReadableCopyright": "Copyright © 2024 CUEpoint Team",
                "NSHighResolutionCapable": True,
                "LSMinimumSystemVersion": "12.0",
                "CFBundleDocumentTypes": [
                    {
                        "CFBundleTypeName": "Audio Files",
                        "CFBundleTypeRole": "Viewer",
                        "LSItemContentTypes": [
                            "public.mp3",
                            "public.mpeg-4-audio",
                            "org.xiph.flac",
                            "public.aiff-audio",
                            "public.aifc-audio",
                            "com.microsoft.waveform-audio"
                        ]
                    }
                ]
            },
            "iconfile": "assets/icon.icns",
            "resources": ["config/", "assets/"],
        }
    },
    zip_safe=False,
)
