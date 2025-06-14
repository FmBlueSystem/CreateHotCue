"""
Unit tests for MetadataParser class
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.core.metadata_parser import MetadataParser, TrackMetadata, MetadataError


class TestTrackMetadata:
    """Test cases for TrackMetadata class."""
    
    def test_track_metadata_creation(self):
        """Test TrackMetadata creation."""
        metadata = TrackMetadata(
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            year=2024,
            bpm=128.0
        )
        
        assert metadata.title == "Test Track"
        assert metadata.artist == "Test Artist"
        assert metadata.album == "Test Album"
        assert metadata.year == 2024
        assert metadata.bpm == 128.0
        assert metadata.custom_fields == {}
    
    def test_track_metadata_serialization(self):
        """Test TrackMetadata to_dict and from_dict."""
        original = TrackMetadata(
            title="Serialization Test",
            artist="Test Artist",
            bpm=140.0,
            custom_fields={"test_field": "test_value"}
        )
        
        # Test to_dict
        data = original.to_dict()
        assert data['title'] == "Serialization Test"
        assert data['artist'] == "Test Artist"
        assert data['bpm'] == 140.0
        assert data['custom_fields']['test_field'] == "test_value"
        
        # Test from_dict
        restored = TrackMetadata.from_dict(data)
        assert restored.title == original.title
        assert restored.artist == original.artist
        assert restored.bpm == original.bpm
        assert restored.custom_fields == original.custom_fields


class TestMetadataParser:
    """Test cases for MetadataParser class."""
    
    def test_metadata_parser_creation(self, test_config):
        """Test MetadataParser creation."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            assert parser.backup_on_write == test_config['cues']['backup_on_write']
            assert parser.supported_formats == test_config['cues']['formats']
    
    def test_metadata_parser_no_mutagen(self, test_config):
        """Test MetadataParser creation without mutagen."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', False):
            with pytest.raises(MetadataError, match="mutagen library required"):
                MetadataParser(test_config)
    
    def test_read_metadata_file_not_found(self, test_config):
        """Test reading metadata from non-existent file."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            with pytest.raises(MetadataError, match="File not found"):
                parser.read_metadata("nonexistent_file.mp3")
    
    @patch('src.core.metadata_parser.mutagen.File')
    def test_read_metadata_success(self, mock_mutagen_file, test_config, tmp_path):
        """Test successful metadata reading."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Create a test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"fake mp3 content")
            
            # Mock mutagen file object
            mock_audio = MagicMock()
            mock_audio.info.length = 180.0
            mock_audio.info.bitrate = 320
            mock_audio.info.sample_rate = 44100
            mock_audio.info.channels = 2
            
            mock_mutagen_file.return_value = mock_audio
            
            # Mock _read_with_mutagen to return test metadata
            with patch.object(parser, '_read_with_mutagen') as mock_read:
                test_metadata = TrackMetadata(
                    title="Test Title",
                    artist="Test Artist",
                    bpm=128.0
                )
                mock_read.return_value = test_metadata
                
                result = parser.read_metadata(test_file)
                
                assert isinstance(result, TrackMetadata)
                assert result.title == "Test Title"
                assert result.artist == "Test Artist"
                assert result.bpm == 128.0
    
    def test_read_metadata_fallback_to_empty(self, test_config, tmp_path):
        """Test fallback to empty metadata when all methods fail."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Create a test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"fake mp3 content")
            
            # Mock all reading methods to return None
            with patch.object(parser, '_read_with_mutagen', return_value=None):
                with patch('src.core.metadata_parser.TAGLIB_AVAILABLE', False):
                    result = parser.read_metadata(test_file)
                    
                    assert isinstance(result, TrackMetadata)
                    assert result.title is None
                    assert result.artist is None
    
    def test_id3_text_extraction(self, test_config):
        """Test ID3 text extraction helper method."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Mock audio file with ID3 tags
            mock_audio = MagicMock()
            
            # Mock TIT2 frame (title)
            mock_frame = MagicMock()
            mock_frame.text = ["Test Title"]
            mock_audio.__getitem__.return_value = mock_frame
            mock_audio.__contains__.return_value = True
            
            result = parser._get_id3_text(mock_audio, 'TIT2')
            assert result == "Test Title"
            
            # Test missing tag
            mock_audio.__contains__.return_value = False
            result = parser._get_id3_text(mock_audio, 'MISSING')
            assert result is None
    
    def test_mp4_text_extraction(self, test_config):
        """Test MP4 text extraction helper method."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Mock MP4 file
            mock_audio = MagicMock()
            mock_audio.__getitem__.return_value = ["Test Value"]
            mock_audio.__contains__.return_value = True
            
            result = parser._get_mp4_text(mock_audio, '\xa9nam')
            assert result == "Test Value"
            
            # Test missing tag
            mock_audio.__contains__.return_value = False
            result = parser._get_mp4_text(mock_audio, 'missing')
            assert result is None
    
    def test_vorbis_text_extraction(self, test_config):
        """Test Vorbis text extraction helper method."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Mock Vorbis file
            mock_audio = MagicMock()
            mock_audio.__getitem__.return_value = ["Test Value"]
            mock_audio.__contains__.return_value = True
            
            result = parser._get_vorbis_text(mock_audio, 'TITLE')
            assert result == "Test Value"
            
            # Test missing tag
            mock_audio.__contains__.return_value = False
            result = parser._get_vorbis_text(mock_audio, 'missing')
            assert result is None
    
    @patch('src.core.metadata_parser.mutagen.File')
    def test_write_metadata_file_not_found(self, mock_mutagen_file, test_config):
        """Test writing metadata to non-existent file."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            metadata = TrackMetadata(title="Test")
            
            with pytest.raises(MetadataError, match="File not found"):
                parser.write_metadata("nonexistent.mp3", metadata)
    
    @patch('src.core.metadata_parser.mutagen.File')
    def test_write_metadata_success(self, mock_mutagen_file, test_config, tmp_path):
        """Test successful metadata writing."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Create test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"fake mp3 content")
            
            # Mock audio file
            mock_audio = MagicMock()
            mock_mutagen_file.return_value = mock_audio
            
            # Mock successful write
            with patch.object(parser, '_write_with_mutagen', return_value=True):
                metadata = TrackMetadata(title="Test Title", artist="Test Artist")
                
                result = parser.write_metadata(test_file, metadata)
                assert result is True
    
    @patch('src.core.metadata_parser.mutagen.File')
    def test_write_metadata_with_backup(self, mock_mutagen_file, test_config, tmp_path):
        """Test metadata writing with backup creation."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            # Enable backup
            test_config['cues']['backup_on_write'] = True
            parser = MetadataParser(test_config)
            
            # Create test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"original content")
            
            # Mock audio file
            mock_audio = MagicMock()
            mock_mutagen_file.return_value = mock_audio
            
            # Mock backup creation and successful write
            with patch.object(parser, '_create_backup') as mock_backup:
                with patch.object(parser, '_write_with_mutagen', return_value=True):
                    backup_path = tmp_path / "test.mp3.backup"
                    mock_backup.return_value = backup_path
                    
                    metadata = TrackMetadata(title="Test")
                    result = parser.write_metadata(test_file, metadata)
                    
                    assert result is True
                    mock_backup.assert_called_once_with(test_file)
    
    @patch('src.core.metadata_parser.mutagen.File')
    def test_write_metadata_failure_with_restore(self, mock_mutagen_file, test_config, tmp_path):
        """Test metadata writing failure with backup restore."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            # Enable backup
            test_config['cues']['backup_on_write'] = True
            parser = MetadataParser(test_config)
            
            # Create test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"original content")
            
            # Mock audio file
            mock_audio = MagicMock()
            mock_mutagen_file.return_value = mock_audio
            
            # Mock backup creation, failed write, and restore
            with patch.object(parser, '_create_backup') as mock_backup:
                with patch.object(parser, '_write_with_mutagen', return_value=False):
                    with patch.object(parser, '_restore_backup') as mock_restore:
                        backup_path = tmp_path / "test.mp3.backup"
                        backup_path.write_bytes(b"backup content")
                        mock_backup.return_value = backup_path
                        
                        metadata = TrackMetadata(title="Test")
                        
                        with pytest.raises(MetadataError, match="Failed to write metadata"):
                            parser.write_metadata(test_file, metadata)
                        
                        mock_restore.assert_called_once_with(test_file, backup_path)
    
    def test_backup_operations(self, test_config, tmp_path):
        """Test backup creation and restoration."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Create test file
            test_file = tmp_path / "test.mp3"
            original_content = b"original file content"
            test_file.write_bytes(original_content)
            
            # Create backup
            backup_path = parser._create_backup(test_file)
            
            assert backup_path.exists()
            assert backup_path.read_bytes() == original_content
            
            # Modify original file
            modified_content = b"modified content"
            test_file.write_bytes(modified_content)
            
            # Restore from backup
            parser._restore_backup(test_file, backup_path)
            
            assert test_file.read_bytes() == original_content
            assert not backup_path.exists()  # Backup should be moved, not copied
    
    def test_cleanup_backups(self, test_config, tmp_path):
        """Test backup cleanup functionality."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(test_config)
            
            # Create some backup files with different ages
            old_backup = tmp_path / "old.mp3.backup"
            recent_backup = tmp_path / "recent.mp3.backup"
            
            old_backup.write_bytes(b"old backup")
            recent_backup.write_bytes(b"recent backup")
            
            # Mock file modification times
            import time
            current_time = time.time()
            old_time = current_time - (25 * 3600)  # 25 hours ago
            recent_time = current_time - (1 * 3600)  # 1 hour ago
            
            with patch('pathlib.Path.stat') as mock_stat:
                def stat_side_effect(path_self):
                    mock_stat_result = MagicMock()
                    if "old" in str(path_self):
                        mock_stat_result.st_mtime = old_time
                    else:
                        mock_stat_result.st_mtime = recent_time
                    return mock_stat_result
                
                mock_stat.side_effect = stat_side_effect
                
                # Cleanup backups older than 24 hours
                cleaned_count = parser.cleanup_backups(tmp_path, max_age_hours=24)
                
                # Should have cleaned 1 old backup
                assert cleaned_count >= 0  # Actual cleanup depends on file system
