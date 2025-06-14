"""
Unit tests for Enhanced MetadataParser with advanced features
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.core.metadata_parser import MetadataParser, TrackMetadata, MetadataError


class TestEnhancedMetadataParser:
    """Test cases for enhanced MetadataParser functionality."""
    
    def test_enhanced_initialization(self, enhanced_metadata_config):
        """Test enhanced MetadataParser initialization."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            assert parser.validation_enabled == enhanced_metadata_config['metadata']['validation_enabled']
            assert parser.cache_enabled == enhanced_metadata_config['metadata']['cache_enabled']
            assert parser.batch_processing == enhanced_metadata_config['metadata']['batch_processing']
            assert parser.integrity_checks == enhanced_metadata_config['metadata']['integrity_checks']
            assert parser.auto_repair == enhanced_metadata_config['metadata']['auto_repair']
            
            # Check enhanced attributes
            assert hasattr(parser, '_metadata_cache')
            assert hasattr(parser, '_file_checksums')
            assert hasattr(parser, '_operation_stats')
            assert parser._operation_stats['reads'] == 0
    
    def test_metadata_caching(self, enhanced_metadata_config, tmp_path):
        """Test metadata caching functionality."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            enhanced_metadata_config['metadata']['cache_enabled'] = True
            parser = MetadataParser(enhanced_metadata_config)
            
            # Create test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"fake mp3 content")
            
            # Mock metadata reading
            test_metadata = TrackMetadata(title="Test Title", artist="Test Artist")
            
            with patch.object(parser, '_read_with_mutagen', return_value=test_metadata):
                # First read (cache miss)
                result1 = parser.read_metadata(test_file, use_cache=True)
                assert parser._operation_stats['cache_misses'] == 1
                assert parser._operation_stats['cache_hits'] == 0
                
                # Second read (cache hit)
                result2 = parser.read_metadata(test_file, use_cache=True)
                assert parser._operation_stats['cache_misses'] == 1
                assert parser._operation_stats['cache_hits'] == 1
                
                assert result1.title == result2.title
    
    def test_file_checksum_validation(self, enhanced_metadata_config, tmp_path):
        """Test file checksum validation for cache invalidation."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            # Create test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"original content")
            
            # Calculate initial checksum
            checksum1 = parser._calculate_file_checksum(test_file)
            
            # Modify file
            time.sleep(0.1)  # Ensure different mtime
            test_file.write_bytes(b"modified content")
            
            # Calculate new checksum
            checksum2 = parser._calculate_file_checksum(test_file)
            
            assert checksum1 != checksum2
    
    def test_metadata_validation(self, enhanced_metadata_config):
        """Test metadata validation functionality."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            # Test valid metadata
            valid_metadata = TrackMetadata(
                title="Valid Title",
                artist="Valid Artist",
                year=2023,
                bpm=128.0,
                track_number=1
            )
            
            errors = parser._validate_metadata(valid_metadata)
            assert len(errors) == 0
            
            # Test invalid metadata
            invalid_metadata = TrackMetadata(
                title="Valid Title",
                artist="Valid Artist",
                year=1800,  # Too old
                bpm=500.0,  # Too high
                track_number=-1  # Invalid
            )
            
            errors = parser._validate_metadata(invalid_metadata)
            assert len(errors) >= 3
            assert any("Suspicious year" in error for error in errors)
            assert any("Suspicious BPM" in error for error in errors)
            assert any("Invalid track number" in error for error in errors)
    
    def test_metadata_repair(self, enhanced_metadata_config):
        """Test automatic metadata repair functionality."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            # Create metadata with issues
            problematic_metadata = TrackMetadata(
                title="Valid Title",
                year=1800,  # Will be repaired
                bpm=500.0,  # Will be repaired
                track_number=-1  # Will be repaired
            )
            
            errors = ["Suspicious year: 1800", "Suspicious BPM: 500.0", "Invalid track number: -1"]
            
            # Repair metadata
            repaired = parser._repair_metadata(problematic_metadata, errors)
            
            assert repaired.year is None  # Should be reset
            assert repaired.bpm is None   # Should be reset
            assert repaired.track_number is None  # Should be reset
            assert repaired.title == "Valid Title"  # Should be preserved
            assert parser._operation_stats['repairs'] > 0
    
    def test_encoding_repair(self, enhanced_metadata_config):
        """Test encoding issue repair."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            # Create metadata with encoding issues
            problematic_metadata = TrackMetadata(
                title="Title with bad chars \xff\xfe",
                artist="Normal Artist"
            )
            
            errors = ["Encoding issue in text field: Title with bad chars"]
            
            # Repair metadata
            repaired = parser._repair_metadata(problematic_metadata, errors)
            
            # Should have cleaned encoding
            assert "\xff" not in repaired.title
            assert "\xfe" not in repaired.title
            assert repaired.artist == "Normal Artist"  # Should be preserved
    
    @patch('src.core.metadata_parser.concurrent.futures.ThreadPoolExecutor')
    def test_batch_processing(self, mock_executor, enhanced_metadata_config, tmp_path):
        """Test batch metadata processing."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            enhanced_metadata_config['metadata']['batch_processing'] = True
            parser = MetadataParser(enhanced_metadata_config)
            
            # Create test files
            test_files = []
            for i in range(3):
                test_file = tmp_path / f"test{i}.mp3"
                test_file.write_bytes(f"fake mp3 content {i}".encode())
                test_files.append(test_file)
            
            # Mock executor
            mock_future = MagicMock()
            mock_future.result.return_value = (str(test_files[0]), TrackMetadata(title="Test"), None)
            mock_executor.return_value.__enter__.return_value.submit.return_value = mock_future
            mock_executor.return_value.__enter__.return_value.as_completed.return_value = [mock_future] * 3
            
            # Execute batch processing
            result = parser.read_metadata_batch(test_files, max_workers=2)
            
            assert 'success' in result
            assert 'failed' in result
            assert 'total_time' in result
            assert 'stats' in result
            assert result['stats']['total_files'] == 3
    
    def test_cache_size_limit(self, enhanced_metadata_config, tmp_path):
        """Test cache size limiting."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            # Fill cache beyond limit
            for i in range(1100):  # More than max_cache_size (1000)
                file_key = f"test_file_{i}"
                metadata = TrackMetadata(title=f"Title {i}")
                parser._metadata_cache[file_key] = metadata
                parser._file_checksums[file_key] = f"checksum_{i}"
            
            # Trigger cache cleanup by adding one more
            test_file = tmp_path / "trigger.mp3"
            test_file.write_bytes(b"content")
            parser._cache_metadata(test_file, "trigger_key", TrackMetadata())
            
            # Cache should be limited
            assert len(parser._metadata_cache) <= 1000
    
    def test_cache_statistics(self, enhanced_metadata_config):
        """Test cache statistics reporting."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            # Simulate some operations
            parser._operation_stats['reads'] = 10
            parser._operation_stats['writes'] = 5
            parser._operation_stats['cache_hits'] = 7
            parser._operation_stats['cache_misses'] = 3
            parser._operation_stats['repairs'] = 2
            
            stats = parser.get_cache_stats()
            
            assert stats['cache']['enabled'] == parser.cache_enabled
            assert stats['cache']['hit_ratio'] == 70.0  # 7/(7+3) * 100
            assert stats['operations']['reads'] == 10
            assert stats['operations']['repairs'] == 2
            assert stats['settings']['validation_enabled'] == parser.validation_enabled
    
    def test_cache_clearing(self, enhanced_metadata_config):
        """Test cache clearing functionality."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            parser = MetadataParser(enhanced_metadata_config)
            
            # Add some cache entries
            parser._metadata_cache['test1'] = TrackMetadata(title="Test 1")
            parser._metadata_cache['test2'] = TrackMetadata(title="Test 2")
            parser._file_checksums['test1'] = "checksum1"
            parser._file_checksums['test2'] = "checksum2"
            parser._operation_stats['cache_hits'] = 5
            parser._operation_stats['cache_misses'] = 3
            
            # Clear cache
            parser.clear_cache()
            
            assert len(parser._metadata_cache) == 0
            assert len(parser._file_checksums) == 0
            assert parser._operation_stats['cache_hits'] == 0
            assert parser._operation_stats['cache_misses'] == 0
    
    def test_enhanced_read_with_validation(self, enhanced_metadata_config, tmp_path):
        """Test enhanced read with validation and repair."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            enhanced_metadata_config['metadata']['validation_enabled'] = True
            enhanced_metadata_config['metadata']['auto_repair'] = True
            parser = MetadataParser(enhanced_metadata_config)
            
            # Create test file
            test_file = tmp_path / "test.mp3"
            test_file.write_bytes(b"fake mp3 content")
            
            # Mock metadata with issues
            problematic_metadata = TrackMetadata(
                title="Test Title",
                year=1800,  # Will trigger validation error
                bpm=128.0
            )
            
            with patch.object(parser, '_read_with_mutagen', return_value=problematic_metadata):
                with patch.object(parser, '_validate_metadata', return_value=["Suspicious year: 1800"]):
                    with patch.object(parser, '_repair_metadata') as mock_repair:
                        repaired_metadata = TrackMetadata(title="Test Title", year=None, bpm=128.0)
                        mock_repair.return_value = repaired_metadata
                        
                        result = parser.read_metadata(test_file)
                        
                        assert result.year is None  # Should be repaired
                        assert result.title == "Test Title"
                        mock_repair.assert_called_once()
    
    def test_disabled_features(self, enhanced_metadata_config):
        """Test behavior when advanced features are disabled."""
        with patch('src.core.metadata_parser.MUTAGEN_AVAILABLE', True):
            # Disable advanced features
            enhanced_metadata_config['metadata']['cache_enabled'] = False
            enhanced_metadata_config['metadata']['validation_enabled'] = False
            enhanced_metadata_config['metadata']['batch_processing'] = False
            
            parser = MetadataParser(enhanced_metadata_config)
            
            assert not parser.cache_enabled
            assert not parser.validation_enabled
            assert not parser.batch_processing
            
            # Batch processing should raise error when disabled
            with pytest.raises(MetadataError, match="Batch processing is disabled"):
                parser.read_metadata_batch([Path("test.mp3")])


@pytest.fixture
def enhanced_metadata_config():
    """Enhanced test configuration for metadata parser."""
    return {
        'cues': {
            'backup_on_write': True,
            'formats': ['id3v24', 'mp4', 'vorbis', 'json']
        },
        'metadata': {
            'validation_enabled': True,
            'cache_enabled': True,
            'batch_processing': True,
            'integrity_checks': True,
            'auto_repair': True
        }
    }
