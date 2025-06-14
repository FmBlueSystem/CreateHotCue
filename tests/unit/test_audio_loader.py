"""
Unit tests for AudioLoader class
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.audio_loader import AudioLoader, AudioData, AudioLoadError


class TestAudioLoader:
    """Test cases for AudioLoader class."""
    
    def test_audio_loader_creation(self, test_config):
        """Test that AudioLoader can be created successfully."""
        loader = AudioLoader(test_config)
        assert loader is not None
        assert loader.target_sample_rate == test_config['audio']['sample_rate']
        assert loader.supported_formats == test_config['audio']['supported_formats']
    
    def test_supported_format_detection(self, test_config):
        """Test detection of supported audio formats."""
        loader = AudioLoader(test_config)
        
        # Test supported formats
        for fmt in test_config['audio']['supported_formats']:
            test_file = Path(f"test.{fmt}")
            assert loader.is_supported_format(test_file) is True
        
        # Test unsupported format
        unsupported_file = Path("test.xyz")
        assert loader.is_supported_format(unsupported_file) is False
    
    def test_file_info_nonexistent_file(self, test_config):
        """Test file info for non-existent file."""
        loader = AudioLoader(test_config)
        
        with pytest.raises(AudioLoadError, match="File not found"):
            loader.get_file_info("nonexistent.mp3")
    
    def test_file_info_unsupported_format(self, test_config, tmp_path):
        """Test file info for unsupported format."""
        loader = AudioLoader(test_config)
        
        # Create a dummy file with unsupported extension
        dummy_file = tmp_path / "test.xyz"
        dummy_file.write_text("dummy content")
        
        with pytest.raises(AudioLoadError, match="Unsupported format"):
            loader.get_file_info(dummy_file)
    
    @patch('src.core.audio_loader.sf.info')
    def test_get_file_info_success(self, mock_sf_info, test_config, tmp_path):
        """Test successful file info retrieval."""
        loader = AudioLoader(test_config)
        
        # Create a dummy WAV file
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy wav content")
        
        # Mock soundfile info
        mock_info = Mock()
        mock_info.samplerate = 44100
        mock_info.channels = 2
        mock_info.frames = 220500
        mock_info.duration = 5.0
        mock_sf_info.return_value = mock_info
        
        info = loader.get_file_info(test_file)
        
        assert info['file_path'] == test_file
        assert info['format'] == 'wav'
        assert info['sample_rate'] == 44100
        assert info['channels'] == 2
        assert info['duration'] == 5.0
    
    def test_load_audio_nonexistent_file(self, test_config):
        """Test loading non-existent audio file."""
        loader = AudioLoader(test_config)
        
        with pytest.raises(AudioLoadError):
            loader.load_audio("nonexistent.mp3")
    
    @patch('src.core.audio_loader.librosa.load')
    @patch('src.core.audio_loader.sf.info')
    def test_load_audio_success(self, mock_sf_info, mock_librosa_load, 
                               test_config, tmp_path):
        """Test successful audio loading."""
        loader = AudioLoader(test_config)
        
        # Create a dummy WAV file
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"dummy wav content")
        
        # Mock soundfile info
        mock_info = Mock()
        mock_info.samplerate = 44100
        mock_info.channels = 2
        mock_info.frames = 220500
        mock_info.duration = 5.0
        mock_sf_info.return_value = mock_info
        
        # Mock librosa load
        sample_data = np.random.random((2, 220500)).astype(np.float32)
        mock_librosa_load.return_value = (sample_data, 44100)
        
        audio_data = loader.load_audio(test_file)
        
        assert isinstance(audio_data, AudioData)
        assert audio_data.file_path == test_file
        assert audio_data.sample_rate == 44100
        assert audio_data.channels == 2
        assert audio_data.duration == pytest.approx(5.0, rel=0.1)
        assert audio_data.data.shape == (2, 220500)
    
    def test_generate_waveform_data(self, test_config, sample_audio_data):
        """Test waveform data generation."""
        loader = AudioLoader(test_config)
        
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
        
        waveform_data = loader.generate_waveform_data(audio_data, zoom_levels=[1, 2, 4])
        
        assert isinstance(waveform_data, dict)
        assert 1 in waveform_data
        assert 2 in waveform_data
        assert 4 in waveform_data
        
        # Check that higher zoom levels have fewer samples
        assert waveform_data[4].shape[-1] <= waveform_data[2].shape[-1]
        assert waveform_data[2].shape[-1] <= waveform_data[1].shape[-1]
    
    def test_calculate_rms_energy(self, test_config, sample_audio_data):
        """Test RMS energy calculation."""
        loader = AudioLoader(test_config)
        
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
        
        rms_data = loader.calculate_rms_energy(audio_data)
        
        assert isinstance(rms_data, np.ndarray)
        assert rms_data.shape[0] == audio_data.channels
        assert rms_data.shape[1] > 0  # Should have RMS values
        
        # RMS values should be positive
        assert np.all(rms_data >= 0)
    
    def test_cleanup(self, test_config):
        """Test loader cleanup."""
        loader = AudioLoader(test_config)
        
        # Should not raise any exceptions
        loader.cleanup()


@pytest.mark.integration
class TestAudioLoaderIntegration:
    """Integration tests for AudioLoader with actual files."""
    
    def test_load_real_audio_file(self, test_config, temp_audio_file):
        """Test loading an actual audio file."""
        loader = AudioLoader(test_config)
        
        # Get file info first
        info = loader.get_file_info(temp_audio_file)
        assert info['format'] == 'wav'
        assert info['duration'] > 0
        
        # Load audio data
        audio_data = loader.load_audio(temp_audio_file)
        
        assert isinstance(audio_data, AudioData)
        assert audio_data.file_path == temp_audio_file
        assert audio_data.sample_rate == test_config['audio']['sample_rate']
        assert audio_data.duration > 0
        assert audio_data.data.shape[0] > 0  # Has channels
        assert audio_data.data.shape[1] > 0  # Has samples
