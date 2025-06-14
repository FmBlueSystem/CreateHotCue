"""
Audio Loader - Multi-format audio loading and processing
Supports MP3, M4A, FLAC, WAV with FFmpeg backend
Optimized for macOS with memory-efficient streaming
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

import numpy as np
from pydub import AudioSegment
from pydub.utils import which
import librosa
import soundfile as sf


@dataclass
class AudioData:
    """Container for loaded audio data."""
    data: np.ndarray  # Audio samples (channels, samples)
    sample_rate: int  # Sample rate in Hz
    duration: float   # Duration in seconds
    channels: int     # Number of channels
    file_path: Path   # Original file path
    format: str       # Original format (mp3, flac, etc.)
    bit_depth: int    # Bit depth
    file_size: int    # File size in bytes
    load_time: float  # Time taken to load in seconds


class AudioLoadError(Exception):
    """Custom exception for audio loading errors."""
    pass


class AudioLoader:
    """
    Multi-format audio loader with streaming support.
    Handles MP3, M4A, FLAC, WAV files with automatic format detection.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Audio processing settings
        self.target_sample_rate = config.get('audio', {}).get('sample_rate', 44100)
        self.max_file_size_mb = config.get('audio', {}).get('max_file_size_mb', 500)
        self.memory_limit_mb = config.get('audio', {}).get('memory_limit_mb', 100)
        self.supported_formats = config.get('audio', {}).get('supported_formats', 
                                                           ['mp3', 'm4a', 'flac', 'wav'])
        
        # Thread pool for background loading
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="AudioLoader")
        self._loading_lock = threading.Lock()
        
        # Check FFmpeg availability
        self._check_dependencies()
        
        self.logger.info(f"AudioLoader initialized - target SR: {self.target_sample_rate}Hz")
    
    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        # Check FFmpeg
        ffmpeg_path = which("ffmpeg")
        if not ffmpeg_path:
            self.logger.warning("FFmpeg not found - some formats may not be supported")
        else:
            self.logger.info(f"FFmpeg found at: {ffmpeg_path}")
        
        # Set FFmpeg path for pydub
        if ffmpeg_path:
            AudioSegment.converter = ffmpeg_path
            AudioSegment.ffmpeg = ffmpeg_path
            AudioSegment.ffprobe = which("ffprobe") or ffmpeg_path.replace("ffmpeg", "ffprobe")
    
    def is_supported_format(self, file_path: Union[str, Path]) -> bool:
        """Check if file format is supported."""
        file_path = Path(file_path)
        extension = file_path.suffix.lower().lstrip('.')
        return extension in self.supported_formats
    
    def get_file_info(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Get basic file information without loading audio data."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise AudioLoadError(f"File not found: {file_path}")
        
        if not self.is_supported_format(file_path):
            raise AudioLoadError(f"Unsupported format: {file_path.suffix}")
        
        # Check file size
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > self.max_file_size_mb:
            raise AudioLoadError(f"File too large: {file_size_mb:.1f}MB > {self.max_file_size_mb}MB")
        
        try:
            # Use librosa to get basic info (faster than loading full audio)
            info = sf.info(str(file_path))
            
            return {
                'file_path': file_path,
                'format': file_path.suffix.lower().lstrip('.'),
                'sample_rate': info.samplerate,
                'channels': info.channels,
                'frames': info.frames,
                'duration': info.duration,
                'file_size': file_size,
                'file_size_mb': file_size_mb
            }
            
        except Exception as e:
            # Fallback to pydub for formats not supported by soundfile
            try:
                audio_segment = AudioSegment.from_file(str(file_path))
                duration = len(audio_segment) / 1000.0  # Convert ms to seconds
                
                return {
                    'file_path': file_path,
                    'format': file_path.suffix.lower().lstrip('.'),
                    'sample_rate': audio_segment.frame_rate,
                    'channels': audio_segment.channels,
                    'frames': int(duration * audio_segment.frame_rate),
                    'duration': duration,
                    'file_size': file_size,
                    'file_size_mb': file_size_mb
                }
            except Exception as e2:
                raise AudioLoadError(f"Failed to read file info: {e2}")
    
    def load_audio(self, file_path: Union[str, Path], 
                   normalize: bool = True,
                   mono: bool = False) -> AudioData:
        """
        Load audio file with automatic format detection and processing.
        
        Args:
            file_path: Path to audio file
            normalize: Whether to normalize audio to [-1, 1] range
            mono: Whether to convert to mono (mix down stereo)
            
        Returns:
            AudioData object with loaded audio and metadata
        """
        start_time = time.time()
        file_path = Path(file_path)
        
        self.logger.info(f"Loading audio file: {file_path.name}")
        
        # Get file info first
        file_info = self.get_file_info(file_path)
        
        try:
            # Load audio data
            audio_data, original_sr = self._load_audio_data(file_path)
            
            # Process audio
            processed_data = self._process_audio(
                audio_data, original_sr, normalize, mono
            )
            
            # Calculate final properties
            channels = processed_data.shape[0] if processed_data.ndim > 1 else 1
            duration = processed_data.shape[-1] / self.target_sample_rate
            
            load_time = time.time() - start_time
            
            result = AudioData(
                data=processed_data,
                sample_rate=self.target_sample_rate,
                duration=duration,
                channels=channels,
                file_path=file_path,
                format=file_info['format'],
                bit_depth=16,  # We normalize to float32, but original is typically 16-bit
                file_size=file_info['file_size'],
                load_time=load_time
            )
            
            self.logger.info(f"Audio loaded successfully in {load_time:.2f}s - "
                           f"{channels}ch, {duration:.1f}s, {self.target_sample_rate}Hz")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to load audio: {e}")
            raise AudioLoadError(f"Failed to load {file_path.name}: {e}")
    
    def _load_audio_data(self, file_path: Path) -> Tuple[np.ndarray, int]:
        """Load raw audio data using the best available method with robust fallbacks."""
        loading_methods = [
            ("librosa", self._load_with_librosa),
            ("soundfile", self._load_with_soundfile),
            ("pydub", self._load_with_pydub),
        ]

        last_error = None

        for method_name, method_func in loading_methods:
            try:
                self.logger.debug(f"Trying {method_name} for {file_path.name}")
                audio_data, sample_rate = method_func(file_path)

                # Validate loaded data
                if self._validate_audio_data(audio_data, sample_rate):
                    self.logger.debug(f"Successfully loaded with {method_name}")
                    return audio_data, sample_rate
                else:
                    raise AudioLoadError(f"Invalid audio data from {method_name}")

            except Exception as e:
                self.logger.debug(f"{method_name} failed: {e}")
                last_error = e
                continue

        # All methods failed
        raise AudioLoadError(f"All loading methods failed. Last error: {last_error}")

    def _load_with_librosa(self, file_path: Path) -> Tuple[np.ndarray, int]:
        """Load audio using librosa."""
        audio_data, sample_rate = librosa.load(
            str(file_path),
            sr=None,  # Keep original sample rate
            mono=False  # Keep original channels
        )

        # Ensure 2D array (channels, samples)
        if audio_data.ndim == 1:
            audio_data = audio_data.reshape(1, -1)
        elif audio_data.ndim == 2 and audio_data.shape[0] > audio_data.shape[1]:
            # If samples x channels, transpose to channels x samples
            audio_data = audio_data.T

        return audio_data, sample_rate

    def _load_with_soundfile(self, file_path: Path) -> Tuple[np.ndarray, int]:
        """Load audio using soundfile (faster for some formats)."""
        import soundfile as sf

        audio_data, sample_rate = sf.read(str(file_path), always_2d=True)

        # soundfile returns (samples, channels), we need (channels, samples)
        audio_data = audio_data.T

        return audio_data, sample_rate

    def _load_with_pydub(self, file_path: Path) -> Tuple[np.ndarray, int]:
        """Load audio using pydub (most compatible)."""
        audio_segment = AudioSegment.from_file(str(file_path))

        # Convert to numpy array
        samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)

        # Handle different bit depths
        if audio_segment.sample_width == 1:  # 8-bit
            samples = samples / (2**7)
        elif audio_segment.sample_width == 2:  # 16-bit
            samples = samples / (2**15)
        elif audio_segment.sample_width == 3:  # 24-bit
            samples = samples / (2**23)
        elif audio_segment.sample_width == 4:  # 32-bit
            samples = samples / (2**31)
        else:
            # Assume 16-bit as fallback
            samples = samples / (2**15)

        # Handle stereo/mono
        if audio_segment.channels == 2:
            samples = samples.reshape((-1, 2)).T
        elif audio_segment.channels == 1:
            samples = samples.reshape(1, -1)
        else:
            # Multi-channel audio - take first two channels
            samples = samples.reshape((-1, audio_segment.channels)).T[:2]

        return samples, audio_segment.frame_rate

    def _validate_audio_data(self, audio_data: np.ndarray, sample_rate: int) -> bool:
        """Validate loaded audio data."""
        try:
            # Check basic properties
            if audio_data is None or audio_data.size == 0:
                return False

            if sample_rate <= 0 or sample_rate > 192000:
                return False

            # Check for valid audio range
            if np.any(np.isnan(audio_data)) or np.any(np.isinf(audio_data)):
                return False

            # Check reasonable amplitude range
            max_amplitude = np.max(np.abs(audio_data))
            if max_amplitude == 0 or max_amplitude > 100:  # Suspiciously high
                return False

            # Check duration is reasonable
            duration = audio_data.shape[-1] / sample_rate
            if duration < 0.1 or duration > 7200:  # 0.1s to 2 hours
                return False

            return True

        except Exception:
            return False
    
    def _process_audio(self, audio_data: np.ndarray, original_sr: int,
                      normalize: bool, mono: bool) -> np.ndarray:
        """Process loaded audio data."""
        processed = audio_data.copy()
        
        # Resample if needed
        if original_sr != self.target_sample_rate:
            self.logger.debug(f"Resampling from {original_sr}Hz to {self.target_sample_rate}Hz")
            
            if processed.ndim == 1:
                processed = librosa.resample(
                    processed, orig_sr=original_sr, target_sr=self.target_sample_rate
                )
            else:
                # Resample each channel
                resampled_channels = []
                for channel in processed:
                    resampled = librosa.resample(
                        channel, orig_sr=original_sr, target_sr=self.target_sample_rate
                    )
                    resampled_channels.append(resampled)
                processed = np.array(resampled_channels)
        
        # Convert to mono if requested
        if mono and processed.ndim > 1 and processed.shape[0] > 1:
            processed = np.mean(processed, axis=0, keepdims=True)
        
        # Normalize if requested
        if normalize:
            max_val = np.max(np.abs(processed))
            if max_val > 0:
                processed = processed / max_val
        
        return processed

    def load_audio_async(self, file_path: Union[str, Path],
                        callback: Optional[callable] = None,
                        normalize: bool = True,
                        mono: bool = False) -> None:
        """
        Load audio file asynchronously in background thread.

        Args:
            file_path: Path to audio file
            callback: Function to call when loading is complete
            normalize: Whether to normalize audio
            mono: Whether to convert to mono
        """
        def load_task():
            try:
                result = self.load_audio(file_path, normalize, mono)
                if callback:
                    callback(result, None)
            except Exception as e:
                if callback:
                    callback(None, e)

        self._executor.submit(load_task)

    def generate_waveform_data(self, audio_data: AudioData,
                              zoom_levels: Optional[list] = None,
                              target_width: int = 1920) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Generate multi-resolution waveform data for efficient rendering.

        Args:
            audio_data: Loaded audio data
            zoom_levels: List of zoom levels to pre-compute
            target_width: Target width in pixels for zoom level 1

        Returns:
            Dictionary mapping zoom level to waveform data with peaks and RMS
        """
        if zoom_levels is None:
            zoom_levels = [1, 2, 4, 8, 16, 32, 64, 128]

        waveform_data = {}
        total_samples = audio_data.data.shape[-1]

        self.logger.info(f"Generating waveform data for {len(zoom_levels)} zoom levels")

        for zoom in zoom_levels:
            # Calculate samples per pixel at this zoom level
            target_pixels = target_width * zoom
            samples_per_pixel = max(1, total_samples // target_pixels)

            if samples_per_pixel == 1:
                # No downsampling needed - use original data
                waveform_data[zoom] = {
                    'peaks': audio_data.data,
                    'rms': np.abs(audio_data.data),  # For single samples, RMS = abs
                    'samples_per_pixel': 1
                }
            else:
                # Downsample with both peaks and RMS
                peaks_channels = []
                rms_channels = []

                for channel in audio_data.data:
                    # Calculate number of complete pixels
                    n_pixels = len(channel) // samples_per_pixel
                    if n_pixels == 0:
                        continue

                    # Reshape to groups of samples_per_pixel
                    reshaped = channel[:n_pixels * samples_per_pixel].reshape(n_pixels, samples_per_pixel)

                    # Calculate peaks (max absolute value) for each pixel
                    peaks = np.max(np.abs(reshaped), axis=1)
                    peaks_channels.append(peaks)

                    # Calculate RMS for each pixel
                    rms = np.sqrt(np.mean(reshaped**2, axis=1))
                    rms_channels.append(rms)

                if peaks_channels:  # Only add if we have data
                    waveform_data[zoom] = {
                        'peaks': np.array(peaks_channels),
                        'rms': np.array(rms_channels),
                        'samples_per_pixel': samples_per_pixel
                    }

        self.logger.info(f"Generated waveform data for zoom levels: {list(waveform_data.keys())}")
        return waveform_data

    def calculate_rms_energy(self, audio_data: AudioData,
                           window_size: int = 1024) -> np.ndarray:
        """
        Calculate RMS energy for waveform visualization.

        Args:
            audio_data: Loaded audio data
            window_size: Window size for RMS calculation

        Returns:
            RMS energy array for each channel
        """
        rms_channels = []

        for channel in audio_data.data:
            # Calculate RMS in overlapping windows
            hop_size = window_size // 2
            n_windows = (len(channel) - window_size) // hop_size + 1

            rms_values = []
            for i in range(n_windows):
                start = i * hop_size
                end = start + window_size
                window = channel[start:end]
                rms = np.sqrt(np.mean(window**2))
                rms_values.append(rms)

            rms_channels.append(np.array(rms_values))

        return np.array(rms_channels)

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            'rss_mb': memory_info.rss / (1024 * 1024),  # Resident Set Size
            'vms_mb': memory_info.vms / (1024 * 1024),  # Virtual Memory Size
            'percent': process.memory_percent()
        }

    def optimize_memory_usage(self, audio_data: AudioData) -> AudioData:
        """Optimize memory usage for large audio files."""
        current_memory = self.get_memory_usage()

        if current_memory['rss_mb'] > self.memory_limit_mb:
            self.logger.warning(f"Memory usage {current_memory['rss_mb']:.1f}MB exceeds limit {self.memory_limit_mb}MB")

            # Convert to lower precision if needed
            if audio_data.data.dtype == np.float64:
                self.logger.info("Converting from float64 to float32 to save memory")
                audio_data.data = audio_data.data.astype(np.float32)

            # For very large files, consider chunked processing
            if audio_data.duration > 600:  # 10 minutes
                self.logger.info("Large file detected - consider chunked processing for better memory usage")

        return audio_data

    def create_audio_chunks(self, audio_data: AudioData, chunk_duration: float = 60.0) -> List[AudioData]:
        """Split large audio files into chunks for memory-efficient processing."""
        if audio_data.duration <= chunk_duration:
            return [audio_data]

        chunks = []
        samples_per_chunk = int(chunk_duration * audio_data.sample_rate)
        total_samples = audio_data.data.shape[-1]

        for start_sample in range(0, total_samples, samples_per_chunk):
            end_sample = min(start_sample + samples_per_chunk, total_samples)

            chunk_data = audio_data.data[:, start_sample:end_sample]
            chunk_duration_actual = chunk_data.shape[-1] / audio_data.sample_rate

            chunk = AudioData(
                data=chunk_data,
                sample_rate=audio_data.sample_rate,
                duration=chunk_duration_actual,
                channels=audio_data.channels,
                file_path=audio_data.file_path,
                format=audio_data.format,
                bit_depth=audio_data.bit_depth,
                file_size=chunk_data.nbytes,
                load_time=0.0
            )
            chunks.append(chunk)

        self.logger.info(f"Split audio into {len(chunks)} chunks of ~{chunk_duration}s each")
        return chunks

    def cleanup(self) -> None:
        """Clean up resources."""
        self._executor.shutdown(wait=True)
        self.logger.info("AudioLoader cleanup complete")
