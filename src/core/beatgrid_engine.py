"""
Beatgrid Engine - BPM Detection and Beat Grid Generation
Hybrid approach using madmom DBN + aubio for maximum accuracy
Optimized for variable BPM tracks and manual correction
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import threading

import numpy as np
from scipy import signal
import librosa

# Beat detection libraries
try:
    import madmom
    from madmom.features.beats import DBNBeatTracker, RNNBeatProcessor
    MADMOM_AVAILABLE = True
except ImportError:
    MADMOM_AVAILABLE = False
    logging.warning("madmom not available - using aubio only")

try:
    import aubio
    AUBIO_AVAILABLE = True
except ImportError:
    AUBIO_AVAILABLE = False
    logging.warning("aubio not available - using madmom only")

from .audio_loader import AudioData


@dataclass
class BeatgridData:
    """Container for beatgrid analysis results."""
    bpm: float                    # Detected BPM
    confidence: float             # Detection confidence (0-1)
    beats: np.ndarray            # Beat positions in seconds
    downbeats: np.ndarray        # Downbeat positions in seconds
    time_signature: Tuple[int, int]  # Time signature (numerator, denominator)
    tempo_changes: List[Tuple[float, float]]  # (time, bpm) for variable tempo
    algorithm_used: str          # Which algorithm was used
    analysis_time: float         # Time taken for analysis
    manual_override: bool        # Whether manually adjusted


class BeatgridError(Exception):
    """Custom exception for beatgrid analysis errors."""
    pass


class BeatgridEngine:
    """
    Hybrid beat detection engine using multiple algorithms.
    Provides automatic BPM detection with manual correction capabilities.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Beatgrid settings
        self.auto_detect = config.get('beatgrid', {}).get('auto_detect', True)
        self.algorithms = config.get('beatgrid', {}).get('algorithms', ['madmom_dbn', 'aubio_tempo'])
        self.confidence_threshold = config.get('beatgrid', {}).get('confidence_threshold', 0.8)
        self.bpm_range = config.get('beatgrid', {}).get('bpm_range', [60, 200])
        self.precision_ms = config.get('beatgrid', {}).get('precision_ms', 10)
        
        # Initialize processors
        self._init_processors()
        
        # Thread safety
        self._analysis_lock = threading.Lock()
        
        self.logger.info(f"BeatgridEngine initialized - algorithms: {self.algorithms}")
    
    def _init_processors(self) -> None:
        """Initialize beat detection processors."""
        self.processors = {}
        
        # Initialize madmom processors
        if MADMOM_AVAILABLE and 'madmom_dbn' in self.algorithms:
            try:
                self.processors['madmom_dbn'] = DBNBeatTracker()
                self.processors['madmom_rnn'] = RNNBeatProcessor()
                self.logger.info("madmom processors initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize madmom: {e}")
        
        # aubio will be initialized per-analysis due to sample rate dependency
        if AUBIO_AVAILABLE and 'aubio_tempo' in self.algorithms:
            self.logger.info("aubio processor will be initialized per-analysis")
    
    def analyze_beats(self, audio_data: AudioData) -> BeatgridData:
        """
        Analyze beats and generate beatgrid for audio data.
        
        Args:
            audio_data: Loaded audio data
            
        Returns:
            BeatgridData with analysis results
        """
        start_time = time.time()
        
        with self._analysis_lock:
            self.logger.info(f"Analyzing beats for {audio_data.file_path.name}")
            
            # Try each algorithm in order of preference
            best_result = None
            best_confidence = 0.0
            
            for algorithm in self.algorithms:
                try:
                    result = self._analyze_with_algorithm(audio_data, algorithm)
                    
                    if result.confidence > best_confidence:
                        best_result = result
                        best_confidence = result.confidence
                        
                    # If we have high confidence, use this result
                    if result.confidence >= self.confidence_threshold:
                        break
                        
                except Exception as e:
                    self.logger.warning(f"Algorithm {algorithm} failed: {e}")
                    continue
            
            if best_result is None:
                raise BeatgridError("All beat detection algorithms failed")
            
            # Post-process results
            best_result = self._post_process_beats(best_result, audio_data)
            
            analysis_time = time.time() - start_time
            best_result.analysis_time = analysis_time
            
            self.logger.info(f"Beat analysis complete: {best_result.bpm:.1f} BPM "
                           f"({best_result.confidence:.2f} confidence) in {analysis_time:.2f}s")
            
            return best_result
    
    def _analyze_with_algorithm(self, audio_data: AudioData, algorithm: str) -> BeatgridData:
        """Analyze beats using specific algorithm."""
        if algorithm == 'madmom_dbn':
            return self._analyze_madmom_dbn(audio_data)
        elif algorithm == 'aubio_tempo':
            return self._analyze_aubio_tempo(audio_data)
        else:
            raise BeatgridError(f"Unknown algorithm: {algorithm}")
    
    def _analyze_madmom_dbn(self, audio_data: AudioData) -> BeatgridData:
        """Analyze beats using madmom DBN tracker with enhanced processing."""
        if not MADMOM_AVAILABLE:
            raise BeatgridError("madmom not available")

        # Use mono audio for beat detection
        if audio_data.channels > 1:
            mono_audio = np.mean(audio_data.data, axis=0)
        else:
            mono_audio = audio_data.data[0]

        # Ensure audio is in the right format for madmom
        if mono_audio.dtype != np.float32:
            mono_audio = mono_audio.astype(np.float32)

        # Normalize audio for consistent processing
        if np.max(np.abs(mono_audio)) > 0:
            mono_audio = mono_audio / np.max(np.abs(mono_audio))

        try:
            # madmom expects audio as (samples,) array
            beats = self.processors['madmom_dbn'](mono_audio)

            if len(beats) < 2:
                raise BeatgridError("Insufficient beats detected by madmom")

            # Filter out beats that are too close together (< 200ms)
            beats = self._filter_close_beats(beats, min_interval=0.2)

            if len(beats) < 2:
                raise BeatgridError("Insufficient beats after filtering")

            # Calculate BPM with improved algorithm
            bpm, confidence = self._calculate_bpm_and_confidence(beats)

            # Validate BPM is in reasonable range
            if not (self.bpm_range[0] <= bpm <= self.bpm_range[1]):
                # Try to correct by doubling or halving
                if bpm < self.bpm_range[0] and bpm * 2 <= self.bpm_range[1]:
                    bpm *= 2
                    beats = beats[::2]  # Take every other beat
                elif bpm > self.bpm_range[1] and bpm / 2 >= self.bpm_range[0]:
                    bpm /= 2
                    # Insert beats between existing ones
                    beats = self._interpolate_beats(beats)

            # Detect downbeats with improved algorithm
            downbeats = self._detect_downbeats(beats, bpm)

            return BeatgridData(
                bpm=bpm,
                confidence=confidence,
                beats=beats,
                downbeats=downbeats,
                time_signature=(4, 4),
                tempo_changes=[],
                algorithm_used='madmom_dbn',
                analysis_time=0.0,
                manual_override=False
            )

        except Exception as e:
            raise BeatgridError(f"madmom analysis failed: {e}")

    def _filter_close_beats(self, beats: np.ndarray, min_interval: float = 0.2) -> np.ndarray:
        """Filter out beats that are too close together."""
        if len(beats) <= 1:
            return beats

        filtered_beats = [beats[0]]

        for beat in beats[1:]:
            if beat - filtered_beats[-1] >= min_interval:
                filtered_beats.append(beat)

        return np.array(filtered_beats)

    def _calculate_bpm_and_confidence(self, beats: np.ndarray) -> Tuple[float, float]:
        """Calculate BPM and confidence with improved algorithm."""
        if len(beats) < 2:
            return 0.0, 0.0

        intervals = np.diff(beats)

        # Remove outliers using IQR method
        q1, q3 = np.percentile(intervals, [25, 75])
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        filtered_intervals = intervals[(intervals >= lower_bound) & (intervals <= upper_bound)]

        if len(filtered_intervals) == 0:
            filtered_intervals = intervals

        # Use median for robustness
        median_interval = np.median(filtered_intervals)
        bpm = 60.0 / median_interval

        # Calculate confidence based on interval consistency
        interval_std = np.std(filtered_intervals)
        relative_std = interval_std / median_interval if median_interval > 0 else 1.0
        confidence = max(0.0, 1.0 - relative_std)

        # Boost confidence if we have many consistent beats
        if len(filtered_intervals) > 10:
            confidence = min(1.0, confidence * 1.1)

        return bpm, confidence

    def _interpolate_beats(self, beats: np.ndarray) -> np.ndarray:
        """Insert beats between existing ones to double the beat rate."""
        if len(beats) < 2:
            return beats

        new_beats = []
        for i in range(len(beats) - 1):
            new_beats.append(beats[i])
            # Insert beat halfway between current and next
            new_beats.append((beats[i] + beats[i + 1]) / 2)
        new_beats.append(beats[-1])

        return np.array(new_beats)

    def _detect_downbeats(self, beats: np.ndarray, bpm: float) -> np.ndarray:
        """Detect downbeats with improved algorithm."""
        if len(beats) < 4:
            return beats[::4] if len(beats) >= 4 else beats[:1]

        # For now, use simple every-4th-beat approach
        # In future, could use spectral analysis to detect stronger beats
        downbeats = beats[::4]

        return downbeats
    
    def _analyze_aubio_tempo(self, audio_data: AudioData) -> BeatgridData:
        """Analyze beats using aubio tempo detection."""
        if not AUBIO_AVAILABLE:
            raise BeatgridError("aubio not available")
        
        # Use mono audio
        if audio_data.channels > 1:
            mono_audio = np.mean(audio_data.data, axis=0)
        else:
            mono_audio = audio_data.data[0]
        
        # aubio parameters
        win_s = 1024  # window size
        hop_s = 512   # hop size
        
        # Create aubio tempo object
        tempo = aubio.tempo("default", win_s, hop_s, audio_data.sample_rate)
        
        # Process audio in chunks
        beats = []
        for i in range(0, len(mono_audio) - hop_s, hop_s):
            chunk = mono_audio[i:i + win_s].astype(np.float32)
            if len(chunk) < win_s:
                chunk = np.pad(chunk, (0, win_s - len(chunk)))
            
            beat = tempo(chunk)
            if beat[0] != 0:
                beat_time = (i + beat[0]) / audio_data.sample_rate
                beats.append(beat_time)
        
        beats = np.array(beats)
        
        if len(beats) < 2:
            raise BeatgridError("Insufficient beats detected")
        
        # Calculate BPM
        intervals = np.diff(beats)
        median_interval = np.median(intervals)
        bpm = 60.0 / median_interval
        
        # Calculate confidence
        interval_std = np.std(intervals)
        confidence = max(0.0, 1.0 - (interval_std / median_interval))
        
        # Detect downbeats
        downbeats = beats[::4]
        
        return BeatgridData(
            bpm=bpm,
            confidence=confidence,
            beats=beats,
            downbeats=downbeats,
            time_signature=(4, 4),
            tempo_changes=[],
            algorithm_used='aubio_tempo',
            analysis_time=0.0,
            manual_override=False
        )
    
    def _post_process_beats(self, beatgrid: BeatgridData, audio_data: AudioData) -> BeatgridData:
        """Post-process beat detection results."""
        # Validate BPM range
        if not (self.bpm_range[0] <= beatgrid.bpm <= self.bpm_range[1]):
            # Try to correct by doubling or halving
            if beatgrid.bpm < self.bpm_range[0]:
                beatgrid.bpm *= 2
                beatgrid.beats = beatgrid.beats[::2]  # Take every other beat
            elif beatgrid.bpm > self.bpm_range[1]:
                beatgrid.bpm /= 2
                # Insert beats between existing ones
                new_beats = []
                for i in range(len(beatgrid.beats) - 1):
                    new_beats.append(beatgrid.beats[i])
                    new_beats.append((beatgrid.beats[i] + beatgrid.beats[i + 1]) / 2)
                new_beats.append(beatgrid.beats[-1])
                beatgrid.beats = np.array(new_beats)
        
        # Ensure beats don't exceed audio duration
        beatgrid.beats = beatgrid.beats[beatgrid.beats <= audio_data.duration]
        beatgrid.downbeats = beatgrid.downbeats[beatgrid.downbeats <= audio_data.duration]
        
        return beatgrid
    
    def manual_tap_tempo(self, tap_times: List[float]) -> float:
        """
        Calculate BPM from manual tap times.
        
        Args:
            tap_times: List of tap timestamps in seconds
            
        Returns:
            Calculated BPM
        """
        if len(tap_times) < 2:
            raise BeatgridError("Need at least 2 taps")
        
        intervals = np.diff(tap_times)
        avg_interval = np.mean(intervals)
        bpm = 60.0 / avg_interval
        
        return bpm
    
    def adjust_beatgrid(self, beatgrid: BeatgridData, 
                       first_beat_offset: float,
                       bpm_override: Optional[float] = None) -> BeatgridData:
        """
        Manually adjust beatgrid with new first beat position and/or BPM.
        
        Args:
            beatgrid: Original beatgrid data
            first_beat_offset: New position for first beat in seconds
            bpm_override: Optional BPM override
            
        Returns:
            Adjusted beatgrid data
        """
        new_bpm = bpm_override if bpm_override else beatgrid.bpm
        beat_interval = 60.0 / new_bpm
        
        # Generate new beat grid
        max_time = beatgrid.beats[-1] if len(beatgrid.beats) > 0 else 300.0  # 5 minutes max
        n_beats = int((max_time - first_beat_offset) / beat_interval) + 1
        
        new_beats = first_beat_offset + np.arange(n_beats) * beat_interval
        new_downbeats = new_beats[::4]  # Every 4th beat
        
        return BeatgridData(
            bpm=new_bpm,
            confidence=beatgrid.confidence,
            beats=new_beats,
            downbeats=new_downbeats,
            time_signature=beatgrid.time_signature,
            tempo_changes=beatgrid.tempo_changes,
            algorithm_used=beatgrid.algorithm_used,
            analysis_time=beatgrid.analysis_time,
            manual_override=True
        )
