"""
Unit tests for CueManager class
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock

from src.core.cue_manager import CueManager, CuePoint, CueType, CueManagerError


class TestCuePoint:
    """Test cases for CuePoint class."""
    
    def test_cue_point_creation(self):
        """Test CuePoint creation with valid data."""
        cue = CuePoint(
            id=1,
            position_ms=5000.0,
            label="Intro",
            color="#FF3366"
        )
        
        assert cue.id == 1
        assert cue.position_ms == 5000.0
        assert cue.position_seconds == 5.0
        assert cue.label == "Intro"
        assert cue.color == "#FF3366"
        assert cue.type == CueType.HOT_CUE
    
    def test_cue_point_validation(self):
        """Test CuePoint validation."""
        # Invalid ID
        with pytest.raises(ValueError, match="Cue ID must be between 1-16"):
            CuePoint(id=0, position_ms=1000.0, label="Test", color="#FF0000")
        
        with pytest.raises(ValueError, match="Cue ID must be between 1-16"):
            CuePoint(id=17, position_ms=1000.0, label="Test", color="#FF0000")
        
        # Invalid position
        with pytest.raises(ValueError, match="Position must be non-negative"):
            CuePoint(id=1, position_ms=-100.0, label="Test", color="#FF0000")
        
        # Invalid color
        with pytest.raises(ValueError, match="Color must be hex format"):
            CuePoint(id=1, position_ms=1000.0, label="Test", color="red")
    
    def test_position_seconds_property(self):
        """Test position_seconds property getter and setter."""
        cue = CuePoint(id=1, position_ms=5000.0, label="Test", color="#FF0000")
        
        assert cue.position_seconds == 5.0
        
        # Test setter
        cue.position_seconds = 10.5
        assert cue.position_ms == 10500.0
        assert cue.position_seconds == 10.5
    
    def test_cue_point_serialization(self):
        """Test CuePoint to_dict and from_dict."""
        original = CuePoint(
            id=2,
            position_ms=7500.0,
            label="Drop",
            color="#00FF88",
            type=CueType.FADE_IN
        )
        
        # Test to_dict
        data = original.to_dict()
        assert data['id'] == 2
        assert data['position_ms'] == 7500.0
        assert data['label'] == "Drop"
        assert data['color'] == "#00FF88"
        assert data['type'] == "fade_in"
        
        # Test from_dict
        restored = CuePoint.from_dict(data)
        assert restored.id == original.id
        assert restored.position_ms == original.position_ms
        assert restored.label == original.label
        assert restored.color == original.color
        assert restored.type == original.type


class TestCueManager:
    """Test cases for CueManager class."""
    
    def test_cue_manager_creation(self, test_config):
        """Test CueManager creation."""
        manager = CueManager(test_config)
        
        assert manager.max_cues == test_config['cues']['max_cues']
        assert len(manager.cue_points) == 0
        assert manager.track_duration_ms == 0.0
    
    def test_set_track(self, test_config):
        """Test setting track information."""
        manager = CueManager(test_config)
        
        file_path = Path("test_track.mp3")
        duration_ms = 180000.0  # 3 minutes
        
        manager.set_track(file_path, duration_ms)
        
        assert manager.track_file_path == file_path
        assert manager.track_duration_ms == duration_ms
        assert len(manager.cue_points) == 0  # Should clear existing cues
    
    def test_add_cue_point(self, test_config):
        """Test adding cue points."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add valid cue point
        cue = manager.add_cue_point(1, 5000.0, "Intro", "#FF3366")
        
        assert cue.id == 1
        assert cue.position_ms == 5000.0
        assert cue.label == "Intro"
        assert cue.color == "#FF3366"
        assert 1 in manager.cue_points
    
    def test_add_cue_point_auto_label_color(self, test_config):
        """Test adding cue point with auto-generated label and color."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        cue = manager.add_cue_point(3, 10000.0)
        
        assert cue.label == "Cue 3"
        assert cue.color in manager.default_colors
    
    def test_add_cue_point_validation(self, test_config):
        """Test cue point validation during addition."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Invalid cue ID
        with pytest.raises(CueManagerError, match="Cue ID must be between"):
            manager.add_cue_point(0, 5000.0)
        
        # Position outside track duration
        with pytest.raises(CueManagerError, match="Position.*outside track duration"):
            manager.add_cue_point(1, 200000.0)  # Beyond 180s track
    
    def test_remove_cue_point(self, test_config):
        """Test removing cue points."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cue point
        manager.add_cue_point(1, 5000.0)
        assert 1 in manager.cue_points
        
        # Remove existing cue
        result = manager.remove_cue_point(1)
        assert result is True
        assert 1 not in manager.cue_points
        
        # Remove non-existing cue
        result = manager.remove_cue_point(2)
        assert result is False
    
    def test_get_cue_point(self, test_config):
        """Test getting cue points."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cue point
        original = manager.add_cue_point(1, 5000.0, "Test")
        
        # Get existing cue
        retrieved = manager.get_cue_point(1)
        assert retrieved is not None
        assert retrieved.id == original.id
        assert retrieved.position_ms == original.position_ms
        
        # Get non-existing cue
        missing = manager.get_cue_point(2)
        assert missing is None
    
    def test_get_all_cue_points_sorted(self, test_config):
        """Test getting all cue points sorted by position."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cues out of order
        manager.add_cue_point(3, 15000.0, "Third")
        manager.add_cue_point(1, 5000.0, "First")
        manager.add_cue_point(2, 10000.0, "Second")
        
        all_cues = manager.get_all_cue_points()
        
        assert len(all_cues) == 3
        assert all_cues[0].position_ms == 5000.0   # First by position
        assert all_cues[1].position_ms == 10000.0  # Second by position
        assert all_cues[2].position_ms == 15000.0  # Third by position
    
    def test_get_cue_points_in_range(self, test_config):
        """Test getting cue points within time range."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cues at different positions
        manager.add_cue_point(1, 5000.0)   # 5s
        manager.add_cue_point(2, 15000.0)  # 15s
        manager.add_cue_point(3, 25000.0)  # 25s
        manager.add_cue_point(4, 35000.0)  # 35s
        
        # Get cues in range 10s-30s
        range_cues = manager.get_cue_points_in_range(10000.0, 30000.0)
        
        assert len(range_cues) == 2
        positions = [cue.position_ms for cue in range_cues]
        assert 15000.0 in positions
        assert 25000.0 in positions
    
    def test_find_nearest_cue(self, test_config):
        """Test finding nearest cue point."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cues
        manager.add_cue_point(1, 5000.0)   # 5s
        manager.add_cue_point(2, 15000.0)  # 15s
        
        # Find nearest to 6s (should be cue 1 at 5s)
        nearest = manager.find_nearest_cue(6000.0, max_distance_ms=2000.0)
        assert nearest is not None
        assert nearest.id == 1
        
        # Find nearest to 20s with small max distance (should find nothing)
        nearest = manager.find_nearest_cue(20000.0, max_distance_ms=1000.0)
        assert nearest is None
        
        # Find nearest to 14s (should be cue 2 at 15s)
        nearest = manager.find_nearest_cue(14000.0, max_distance_ms=2000.0)
        assert nearest is not None
        assert nearest.id == 2
    
    def test_update_cue_properties(self, test_config):
        """Test updating cue point properties."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cue
        manager.add_cue_point(1, 5000.0, "Original", "#FF0000")
        
        # Update label
        result = manager.update_cue_label(1, "Updated Label")
        assert result is True
        assert manager.get_cue_point(1).label == "Updated Label"
        
        # Update color
        result = manager.update_cue_color(1, "#00FF00")
        assert result is True
        assert manager.get_cue_point(1).color == "#00FF00"
        
        # Update non-existing cue
        result = manager.update_cue_label(99, "Test")
        assert result is False
    
    def test_clear_all_cues(self, test_config):
        """Test clearing all cue points."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add multiple cues
        manager.add_cue_point(1, 5000.0)
        manager.add_cue_point(2, 10000.0)
        manager.add_cue_point(3, 15000.0)
        
        assert len(manager.cue_points) == 3
        
        # Clear all
        count = manager.clear_all_cues()
        
        assert count == 3
        assert len(manager.cue_points) == 0
    
    def test_export_import_json(self, test_config):
        """Test JSON export and import."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Add cues
        manager.add_cue_point(1, 5000.0, "Intro", "#FF0000")
        manager.add_cue_point(2, 15000.0, "Drop", "#00FF00")
        
        # Export
        exported_data = manager.export_to_json()
        
        assert 'cue_points' in exported_data
        assert len(exported_data['cue_points']) == 2
        assert exported_data['track_duration_ms'] == 180000.0
        
        # Clear and import
        manager.clear_all_cues()
        assert len(manager.cue_points) == 0
        
        imported_count = manager.import_from_json(exported_data)
        
        assert imported_count == 2
        assert len(manager.cue_points) == 2
        assert manager.get_cue_point(1).label == "Intro"
        assert manager.get_cue_point(2).label == "Drop"
    
    def test_get_statistics(self, test_config):
        """Test cue point statistics."""
        manager = CueManager(test_config)
        manager.set_track(Path("test.mp3"), 180000.0)
        
        # Empty statistics
        stats = manager.get_statistics()
        assert stats['total_cues'] == 0
        
        # Add cues
        manager.add_cue_point(1, 5000.0)
        manager.add_cue_point(2, 15000.0)
        manager.add_cue_point(3, 25000.0)
        
        stats = manager.get_statistics()
        
        assert stats['total_cues'] == 3
        assert stats['first_cue_ms'] == 5000.0
        assert stats['last_cue_ms'] == 25000.0
        assert stats['average_spacing_ms'] == 10000.0  # (15-5 + 25-15) / 2
