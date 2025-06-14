"""
Serato Compatibility Bridge - Full compatibility with Serato DJ Pro
Reads and writes Serato-specific metadata tags for cue points and beatgrids
"""

import logging
import struct
import base64
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import numpy as np

from .cue_manager import CuePoint, CueType
from .beatgrid_engine import BeatgridData


# Serato color mapping (RGB values)
SERATO_COLORS = {
    0xCC0000: '#CC0000',  # Red
    0xCC4400: '#CC4400',  # Orange
    0xCC8800: '#CC8800',  # Yellow
    0x88CC00: '#88CC00',  # Lime
    0x00CC00: '#00CC00',  # Green
    0x00CC44: '#00CC44',  # Teal
    0x00CC88: '#00CC88',  # Cyan
    0x0088CC: '#0088CC',  # Light Blue
    0x0044CC: '#0044CC',  # Blue
    0x4400CC: '#4400CC',  # Purple
    0x8800CC: '#8800CC',  # Magenta
    0xCC0088: '#CC0088',  # Pink
    0xCC0044: '#CC0044',  # Rose
    0x884400: '#884400',  # Brown
    0x888888: '#888888',  # Gray
    0x000000: '#000000',  # Black
}

# Reverse mapping for writing
COLOR_TO_SERATO = {v: k for k, v in SERATO_COLORS.items()}


class SeratoError(Exception):
    """Custom exception for Serato compatibility errors."""
    pass


class SeratoBridge:
    """
    Serato DJ Pro compatibility bridge.
    Handles reading and writing Serato-specific metadata tags.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Serato compatibility settings
        self.serato_compatibility = config.get('cues', {}).get('serato_compatibility', True)

        # Enhanced settings
        self.strict_validation = config.get('serato', {}).get('strict_validation', True)
        self.auto_repair = config.get('serato', {}).get('auto_repair', True)
        self.version_detection = config.get('serato', {}).get('version_detection', True)
        self.backup_serato_data = config.get('serato', {}).get('backup_serato_data', True)

        # Performance tracking
        self._operation_stats = {
            'reads': 0, 'writes': 0, 'repairs': 0, 'version_detections': 0,
            'markers2_processed': 0, 'legacy_processed': 0, 'mp4_processed': 0
        }

        # Serato version compatibility
        self._supported_versions = {
            'markers2': '2.0+',
            'markers_legacy': '1.x',
            'beatgrid': '2.0+',
            'analysis': '2.1+'
        }

        if not self.serato_compatibility:
            self.logger.info("Serato compatibility disabled")
            return

        self.logger.info(f"Enhanced SeratoBridge initialized - strict: {self.strict_validation}, "
                        f"auto_repair: {self.auto_repair}, version_detection: {self.version_detection}")
    
    def read_serato_cues(self, audio_file) -> List[CuePoint]:
        """
        Read Serato cue points from audio file metadata.
        
        Args:
            audio_file: Mutagen audio file object
            
        Returns:
            List of CuePoint objects
        """
        if not self.serato_compatibility:
            return []
        
        cue_points = []
        
        try:
            # Try to read Serato Markers2 (newer format)
            if 'GEOB:Serato Markers2' in audio_file:
                cue_points.extend(self._parse_markers2(audio_file['GEOB:Serato Markers2']))
            
            # Try to read Serato Markers_ (legacy format)
            elif 'GEOB:Serato Markers_' in audio_file:
                cue_points.extend(self._parse_markers_legacy(audio_file['GEOB:Serato Markers_']))
            
            # Try MP4 format
            elif hasattr(audio_file, 'tags') and 'com.serato.dj.markers' in audio_file.tags:
                cue_points.extend(self._parse_mp4_markers(audio_file.tags['com.serato.dj.markers']))
            
            self.logger.info(f"Read {len(cue_points)} Serato cue points")
            
        except Exception as e:
            self.logger.warning(f"Failed to read Serato cues: {e}")
        
        return cue_points
    
    def write_serato_cues(self, audio_file, cue_points: List[CuePoint]) -> bool:
        """
        Write Serato cue points to audio file metadata.
        
        Args:
            audio_file: Mutagen audio file object
            cue_points: List of CuePoint objects to write
            
        Returns:
            True if successful, False otherwise
        """
        if not self.serato_compatibility:
            return False
        
        try:
            # Write in Markers2 format (preferred)
            markers_data = self._create_markers2(cue_points)
            
            if hasattr(audio_file, 'tags') and hasattr(audio_file.tags, 'setall'):
                # ID3 format
                from mutagen.id3 import GEOB
                geob_frame = GEOB(
                    encoding=0,
                    mime='application/octet-stream',
                    filename='Serato Markers2',
                    data=markers_data
                )
                audio_file.tags.setall('GEOB:Serato Markers2', [geob_frame])
                
            elif hasattr(audio_file, '__setitem__'):
                # MP4 format
                audio_file['com.serato.dj.markers'] = [markers_data]
            
            self.logger.info(f"Wrote {len(cue_points)} Serato cue points")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write Serato cues: {e}")
            return False
    
    def read_serato_beatgrid(self, audio_file) -> Optional[BeatgridData]:
        """
        Read Serato beatgrid from audio file metadata.
        
        Args:
            audio_file: Mutagen audio file object
            
        Returns:
            BeatgridData object or None
        """
        if not self.serato_compatibility:
            return None
        
        try:
            # Try to read Serato BeatGrid
            if 'GEOB:Serato BeatGrid' in audio_file:
                return self._parse_beatgrid(audio_file['GEOB:Serato BeatGrid'])
            elif hasattr(audio_file, 'tags') and 'com.serato.dj.beatgrid' in audio_file.tags:
                return self._parse_mp4_beatgrid(audio_file.tags['com.serato.dj.beatgrid'])
            
        except Exception as e:
            self.logger.warning(f"Failed to read Serato beatgrid: {e}")
        
        return None
    
    def write_serato_beatgrid(self, audio_file, beatgrid: BeatgridData) -> bool:
        """
        Write Serato beatgrid to audio file metadata.
        
        Args:
            audio_file: Mutagen audio file object
            beatgrid: BeatgridData object to write
            
        Returns:
            True if successful, False otherwise
        """
        if not self.serato_compatibility:
            return False
        
        try:
            beatgrid_data = self._create_beatgrid(beatgrid)
            
            if hasattr(audio_file, 'tags') and hasattr(audio_file.tags, 'setall'):
                # ID3 format
                from mutagen.id3 import GEOB
                geob_frame = GEOB(
                    encoding=0,
                    mime='application/octet-stream',
                    filename='Serato BeatGrid',
                    data=beatgrid_data
                )
                audio_file.tags.setall('GEOB:Serato BeatGrid', [geob_frame])
                
            elif hasattr(audio_file, '__setitem__'):
                # MP4 format
                audio_file['com.serato.dj.beatgrid'] = [beatgrid_data]
            
            self.logger.info("Wrote Serato beatgrid")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write Serato beatgrid: {e}")
            return False
    
    def _parse_markers2(self, geob_frame) -> List[CuePoint]:
        """Parse Serato Markers2 format."""
        cue_points = []
        
        try:
            data = geob_frame.data
            
            # Skip header
            if not data.startswith(b'\x01\x01'):
                return cue_points
            
            offset = 2
            
            while offset < len(data):
                # Read entry header
                if offset + 8 > len(data):
                    break
                
                entry_type = data[offset:offset+4]
                entry_size = struct.unpack('>I', data[offset+4:offset+8])[0]
                
                if offset + 8 + entry_size > len(data):
                    break
                
                entry_data = data[offset+8:offset+8+entry_size]
                
                if entry_type == b'CUE\x00':
                    cue_point = self._parse_cue_entry(entry_data)
                    if cue_point:
                        cue_points.append(cue_point)
                
                offset += 8 + entry_size
            
        except Exception as e:
            self.logger.warning(f"Failed to parse Markers2: {e}")
        
        return cue_points
    
    def _parse_cue_entry(self, data: bytes) -> Optional[CuePoint]:
        """Parse individual cue entry from Markers2."""
        try:
            if len(data) < 13:
                return None
            
            # Parse cue data
            cue_id = data[0]
            position_ms = struct.unpack('>I', data[1:5])[0]
            color_rgb = struct.unpack('>I', b'\x00' + data[5:8])[0]
            
            # Skip some bytes and read label
            label_start = 13
            label_end = data.find(b'\x00', label_start)
            if label_end == -1:
                label_end = len(data)
            
            label = data[label_start:label_end].decode('utf-8', errors='ignore')
            
            # Convert Serato color to hex
            color = SERATO_COLORS.get(color_rgb, '#FF3366')
            
            return CuePoint(
                id=cue_id,
                position_ms=position_ms,
                label=label or f"Cue {cue_id}",
                color=color,
                type=CueType.HOT_CUE,
                serato_id=cue_id,
                serato_color=color_rgb
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to parse cue entry: {e}")
            return None
    
    def _create_markers2(self, cue_points: List[CuePoint]) -> bytes:
        """Create Serato Markers2 format data."""
        data = bytearray(b'\x01\x01')  # Header
        
        for cue in cue_points:
            # Create cue entry
            entry_data = bytearray()
            
            # Cue ID
            entry_data.append(cue.id)
            
            # Position (4 bytes, big endian)
            entry_data.extend(struct.pack('>I', int(cue.position_ms)))
            
            # Color (3 bytes RGB)
            serato_color = COLOR_TO_SERATO.get(cue.color, 0xCC0000)
            entry_data.extend(struct.pack('>I', serato_color)[1:4])
            
            # Some padding/flags
            entry_data.extend(b'\x00\x00\x00\x00\x00')
            
            # Label (null-terminated UTF-8)
            label_bytes = cue.label.encode('utf-8')
            entry_data.extend(label_bytes)
            entry_data.append(0)  # Null terminator
            
            # Add entry to data
            data.extend(b'CUE\x00')  # Entry type
            data.extend(struct.pack('>I', len(entry_data)))  # Entry size
            data.extend(entry_data)
        
        return bytes(data)
    
    def _parse_beatgrid(self, geob_frame) -> Optional[BeatgridData]:
        """Parse Serato BeatGrid format."""
        try:
            data = geob_frame.data
            
            if len(data) < 16:
                return None
            
            # Parse beatgrid header
            version = struct.unpack('>I', data[0:4])[0]
            num_markers = struct.unpack('>I', data[4:8])[0]
            
            if version != 1 or num_markers == 0:
                return None
            
            # Parse beat markers
            beats = []
            offset = 8
            
            for i in range(num_markers):
                if offset + 8 > len(data):
                    break
                
                position_ms = struct.unpack('>f', data[offset:offset+4])[0]
                bpm = struct.unpack('>f', data[offset+4:offset+8])[0]
                
                beats.append(position_ms / 1000.0)  # Convert to seconds
                offset += 8
            
            if not beats:
                return None
            
            # Calculate average BPM
            avg_bpm = bpm  # Use last BPM value
            
            # Generate downbeats (simplified)
            downbeats = beats[::4] if len(beats) >= 4 else beats[:1]
            
            return BeatgridData(
                bpm=avg_bpm,
                confidence=0.9,  # Assume high confidence for Serato data
                beats=np.array(beats),
                downbeats=np.array(downbeats),
                time_signature=(4, 4),
                tempo_changes=[],
                algorithm_used='serato',
                analysis_time=0.0,
                manual_override=True
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to parse Serato beatgrid: {e}")
            return None
    
    def _create_beatgrid(self, beatgrid: BeatgridData) -> bytes:
        """Create Serato BeatGrid format data."""
        data = bytearray()
        
        # Header
        data.extend(struct.pack('>I', 1))  # Version
        data.extend(struct.pack('>I', len(beatgrid.beats)))  # Number of markers
        
        # Beat markers
        for beat_time in beatgrid.beats:
            position_ms = beat_time * 1000.0
            data.extend(struct.pack('>f', position_ms))
            data.extend(struct.pack('>f', beatgrid.bpm))
        
        return bytes(data)
    
    def convert_cue_to_serato_format(self, cue: CuePoint) -> Dict[str, Any]:
        """Convert CuePoint to Serato-compatible format."""
        serato_color = COLOR_TO_SERATO.get(cue.color, 0xCC0000)
        
        return {
            'id': cue.id,
            'position': int(cue.position_ms),
            'color': serato_color,
            'label': cue.label,
            'type': 0  # Hot cue type in Serato
        }
    
    def convert_serato_to_cue(self, serato_data: Dict[str, Any]) -> CuePoint:
        """Convert Serato format to CuePoint."""
        color = SERATO_COLORS.get(serato_data.get('color', 0xCC0000), '#FF3366')
        
        return CuePoint(
            id=serato_data['id'],
            position_ms=float(serato_data['position']),
            label=serato_data.get('label', f"Cue {serato_data['id']}"),
            color=color,
            type=CueType.HOT_CUE,
            serato_id=serato_data['id'],
            serato_color=serato_data.get('color')
        )

    def read_serato_cues_enhanced(self, audio_file, validate: bool = True) -> Dict[str, Any]:
        """Enhanced Serato cue reading with validation and repair."""
        start_time = time.time()
        result = {
            'cue_points': [],
            'format_detected': None,
            'version_info': {},
            'validation_errors': [],
            'repairs_made': [],
            'processing_time': 0
        }

        if not self.serato_compatibility:
            return result

        try:
            # Detect Serato format and version
            format_info = self._detect_serato_format(audio_file)
            result['format_detected'] = format_info['format']
            result['version_info'] = format_info['version_info']

            # Read cues based on detected format
            if format_info['format'] == 'markers2':
                cue_points = self._parse_markers2_enhanced(audio_file['GEOB:Serato Markers2'])
                self._operation_stats['markers2_processed'] += 1

            elif format_info['format'] == 'markers_legacy':
                cue_points = self._parse_markers_legacy_enhanced(audio_file['GEOB:Serato Markers_'])
                self._operation_stats['legacy_processed'] += 1

            elif format_info['format'] == 'mp4':
                cue_points = self._parse_mp4_markers_enhanced(audio_file.tags['com.serato.dj.markers'])
                self._operation_stats['mp4_processed'] += 1

            else:
                cue_points = []

            # Validate cues if requested
            if validate and self.strict_validation:
                for cue in cue_points:
                    validation_errors = self._validate_serato_cue(cue)
                    if validation_errors:
                        result['validation_errors'].extend(validation_errors)

                        # Auto-repair if enabled
                        if self.auto_repair:
                            repaired_cue = self._repair_serato_cue(cue, validation_errors)
                            if repaired_cue != cue:
                                result['repairs_made'].append({
                                    'cue_id': cue.id,
                                    'original': cue.to_dict(),
                                    'repaired': repaired_cue.to_dict(),
                                    'errors_fixed': validation_errors
                                })
                                cue_points[cue_points.index(cue)] = repaired_cue
                                self._operation_stats['repairs'] += 1

            result['cue_points'] = cue_points
            self._operation_stats['reads'] += 1

        except Exception as e:
            self.logger.error(f"Enhanced Serato cue reading failed: {e}")
            result['validation_errors'].append(f"Reading failed: {e}")

        result['processing_time'] = time.time() - start_time

        self.logger.info(f"Enhanced Serato read: {len(result['cue_points'])} cues, "
                        f"{len(result['validation_errors'])} errors, "
                        f"{len(result['repairs_made'])} repairs in {result['processing_time']:.3f}s")

        return result

    def _detect_serato_format(self, audio_file) -> Dict[str, Any]:
        """Detect Serato format and version information."""
        format_info = {
            'format': None,
            'version_info': {},
            'confidence': 0.0
        }

        if not self.version_detection:
            # Simple detection
            if 'GEOB:Serato Markers2' in audio_file:
                format_info['format'] = 'markers2'
            elif 'GEOB:Serato Markers_' in audio_file:
                format_info['format'] = 'markers_legacy'
            elif hasattr(audio_file, 'tags') and 'com.serato.dj.markers' in audio_file.tags:
                format_info['format'] = 'mp4'
            return format_info

        # Enhanced version detection
        if 'GEOB:Serato Markers2' in audio_file:
            format_info['format'] = 'markers2'
            format_info['confidence'] = 0.95

            # Try to detect Serato version from data structure
            try:
                data = audio_file['GEOB:Serato Markers2'].data
                if len(data) > 10:
                    # Analyze header for version hints
                    header = data[:10]
                    if header.startswith(b'\x01\x01'):
                        format_info['version_info'] = {
                            'serato_version': '2.0+',
                            'format_version': 'markers2_v1',
                            'header_type': 'standard'
                        }

            except Exception as e:
                self.logger.debug(f"Version detection failed: {e}")

        elif 'GEOB:Serato Markers_' in audio_file:
            format_info['format'] = 'markers_legacy'
            format_info['confidence'] = 0.8
            format_info['version_info'] = {
                'serato_version': '1.x',
                'format_version': 'markers_legacy',
                'header_type': 'legacy'
            }

        elif hasattr(audio_file, 'tags') and 'com.serato.dj.markers' in audio_file.tags:
            format_info['format'] = 'mp4'
            format_info['confidence'] = 0.9
            format_info['version_info'] = {
                'serato_version': '2.0+',
                'format_version': 'mp4_atoms',
                'container': 'mp4'
            }

        self._operation_stats['version_detections'] += 1
        return format_info

    def _validate_serato_cue(self, cue: CuePoint) -> List[str]:
        """Validate Serato cue point for common issues."""
        errors = []

        # Check cue ID range
        if not (1 <= cue.id <= 16):
            errors.append(f"Invalid cue ID: {cue.id} (must be 1-16)")

        # Check position validity
        if cue.position_ms < 0:
            errors.append(f"Negative position: {cue.position_ms}")

        # Check color validity
        if cue.serato_color is not None:
            if cue.serato_color not in SERATO_COLORS:
                errors.append(f"Unknown Serato color: {cue.serato_color}")

        # Check label validity
        if cue.label:
            if len(cue.label) > 100:  # Serato limit
                errors.append(f"Label too long: {len(cue.label)} chars (max 100)")

            # Check for problematic characters
            problematic_chars = ['\x00', '\xff', '\xfe']
            if any(char in cue.label for char in problematic_chars):
                errors.append("Label contains problematic characters")

        return errors

    def _repair_serato_cue(self, cue: CuePoint, errors: List[str]) -> CuePoint:
        """Attempt to repair Serato cue point issues."""
        # Create a copy for repair
        repaired_data = cue.to_dict()

        for error in errors:
            if "Invalid cue ID" in error:
                # Clamp to valid range
                repaired_data['id'] = max(1, min(16, cue.id))

            elif "Negative position" in error:
                # Set to zero
                repaired_data['position_ms'] = 0.0

            elif "Unknown Serato color" in error:
                # Use default red color
                repaired_data['serato_color'] = 0xCC0000
                repaired_data['color'] = '#CC0000'

            elif "Label too long" in error:
                # Truncate label
                repaired_data['label'] = cue.label[:100] if cue.label else None

            elif "problematic characters" in error:
                # Clean label
                if cue.label:
                    cleaned_label = ''.join(char for char in cue.label
                                          if ord(char) >= 32 and ord(char) < 127)
                    repaired_data['label'] = cleaned_label or f"Cue {cue.id}"

        return CuePoint.from_dict(repaired_data)

    def get_serato_statistics(self) -> Dict[str, Any]:
        """Get detailed Serato processing statistics."""
        return {
            'operations': self._operation_stats.copy(),
            'supported_versions': self._supported_versions.copy(),
            'settings': {
                'compatibility_enabled': self.serato_compatibility,
                'strict_validation': self.strict_validation,
                'auto_repair': self.auto_repair,
                'version_detection': self.version_detection,
                'backup_serato_data': self.backup_serato_data
            },
            'color_mappings': {
                'total_colors': len(SERATO_COLORS),
                'bidirectional_mapping': len(COLOR_TO_SERATO) == len(SERATO_COLORS)
            }
        }

    def validate_serato_compatibility(self, audio_file) -> Dict[str, Any]:
        """Comprehensive Serato compatibility validation."""
        validation_result = {
            'compatible': False,
            'format_support': {},
            'issues': [],
            'recommendations': []
        }

        # Check for Serato data presence
        has_markers2 = 'GEOB:Serato Markers2' in audio_file
        has_markers_legacy = 'GEOB:Serato Markers_' in audio_file
        has_mp4_markers = (hasattr(audio_file, 'tags') and
                          'com.serato.dj.markers' in audio_file.tags)

        validation_result['format_support'] = {
            'markers2': has_markers2,
            'markers_legacy': has_markers_legacy,
            'mp4_markers': has_mp4_markers
        }

        if not any([has_markers2, has_markers_legacy, has_mp4_markers]):
            validation_result['issues'].append("No Serato data found")
            validation_result['recommendations'].append("Add cue points to create Serato data")
        else:
            validation_result['compatible'] = True

            # Check data integrity
            if has_markers2:
                try:
                    data = audio_file['GEOB:Serato Markers2'].data
                    if len(data) < 10:
                        validation_result['issues'].append("Markers2 data too short")
                    elif not data.startswith(b'\x01\x01'):
                        validation_result['issues'].append("Invalid Markers2 header")
                except Exception as e:
                    validation_result['issues'].append(f"Markers2 data corrupted: {e}")

        return validation_result
