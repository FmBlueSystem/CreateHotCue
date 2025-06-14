"""
Audio Engine - Low-latency audio playback with sounddevice
Professional DJ-grade audio output with precise timing and control
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# Audio output libraries
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning("sounddevice not available - audio playback disabled")

from ..core.audio_loader import AudioData


class PlaybackState(Enum):
    """Playback state enumeration."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"


@dataclass
class AudioDevice:
    """Audio output device information."""
    id: int
    name: str
    channels: int
    sample_rate: float
    latency: float
    is_default: bool


class AudioEngine(QObject):
    """
    Professional audio playback engine with low-latency output.
    Designed for DJ applications with precise timing requirements.
    """
    
    # Signals
    playback_started = pyqtSignal()
    playback_paused = pyqtSignal()
    playback_stopped = pyqtSignal()
    position_changed = pyqtSignal(float)  # position in seconds
    state_changed = pyqtSignal(str)       # PlaybackState.value
    device_changed = pyqtSignal(str)      # device name
    error_occurred = pyqtSignal(str)      # error message
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Audio settings
        self.sample_rate = config.get('audio', {}).get('sample_rate', 44100)
        self.buffer_size = config.get('audio', {}).get('buffer_size', 512)
        self.channels = config.get('audio', {}).get('output_channels', 2)
        self.target_latency = config.get('audio', {}).get('target_latency_ms', 10) / 1000.0
        
        # Playback state
        self.state = PlaybackState.STOPPED
        self.current_audio: Optional[AudioData] = None
        self.current_position = 0.0  # seconds
        self.playback_speed = 1.0
        self.volume = 1.0
        
        # Audio streaming
        self.stream: Optional[sd.OutputStream] = None
        self.audio_buffer: Optional[np.ndarray] = None
        self.buffer_position = 0
        self.is_looping = False
        self.loop_start = 0.0
        self.loop_end = 0.0
        
        # Threading
        self.playback_lock = threading.RLock()
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self._update_position)
        
        # Device management
        self.available_devices: List[AudioDevice] = []
        self.current_device: Optional[AudioDevice] = None
        
        # Initialize
        self._initialize_audio()
        
        self.logger.info("AudioEngine initialized")
    
    def _initialize_audio(self) -> None:
        """Initialize audio system and detect devices."""
        if not SOUNDDEVICE_AVAILABLE:
            self.logger.error("sounddevice not available - audio playback disabled")
            return
        
        try:
            # Scan available devices
            self._scan_audio_devices()
            
            # Set default device
            self._set_default_device()
            
            self.logger.info(f"Audio system initialized - {len(self.available_devices)} devices found")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize audio: {e}")
            self.error_occurred.emit(f"Audio initialization failed: {e}")
    
    def _scan_audio_devices(self) -> None:
        """Scan and catalog available audio output devices."""
        if not SOUNDDEVICE_AVAILABLE:
            return
        
        self.available_devices.clear()
        
        try:
            devices = sd.query_devices()
            default_device = sd.default.device[1]  # Output device
            
            for i, device in enumerate(devices):
                if device['max_output_channels'] > 0:  # Output device
                    audio_device = AudioDevice(
                        id=i,
                        name=device['name'],
                        channels=device['max_output_channels'],
                        sample_rate=device['default_samplerate'],
                        latency=device['default_low_output_latency'],
                        is_default=(i == default_device)
                    )
                    self.available_devices.append(audio_device)
            
            self.logger.debug(f"Found {len(self.available_devices)} output devices")
            
        except Exception as e:
            self.logger.error(f"Failed to scan audio devices: {e}")
    
    def _set_default_device(self) -> None:
        """Set the default audio output device."""
        if not self.available_devices:
            return
        
        # Find default device
        default_device = next((d for d in self.available_devices if d.is_default), None)
        
        if default_device:
            self.current_device = default_device
        else:
            # Use first available device
            self.current_device = self.available_devices[0]
        
        self.logger.info(f"Using audio device: {self.current_device.name}")
    
    def get_available_devices(self) -> List[AudioDevice]:
        """Get list of available audio output devices."""
        return self.available_devices.copy()
    
    def set_audio_device(self, device_id: int) -> bool:
        """Set audio output device by ID."""
        device = next((d for d in self.available_devices if d.id == device_id), None)
        
        if not device:
            self.logger.error(f"Audio device {device_id} not found")
            return False
        
        # Stop current playback
        was_playing = self.state == PlaybackState.PLAYING
        if was_playing:
            self.pause()
        
        # Close current stream
        self._close_stream()
        
        # Set new device
        self.current_device = device
        self.device_changed.emit(device.name)
        
        # Resume playback if it was playing
        if was_playing and self.current_audio:
            self.play()
        
        self.logger.info(f"Switched to audio device: {device.name}")
        return True
    
    def load_audio(self, audio_data: AudioData) -> bool:
        """Load audio data for playback."""
        try:
            with self.playback_lock:
                # Stop current playback
                self.stop()
                
                self.current_audio = audio_data
                self.current_position = 0.0
                
                # Prepare audio buffer
                self._prepare_audio_buffer()
                
                self.logger.info(f"Audio loaded: {audio_data.duration:.1f}s, "
                               f"{audio_data.channels}ch, {audio_data.sample_rate}Hz")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to load audio: {e}")
            self.error_occurred.emit(f"Failed to load audio: {e}")
            return False
    
    def _prepare_audio_buffer(self) -> None:
        """Prepare audio buffer for playback."""
        if not self.current_audio:
            return
        
        # Convert to playback format
        audio_data = self.current_audio.data
        
        # Ensure correct channel count
        if audio_data.shape[0] == 1 and self.channels == 2:
            # Mono to stereo
            audio_data = np.repeat(audio_data, 2, axis=0)
        elif audio_data.shape[0] == 2 and self.channels == 1:
            # Stereo to mono
            audio_data = np.mean(audio_data, axis=0, keepdims=True)
        
        # Transpose for sounddevice (frames, channels)
        self.audio_buffer = audio_data.T
        self.buffer_position = 0
        
        self.logger.debug(f"Audio buffer prepared: {self.audio_buffer.shape}")
    
    def play(self) -> bool:
        """Start or resume audio playback."""
        if not SOUNDDEVICE_AVAILABLE or not self.current_audio:
            return False
        
        try:
            with self.playback_lock:
                if self.state == PlaybackState.PLAYING:
                    return True
                
                # Create audio stream if needed
                if not self.stream or self.stream.closed:
                    self._create_stream()
                
                # Start stream
                if self.stream and not self.stream.active:
                    self.stream.start()
                
                # Update state
                self.state = PlaybackState.PLAYING
                self.state_changed.emit(self.state.value)
                self.playback_started.emit()
                
                # Start position timer
                self.position_timer.start(50)  # Update every 50ms
                
                self.logger.debug("Playback started")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start playback: {e}")
            self.error_occurred.emit(f"Playback failed: {e}")
            return False
    
    def pause(self) -> bool:
        """Pause audio playback."""
        try:
            with self.playback_lock:
                if self.state != PlaybackState.PLAYING:
                    return True
                
                # Stop stream
                if self.stream and self.stream.active:
                    self.stream.stop()
                
                # Update state
                self.state = PlaybackState.PAUSED
                self.state_changed.emit(self.state.value)
                self.playback_paused.emit()
                
                # Stop position timer
                self.position_timer.stop()
                
                self.logger.debug("Playback paused")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to pause playback: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop audio playback and reset position."""
        try:
            with self.playback_lock:
                # Stop stream
                if self.stream and self.stream.active:
                    self.stream.stop()
                
                # Reset position
                self.current_position = 0.0
                self.buffer_position = 0
                
                # Update state
                self.state = PlaybackState.STOPPED
                self.state_changed.emit(self.state.value)
                self.playback_stopped.emit()
                self.position_changed.emit(self.current_position)
                
                # Stop position timer
                self.position_timer.stop()
                
                self.logger.debug("Playback stopped")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to stop playback: {e}")
            return False
    
    def seek(self, position_seconds: float) -> bool:
        """Seek to specific position in track."""
        if not self.current_audio:
            return False
        
        try:
            with self.playback_lock:
                # Clamp position
                position_seconds = max(0.0, min(position_seconds, self.current_audio.duration))
                
                # Calculate buffer position
                sample_position = int(position_seconds * self.current_audio.sample_rate)
                self.buffer_position = sample_position
                self.current_position = position_seconds
                
                self.position_changed.emit(self.current_position)
                
                self.logger.debug(f"Seeked to {position_seconds:.2f}s")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to seek: {e}")
            return False
    
    def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0 - 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        self.logger.debug(f"Volume set to {self.volume:.2f}")
    
    def set_speed(self, speed: float) -> None:
        """Set playback speed (0.5 - 2.0)."""
        self.playback_speed = max(0.5, min(2.0, speed))
        self.logger.debug(f"Speed set to {self.playback_speed:.2f}")
    
    def _create_stream(self) -> None:
        """Create audio output stream."""
        if not SOUNDDEVICE_AVAILABLE or not self.current_device:
            return
        
        try:
            self.stream = sd.OutputStream(
                device=self.current_device.id,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                latency=self.target_latency,
                callback=self._audio_callback,
                finished_callback=self._stream_finished
            )
            
            self.logger.debug(f"Audio stream created: {self.channels}ch, "
                            f"{self.sample_rate}Hz, {self.buffer_size} frames")
            
        except Exception as e:
            self.logger.error(f"Failed to create audio stream: {e}")
            raise
    
    def _audio_callback(self, outdata: np.ndarray, frames: int, time, status) -> None:
        """Audio callback function for real-time playback."""
        if status:
            self.logger.warning(f"Audio callback status: {status}")
        
        try:
            with self.playback_lock:
                if not self.audio_buffer is None and self.state == PlaybackState.PLAYING:
                    # Calculate how many frames to read
                    remaining_frames = len(self.audio_buffer) - self.buffer_position
                    frames_to_read = min(frames, remaining_frames)
                    
                    if frames_to_read > 0:
                        # Copy audio data
                        end_pos = self.buffer_position + frames_to_read
                        outdata[:frames_to_read] = self.audio_buffer[self.buffer_position:end_pos] * self.volume
                        
                        # Update position
                        self.buffer_position += frames_to_read
                        
                        # Fill remaining with silence if needed
                        if frames_to_read < frames:
                            outdata[frames_to_read:] = 0.0
                            
                            # End of track reached
                            if not self.is_looping:
                                # Will be handled by position timer
                                pass
                    else:
                        # No more data
                        outdata[:] = 0.0
                else:
                    # Not playing or no data
                    outdata[:] = 0.0
                    
        except Exception as e:
            self.logger.error(f"Audio callback error: {e}")
            outdata[:] = 0.0
    
    def _stream_finished(self) -> None:
        """Called when audio stream finishes."""
        self.logger.debug("Audio stream finished")
    
    def _update_position(self) -> None:
        """Update current playback position."""
        if not self.current_audio or self.state != PlaybackState.PLAYING:
            return
        
        try:
            with self.playback_lock:
                # Calculate current position from buffer position
                self.current_position = self.buffer_position / self.current_audio.sample_rate
                
                # Check if end of track reached
                if self.current_position >= self.current_audio.duration:
                    if self.is_looping and self.loop_end > self.loop_start:
                        # Loop back to start
                        self.seek(self.loop_start)
                    else:
                        # Stop at end
                        self.stop()
                        return
                
                self.position_changed.emit(self.current_position)
                
        except Exception as e:
            self.logger.error(f"Position update error: {e}")
    
    def _close_stream(self) -> None:
        """Close current audio stream."""
        if self.stream:
            try:
                if self.stream.active:
                    self.stream.stop()
                self.stream.close()
                self.stream = None
                self.logger.debug("Audio stream closed")
            except Exception as e:
                self.logger.error(f"Failed to close stream: {e}")
    
    def get_position(self) -> float:
        """Get current playback position in seconds."""
        return self.current_position
    
    def get_state(self) -> PlaybackState:
        """Get current playback state."""
        return self.state
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self.state == PlaybackState.PLAYING
    
    def cleanup(self) -> None:
        """Clean up audio resources."""
        self.stop()
        self._close_stream()
        self.position_timer.stop()
        self.logger.info("AudioEngine cleaned up")
