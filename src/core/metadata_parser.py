"""
Metadata Parser - Safe audio metadata reading and writing
Supports ID3v2.4, MP4, Vorbis with backup and rollback capabilities
"""

import logging
import shutil
import time
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass
import json

# Audio metadata libraries
try:
    import mutagen
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TPOS, TRCK, TCON, COMM
    from mutagen.mp4 import MP4
    from mutagen.oggvorbis import OggVorbis
    from mutagen.flac import FLAC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logging.warning("mutagen not available - metadata features limited")

try:
    import taglib
    TAGLIB_AVAILABLE = True
except ImportError:
    TAGLIB_AVAILABLE = False
    logging.warning("pytaglib not available - using mutagen only")


@dataclass
class TrackMetadata:
    """Container for track metadata."""
    # Basic metadata
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    
    # DJ-specific metadata
    bpm: Optional[float] = None
    key: Optional[str] = None
    energy: Optional[int] = None
    comment: Optional[str] = None
    
    # Technical metadata
    duration_ms: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    
    # Custom fields
    custom_fields: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_fields is None:
            self.custom_fields = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'year': self.year,
            'genre': self.genre,
            'track_number': self.track_number,
            'disc_number': self.disc_number,
            'bpm': self.bpm,
            'key': self.key,
            'energy': self.energy,
            'comment': self.comment,
            'duration_ms': self.duration_ms,
            'bitrate': self.bitrate,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'custom_fields': self.custom_fields
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrackMetadata':
        """Create from dictionary."""
        return cls(
            title=data.get('title'),
            artist=data.get('artist'),
            album=data.get('album'),
            year=data.get('year'),
            genre=data.get('genre'),
            track_number=data.get('track_number'),
            disc_number=data.get('disc_number'),
            bpm=data.get('bpm'),
            key=data.get('key'),
            energy=data.get('energy'),
            comment=data.get('comment'),
            duration_ms=data.get('duration_ms'),
            bitrate=data.get('bitrate'),
            sample_rate=data.get('sample_rate'),
            channels=data.get('channels'),
            custom_fields=data.get('custom_fields', {})
        )


class MetadataError(Exception):
    """Custom exception for metadata operations."""
    pass


class MetadataParser:
    """
    Safe metadata parser with backup and rollback capabilities.
    Supports ID3v2.4, MP4, Vorbis, and FLAC formats.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Metadata settings
        self.backup_on_write = config.get('cues', {}).get('backup_on_write', True)
        self.supported_formats = config.get('cues', {}).get('formats', ['id3v24', 'mp4', 'vorbis', 'json'])

        # Enhanced settings
        self.validation_enabled = config.get('metadata', {}).get('validation_enabled', True)
        self.cache_enabled = config.get('metadata', {}).get('cache_enabled', True)
        self.batch_processing = config.get('metadata', {}).get('batch_processing', True)
        self.integrity_checks = config.get('metadata', {}).get('integrity_checks', True)
        self.auto_repair = config.get('metadata', {}).get('auto_repair', True)

        # Performance tracking
        self._metadata_cache: Dict[str, TrackMetadata] = {}
        self._file_checksums: Dict[str, str] = {}
        self._operation_stats = {
            'reads': 0, 'writes': 0, 'cache_hits': 0, 'cache_misses': 0,
            'repairs': 0, 'backups_created': 0, 'rollbacks': 0
        }

        # Check library availability
        if not MUTAGEN_AVAILABLE:
            raise MetadataError("mutagen library required for metadata operations")

        self.logger.info(f"Enhanced MetadataParser initialized - formats: {self.supported_formats}, "
                        f"cache: {self.cache_enabled}, validation: {self.validation_enabled}")
    
    def read_metadata(self, file_path: Union[str, Path], use_cache: bool = True) -> TrackMetadata:
        """
        Read metadata from audio file with intelligent caching.

        Args:
            file_path: Path to audio file
            use_cache: Whether to use cached metadata

        Returns:
            TrackMetadata object with parsed metadata
        """
        file_path = Path(file_path)
        file_key = str(file_path.absolute())

        if not file_path.exists():
            raise MetadataError(f"File not found: {file_path}")

        # Check cache first
        if use_cache and self.cache_enabled:
            cached_metadata = self._get_cached_metadata(file_path, file_key)
            if cached_metadata:
                self._operation_stats['cache_hits'] += 1
                return cached_metadata
            self._operation_stats['cache_misses'] += 1

        try:
            start_time = time.time()

            # Try mutagen first (most comprehensive)
            metadata = self._read_with_mutagen(file_path)

            # Fallback to taglib if available
            if not metadata and TAGLIB_AVAILABLE:
                metadata = self._read_with_taglib(file_path)

            if not metadata:
                # Create empty metadata
                metadata = TrackMetadata()

            # Validate metadata if enabled
            if self.validation_enabled:
                validation_errors = self._validate_metadata(metadata)
                if validation_errors and self.auto_repair:
                    metadata = self._repair_metadata(metadata, validation_errors)

            # Cache the result
            if self.cache_enabled:
                self._cache_metadata(file_path, file_key, metadata)

            read_time = time.time() - start_time
            self._operation_stats['reads'] += 1

            self.logger.debug(f"Read metadata from {file_path.name} in {read_time:.3f}s")
            return metadata

        except Exception as e:
            self.logger.error(f"Failed to read metadata from {file_path}: {e}")
            raise MetadataError(f"Failed to read metadata: {e}")
    
    def write_metadata(self, file_path: Union[str, Path], metadata: TrackMetadata) -> bool:
        """
        Write metadata to audio file with backup.
        
        Args:
            file_path: Path to audio file
            metadata: Metadata to write
            
        Returns:
            True if successful, False otherwise
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise MetadataError(f"File not found: {file_path}")
        
        # Create backup if enabled
        backup_path = None
        if self.backup_on_write:
            backup_path = self._create_backup(file_path)
        
        try:
            # Write metadata based on file format
            success = self._write_with_mutagen(file_path, metadata)
            
            if success:
                self.logger.info(f"Metadata written to {file_path.name}")
                return True
            else:
                raise MetadataError("Failed to write metadata")
                
        except Exception as e:
            self.logger.error(f"Failed to write metadata to {file_path}: {e}")
            
            # Restore backup if write failed
            if backup_path and backup_path.exists():
                self._restore_backup(file_path, backup_path)
                self.logger.info(f"Restored backup for {file_path.name}")
            
            raise MetadataError(f"Failed to write metadata: {e}")
    
    def _read_with_mutagen(self, file_path: Path) -> Optional[TrackMetadata]:
        """Read metadata using mutagen."""
        try:
            # Load file with mutagen
            audio_file = mutagen.File(str(file_path))
            
            if audio_file is None:
                return None
            
            metadata = TrackMetadata()
            
            # Extract common fields based on file type
            if isinstance(audio_file, mutagen.id3.ID3FileType):
                metadata = self._extract_id3_metadata(audio_file)
            elif isinstance(audio_file, MP4):
                metadata = self._extract_mp4_metadata(audio_file)
            elif isinstance(audio_file, (OggVorbis, FLAC)):
                metadata = self._extract_vorbis_metadata(audio_file)
            else:
                # Generic extraction
                metadata = self._extract_generic_metadata(audio_file)
            
            # Add technical info
            if hasattr(audio_file, 'info'):
                info = audio_file.info
                metadata.duration_ms = getattr(info, 'length', 0) * 1000
                metadata.bitrate = getattr(info, 'bitrate', None)
                metadata.sample_rate = getattr(info, 'sample_rate', None)
                metadata.channels = getattr(info, 'channels', None)
            
            return metadata
            
        except Exception as e:
            self.logger.warning(f"mutagen failed to read {file_path}: {e}")
            return None
    
    def _extract_id3_metadata(self, audio_file) -> TrackMetadata:
        """Extract metadata from ID3 tags."""
        metadata = TrackMetadata()
        
        # Basic tags
        metadata.title = self._get_id3_text(audio_file, 'TIT2')
        metadata.artist = self._get_id3_text(audio_file, 'TPE1')
        metadata.album = self._get_id3_text(audio_file, 'TALB')
        metadata.genre = self._get_id3_text(audio_file, 'TCON')
        
        # Year from date
        year_text = self._get_id3_text(audio_file, 'TDRC')
        if year_text:
            try:
                metadata.year = int(year_text[:4])
            except (ValueError, TypeError):
                pass
        
        # Track and disc numbers
        track_text = self._get_id3_text(audio_file, 'TRCK')
        if track_text and '/' in track_text:
            try:
                metadata.track_number = int(track_text.split('/')[0])
            except (ValueError, TypeError):
                pass
        
        disc_text = self._get_id3_text(audio_file, 'TPOS')
        if disc_text:
            try:
                metadata.disc_number = int(disc_text.split('/')[0])
            except (ValueError, TypeError):
                pass
        
        # BPM
        bpm_text = self._get_id3_text(audio_file, 'TBPM')
        if bpm_text:
            try:
                metadata.bpm = float(bpm_text)
            except (ValueError, TypeError):
                pass
        
        # Key
        metadata.key = self._get_id3_text(audio_file, 'TKEY')
        
        # Comment
        if 'COMM::eng' in audio_file:
            metadata.comment = str(audio_file['COMM::eng'].text[0])
        
        return metadata
    
    def _extract_mp4_metadata(self, audio_file: MP4) -> TrackMetadata:
        """Extract metadata from MP4 tags."""
        metadata = TrackMetadata()
        
        # Basic tags
        metadata.title = self._get_mp4_text(audio_file, '\xa9nam')
        metadata.artist = self._get_mp4_text(audio_file, '\xa9ART')
        metadata.album = self._get_mp4_text(audio_file, '\xa9alb')
        metadata.genre = self._get_mp4_text(audio_file, '\xa9gen')
        
        # Year
        year_text = self._get_mp4_text(audio_file, '\xa9day')
        if year_text:
            try:
                metadata.year = int(year_text[:4])
            except (ValueError, TypeError):
                pass
        
        # Track number
        if 'trkn' in audio_file:
            track_info = audio_file['trkn'][0]
            if isinstance(track_info, tuple) and len(track_info) >= 1:
                metadata.track_number = track_info[0]
        
        # Disc number
        if 'disk' in audio_file:
            disc_info = audio_file['disk'][0]
            if isinstance(disc_info, tuple) and len(disc_info) >= 1:
                metadata.disc_number = disc_info[0]
        
        # BPM
        if 'tmpo' in audio_file:
            try:
                metadata.bpm = float(audio_file['tmpo'][0])
            except (ValueError, TypeError, IndexError):
                pass
        
        # Comment
        metadata.comment = self._get_mp4_text(audio_file, '\xa9cmt')
        
        return metadata
    
    def _extract_vorbis_metadata(self, audio_file) -> TrackMetadata:
        """Extract metadata from Vorbis comments."""
        metadata = TrackMetadata()
        
        # Basic tags
        metadata.title = self._get_vorbis_text(audio_file, 'TITLE')
        metadata.artist = self._get_vorbis_text(audio_file, 'ARTIST')
        metadata.album = self._get_vorbis_text(audio_file, 'ALBUM')
        metadata.genre = self._get_vorbis_text(audio_file, 'GENRE')
        
        # Year
        year_text = self._get_vorbis_text(audio_file, 'DATE')
        if year_text:
            try:
                metadata.year = int(year_text[:4])
            except (ValueError, TypeError):
                pass
        
        # Track number
        track_text = self._get_vorbis_text(audio_file, 'TRACKNUMBER')
        if track_text:
            try:
                metadata.track_number = int(track_text)
            except (ValueError, TypeError):
                pass
        
        # Disc number
        disc_text = self._get_vorbis_text(audio_file, 'DISCNUMBER')
        if disc_text:
            try:
                metadata.disc_number = int(disc_text)
            except (ValueError, TypeError):
                pass
        
        # BPM
        bpm_text = self._get_vorbis_text(audio_file, 'BPM')
        if bpm_text:
            try:
                metadata.bpm = float(bpm_text)
            except (ValueError, TypeError):
                pass
        
        # Comment
        metadata.comment = self._get_vorbis_text(audio_file, 'COMMENT')
        
        return metadata
    
    def _extract_generic_metadata(self, audio_file) -> TrackMetadata:
        """Extract metadata using generic approach."""
        metadata = TrackMetadata()
        
        # Try common field names
        common_fields = {
            'title': ['title', 'TIT2', '\xa9nam'],
            'artist': ['artist', 'TPE1', '\xa9ART'],
            'album': ['album', 'TALB', '\xa9alb'],
            'genre': ['genre', 'TCON', '\xa9gen']
        }
        
        for field, possible_keys in common_fields.items():
            for key in possible_keys:
                if key in audio_file:
                    value = audio_file[key]
                    if isinstance(value, list) and value:
                        setattr(metadata, field, str(value[0]))
                    else:
                        setattr(metadata, field, str(value))
                    break
        
        return metadata
    
    def _get_id3_text(self, audio_file, tag: str) -> Optional[str]:
        """Get text from ID3 tag."""
        if tag in audio_file:
            frame = audio_file[tag]
            if hasattr(frame, 'text') and frame.text:
                return str(frame.text[0])
        return None
    
    def _get_mp4_text(self, audio_file: MP4, tag: str) -> Optional[str]:
        """Get text from MP4 tag."""
        if tag in audio_file:
            value = audio_file[tag]
            if isinstance(value, list) and value:
                return str(value[0])
        return None
    
    def _get_vorbis_text(self, audio_file, tag: str) -> Optional[str]:
        """Get text from Vorbis comment."""
        if tag in audio_file:
            value = audio_file[tag]
            if isinstance(value, list) and value:
                return str(value[0])
        return None

    def _read_with_taglib(self, file_path: Path) -> Optional[TrackMetadata]:
        """Read metadata using taglib (fallback)."""
        if not TAGLIB_AVAILABLE:
            return None

        try:
            with taglib.File(str(file_path)) as f:
                metadata = TrackMetadata()

                # Basic fields
                metadata.title = f.tags.get('TITLE', [None])[0]
                metadata.artist = f.tags.get('ARTIST', [None])[0]
                metadata.album = f.tags.get('ALBUM', [None])[0]
                metadata.genre = f.tags.get('GENRE', [None])[0]

                # Year
                year_list = f.tags.get('DATE', [])
                if year_list:
                    try:
                        metadata.year = int(year_list[0][:4])
                    except (ValueError, TypeError):
                        pass

                # Track number
                track_list = f.tags.get('TRACKNUMBER', [])
                if track_list:
                    try:
                        metadata.track_number = int(track_list[0])
                    except (ValueError, TypeError):
                        pass

                # Technical info
                metadata.duration_ms = f.length * 1000
                metadata.bitrate = f.bitrate
                metadata.sample_rate = f.sampleRate
                metadata.channels = f.channels

                return metadata

        except Exception as e:
            self.logger.warning(f"taglib failed to read {file_path}: {e}")
            return None

    def _write_with_mutagen(self, file_path: Path, metadata: TrackMetadata) -> bool:
        """Write metadata using mutagen."""
        try:
            audio_file = mutagen.File(str(file_path))

            if audio_file is None:
                return False

            # Write based on file type
            if isinstance(audio_file, mutagen.id3.ID3FileType):
                return self._write_id3_metadata(audio_file, metadata)
            elif isinstance(audio_file, MP4):
                return self._write_mp4_metadata(audio_file, metadata)
            elif isinstance(audio_file, (OggVorbis, FLAC)):
                return self._write_vorbis_metadata(audio_file, metadata)
            else:
                return self._write_generic_metadata(audio_file, metadata)

        except Exception as e:
            self.logger.error(f"Failed to write metadata with mutagen: {e}")
            return False

    def _write_id3_metadata(self, audio_file, metadata: TrackMetadata) -> bool:
        """Write ID3 metadata."""
        try:
            # Ensure ID3 tag exists
            if not hasattr(audio_file, 'tags') or audio_file.tags is None:
                audio_file.add_tags()

            tags = audio_file.tags

            # Basic fields
            if metadata.title:
                tags.setall('TIT2', [TIT2(encoding=3, text=metadata.title)])
            if metadata.artist:
                tags.setall('TPE1', [TPE1(encoding=3, text=metadata.artist)])
            if metadata.album:
                tags.setall('TALB', [TALB(encoding=3, text=metadata.album)])
            if metadata.genre:
                tags.setall('TCON', [TCON(encoding=3, text=metadata.genre)])

            # Year
            if metadata.year:
                tags.setall('TDRC', [TDRC(encoding=3, text=str(metadata.year))])

            # Track number
            if metadata.track_number:
                tags.setall('TRCK', [TRCK(encoding=3, text=str(metadata.track_number))])

            # Disc number
            if metadata.disc_number:
                tags.setall('TPOS', [TPOS(encoding=3, text=str(metadata.disc_number))])

            # BPM
            if metadata.bpm:
                from mutagen.id3 import TBPM
                tags.setall('TBPM', [TBPM(encoding=3, text=str(int(metadata.bpm)))])

            # Key
            if metadata.key:
                from mutagen.id3 import TKEY
                tags.setall('TKEY', [TKEY(encoding=3, text=metadata.key)])

            # Comment
            if metadata.comment:
                tags.setall('COMM::eng', [COMM(encoding=3, lang='eng', desc='', text=metadata.comment)])

            # Save
            audio_file.save()
            return True

        except Exception as e:
            self.logger.error(f"Failed to write ID3 metadata: {e}")
            return False

    def _write_mp4_metadata(self, audio_file: MP4, metadata: TrackMetadata) -> bool:
        """Write MP4 metadata."""
        try:
            # Basic fields
            if metadata.title:
                audio_file['\xa9nam'] = [metadata.title]
            if metadata.artist:
                audio_file['\xa9ART'] = [metadata.artist]
            if metadata.album:
                audio_file['\xa9alb'] = [metadata.album]
            if metadata.genre:
                audio_file['\xa9gen'] = [metadata.genre]

            # Year
            if metadata.year:
                audio_file['\xa9day'] = [str(metadata.year)]

            # Track number
            if metadata.track_number:
                audio_file['trkn'] = [(metadata.track_number, 0)]

            # Disc number
            if metadata.disc_number:
                audio_file['disk'] = [(metadata.disc_number, 0)]

            # BPM
            if metadata.bpm:
                audio_file['tmpo'] = [int(metadata.bpm)]

            # Comment
            if metadata.comment:
                audio_file['\xa9cmt'] = [metadata.comment]

            # Save
            audio_file.save()
            return True

        except Exception as e:
            self.logger.error(f"Failed to write MP4 metadata: {e}")
            return False

    def _write_vorbis_metadata(self, audio_file, metadata: TrackMetadata) -> bool:
        """Write Vorbis metadata."""
        try:
            # Basic fields
            if metadata.title:
                audio_file['TITLE'] = [metadata.title]
            if metadata.artist:
                audio_file['ARTIST'] = [metadata.artist]
            if metadata.album:
                audio_file['ALBUM'] = [metadata.album]
            if metadata.genre:
                audio_file['GENRE'] = [metadata.genre]

            # Year
            if metadata.year:
                audio_file['DATE'] = [str(metadata.year)]

            # Track number
            if metadata.track_number:
                audio_file['TRACKNUMBER'] = [str(metadata.track_number)]

            # Disc number
            if metadata.disc_number:
                audio_file['DISCNUMBER'] = [str(metadata.disc_number)]

            # BPM
            if metadata.bpm:
                audio_file['BPM'] = [str(int(metadata.bpm))]

            # Comment
            if metadata.comment:
                audio_file['COMMENT'] = [metadata.comment]

            # Save
            audio_file.save()
            return True

        except Exception as e:
            self.logger.error(f"Failed to write Vorbis metadata: {e}")
            return False

    def _write_generic_metadata(self, audio_file, metadata: TrackMetadata) -> bool:
        """Write metadata using generic approach."""
        try:
            # Try to write common fields
            if metadata.title:
                audio_file['title'] = [metadata.title]
            if metadata.artist:
                audio_file['artist'] = [metadata.artist]
            if metadata.album:
                audio_file['album'] = [metadata.album]
            if metadata.genre:
                audio_file['genre'] = [metadata.genre]

            audio_file.save()
            return True

        except Exception as e:
            self.logger.error(f"Failed to write generic metadata: {e}")
            return False

    def _create_backup(self, file_path: Path) -> Path:
        """Create backup of file before writing."""
        backup_path = file_path.with_suffix(f'{file_path.suffix}.backup')
        shutil.copy2(file_path, backup_path)
        self.logger.debug(f"Created backup: {backup_path}")
        return backup_path

    def _restore_backup(self, original_path: Path, backup_path: Path) -> None:
        """Restore file from backup."""
        shutil.move(backup_path, original_path)
        self.logger.info(f"Restored from backup: {original_path}")

    def cleanup_backups(self, directory: Path, max_age_hours: int = 24) -> int:
        """Clean up old backup files."""
        if not directory.exists():
            return 0

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0

        for backup_file in directory.glob('*.backup'):
            try:
                file_age = current_time - backup_file.stat().st_mtime
                if file_age > max_age_seconds:
                    backup_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                self.logger.warning(f"Failed to clean backup {backup_file}: {e}")

        if cleaned_count > 0:
            self.logger.info(f"Cleaned {cleaned_count} old backup files")

        return cleaned_count

    def _get_cached_metadata(self, file_path: Path, file_key: str) -> Optional[TrackMetadata]:
        """Get cached metadata if file hasn't changed."""
        if file_key not in self._metadata_cache:
            return None

        # Check if file has been modified
        try:
            current_checksum = self._calculate_file_checksum(file_path)
            cached_checksum = self._file_checksums.get(file_key)

            if current_checksum == cached_checksum:
                return self._metadata_cache[file_key]
            else:
                # File changed, remove from cache
                self._metadata_cache.pop(file_key, None)
                self._file_checksums.pop(file_key, None)
                return None

        except Exception as e:
            self.logger.warning(f"Failed to check file checksum: {e}")
            return None

    def _cache_metadata(self, file_path: Path, file_key: str, metadata: TrackMetadata) -> None:
        """Cache metadata with file checksum."""
        try:
            checksum = self._calculate_file_checksum(file_path)
            self._metadata_cache[file_key] = metadata
            self._file_checksums[file_key] = checksum

            # Limit cache size
            max_cache_size = 1000
            if len(self._metadata_cache) > max_cache_size:
                # Remove oldest entries
                oldest_keys = list(self._metadata_cache.keys())[:100]
                for key in oldest_keys:
                    self._metadata_cache.pop(key, None)
                    self._file_checksums.pop(key, None)

        except Exception as e:
            self.logger.warning(f"Failed to cache metadata: {e}")

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate file checksum for cache validation."""
        import hashlib

        # Use file size and modification time for quick checksum
        stat = file_path.stat()
        checksum_data = f"{stat.st_size}_{stat.st_mtime}".encode()
        return hashlib.md5(checksum_data).hexdigest()

    def _validate_metadata(self, metadata: TrackMetadata) -> List[str]:
        """Validate metadata for common issues."""
        errors = []

        # Check for suspicious values
        if metadata.year and (metadata.year < 1900 or metadata.year > 2030):
            errors.append(f"Suspicious year: {metadata.year}")

        if metadata.bpm and (metadata.bpm < 30 or metadata.bpm > 300):
            errors.append(f"Suspicious BPM: {metadata.bpm}")

        if metadata.track_number and metadata.track_number < 1:
            errors.append(f"Invalid track number: {metadata.track_number}")

        # Check for encoding issues
        text_fields = [metadata.title, metadata.artist, metadata.album, metadata.genre]
        for field in text_fields:
            if field and any(ord(char) > 127 for char in field):
                try:
                    field.encode('utf-8')
                except UnicodeEncodeError:
                    errors.append(f"Encoding issue in text field: {field[:20]}...")

        return errors

    def _repair_metadata(self, metadata: TrackMetadata, errors: List[str]) -> TrackMetadata:
        """Attempt to repair metadata issues."""
        repaired = TrackMetadata.from_dict(metadata.to_dict())  # Create copy

        for error in errors:
            if "Suspicious year" in error:
                # Reset suspicious year
                repaired.year = None
                self._operation_stats['repairs'] += 1

            elif "Suspicious BPM" in error:
                # Reset suspicious BPM
                repaired.bpm = None
                self._operation_stats['repairs'] += 1

            elif "Invalid track number" in error:
                # Reset invalid track number
                repaired.track_number = None
                self._operation_stats['repairs'] += 1

            elif "Encoding issue" in error:
                # Try to fix encoding issues
                for field_name in ['title', 'artist', 'album', 'genre']:
                    field_value = getattr(repaired, field_name)
                    if field_value:
                        try:
                            # Try to clean up encoding
                            cleaned = field_value.encode('utf-8', errors='ignore').decode('utf-8')
                            setattr(repaired, field_name, cleaned)
                            self._operation_stats['repairs'] += 1
                        except Exception:
                            # If all else fails, clear the field
                            setattr(repaired, field_name, None)

        if self._operation_stats['repairs'] > 0:
            self.logger.info(f"Repaired {len(errors)} metadata issues")

        return repaired

    def read_metadata_batch(self, file_paths: List[Path],
                           max_workers: int = 4) -> Dict[str, Any]:
        """Read metadata from multiple files in parallel."""
        if not self.batch_processing:
            raise MetadataError("Batch processing is disabled")

        import concurrent.futures
        import threading

        results = {
            'success': {},
            'failed': {},
            'total_time': 0,
            'stats': {}
        }

        start_time = time.time()

        def read_single_file(file_path: Path) -> tuple:
            try:
                metadata = self.read_metadata(file_path)
                return str(file_path), metadata, None
            except Exception as e:
                return str(file_path), None, str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(read_single_file, path): path
                             for path in file_paths}

            for future in concurrent.futures.as_completed(future_to_path):
                file_path_str, metadata, error = future.result()

                if error:
                    results['failed'][file_path_str] = error
                else:
                    results['success'][file_path_str] = metadata.to_dict()

        results['total_time'] = time.time() - start_time
        results['stats'] = {
            'total_files': len(file_paths),
            'successful': len(results['success']),
            'failed': len(results['failed']),
            'success_rate': len(results['success']) / len(file_paths) * 100
        }

        self.logger.info(f"Batch metadata read completed: {results['stats']['successful']}/{len(file_paths)} "
                        f"files in {results['total_time']:.2f}s")

        return results

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache and performance statistics."""
        return {
            'cache': {
                'enabled': self.cache_enabled,
                'size': len(self._metadata_cache),
                'checksums': len(self._file_checksums),
                'hit_ratio': (self._operation_stats['cache_hits'] /
                             max(1, self._operation_stats['cache_hits'] + self._operation_stats['cache_misses']) * 100)
            },
            'operations': self._operation_stats.copy(),
            'settings': {
                'validation_enabled': self.validation_enabled,
                'auto_repair': self.auto_repair,
                'batch_processing': self.batch_processing,
                'integrity_checks': self.integrity_checks
            }
        }

    def clear_cache(self) -> None:
        """Clear metadata cache."""
        self._metadata_cache.clear()
        self._file_checksums.clear()
        self._operation_stats['cache_hits'] = 0
        self._operation_stats['cache_misses'] = 0
        self.logger.info("Metadata cache cleared")
