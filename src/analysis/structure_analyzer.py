"""
Structure Analyzer - Automatic detection of musical structure
Detects intro, verse, chorus, breakdown, buildup, outro sections using audio analysis
"""

import logging
import time
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Audio analysis libraries
try:
    import librosa
    import librosa.display
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.warning("librosa not available - structure analysis limited")

try:
    import scipy.signal
    import scipy.ndimage
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.warning("scipy not available - advanced analysis disabled")

from ..core.audio_loader import AudioData
from ..core.beatgrid_engine import BeatgridData


class StructureType(Enum):
    """Types of musical structure sections."""
    INTRO = "intro"
    VERSE = "verse"
    CHORUS = "chorus"
    BRIDGE = "bridge"
    BREAKDOWN = "breakdown"
    BUILDUP = "buildup"
    DROP = "drop"
    OUTRO = "outro"
    UNKNOWN = "unknown"


@dataclass
class StructureSection:
    """Individual structure section with timing and characteristics."""
    type: StructureType
    start_time: float          # Start time in seconds
    end_time: float            # End time in seconds
    confidence: float          # Detection confidence (0-1)
    energy_level: float        # Average energy level (0-1)
    spectral_centroid: float   # Average spectral centroid
    tempo_stability: float     # Tempo stability within section
    label: str = ""            # User-defined label
    color: str = "#888888"     # Display color
    
    def __post_init__(self):
        """Set default label and color based on type."""
        if not self.label:
            self.label = self.type.value.title()
        
        if self.color == "#888888":
            self.color = self._get_default_color()
    
    def _get_default_color(self) -> str:
        """Get default color for structure type."""
        color_map = {
            StructureType.INTRO: "#4A90E2",     # Blue
            StructureType.VERSE: "#7ED321",     # Green
            StructureType.CHORUS: "#F5A623",    # Orange
            StructureType.BRIDGE: "#9013FE",    # Purple
            StructureType.BREAKDOWN: "#50E3C2", # Cyan
            StructureType.BUILDUP: "#BD10E0",   # Magenta
            StructureType.DROP: "#FF3366",      # Red
            StructureType.OUTRO: "#B8E986",     # Light Green
            StructureType.UNKNOWN: "#888888"    # Gray
        }
        return color_map.get(self.type, "#888888")
    
    @property
    def duration(self) -> float:
        """Get section duration in seconds."""
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'type': self.type.value,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'confidence': self.confidence,
            'energy_level': self.energy_level,
            'spectral_centroid': self.spectral_centroid,
            'tempo_stability': self.tempo_stability,
            'label': self.label,
            'color': self.color
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StructureSection':
        """Create from dictionary."""
        return cls(
            type=StructureType(data['type']),
            start_time=data['start_time'],
            end_time=data['end_time'],
            confidence=data['confidence'],
            energy_level=data['energy_level'],
            spectral_centroid=data['spectral_centroid'],
            tempo_stability=data['tempo_stability'],
            label=data.get('label', ''),
            color=data.get('color', '#888888')
        )


@dataclass
class StructureAnalysisResult:
    """Complete structure analysis result."""
    sections: List[StructureSection] = field(default_factory=list)
    confidence: float = 0.0
    analysis_time: float = 0.0
    algorithm_used: str = "librosa_segmentation"
    features_used: List[str] = field(default_factory=list)
    
    def get_section_at_time(self, time_seconds: float) -> Optional[StructureSection]:
        """Get the structure section at a specific time."""
        for section in self.sections:
            if section.start_time <= time_seconds <= section.end_time:
                return section
        return None
    
    def get_sections_by_type(self, section_type: StructureType) -> List[StructureSection]:
        """Get all sections of a specific type."""
        return [s for s in self.sections if s.type == section_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'sections': [section.to_dict() for section in self.sections],
            'confidence': self.confidence,
            'analysis_time': self.analysis_time,
            'algorithm_used': self.algorithm_used,
            'features_used': self.features_used
        }


class StructureAnalysisError(Exception):
    """Custom exception for structure analysis errors."""
    pass


class StructureAnalyzer:
    """
    Advanced structure analyzer for automatic detection of musical sections.
    Uses multiple audio features and machine learning techniques.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Structure analysis settings
        self.enabled = config.get('structure', {}).get('auto_detect', True)
        self.confidence_threshold = config.get('structure', {}).get('confidence_threshold', 0.7)
        self.min_section_duration = config.get('structure', {}).get('min_section_duration', 8.0)
        self.max_sections = config.get('structure', {}).get('max_sections', 20)
        
        # Analysis parameters
        self.hop_length = config.get('structure', {}).get('hop_length', 512)
        self.frame_length = config.get('structure', {}).get('frame_length', 2048)
        self.n_mels = config.get('structure', {}).get('n_mels', 128)
        
        # Feature weights for classification
        self.feature_weights = config.get('structure', {}).get('feature_weights', {
            'energy': 0.3,
            'spectral_centroid': 0.2,
            'mfcc': 0.25,
            'chroma': 0.15,
            'tempo': 0.1
        })
        
        # Check library availability
        if not LIBROSA_AVAILABLE:
            self.logger.warning("librosa not available - structure analysis disabled")
            self.enabled = False
        
        if self.enabled:
            self.logger.info(f"StructureAnalyzer initialized - confidence threshold: {self.confidence_threshold}")
    
    def analyze_structure(self, audio_data: AudioData, 
                         beatgrid_data: Optional[BeatgridData] = None) -> StructureAnalysisResult:
        """
        Analyze musical structure of audio track.
        
        Args:
            audio_data: Audio data to analyze
            beatgrid_data: Optional beatgrid data for tempo-aware analysis
            
        Returns:
            StructureAnalysisResult with detected sections
        """
        if not self.enabled:
            return StructureAnalysisResult(
                sections=[],
                confidence=0.0,
                algorithm_used="disabled"
            )
        
        start_time = time.time()
        
        try:
            # Use mono audio for analysis
            if audio_data.channels > 1:
                mono_audio = np.mean(audio_data.data, axis=0)
            else:
                mono_audio = audio_data.data[0]
            
            # Extract audio features
            features = self._extract_features(mono_audio, audio_data.sample_rate)
            
            # Detect segment boundaries
            boundaries = self._detect_boundaries(features, audio_data.sample_rate)
            
            # Classify segments
            sections = self._classify_segments(
                boundaries, features, mono_audio, 
                audio_data.sample_rate, beatgrid_data
            )
            
            # Post-process and validate sections
            sections = self._post_process_sections(sections, audio_data.duration)
            
            # Calculate overall confidence
            overall_confidence = np.mean([s.confidence for s in sections]) if sections else 0.0
            
            analysis_time = time.time() - start_time
            
            result = StructureAnalysisResult(
                sections=sections,
                confidence=overall_confidence,
                analysis_time=analysis_time,
                algorithm_used="librosa_segmentation",
                features_used=list(features.keys())
            )
            
            self.logger.info(f"Structure analysis complete: {len(sections)} sections "
                           f"({overall_confidence:.2f} confidence) in {analysis_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Structure analysis failed: {e}")
            raise StructureAnalysisError(f"Analysis failed: {e}")
    
    def _extract_features(self, audio: np.ndarray, sample_rate: int) -> Dict[str, np.ndarray]:
        """Extract audio features for structure analysis."""
        features = {}
        
        try:
            # Spectral features
            stft = librosa.stft(audio, hop_length=self.hop_length, n_fft=self.frame_length)
            magnitude = np.abs(stft)
            
            # Energy (RMS)
            features['energy'] = librosa.feature.rms(
                S=magnitude, hop_length=self.hop_length
            )[0]
            
            # Spectral centroid
            features['spectral_centroid'] = librosa.feature.spectral_centroid(
                S=magnitude, sr=sample_rate, hop_length=self.hop_length
            )[0]
            
            # MFCCs
            features['mfcc'] = librosa.feature.mfcc(
                y=audio, sr=sample_rate, n_mfcc=13, 
                hop_length=self.hop_length
            )
            
            # Chroma features
            features['chroma'] = librosa.feature.chroma_stft(
                S=magnitude, sr=sample_rate, hop_length=self.hop_length
            )
            
            # Spectral contrast
            features['spectral_contrast'] = librosa.feature.spectral_contrast(
                S=magnitude, sr=sample_rate, hop_length=self.hop_length
            )
            
            # Zero crossing rate
            features['zcr'] = librosa.feature.zero_crossing_rate(
                audio, hop_length=self.hop_length
            )[0]
            
            # Tempo features
            onset_envelope = librosa.onset.onset_strength(
                y=audio, sr=sample_rate, hop_length=self.hop_length
            )
            features['onset_strength'] = onset_envelope
            
            self.logger.debug(f"Extracted {len(features)} feature types")
            
        except Exception as e:
            self.logger.error(f"Feature extraction failed: {e}")
            raise StructureAnalysisError(f"Feature extraction failed: {e}")
        
        return features
    
    def _detect_boundaries(self, features: Dict[str, np.ndarray], 
                          sample_rate: int) -> np.ndarray:
        """Detect segment boundaries using feature analysis."""
        try:
            # Combine features for boundary detection
            feature_matrix = self._combine_features_for_segmentation(features)
            
            # Use librosa's segment boundaries detection
            boundaries = librosa.segment.agglomerative(
                feature_matrix, 
                k=None,  # Let algorithm determine number of segments
                clusterer=None
            )
            
            # Convert frame indices to time
            boundary_times = librosa.frames_to_time(
                boundaries, sr=sample_rate, hop_length=self.hop_length
            )
            
            # Ensure we have start and end boundaries
            if boundary_times[0] > 0:
                boundary_times = np.insert(boundary_times, 0, 0.0)
            
            duration = len(features['energy']) * self.hop_length / sample_rate
            if boundary_times[-1] < duration:
                boundary_times = np.append(boundary_times, duration)
            
            self.logger.debug(f"Detected {len(boundary_times)} boundaries")
            
            return boundary_times
            
        except Exception as e:
            self.logger.error(f"Boundary detection failed: {e}")
            # Fallback: create simple time-based segments
            duration = len(features['energy']) * self.hop_length / sample_rate
            return np.linspace(0, duration, min(8, int(duration / 30)))  # 30s segments max
    
    def _combine_features_for_segmentation(self, features: Dict[str, np.ndarray]) -> np.ndarray:
        """Combine features into matrix for segmentation."""
        feature_list = []
        
        # Add energy (normalized)
        energy_norm = features['energy'] / (np.max(features['energy']) + 1e-8)
        feature_list.append(energy_norm)
        
        # Add spectral centroid (normalized)
        centroid_norm = features['spectral_centroid'] / (np.max(features['spectral_centroid']) + 1e-8)
        feature_list.append(centroid_norm)
        
        # Add first few MFCCs
        for i in range(min(5, features['mfcc'].shape[0])):
            mfcc_norm = features['mfcc'][i] / (np.max(np.abs(features['mfcc'][i])) + 1e-8)
            feature_list.append(mfcc_norm)
        
        # Add chroma features (sum across octaves)
        chroma_sum = np.sum(features['chroma'], axis=0)
        chroma_norm = chroma_sum / (np.max(chroma_sum) + 1e-8)
        feature_list.append(chroma_norm)
        
        # Stack features
        feature_matrix = np.vstack(feature_list)

        return feature_matrix

    def _classify_segments(self, boundaries: np.ndarray, features: Dict[str, np.ndarray],
                          audio: np.ndarray, sample_rate: int,
                          beatgrid_data: Optional[BeatgridData] = None) -> List[StructureSection]:
        """Classify detected segments into structure types."""
        sections = []

        for i in range(len(boundaries) - 1):
            start_time = boundaries[i]
            end_time = boundaries[i + 1]

            # Skip very short segments
            if end_time - start_time < self.min_section_duration:
                continue

            # Extract features for this segment
            segment_features = self._extract_segment_features(
                start_time, end_time, features, sample_rate
            )

            # Classify segment type
            section_type, confidence = self._classify_segment_type(
                segment_features, start_time, end_time, len(sections), beatgrid_data
            )

            # Create structure section
            section = StructureSection(
                type=section_type,
                start_time=start_time,
                end_time=end_time,
                confidence=confidence,
                energy_level=segment_features['avg_energy'],
                spectral_centroid=segment_features['avg_spectral_centroid'],
                tempo_stability=segment_features['tempo_stability']
            )

            sections.append(section)

        return sections

    def _extract_segment_features(self, start_time: float, end_time: float,
                                 features: Dict[str, np.ndarray],
                                 sample_rate: int) -> Dict[str, float]:
        """Extract aggregated features for a segment."""
        # Convert times to frame indices
        start_frame = int(start_time * sample_rate / self.hop_length)
        end_frame = int(end_time * sample_rate / self.hop_length)

        # Ensure valid frame range
        start_frame = max(0, start_frame)
        end_frame = min(len(features['energy']), end_frame)

        if start_frame >= end_frame:
            # Fallback for invalid ranges
            return {
                'avg_energy': 0.0,
                'avg_spectral_centroid': 0.0,
                'energy_variance': 0.0,
                'spectral_variance': 0.0,
                'tempo_stability': 0.0
            }

        # Extract segment data
        segment_energy = features['energy'][start_frame:end_frame]
        segment_centroid = features['spectral_centroid'][start_frame:end_frame]
        segment_onset = features['onset_strength'][start_frame:end_frame]

        # Calculate aggregated features
        segment_features = {
            'avg_energy': np.mean(segment_energy),
            'avg_spectral_centroid': np.mean(segment_centroid),
            'energy_variance': np.var(segment_energy),
            'spectral_variance': np.var(segment_centroid),
            'tempo_stability': self._calculate_tempo_stability(segment_onset)
        }

        return segment_features

    def _calculate_tempo_stability(self, onset_strength: np.ndarray) -> float:
        """Calculate tempo stability for a segment."""
        if len(onset_strength) < 10:
            return 0.0

        try:
            # Calculate autocorrelation to find periodic patterns
            autocorr = np.correlate(onset_strength, onset_strength, mode='full')
            autocorr = autocorr[len(autocorr)//2:]

            # Find peaks in autocorrelation
            if SCIPY_AVAILABLE:
                peaks, _ = scipy.signal.find_peaks(autocorr, height=np.max(autocorr) * 0.3)
                if len(peaks) > 1:
                    # Measure consistency of peak spacing
                    peak_diffs = np.diff(peaks)
                    stability = 1.0 - (np.std(peak_diffs) / (np.mean(peak_diffs) + 1e-8))
                    return max(0.0, min(1.0, stability))

            # Fallback: measure variance in onset strength
            return 1.0 - (np.std(onset_strength) / (np.mean(onset_strength) + 1e-8))

        except Exception:
            return 0.5  # Default moderate stability

    def _classify_segment_type(self, segment_features: Dict[str, float],
                              start_time: float, end_time: float,
                              segment_index: int,
                              beatgrid_data: Optional[BeatgridData] = None) -> Tuple[StructureType, float]:
        """Classify a segment into a structure type."""
        duration = end_time - start_time
        track_position = start_time / (end_time + start_time)  # Rough position in track

        # Feature-based classification rules
        energy = segment_features['avg_energy']
        spectral_centroid = segment_features['avg_spectral_centroid']
        energy_variance = segment_features['energy_variance']
        tempo_stability = segment_features['tempo_stability']

        # Normalize features (rough normalization)
        energy_norm = min(1.0, energy * 10)  # Assume typical energy range
        centroid_norm = min(1.0, spectral_centroid / 4000)  # Assume 4kHz max

        # Classification logic based on position and features
        confidence = 0.5  # Base confidence

        # Intro detection (beginning of track, moderate energy)
        if track_position < 0.15 and energy_norm < 0.6:
            return StructureType.INTRO, min(0.9, confidence + 0.3)

        # Outro detection (end of track, decreasing energy)
        elif track_position > 0.85 and energy_norm < 0.5:
            return StructureType.OUTRO, min(0.9, confidence + 0.3)

        # Drop detection (high energy, high spectral content)
        elif energy_norm > 0.8 and centroid_norm > 0.7:
            return StructureType.DROP, min(0.9, confidence + 0.4)

        # Breakdown detection (low energy, low spectral content)
        elif energy_norm < 0.3 and centroid_norm < 0.4:
            return StructureType.BREAKDOWN, min(0.8, confidence + 0.3)

        # Buildup detection (increasing energy, high variance)
        elif energy_variance > 0.1 and tempo_stability > 0.7:
            return StructureType.BUILDUP, min(0.8, confidence + 0.2)

        # Chorus detection (high energy, stable tempo)
        elif energy_norm > 0.6 and tempo_stability > 0.6:
            return StructureType.CHORUS, min(0.8, confidence + 0.2)

        # Verse detection (moderate energy, stable)
        elif 0.3 < energy_norm < 0.7 and tempo_stability > 0.5:
            return StructureType.VERSE, min(0.7, confidence + 0.1)

        # Bridge detection (moderate features, middle position)
        elif 0.3 < track_position < 0.7 and energy_norm > 0.4:
            return StructureType.BRIDGE, min(0.6, confidence)

        # Default to unknown
        else:
            return StructureType.UNKNOWN, confidence

    def _post_process_sections(self, sections: List[StructureSection],
                              track_duration: float) -> List[StructureSection]:
        """Post-process sections to improve classification."""
        if not sections:
            return sections

        # Sort sections by start time
        sections.sort(key=lambda s: s.start_time)

        # Merge very short sections with neighbors
        merged_sections = []
        for section in sections:
            if section.duration < self.min_section_duration / 2:
                # Try to merge with previous section
                if merged_sections and merged_sections[-1].type == section.type:
                    merged_sections[-1].end_time = section.end_time
                    continue

            merged_sections.append(section)

        # Apply structural logic rules
        processed_sections = self._apply_structural_rules(merged_sections)

        # Ensure sections cover the full track
        processed_sections = self._fill_gaps(processed_sections, track_duration)

        return processed_sections

    def _apply_structural_rules(self, sections: List[StructureSection]) -> List[StructureSection]:
        """Apply musical structure rules to improve classification."""
        if len(sections) < 2:
            return sections

        # Rule 1: First section is likely intro if short and low energy
        if (sections[0].duration < 30 and
            sections[0].energy_level < 0.5 and
            sections[0].type != StructureType.INTRO):
            sections[0].type = StructureType.INTRO
            sections[0].confidence = min(0.8, sections[0].confidence + 0.2)

        # Rule 2: Last section is likely outro if low energy
        if (sections[-1].energy_level < 0.4 and
            sections[-1].type != StructureType.OUTRO):
            sections[-1].type = StructureType.OUTRO
            sections[-1].confidence = min(0.8, sections[-1].confidence + 0.2)

        # Rule 3: High energy sections after buildups are likely drops
        for i in range(len(sections) - 1):
            if (sections[i].type == StructureType.BUILDUP and
                sections[i+1].energy_level > 0.7):
                sections[i+1].type = StructureType.DROP
                sections[i+1].confidence = min(0.9, sections[i+1].confidence + 0.3)

        return sections

    def _fill_gaps(self, sections: List[StructureSection],
                   track_duration: float) -> List[StructureSection]:
        """Fill gaps between sections."""
        if not sections:
            # Create a single unknown section for the entire track
            return [StructureSection(
                type=StructureType.UNKNOWN,
                start_time=0.0,
                end_time=track_duration,
                confidence=0.1,
                energy_level=0.5,
                spectral_centroid=1000.0,
                tempo_stability=0.5
            )]

        filled_sections = []

        # Add section from start if needed
        if sections[0].start_time > 0:
            filled_sections.append(StructureSection(
                type=StructureType.UNKNOWN,
                start_time=0.0,
                end_time=sections[0].start_time,
                confidence=0.1,
                energy_level=0.5,
                spectral_centroid=1000.0,
                tempo_stability=0.5
            ))

        # Add existing sections and fill gaps
        for i, section in enumerate(sections):
            filled_sections.append(section)

            # Fill gap to next section
            if i < len(sections) - 1:
                next_section = sections[i + 1]
                if section.end_time < next_section.start_time:
                    filled_sections.append(StructureSection(
                        type=StructureType.UNKNOWN,
                        start_time=section.end_time,
                        end_time=next_section.start_time,
                        confidence=0.1,
                        energy_level=0.5,
                        spectral_centroid=1000.0,
                        tempo_stability=0.5
                    ))

        # Add section to end if needed
        if sections[-1].end_time < track_duration:
            filled_sections.append(StructureSection(
                type=StructureType.UNKNOWN,
                start_time=sections[-1].end_time,
                end_time=track_duration,
                confidence=0.1,
                energy_level=0.5,
                spectral_centroid=1000.0,
                tempo_stability=0.5
            ))

        return filled_sections
