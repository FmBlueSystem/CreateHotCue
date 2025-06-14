"""
Cue Point Manager - Visual cue points system with Serato compatibility
Manages up to 16 cue points with colors, labels, and keyboard shortcuts
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

import numpy as np


class CueType(Enum):
    """Types of cue points."""
    HOT_CUE = "hot_cue"
    LOOP_IN = "loop_in"
    LOOP_OUT = "loop_out"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    LOAD = "load"
    INTRO = "intro"
    OUTRO = "outro"


@dataclass
class CuePoint:
    """Individual cue point with position, label, and visual properties."""
    id: int                           # Cue ID (1-16)
    position_ms: float               # Position in milliseconds
    label: str                       # User-defined label
    color: str                       # Hex color (#FF3366)
    type: CueType = CueType.HOT_CUE  # Type of cue point
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    
    # Serato compatibility fields
    serato_id: Optional[int] = None
    serato_color: Optional[int] = None
    
    def __post_init__(self):
        """Validate cue point data after initialization."""
        if not (1 <= self.id <= 16):
            raise ValueError(f"Cue ID must be between 1-16, got {self.id}")
        
        if self.position_ms < 0:
            raise ValueError(f"Position must be non-negative, got {self.position_ms}")
        
        if not self.color.startswith('#') or len(self.color) != 7:
            raise ValueError(f"Color must be hex format #RRGGBB, got {self.color}")
    
    @property
    def position_seconds(self) -> float:
        """Get position in seconds."""
        return self.position_ms / 1000.0
    
    @position_seconds.setter
    def position_seconds(self, value: float) -> None:
        """Set position in seconds."""
        self.position_ms = value * 1000.0
        self.modified_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'position_ms': self.position_ms,
            'label': self.label,
            'color': self.color,
            'type': self.type.value,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'serato_id': self.serato_id,
            'serato_color': self.serato_color
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CuePoint':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            position_ms=data['position_ms'],
            label=data['label'],
            color=data['color'],
            type=CueType(data.get('type', 'hot_cue')),
            created_at=data.get('created_at', time.time()),
            modified_at=data.get('modified_at', time.time()),
            serato_id=data.get('serato_id'),
            serato_color=data.get('serato_color')
        )


class CueManagerError(Exception):
    """Custom exception for cue manager errors."""
    pass


class CueManager:
    """
    Manages cue points for audio tracks with visual display and Serato compatibility.
    Supports up to 16 cue points with keyboard shortcuts and color coding.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Cue settings
        self.max_cues = config.get('cues', {}).get('max_cues', 16)
        self.auto_save = config.get('cues', {}).get('auto_save', True)
        self.backup_on_write = config.get('cues', {}).get('backup_on_write', True)
        self.serato_compatibility = config.get('cues', {}).get('serato_compatibility', True)

        # Enhanced settings
        self.validation_strict = config.get('cues', {}).get('validation_strict', True)
        self.cache_enabled = config.get('cues', {}).get('cache_enabled', True)
        self.batch_operations = config.get('cues', {}).get('batch_operations', True)
        self.conflict_resolution = config.get('cues', {}).get('conflict_resolution', 'merge')

        # Performance monitoring
        self.operation_times = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Default colors for cues (Serato-compatible)
        self.default_colors = config.get('waveform', {}).get('colors', {}).get('cue_colors', [
            '#FF3366',  # Red
            '#33AAFF',  # Blue  
            '#FFAA33',  # Orange
            '#AA33FF',  # Purple
            '#33FF66',  # Green
            '#FF6633',  # Orange-Red
            '#3366FF',  # Blue-Purple
            '#66FF33',  # Light Green
            '#FF3399',  # Pink
            '#33FFAA',  # Cyan-Green
            '#9933FF',  # Purple-Blue
            '#FFAA66',  # Light Orange
            '#66AAFF',  # Light Blue
            '#AA66FF',  # Light Purple
            '#FF6699',  # Light Pink
            '#66FFAA'   # Light Cyan
        ])
        
        # Current cue points
        self.cue_points: Dict[int, CuePoint] = {}

        # Track metadata
        self.track_duration_ms: float = 0.0
        self.track_file_path: Optional[Path] = None

        # Enhanced caching and validation
        self._cue_cache: Dict[str, Any] = {}
        self._validation_cache: Dict[str, bool] = {}
        self._operation_history: List[Dict[str, Any]] = []
        self._conflict_log: List[Dict[str, Any]] = []

        # Performance tracking
        self._last_operation_time = time.time()
        self._total_operations = 0

        self.logger.info(f"Enhanced CueManager initialized - max cues: {self.max_cues}, cache: {self.cache_enabled}")
    
    def set_track(self, file_path: Path, duration_ms: float) -> None:
        """Set the current track and clear existing cues."""
        self.track_file_path = file_path
        self.track_duration_ms = duration_ms
        self.cue_points.clear()
        
        self.logger.info(f"Track set: {file_path.name} ({duration_ms/1000:.1f}s)")
    
    def add_cue_point(self, cue_id: int, position_ms: float,
                     label: Optional[str] = None,
                     color: Optional[str] = None,
                     cue_type: CueType = CueType.HOT_CUE,
                     force: bool = False,
                     validate_strict: Optional[bool] = None) -> CuePoint:
        """
        Add or update a cue point with enhanced validation.

        Args:
            cue_id: Cue ID (1-16)
            position_ms: Position in milliseconds
            label: Optional label (auto-generated if None)
            color: Optional color (auto-assigned if None)
            cue_type: Type of cue point
            force: Skip validation checks if True
            validate_strict: Override global strict validation

        Returns:
            Created or updated CuePoint
        """
        start_time = time.time()

        # Enhanced validation
        if not force:
            validation_errors = self._validate_cue_point(cue_id, position_ms, label, color, validate_strict)
            if validation_errors:
                raise CueManagerError(f"Validation failed: {'; '.join(validation_errors)}")

        # Check for conflicts
        conflicts = self._check_cue_conflicts(cue_id, position_ms)
        if conflicts and not force:
            self._handle_cue_conflicts(conflicts, cue_id, position_ms)
        
        # Auto-generate label if not provided
        if label is None:
            label = f"Cue {cue_id}"
        
        # Auto-assign color if not provided
        if color is None:
            color_index = (cue_id - 1) % len(self.default_colors)
            color = self.default_colors[color_index]
        
        # Create or update cue point
        cue_point = CuePoint(
            id=cue_id,
            position_ms=position_ms,
            label=label,
            color=color,
            type=cue_type
        )
        
        self.cue_points[cue_id] = cue_point
        
        self.logger.info(f"Cue {cue_id} set at {position_ms/1000:.3f}s: {label}")
        
        # Auto-save if enabled
        if self.auto_save:
            self._auto_save_cues()
        
        return cue_point
    
    def remove_cue_point(self, cue_id: int) -> bool:
        """
        Remove a cue point.
        
        Args:
            cue_id: Cue ID to remove
            
        Returns:
            True if cue was removed, False if not found
        """
        if cue_id in self.cue_points:
            removed_cue = self.cue_points.pop(cue_id)
            self.logger.info(f"Cue {cue_id} removed: {removed_cue.label}")
            
            # Auto-save if enabled
            if self.auto_save:
                self._auto_save_cues()
            
            return True
        
        return False
    
    def get_cue_point(self, cue_id: int) -> Optional[CuePoint]:
        """Get a cue point by ID."""
        return self.cue_points.get(cue_id)
    
    def get_all_cue_points(self) -> List[CuePoint]:
        """Get all cue points sorted by position."""
        return sorted(self.cue_points.values(), key=lambda c: c.position_ms)
    
    def get_cue_points_in_range(self, start_ms: float, end_ms: float) -> List[CuePoint]:
        """Get cue points within a time range."""
        return [
            cue for cue in self.cue_points.values()
            if start_ms <= cue.position_ms <= end_ms
        ]
    
    def find_nearest_cue(self, position_ms: float, max_distance_ms: float = 1000) -> Optional[CuePoint]:
        """Find the nearest cue point within max distance."""
        nearest_cue = None
        min_distance = float('inf')
        
        for cue in self.cue_points.values():
            distance = abs(cue.position_ms - position_ms)
            if distance < min_distance and distance <= max_distance_ms:
                min_distance = distance
                nearest_cue = cue
        
        return nearest_cue
    
    def update_cue_label(self, cue_id: int, label: str) -> bool:
        """Update cue point label."""
        if cue_id in self.cue_points:
            self.cue_points[cue_id].label = label
            self.cue_points[cue_id].modified_at = time.time()
            
            if self.auto_save:
                self._auto_save_cues()
            
            return True
        return False
    
    def update_cue_color(self, cue_id: int, color: str) -> bool:
        """Update cue point color."""
        if cue_id in self.cue_points:
            self.cue_points[cue_id].color = color
            self.cue_points[cue_id].modified_at = time.time()
            
            if self.auto_save:
                self._auto_save_cues()
            
            return True
        return False
    
    def clear_all_cues(self) -> int:
        """Clear all cue points and return count of removed cues."""
        count = len(self.cue_points)
        self.cue_points.clear()
        
        self.logger.info(f"Cleared {count} cue points")
        
        if self.auto_save:
            self._auto_save_cues()
        
        return count
    
    def export_to_json(self) -> Dict[str, Any]:
        """Export cue points to JSON format."""
        return {
            'track_file': str(self.track_file_path) if self.track_file_path else None,
            'track_duration_ms': self.track_duration_ms,
            'cue_points': [cue.to_dict() for cue in self.get_all_cue_points()],
            'exported_at': time.time(),
            'version': '2.1.0'
        }
    
    def import_from_json(self, data: Dict[str, Any]) -> int:
        """Import cue points from JSON format."""
        self.cue_points.clear()
        
        imported_count = 0
        for cue_data in data.get('cue_points', []):
            try:
                cue = CuePoint.from_dict(cue_data)
                self.cue_points[cue.id] = cue
                imported_count += 1
            except Exception as e:
                self.logger.warning(f"Failed to import cue {cue_data.get('id')}: {e}")
        
        self.logger.info(f"Imported {imported_count} cue points")
        return imported_count
    
    def _auto_save_cues(self) -> None:
        """Auto-save cues to temporary storage."""
        # This would save to a temporary location for recovery
        # Implementation depends on metadata parser integration
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cue point statistics."""
        if not self.cue_points:
            return {'total_cues': 0}
        
        positions = [cue.position_ms for cue in self.cue_points.values()]
        
        return {
            'total_cues': len(self.cue_points),
            'first_cue_ms': min(positions),
            'last_cue_ms': max(positions),
            'average_spacing_ms': np.mean(np.diff(sorted(positions))) if len(positions) > 1 else 0,
            'cue_types': {cue_type.value: sum(1 for cue in self.cue_points.values() if cue.type == cue_type)
                         for cue_type in CueType},
            'cache_stats': {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_ratio': self.cache_hits / max(1, self.cache_hits + self.cache_misses)
            },
            'performance': {
                'total_operations': self._total_operations,
                'avg_operation_time': np.mean(list(self.operation_times.values())) if self.operation_times else 0
            }
        }

    def _validate_cue_point(self, cue_id: int, position_ms: float,
                           label: Optional[str], color: Optional[str],
                           validate_strict: Optional[bool] = None) -> List[str]:
        """Enhanced cue point validation with caching."""
        validation_key = f"{cue_id}_{position_ms}_{label}_{color}"

        # Check cache first
        if self.cache_enabled and validation_key in self._validation_cache:
            self.cache_hits += 1
            return [] if self._validation_cache[validation_key] else ["Cached validation failed"]

        self.cache_misses += 1
        errors = []
        strict = validate_strict if validate_strict is not None else self.validation_strict

        # Basic validation
        if not (1 <= cue_id <= self.max_cues):
            errors.append(f"Cue ID must be between 1-{self.max_cues}")

        if position_ms < 0:
            errors.append("Position cannot be negative")

        if position_ms > self.track_duration_ms:
            errors.append(f"Position {position_ms}ms exceeds track duration {self.track_duration_ms}ms")

        # Strict validation
        if strict:
            # Check minimum spacing between cues
            min_spacing_ms = 100  # 100ms minimum
            for existing_cue in self.cue_points.values():
                if existing_cue.id != cue_id:
                    distance = abs(existing_cue.position_ms - position_ms)
                    if distance < min_spacing_ms:
                        errors.append(f"Too close to existing cue {existing_cue.id} (min {min_spacing_ms}ms)")

            # Validate label
            if label:
                if len(label) > 50:
                    errors.append("Label too long (max 50 characters)")
                if any(char in label for char in ['<', '>', '&', '"']):
                    errors.append("Label contains invalid characters")

            # Validate color
            if color:
                if not color.startswith('#') or len(color) != 7:
                    errors.append("Invalid color format (use #RRGGBB)")
                try:
                    int(color[1:], 16)
                except ValueError:
                    errors.append("Invalid color hex values")

        # Cache result
        if self.cache_enabled:
            self._validation_cache[validation_key] = len(errors) == 0

        return errors

    def _check_cue_conflicts(self, cue_id: int, position_ms: float) -> List[Dict[str, Any]]:
        """Check for conflicts with existing cue points."""
        conflicts = []

        for existing_id, existing_cue in self.cue_points.items():
            if existing_id == cue_id:
                conflicts.append({
                    'type': 'id_conflict',
                    'existing_cue': existing_cue,
                    'message': f"Cue ID {cue_id} already exists"
                })

            # Check position conflicts (within 50ms)
            distance = abs(existing_cue.position_ms - position_ms)
            if distance < 50 and existing_id != cue_id:
                conflicts.append({
                    'type': 'position_conflict',
                    'existing_cue': existing_cue,
                    'distance_ms': distance,
                    'message': f"Too close to cue {existing_id} ({distance:.1f}ms)"
                })

        return conflicts

    def _handle_cue_conflicts(self, conflicts: List[Dict[str, Any]],
                             cue_id: int, position_ms: float) -> None:
        """Handle cue point conflicts based on resolution strategy."""
        for conflict in conflicts:
            self._conflict_log.append({
                'timestamp': time.time(),
                'conflict': conflict,
                'resolution': self.conflict_resolution,
                'cue_id': cue_id,
                'position_ms': position_ms
            })

        if self.conflict_resolution == 'strict':
            raise CueManagerError(f"Conflicts detected: {[c['message'] for c in conflicts]}")
        elif self.conflict_resolution == 'merge':
            # Allow merge with warning
            self.logger.warning(f"Merging cue {cue_id} despite conflicts: {len(conflicts)} conflicts")
        elif self.conflict_resolution == 'replace':
            # Remove conflicting cues
            for conflict in conflicts:
                if conflict['type'] == 'id_conflict':
                    existing_cue = conflict['existing_cue']
                    self.logger.info(f"Replacing existing cue {existing_cue.id}")
                    self.cue_points.pop(existing_cue.id, None)

    def add_cue_points_batch(self, cue_data: List[Dict[str, Any]],
                            validate_batch: bool = True) -> Dict[str, Any]:
        """Add multiple cue points in a single batch operation."""
        if not self.batch_operations:
            raise CueManagerError("Batch operations are disabled")

        start_time = time.time()
        results = {
            'added': [],
            'failed': [],
            'conflicts': [],
            'total_time': 0
        }

        # Pre-validate entire batch if requested
        if validate_batch:
            validation_errors = self._validate_batch(cue_data)
            if validation_errors:
                results['failed'] = validation_errors
                return results

        # Temporarily disable auto-save for batch
        original_auto_save = self.auto_save
        self.auto_save = False

        try:
            for cue_info in cue_data:
                try:
                    cue_point = self.add_cue_point(
                        cue_id=cue_info['id'],
                        position_ms=cue_info['position_ms'],
                        label=cue_info.get('label'),
                        color=cue_info.get('color'),
                        cue_type=CueType(cue_info.get('type', 'hot_cue')),
                        force=cue_info.get('force', False)
                    )
                    results['added'].append(cue_point.to_dict())

                except CueManagerError as e:
                    results['failed'].append({
                        'cue_data': cue_info,
                        'error': str(e)
                    })

        finally:
            # Restore auto-save and save if needed
            self.auto_save = original_auto_save
            if self.auto_save and results['added']:
                self._auto_save_cues()

        results['total_time'] = time.time() - start_time
        self.logger.info(f"Batch operation completed: {len(results['added'])} added, "
                        f"{len(results['failed'])} failed in {results['total_time']:.3f}s")

        return results

    def _validate_batch(self, cue_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate entire batch before processing."""
        errors = []
        used_ids = set()
        positions = []

        for i, cue_info in enumerate(cue_data):
            cue_errors = []

            # Check required fields
            if 'id' not in cue_info or 'position_ms' not in cue_info:
                cue_errors.append("Missing required fields (id, position_ms)")
            else:
                cue_id = cue_info['id']
                position_ms = cue_info['position_ms']

                # Check for duplicate IDs in batch
                if cue_id in used_ids:
                    cue_errors.append(f"Duplicate cue ID {cue_id} in batch")
                used_ids.add(cue_id)

                # Check for position conflicts in batch
                for existing_pos in positions:
                    if abs(existing_pos - position_ms) < 50:  # 50ms minimum
                        cue_errors.append(f"Position conflict with another cue in batch")
                positions.append(position_ms)

            if cue_errors:
                errors.append({
                    'index': i,
                    'cue_data': cue_info,
                    'errors': cue_errors
                })

        return errors

    def optimize_cue_positions(self, strategy: str = 'beat_align') -> Dict[str, Any]:
        """Optimize cue point positions using various strategies."""
        if not self.cue_points:
            return {'optimized': 0, 'strategy': strategy}

        start_time = time.time()
        optimized_count = 0

        if strategy == 'beat_align':
            # This would align cues to nearest beats (requires beatgrid data)
            # For now, just round to nearest 10ms
            for cue in self.cue_points.values():
                original_pos = cue.position_ms
                optimized_pos = round(cue.position_ms / 10) * 10
                if abs(original_pos - optimized_pos) > 1:
                    cue.position_ms = optimized_pos
                    cue.modified_at = time.time()
                    optimized_count += 1

        elif strategy == 'spacing_optimize':
            # Ensure minimum spacing between cues
            sorted_cues = sorted(self.cue_points.values(), key=lambda c: c.position_ms)
            min_spacing = 200  # 200ms minimum

            for i in range(1, len(sorted_cues)):
                prev_cue = sorted_cues[i-1]
                curr_cue = sorted_cues[i]

                if curr_cue.position_ms - prev_cue.position_ms < min_spacing:
                    new_position = prev_cue.position_ms + min_spacing
                    if new_position <= self.track_duration_ms:
                        curr_cue.position_ms = new_position
                        curr_cue.modified_at = time.time()
                        optimized_count += 1

        optimization_time = time.time() - start_time

        if optimized_count > 0 and self.auto_save:
            self._auto_save_cues()

        self.logger.info(f"Optimized {optimized_count} cue positions using {strategy} "
                        f"in {optimization_time:.3f}s")

        return {
            'optimized': optimized_count,
            'strategy': strategy,
            'time': optimization_time
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics."""
        return {
            'cache_stats': {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_ratio': self.cache_hits / max(1, self.cache_hits + self.cache_misses),
                'cache_size': len(self._validation_cache)
            },
            'operations': {
                'total': self._total_operations,
                'operation_times': dict(self.operation_times),
                'avg_time': np.mean(list(self.operation_times.values())) if self.operation_times else 0
            },
            'conflicts': {
                'total_conflicts': len(self._conflict_log),
                'recent_conflicts': self._conflict_log[-10:] if self._conflict_log else []
            },
            'memory': {
                'cue_points': len(self.cue_points),
                'cache_entries': len(self._validation_cache),
                'history_entries': len(self._operation_history)
            }
        }

    def clear_cache(self) -> None:
        """Clear all caches to free memory."""
        self._validation_cache.clear()
        self._cue_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        self.logger.info("Cue manager caches cleared")
