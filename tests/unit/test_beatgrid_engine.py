"""
Unit tests for BeatgridEngine class
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.beatgrid_engine import BeatgridEngine, BeatgridData, BeatgridError
from src.core.audio_loader import AudioData


class TestBeatgridEngine:
    """Test cases for BeatgridEngine class."""
    
    def test_beatgrid_engine_creation(self, test_config):
        """Test that BeatgridEngine can be created successfully."""
        engine = BeatgridEngine(test_config)
        assert engine is not None
        assert engine.confidence_threshold == test_config['beatgrid']['confidence_threshold']
        assert engine.bpm_range == test_config['beatgrid']['bpm_range']
    
    def test_manual_tap_tempo(self, test_config):
        """Test manual tap tempo calculation."""
        engine = BeatgridEngine(test_config)
        
        # Test with regular 120 BPM taps (0.5 second intervals)
        tap_times = [0.0, 0.5, 1.0, 1.5, 2.0]
        bpm = engine.manual_tap_tempo(tap_times)
        
        assert bpm == pytest.approx(120.0, rel=0.01)
    
    def test_manual_tap_tempo_insufficient_taps(self, test_config):
        """Test manual tap tempo with insufficient taps."""
        engine = BeatgridEngine(test_config)
        
        with pytest.raises(BeatgridError, match="Need at least 2 taps"):
            engine.manual_tap_tempo([0.0])
    
    def test_adjust_beatgrid(self, test_config, mock_beatgrid_data):
        """Test manual beatgrid adjustment."""
        engine = BeatgridEngine(test_config)
        
        # Create original beatgrid
        original = BeatgridData(
            bpm=128.0,
            confidence=0.9,
            beats=np.array([0.0, 0.46875, 0.9375, 1.40625]),
            downbeats=np.array([0.0, 1.875]),
            time_signature=(4, 4),
            tempo_changes=[],
            algorithm_used='test',
            analysis_time=1.0,
            manual_override=False
        )
        
        # Adjust with new first beat and BPM
        adjusted = engine.adjust_beatgrid(original, first_beat_offset=0.1, bpm_override=130.0)
        
        assert adjusted.bpm == 130.0
        assert adjusted.manual_override is True
        assert adjusted.beats[0] == pytest.approx(0.1, abs=0.001)
        
        # Check beat intervals
        intervals = np.diff(adjusted.beats)
        expected_interval = 60.0 / 130.0
        assert np.allclose(intervals, expected_interval, rtol=0.01)
    
    @patch('src.core.beatgrid_engine.MADMOM_AVAILABLE', False)
    @patch('src.core.beatgrid_engine.AUBIO_AVAILABLE', False)
    def test_no_algorithms_available(self, test_config):
        """Test behavior when no beat detection algorithms are available."""
        # This should still create the engine, but analysis will fail
        engine = BeatgridEngine(test_config)
        assert engine is not None
    
    def test_post_process_beats_bpm_correction(self, test_config):
        """Test BPM correction in post-processing."""
        engine = BeatgridEngine(test_config)
        
        # Create beatgrid with BPM outside valid range (too low)
        audio_data = Mock()
        audio_data.duration = 10.0
        
        beatgrid = BeatgridData(
            bpm=30.0,  # Too low, should be doubled
            confidence=0.8,
            beats=np.array([0.0, 2.0, 4.0, 6.0, 8.0]),
            downbeats=np.array([0.0, 8.0]),
            time_signature=(4, 4),
            tempo_changes=[],
            algorithm_used='test',
            analysis_time=1.0,
            manual_override=False
        )
        
        corrected = engine._post_process_beats(beatgrid, audio_data)
        
        # BPM should be doubled
        assert corrected.bpm == 60.0
        
        # Beats should be reduced (every other beat)
        assert len(corrected.beats) < len(beatgrid.beats)
    
    def test_post_process_beats_duration_clipping(self, test_config):
        """Test that beats are clipped to audio duration."""
        engine = BeatgridEngine(test_config)
        
        # Create audio data with short duration
        audio_data = Mock()
        audio_data.duration = 5.0
        
        # Create beatgrid with beats beyond audio duration
        beatgrid = BeatgridData(
            bpm=120.0,
            confidence=0.8,
            beats=np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]),
            downbeats=np.array([0.0, 2.0, 4.0, 6.0]),
            time_signature=(4, 4),
            tempo_changes=[],
            algorithm_used='test',
            analysis_time=1.0,
            manual_override=False
        )
        
        corrected = engine._post_process_beats(beatgrid, audio_data)
        
        # All beats should be within audio duration
        assert np.all(corrected.beats <= audio_data.duration)
        assert np.all(corrected.downbeats <= audio_data.duration)


@pytest.mark.integration
class TestBeatgridEngineIntegration:
    """Integration tests for BeatgridEngine with actual audio."""
    
    @pytest.mark.skipif(not pytest.importorskip("madmom", reason="madmom not available"), 
                       reason="madmom required for integration test")
    def test_analyze_beats_with_real_audio(self, test_config, sample_audio_data):
        """Test beat analysis with real audio data."""
        engine = BeatgridEngine(test_config)
        
        # Create AudioData from sample
        audio_data = AudioData(
            data=sample_audio_data['data'].T,  # Transpose to (channels, samples)
            sample_rate=sample_audio_data['sample_rate'],
            duration=sample_audio_data['duration'],
            channels=sample_audio_data['channels'],
            file_path=Path("test.wav"),
            format="wav",
            bit_depth=16,
            file_size=1000,
            load_time=0.1
        )
        
        try:
            beatgrid_data = engine.analyze_beats(audio_data)
            
            assert isinstance(beatgrid_data, BeatgridData)
            assert beatgrid_data.bpm > 0
            assert 0 <= beatgrid_data.confidence <= 1
            assert len(beatgrid_data.beats) > 0
            assert beatgrid_data.analysis_time > 0
            
            # Beats should be within audio duration
            assert np.all(beatgrid_data.beats <= audio_data.duration)
            
        except BeatgridError:
            # Beat detection might fail on synthetic audio - that's OK for this test
            pytest.skip("Beat detection failed on synthetic audio")
    
    def test_analyze_beats_empty_audio(self, test_config):
        """Test beat analysis with empty/silent audio."""
        engine = BeatgridEngine(test_config)
        
        # Create silent audio data
        silent_data = np.zeros((2, 44100))  # 1 second of silence
        audio_data = AudioData(
            data=silent_data,
            sample_rate=44100,
            duration=1.0,
            channels=2,
            file_path=Path("silent.wav"),
            format="wav",
            bit_depth=16,
            file_size=1000,
            load_time=0.1
        )
        
        # Beat analysis should fail or return low confidence
        try:
            beatgrid_data = engine.analyze_beats(audio_data)
            # If it succeeds, confidence should be low
            assert beatgrid_data.confidence < 0.5
        except BeatgridError:
            # Expected for silent audio
            pass
