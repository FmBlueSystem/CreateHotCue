"""
Unit tests for StructureAnalyzer class
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

from src.analysis.structure_analyzer import (
    StructureAnalyzer, StructureSection, StructureType, 
    StructureAnalysisResult, StructureAnalysisError
)
from src.core.audio_loader import AudioData


class TestStructureSection:
    """Test cases for StructureSection class."""
    
    def test_structure_section_creation(self):
        """Test StructureSection creation with valid data."""
        section = StructureSection(
            type=StructureType.CHORUS,
            start_time=30.0,
            end_time=60.0,
            confidence=0.85,
            energy_level=0.7,
            spectral_centroid=2000.0,
            tempo_stability=0.9
        )
        
        assert section.type == StructureType.CHORUS
        assert section.start_time == 30.0
        assert section.end_time == 60.0
        assert section.duration == 30.0
        assert section.confidence == 0.85
        assert section.label == "Chorus"  # Auto-generated
        assert section.color.startswith("#")  # Has default color
    
    def test_structure_section_serialization(self):
        """Test StructureSection to_dict and from_dict."""
        original = StructureSection(
            type=StructureType.VERSE,
            start_time=10.0,
            end_time=25.0,
            confidence=0.75,
            energy_level=0.5,
            spectral_centroid=1500.0,
            tempo_stability=0.8,
            label="Custom Verse",
            color="#123456"
        )
        
        # Test to_dict
        data = original.to_dict()
        assert data['type'] == 'verse'
        assert data['start_time'] == 10.0
        assert data['label'] == "Custom Verse"
        assert data['color'] == "#123456"
        
        # Test from_dict
        restored = StructureSection.from_dict(data)
        assert restored.type == original.type
        assert restored.start_time == original.start_time
        assert restored.label == original.label
        assert restored.color == original.color
    
    def test_default_colors(self):
        """Test default color assignment for different structure types."""
        intro = StructureSection(
            type=StructureType.INTRO,
            start_time=0.0,
            end_time=10.0,
            confidence=0.8,
            energy_level=0.3,
            spectral_centroid=1000.0,
            tempo_stability=0.7
        )
        
        chorus = StructureSection(
            type=StructureType.CHORUS,
            start_time=30.0,
            end_time=60.0,
            confidence=0.9,
            energy_level=0.8,
            spectral_centroid=2500.0,
            tempo_stability=0.9
        )
        
        # Different structure types should have different colors
        assert intro.color != chorus.color
        assert intro.color.startswith("#")
        assert chorus.color.startswith("#")


class TestStructureAnalysisResult:
    """Test cases for StructureAnalysisResult class."""
    
    def test_analysis_result_creation(self):
        """Test StructureAnalysisResult creation."""
        sections = [
            StructureSection(StructureType.INTRO, 0.0, 10.0, 0.8, 0.3, 1000.0, 0.7),
            StructureSection(StructureType.VERSE, 10.0, 30.0, 0.75, 0.5, 1500.0, 0.8),
            StructureSection(StructureType.CHORUS, 30.0, 60.0, 0.9, 0.8, 2500.0, 0.9)
        ]
        
        result = StructureAnalysisResult(
            sections=sections,
            confidence=0.82,
            analysis_time=2.5,
            algorithm_used="librosa_segmentation",
            features_used=["energy", "spectral_centroid", "mfcc"]
        )
        
        assert len(result.sections) == 3
        assert result.confidence == 0.82
        assert result.analysis_time == 2.5
        assert "energy" in result.features_used
    
    def test_get_section_at_time(self):
        """Test getting section at specific time."""
        sections = [
            StructureSection(StructureType.INTRO, 0.0, 10.0, 0.8, 0.3, 1000.0, 0.7),
            StructureSection(StructureType.VERSE, 10.0, 30.0, 0.75, 0.5, 1500.0, 0.8),
            StructureSection(StructureType.CHORUS, 30.0, 60.0, 0.9, 0.8, 2500.0, 0.9)
        ]
        
        result = StructureAnalysisResult(sections=sections)
        
        # Test finding sections
        intro_section = result.get_section_at_time(5.0)
        assert intro_section.type == StructureType.INTRO
        
        verse_section = result.get_section_at_time(20.0)
        assert verse_section.type == StructureType.VERSE
        
        chorus_section = result.get_section_at_time(45.0)
        assert chorus_section.type == StructureType.CHORUS
        
        # Test time outside any section
        no_section = result.get_section_at_time(70.0)
        assert no_section is None
    
    def test_get_sections_by_type(self):
        """Test getting sections by type."""
        sections = [
            StructureSection(StructureType.VERSE, 10.0, 30.0, 0.75, 0.5, 1500.0, 0.8),
            StructureSection(StructureType.CHORUS, 30.0, 60.0, 0.9, 0.8, 2500.0, 0.9),
            StructureSection(StructureType.VERSE, 60.0, 80.0, 0.7, 0.5, 1400.0, 0.8)
        ]
        
        result = StructureAnalysisResult(sections=sections)
        
        # Get all verse sections
        verse_sections = result.get_sections_by_type(StructureType.VERSE)
        assert len(verse_sections) == 2
        assert all(s.type == StructureType.VERSE for s in verse_sections)
        
        # Get chorus sections
        chorus_sections = result.get_sections_by_type(StructureType.CHORUS)
        assert len(chorus_sections) == 1
        assert chorus_sections[0].type == StructureType.CHORUS


class TestStructureAnalyzer:
    """Test cases for StructureAnalyzer class."""
    
    def test_structure_analyzer_creation(self, test_config):
        """Test StructureAnalyzer creation."""
        with patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', True):
            analyzer = StructureAnalyzer(test_config)
            
            assert analyzer.enabled == test_config.get('structure', {}).get('auto_detect', True)
            assert analyzer.confidence_threshold == test_config.get('structure', {}).get('confidence_threshold', 0.7)
            assert analyzer.min_section_duration == test_config.get('structure', {}).get('min_section_duration', 8.0)
    
    def test_structure_analyzer_disabled_without_librosa(self, test_config):
        """Test StructureAnalyzer behavior without librosa."""
        with patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', False):
            analyzer = StructureAnalyzer(test_config)
            
            assert not analyzer.enabled
    
    def test_analyze_structure_disabled(self, test_config):
        """Test structure analysis when disabled."""
        with patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', False):
            analyzer = StructureAnalyzer(test_config)
            
            # Create mock audio data
            audio_data = Mock(spec=AudioData)
            audio_data.channels = 1
            audio_data.data = np.array([np.random.randn(44100)])  # 1 second of audio
            audio_data.sample_rate = 44100
            audio_data.duration = 1.0
            
            result = analyzer.analyze_structure(audio_data)
            
            assert len(result.sections) == 0
            assert result.confidence == 0.0
            assert result.algorithm_used == "disabled"
    
    @patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', True)
    @patch('src.analysis.structure_analyzer.librosa')
    def test_feature_extraction(self, mock_librosa, test_config):
        """Test audio feature extraction."""
        analyzer = StructureAnalyzer(test_config)
        
        # Mock librosa functions
        mock_librosa.stft.return_value = np.random.complex128((1025, 100))
        mock_librosa.feature.rms.return_value = np.array([np.random.rand(100)])
        mock_librosa.feature.spectral_centroid.return_value = np.array([np.random.rand(100) * 4000])
        mock_librosa.feature.mfcc.return_value = np.random.rand(13, 100)
        mock_librosa.feature.chroma_stft.return_value = np.random.rand(12, 100)
        mock_librosa.feature.spectral_contrast.return_value = np.random.rand(7, 100)
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([np.random.rand(100)])
        mock_librosa.onset.onset_strength.return_value = np.random.rand(100)
        
        # Test feature extraction
        audio = np.random.randn(44100)  # 1 second of audio
        sample_rate = 44100
        
        features = analyzer._extract_features(audio, sample_rate)
        
        assert 'energy' in features
        assert 'spectral_centroid' in features
        assert 'mfcc' in features
        assert 'chroma' in features
        assert 'onset_strength' in features
        
        # Verify librosa functions were called
        mock_librosa.stft.assert_called_once()
        mock_librosa.feature.rms.assert_called_once()
        mock_librosa.feature.spectral_centroid.assert_called_once()
    
    @patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', True)
    @patch('src.analysis.structure_analyzer.librosa')
    def test_boundary_detection(self, mock_librosa, test_config):
        """Test segment boundary detection."""
        analyzer = StructureAnalyzer(test_config)
        
        # Mock librosa segmentation
        mock_boundaries = np.array([0, 25, 50, 75, 100])  # Frame indices
        mock_librosa.segment.agglomerative.return_value = mock_boundaries
        mock_librosa.frames_to_time.return_value = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        
        # Create mock features
        features = {
            'energy': np.random.rand(100),
            'spectral_centroid': np.random.rand(100) * 4000,
            'mfcc': np.random.rand(13, 100),
            'chroma': np.random.rand(12, 100)
        }
        
        boundaries = analyzer._detect_boundaries(features, 44100)
        
        assert len(boundaries) >= 2  # Should have at least start and end
        assert boundaries[0] == 0.0  # Should start at 0
        assert boundaries[-1] > boundaries[0]  # Should end after start
    
    def test_segment_classification(self, test_config):
        """Test segment classification logic."""
        with patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', True):
            analyzer = StructureAnalyzer(test_config)
            
            # Test intro classification (beginning, low energy)
            segment_features = {
                'avg_energy': 0.3,
                'avg_spectral_centroid': 1000.0,
                'energy_variance': 0.05,
                'spectral_variance': 100.0,
                'tempo_stability': 0.6
            }
            
            section_type, confidence = analyzer._classify_segment_type(
                segment_features, 0.0, 10.0, 0, None
            )
            
            assert section_type == StructureType.INTRO
            assert confidence > 0.5
            
            # Test drop classification (high energy, high spectral content)
            segment_features = {
                'avg_energy': 0.9,
                'avg_spectral_centroid': 3000.0,
                'energy_variance': 0.1,
                'spectral_variance': 500.0,
                'tempo_stability': 0.8
            }
            
            section_type, confidence = analyzer._classify_segment_type(
                segment_features, 60.0, 90.0, 2, None
            )
            
            assert section_type == StructureType.DROP
            assert confidence > 0.5
    
    def test_post_processing(self, test_config):
        """Test section post-processing."""
        with patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', True):
            analyzer = StructureAnalyzer(test_config)
            
            # Create sections with gaps
            sections = [
                StructureSection(StructureType.INTRO, 0.0, 10.0, 0.8, 0.3, 1000.0, 0.7),
                StructureSection(StructureType.VERSE, 15.0, 30.0, 0.75, 0.5, 1500.0, 0.8),  # Gap from 10-15
                StructureSection(StructureType.CHORUS, 30.0, 60.0, 0.9, 0.8, 2500.0, 0.9)
            ]
            
            track_duration = 70.0
            processed_sections = analyzer._fill_gaps(sections, track_duration)
            
            # Should have filled gaps
            assert len(processed_sections) > len(sections)
            
            # Should cover full duration
            assert processed_sections[0].start_time == 0.0
            assert processed_sections[-1].end_time == track_duration
    
    @patch('src.analysis.structure_analyzer.LIBROSA_AVAILABLE', True)
    @patch('src.analysis.structure_analyzer.librosa')
    def test_full_analysis_workflow(self, mock_librosa, test_config):
        """Test complete structure analysis workflow."""
        analyzer = StructureAnalyzer(test_config)
        
        # Mock all librosa functions
        mock_librosa.stft.return_value = np.random.complex128((1025, 100))
        mock_librosa.feature.rms.return_value = np.array([np.random.rand(100)])
        mock_librosa.feature.spectral_centroid.return_value = np.array([np.random.rand(100) * 4000])
        mock_librosa.feature.mfcc.return_value = np.random.rand(13, 100)
        mock_librosa.feature.chroma_stft.return_value = np.random.rand(12, 100)
        mock_librosa.feature.spectral_contrast.return_value = np.random.rand(7, 100)
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([np.random.rand(100)])
        mock_librosa.onset.onset_strength.return_value = np.random.rand(100)
        mock_librosa.segment.agglomerative.return_value = np.array([0, 25, 50, 75, 100])
        mock_librosa.frames_to_time.return_value = np.array([0.0, 10.0, 20.0, 30.0, 40.0])
        
        # Create mock audio data
        audio_data = Mock(spec=AudioData)
        audio_data.channels = 1
        audio_data.data = np.array([np.random.randn(44100 * 4)])  # 4 seconds of audio
        audio_data.sample_rate = 44100
        audio_data.duration = 4.0
        
        # Perform analysis
        result = analyzer.analyze_structure(audio_data)
        
        assert isinstance(result, StructureAnalysisResult)
        assert len(result.sections) > 0
        assert result.confidence >= 0.0
        assert result.analysis_time > 0.0
        assert result.algorithm_used == "librosa_segmentation"
        assert len(result.features_used) > 0


@pytest.fixture
def test_config():
    """Test configuration for structure analyzer."""
    return {
        'structure': {
            'auto_detect': True,
            'confidence_threshold': 0.7,
            'min_section_duration': 8.0,
            'max_sections': 20,
            'hop_length': 512,
            'frame_length': 2048,
            'n_mels': 128,
            'feature_weights': {
                'energy': 0.3,
                'spectral_centroid': 0.2,
                'mfcc': 0.25,
                'chroma': 0.15,
                'tempo': 0.1
            }
        }
    }
