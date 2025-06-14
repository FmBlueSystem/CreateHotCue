"""
Unit tests for Enhanced CueManager with advanced features
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.cue_manager import CueManager, CuePoint, CueType, CueManagerError


class TestEnhancedCueManager:
    """Test cases for enhanced CueManager functionality."""
    
    def test_enhanced_initialization(self, enhanced_test_config):
        """Test enhanced CueManager initialization."""
        manager = CueManager(enhanced_test_config)
        
        assert manager.validation_strict == enhanced_test_config['cues']['validation_strict']
        assert manager.cache_enabled == enhanced_test_config['cues']['cache_enabled']
        assert manager.batch_operations == enhanced_test_config['cues']['batch_operations']
        assert manager.conflict_resolution == enhanced_test_config['cues']['conflict_resolution']
        
        # Check enhanced attributes
        assert hasattr(manager, '_cue_cache')
        assert hasattr(manager, '_validation_cache')
        assert hasattr(manager, '_operation_history')
        assert hasattr(manager, '_conflict_log')
        assert manager.cache_hits == 0
        assert manager.cache_misses == 0
    
    def test_enhanced_validation(self, enhanced_test_config):
        """Test enhanced cue point validation."""
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Test strict validation
        errors = manager._validate_cue_point(1, 5000.0, "Test Label", "#FF0000", True)
        assert len(errors) == 0
        
        # Test validation with errors
        errors = manager._validate_cue_point(0, -1000.0, "A" * 60, "invalid_color", True)
        assert len(errors) > 0
        assert any("Cue ID must be between" in error for error in errors)
        assert any("Position cannot be negative" in error for error in errors)
        assert any("Label too long" in error for error in errors)
        assert any("Invalid color format" in error for error in errors)
    
    def test_validation_caching(self, enhanced_test_config):
        """Test validation result caching."""
        enhanced_test_config['cues']['cache_enabled'] = True
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # First validation (cache miss)
        errors1 = manager._validate_cue_point(1, 5000.0, "Test", "#FF0000", True)
        assert manager.cache_misses == 1
        assert manager.cache_hits == 0
        
        # Second validation (cache hit)
        errors2 = manager._validate_cue_point(1, 5000.0, "Test", "#FF0000", True)
        assert manager.cache_misses == 1
        assert manager.cache_hits == 1
        assert errors1 == errors2
    
    def test_conflict_detection(self, enhanced_test_config):
        """Test cue point conflict detection."""
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add first cue
        manager.add_cue_point(1, 5000.0, "First", force=True)
        
        # Test ID conflict
        conflicts = manager._check_cue_conflicts(1, 10000.0)
        assert len(conflicts) == 1
        assert conflicts[0]['type'] == 'id_conflict'
        
        # Test position conflict
        conflicts = manager._check_cue_conflicts(2, 5030.0)  # Within 50ms
        assert len(conflicts) == 1
        assert conflicts[0]['type'] == 'position_conflict'
    
    def test_conflict_resolution_strategies(self, enhanced_test_config):
        """Test different conflict resolution strategies."""
        # Test strict resolution
        enhanced_test_config['cues']['conflict_resolution'] = 'strict'
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        manager.add_cue_point(1, 5000.0, force=True)
        
        with pytest.raises(CueManagerError, match="Conflicts detected"):
            manager.add_cue_point(1, 10000.0)  # ID conflict
        
        # Test merge resolution
        enhanced_test_config['cues']['conflict_resolution'] = 'merge'
        manager2 = CueManager(enhanced_test_config)
        manager2.set_track(Path("test.mp3"), 180000.0)
        
        manager2.add_cue_point(1, 5000.0, force=True)
        # Should succeed with warning
        cue = manager2.add_cue_point(1, 10000.0)
        assert cue.position_ms == 10000.0
    
    def test_batch_operations(self, enhanced_test_config):
        """Test batch cue point operations."""
        enhanced_test_config['cues']['batch_operations'] = True
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Prepare batch data
        cue_data = [
            {'id': 1, 'position_ms': 5000.0, 'label': 'Intro'},
            {'id': 2, 'position_ms': 15000.0, 'label': 'Build'},
            {'id': 3, 'position_ms': 25000.0, 'label': 'Drop'},
            {'id': 4, 'position_ms': 35000.0, 'label': 'Break'}
        ]
        
        # Execute batch operation
        result = manager.add_cue_points_batch(cue_data)
        
        assert len(result['added']) == 4
        assert len(result['failed']) == 0
        assert result['total_time'] > 0
        assert len(manager.cue_points) == 4
    
    def test_batch_validation(self, enhanced_test_config):
        """Test batch validation before processing."""
        enhanced_test_config['cues']['batch_operations'] = True
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Batch with errors
        cue_data = [
            {'id': 1, 'position_ms': 5000.0},  # Valid
            {'id': 1, 'position_ms': 10000.0}, # Duplicate ID
            {'position_ms': 15000.0},          # Missing ID
            {'id': 3, 'position_ms': 5010.0}   # Position conflict
        ]
        
        errors = manager._validate_batch(cue_data)
        assert len(errors) >= 2  # At least duplicate ID and missing field errors
    
    def test_cue_optimization(self, enhanced_test_config):
        """Test cue point position optimization."""
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cues with sub-optimal positions
        manager.add_cue_point(1, 5003.7, force=True)  # Will be rounded
        manager.add_cue_point(2, 15007.2, force=True)
        
        # Optimize with beat alignment
        result = manager.optimize_cue_positions('beat_align')
        
        assert result['optimized'] >= 0
        assert result['strategy'] == 'beat_align'
        assert result['time'] > 0
        
        # Check that positions were rounded
        cue1 = manager.get_cue_point(1)
        assert cue1.position_ms % 10 == 0  # Should be rounded to 10ms
    
    def test_spacing_optimization(self, enhanced_test_config):
        """Test spacing optimization strategy."""
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cues too close together
        manager.add_cue_point(1, 5000.0, force=True)
        manager.add_cue_point(2, 5050.0, force=True)  # Only 50ms apart
        manager.add_cue_point(3, 5100.0, force=True)  # Only 50ms apart
        
        # Optimize spacing
        result = manager.optimize_cue_positions('spacing_optimize')
        
        assert result['optimized'] >= 0
        
        # Check that spacing was improved
        cues = manager.get_all_cue_points()
        for i in range(1, len(cues)):
            spacing = cues[i].position_ms - cues[i-1].position_ms
            assert spacing >= 200  # Minimum 200ms spacing
    
    def test_performance_metrics(self, enhanced_test_config):
        """Test performance metrics collection."""
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Perform some operations
        manager.add_cue_point(1, 5000.0)
        manager.add_cue_point(2, 15000.0)
        manager.update_cue_label(1, "Updated")
        
        # Get metrics
        metrics = manager.get_performance_metrics()
        
        assert 'cache_stats' in metrics
        assert 'operations' in metrics
        assert 'conflicts' in metrics
        assert 'memory' in metrics
        
        assert metrics['cache_stats']['hits'] >= 0
        assert metrics['cache_stats']['misses'] >= 0
        assert metrics['operations']['total'] > 0
        assert metrics['memory']['cue_points'] == 2
    
    def test_cache_management(self, enhanced_test_config):
        """Test cache management functionality."""
        enhanced_test_config['cues']['cache_enabled'] = True
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Generate cache entries
        for i in range(10):
            manager._validate_cue_point(i+1, i*1000.0, f"Test {i}", "#FF0000", True)
        
        assert len(manager._validation_cache) > 0
        
        # Clear cache
        manager.clear_cache()
        
        assert len(manager._validation_cache) == 0
        assert manager.cache_hits == 0
        assert manager.cache_misses == 0
    
    def test_enhanced_statistics(self, enhanced_test_config):
        """Test enhanced statistics with performance data."""
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add some cues and perform operations
        manager.add_cue_point(1, 5000.0)
        manager.add_cue_point(2, 15000.0)
        manager._validate_cue_point(3, 25000.0, "Test", "#FF0000", True)
        
        stats = manager.get_statistics()
        
        # Check enhanced statistics
        assert 'cache_stats' in stats
        assert 'performance' in stats
        assert stats['cache_stats']['hit_ratio'] >= 0
        assert stats['performance']['total_operations'] >= 0
    
    def test_force_operations(self, enhanced_test_config):
        """Test force parameter to skip validation."""
        enhanced_test_config['cues']['validation_strict'] = True
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # This should fail with strict validation
        with pytest.raises(CueManagerError):
            manager.add_cue_point(0, -1000.0, "Invalid")  # Invalid ID and position
        
        # This should succeed with force=True
        cue = manager.add_cue_point(0, -1000.0, "Invalid", force=True)
        assert cue.id == 0
        assert cue.position_ms == -1000.0
    
    def test_operation_history(self, enhanced_test_config):
        """Test operation history tracking."""
        manager = CueManager(enhanced_test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Perform operations
        manager.add_cue_point(1, 5000.0)
        manager.update_cue_label(1, "Updated")
        manager.remove_cue_point(1)
        
        # Check that operations were tracked
        assert manager._total_operations > 0
        assert len(manager.operation_times) >= 0


@pytest.fixture
def enhanced_test_config():
    """Enhanced test configuration with all advanced features enabled."""
    return {
        'cues': {
            'max_cues': 16,
            'auto_save': False,  # Disable for testing
            'backup_on_write': True,
            'serato_compatibility': True,
            'validation_strict': True,
            'cache_enabled': True,
            'batch_operations': True,
            'conflict_resolution': 'merge',
            'formats': ['id3v24', 'mp4', 'vorbis', 'json'],
            'default_colors': [
                '#FF3366', '#33AAFF', '#FFAA33', '#AA33FF',
                '#33FF66', '#FF6633', '#3366FF', '#66FF33'
            ]
        }
    }
