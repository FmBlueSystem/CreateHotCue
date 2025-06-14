"""
Enhanced Sidebar Widget - Cue Points & Structure Display
Interactive cue point management with visual editing and keyboard shortcuts
"""

import logging
from typing import Dict, Any, Optional, List
import time

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QListWidget, QListWidgetItem, QPushButton,
                            QLineEdit, QColorDialog, QMenu, QMessageBox,
                            QGroupBox, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPalette, QFont, QAction, QKeySequence

from ..core.cue_manager import CuePoint, CueType, CueManager


class CuePointWidget(QWidget):
    """Individual cue point widget with inline editing."""

    # Signals
    cue_selected = pyqtSignal(int)  # Emitted when cue is selected
    cue_edited = pyqtSignal(int, str, str)  # Emitted when cue is edited (id, label, color)
    cue_deleted = pyqtSignal(int)  # Emitted when cue is deleted

    def __init__(self, cue_point: CuePoint, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.cue_point = cue_point
        self.editing = False

        self._setup_ui()
        self._update_display()

    def _setup_ui(self) -> None:
        """Setup cue point widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        # Cue number label
        self.number_label = QLabel(f"{self.cue_point.id}")
        self.number_label.setFixedWidth(25)
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.number_label)

        # Color indicator
        self.color_button = QPushButton()
        self.color_button.setFixedSize(20, 20)
        self.color_button.clicked.connect(self._change_color)
        layout.addWidget(self.color_button)

        # Position label
        self.position_label = QLabel()
        self.position_label.setFixedWidth(60)
        layout.addWidget(self.position_label)

        # Label (editable)
        self.label_edit = QLineEdit(self.cue_point.label)
        self.label_edit.editingFinished.connect(self._on_label_edited)
        layout.addWidget(self.label_edit)

        # Delete button
        self.delete_button = QPushButton("×")
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.clicked.connect(self._delete_cue)
        layout.addWidget(self.delete_button)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _update_display(self) -> None:
        """Update widget display."""
        # Update color button
        color = QColor(self.cue_point.color)
        self.color_button.setStyleSheet(f"background-color: {self.cue_point.color}; border: 1px solid #333;")

        # Update position
        minutes = int(self.cue_point.position_seconds // 60)
        seconds = self.cue_point.position_seconds % 60
        self.position_label.setText(f"{minutes}:{seconds:05.2f}")

        # Update label
        if not self.editing:
            self.label_edit.setText(self.cue_point.label)

    def _change_color(self) -> None:
        """Open color picker dialog."""
        current_color = QColor(self.cue_point.color)
        color = QColorDialog.getColor(current_color, self, "Choose Cue Color")

        if color.isValid():
            new_color = color.name()
            self.cue_point.color = new_color
            self._update_display()
            self.cue_edited.emit(self.cue_point.id, self.cue_point.label, new_color)

    def _on_label_edited(self) -> None:
        """Handle label editing."""
        new_label = self.label_edit.text().strip()
        if new_label and new_label != self.cue_point.label:
            self.cue_point.label = new_label
            self.cue_edited.emit(self.cue_point.id, new_label, self.cue_point.color)

        self.editing = False

    def _delete_cue(self) -> None:
        """Delete this cue point."""
        reply = QMessageBox.question(
            self,
            "Delete Cue Point",
            f"Delete cue point {self.cue_point.id}: {self.cue_point.label}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.cue_deleted.emit(self.cue_point.id)

    def _show_context_menu(self, position) -> None:
        """Show context menu."""
        menu = QMenu(self)

        # Jump to cue
        jump_action = QAction("Jump to Cue", self)
        jump_action.triggered.connect(lambda: self.cue_selected.emit(self.cue_point.id))
        menu.addAction(jump_action)

        # Edit label
        edit_action = QAction("Edit Label", self)
        edit_action.triggered.connect(self._start_editing)
        menu.addAction(edit_action)

        # Change color
        color_action = QAction("Change Color", self)
        color_action.triggered.connect(self._change_color)
        menu.addAction(color_action)

        menu.addSeparator()

        # Delete
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_cue)
        menu.addAction(delete_action)

        menu.exec(self.mapToGlobal(position))

    def _start_editing(self) -> None:
        """Start editing the label."""
        self.editing = True
        self.label_edit.setFocus()
        self.label_edit.selectAll()

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.cue_selected.emit(self.cue_point.id)
        super().mousePressEvent(event)


class Sidebar(QWidget):
    """
    Enhanced sidebar for displaying and managing cue points and musical structure.
    Provides interactive cue point editing with visual feedback.
    """

    # Signals
    cue_selected = pyqtSignal(int)  # Emitted when cue is selected
    cue_jump_requested = pyqtSignal(float)  # Emitted when jump to position requested

    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.config = config
        self.logger = logging.getLogger(__name__)

        # Cue manager reference (will be set by MainWindow)
        self.cue_manager: Optional[CueManager] = None

        # UI components
        self.cue_widgets: Dict[int, CuePointWidget] = {}

        self._setup_ui()
        self._setup_keyboard_shortcuts()

        self.logger.info("Enhanced Sidebar created")

    def _setup_ui(self) -> None:
        """Setup enhanced sidebar UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Cue points section
        cue_group = QGroupBox("Cue Points")
        cue_layout = QVBoxLayout(cue_group)

        # Cue controls
        controls_layout = QHBoxLayout()

        self.add_cue_button = QPushButton("Add Cue")
        self.add_cue_button.clicked.connect(self._add_cue_at_current_position)
        controls_layout.addWidget(self.add_cue_button)

        self.clear_cues_button = QPushButton("Clear All")
        self.clear_cues_button.clicked.connect(self._clear_all_cues)
        controls_layout.addWidget(self.clear_cues_button)

        cue_layout.addLayout(controls_layout)

        # Cue list (scrollable)
        self.cue_scroll_area = QScrollArea()
        self.cue_scroll_area.setWidgetResizable(True)
        self.cue_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarNever)

        self.cue_container = QWidget()
        self.cue_container_layout = QVBoxLayout(self.cue_container)
        self.cue_container_layout.setContentsMargins(0, 0, 0, 0)
        self.cue_container_layout.addStretch()

        self.cue_scroll_area.setWidget(self.cue_container)
        cue_layout.addWidget(self.cue_scroll_area)

        layout.addWidget(cue_group)

        # Structure section (Phase 3 implementation)
        structure_group = QGroupBox("Structure Analysis")
        structure_layout = QVBoxLayout(structure_group)

        # Structure controls
        structure_controls_layout = QHBoxLayout()

        self.analyze_structure_button = QPushButton("Analyze Structure")
        self.analyze_structure_button.clicked.connect(self._analyze_structure)
        structure_controls_layout.addWidget(self.analyze_structure_button)

        self.toggle_structure_button = QPushButton("Show/Hide")
        self.toggle_structure_button.clicked.connect(self._toggle_structure_display)
        structure_controls_layout.addWidget(self.toggle_structure_button)

        structure_layout.addLayout(structure_controls_layout)

        # Structure list (scrollable)
        self.structure_scroll_area = QScrollArea()
        self.structure_scroll_area.setWidgetResizable(True)
        self.structure_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarNever)

        self.structure_container = QWidget()
        self.structure_container_layout = QVBoxLayout(self.structure_container)
        self.structure_container_layout.setContentsMargins(0, 0, 0, 0)
        self.structure_container_layout.addStretch()

        self.structure_scroll_area.setWidget(self.structure_container)
        structure_layout.addWidget(self.structure_scroll_area)

        layout.addWidget(structure_group)

        # Structure data
        self.structure_sections: List[Any] = []
        self.structure_widgets: Dict[str, Any] = {}

        # Set fixed width
        sidebar_width = self.config.get('ui', {}).get('sidebar_width', 300)
        self.setFixedWidth(sidebar_width)

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for cue operations."""
        # Shortcuts will be handled by MainWindow
        pass

    def set_cue_manager(self, cue_manager: CueManager) -> None:
        """Set the cue manager reference."""
        self.cue_manager = cue_manager

    def update_cue_points(self, cue_points: List[CuePoint]) -> None:
        """Update the display with new cue points."""
        # Clear existing widgets
        self._clear_cue_widgets()

        # Add new cue widgets
        for cue_point in sorted(cue_points, key=lambda c: c.position_ms):
            self._add_cue_widget(cue_point)

        self.logger.debug(f"Updated display with {len(cue_points)} cue points")

    def _add_cue_widget(self, cue_point: CuePoint) -> None:
        """Add a cue point widget to the display."""
        widget = CuePointWidget(cue_point, self)

        # Connect signals
        widget.cue_selected.connect(self._on_cue_selected)
        widget.cue_edited.connect(self._on_cue_edited)
        widget.cue_deleted.connect(self._on_cue_deleted)

        # Insert in correct position (sorted by position)
        insert_index = 0
        for i in range(self.cue_container_layout.count() - 1):  # -1 for stretch
            item = self.cue_container_layout.itemAt(i)
            if item and item.widget():
                existing_widget = item.widget()
                if isinstance(existing_widget, CuePointWidget):
                    if existing_widget.cue_point.position_ms > cue_point.position_ms:
                        break
                    insert_index = i + 1

        self.cue_container_layout.insertWidget(insert_index, widget)
        self.cue_widgets[cue_point.id] = widget

    def _clear_cue_widgets(self) -> None:
        """Clear all cue point widgets."""
        for widget in self.cue_widgets.values():
            widget.setParent(None)
            widget.deleteLater()

        self.cue_widgets.clear()

    def _on_cue_selected(self, cue_id: int) -> None:
        """Handle cue selection."""
        if self.cue_manager:
            cue_point = self.cue_manager.get_cue_point(cue_id)
            if cue_point:
                self.cue_jump_requested.emit(cue_point.position_seconds)
                self.cue_selected.emit(cue_id)

    def _on_cue_edited(self, cue_id: int, label: str, color: str) -> None:
        """Handle cue editing."""
        if self.cue_manager:
            if label != self.cue_manager.get_cue_point(cue_id).label:
                self.cue_manager.update_cue_label(cue_id, label)

            if color != self.cue_manager.get_cue_point(cue_id).color:
                self.cue_manager.update_cue_color(cue_id, color)

    def _on_cue_deleted(self, cue_id: int) -> None:
        """Handle cue deletion."""
        if self.cue_manager:
            self.cue_manager.remove_cue_point(cue_id)

            # Remove widget
            if cue_id in self.cue_widgets:
                widget = self.cue_widgets.pop(cue_id)
                widget.setParent(None)
                widget.deleteLater()

    def _add_cue_at_current_position(self) -> None:
        """Add cue at current playback position."""
        # This will be connected to MainWindow's current position
        # For now, add at 0 seconds as placeholder
        if self.cue_manager:
            # Find next available cue ID
            used_ids = set(self.cue_manager.cue_points.keys())
            for cue_id in range(1, 17):  # 1-16
                if cue_id not in used_ids:
                    try:
                        cue_point = self.cue_manager.add_cue_point(cue_id, 0.0)
                        self._add_cue_widget(cue_point)
                        break
                    except Exception as e:
                        self.logger.warning(f"Failed to add cue: {e}")

    def _clear_all_cues(self) -> None:
        """Clear all cue points."""
        reply = QMessageBox.question(
            self,
            "Clear All Cues",
            "Are you sure you want to delete all cue points?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes and self.cue_manager:
            self.cue_manager.clear_all_cues()
            self._clear_cue_widgets()

    def add_cue_at_position(self, position_seconds: float) -> None:
        """Add cue at specific position (called from MainWindow)."""
        if not self.cue_manager:
            return

        # Find next available cue ID
        used_ids = set(self.cue_manager.cue_points.keys())
        for cue_id in range(1, 17):  # 1-16
            if cue_id not in used_ids:
                try:
                    position_ms = position_seconds * 1000.0
                    cue_point = self.cue_manager.add_cue_point(cue_id, position_ms)
                    self._add_cue_widget(cue_point)
                    self.logger.info(f"Added cue {cue_id} at {position_seconds:.2f}s")
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to add cue: {e}")
                    QMessageBox.warning(self, "Error", f"Failed to add cue: {e}")
                    break
        else:
            QMessageBox.information(self, "Cue Limit", "Maximum of 16 cue points reached.")

    def highlight_cue(self, cue_id: int) -> None:
        """Highlight a specific cue point."""
        # Reset all highlights
        for widget in self.cue_widgets.values():
            widget.setStyleSheet("")

        # Highlight selected cue
        if cue_id in self.cue_widgets:
            widget = self.cue_widgets[cue_id]
            widget.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); border: 1px solid #0078d4;")

    def get_cue_statistics(self) -> Dict[str, Any]:
        """Get cue point statistics for display."""
        if not self.cue_manager:
            return {'total_cues': 0}

        return self.cue_manager.get_statistics()

    def export_cues_to_json(self) -> Optional[Dict[str, Any]]:
        """Export cue points to JSON format."""
        if not self.cue_manager:
            return None

        return self.cue_manager.export_to_json()

    def import_cues_from_json(self, data: Dict[str, Any]) -> bool:
        """Import cue points from JSON format."""
        if not self.cue_manager:
            return False

        try:
            count = self.cue_manager.import_from_json(data)

            # Update display
            cue_points = self.cue_manager.get_all_cue_points()
            self.update_cue_points(cue_points)

            QMessageBox.information(self, "Import Complete", f"Imported {count} cue points.")
            return True

        except Exception as e:
            self.logger.error(f"Failed to import cues: {e}")
            QMessageBox.warning(self, "Import Error", f"Failed to import cues: {e}")
            return False

    def add_cue_points_batch(self, cue_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add multiple cue points in batch operation."""
        if not self.cue_manager:
            return {'success': False, 'error': 'No cue manager available'}

        try:
            result = self.cue_manager.add_cue_points_batch(cue_data_list)

            # Update display with all cue points
            cue_points = self.cue_manager.get_all_cue_points()
            self.update_cue_points(cue_points)

            return result

        except Exception as e:
            self.logger.error(f"Batch cue addition failed: {e}")
            return {'success': False, 'error': str(e)}

    def optimize_cue_positions(self, strategy: str = 'beat_align') -> Dict[str, Any]:
        """Optimize cue point positions using specified strategy."""
        if not self.cue_manager:
            return {'optimized': 0, 'error': 'No cue manager available'}

        try:
            result = self.cue_manager.optimize_cue_positions(strategy)

            # Update display after optimization
            cue_points = self.cue_manager.get_all_cue_points()
            self.update_cue_points(cue_points)

            QMessageBox.information(
                self,
                "Optimization Complete",
                f"Optimized {result['optimized']} cue points using {strategy} strategy."
            )

            return result

        except Exception as e:
            self.logger.error(f"Cue optimization failed: {e}")
            QMessageBox.warning(self, "Optimization Error", f"Failed to optimize cues: {e}")
            return {'optimized': 0, 'error': str(e)}

    def validate_all_cues(self) -> Dict[str, Any]:
        """Validate all cue points and show results."""
        if not self.cue_manager:
            return {'valid': 0, 'invalid': 0}

        validation_results = {
            'valid': 0,
            'invalid': 0,
            'errors': []
        }

        for cue_id, cue_point in self.cue_manager.cue_points.items():
            try:
                # Use the enhanced validation from cue manager
                errors = self.cue_manager._validate_cue_point(
                    cue_point.id, cue_point.position_ms,
                    cue_point.label, cue_point.color, True
                )

                if errors:
                    validation_results['invalid'] += 1
                    validation_results['errors'].append({
                        'cue_id': cue_id,
                        'errors': errors
                    })
                else:
                    validation_results['valid'] += 1

            except Exception as e:
                validation_results['invalid'] += 1
                validation_results['errors'].append({
                    'cue_id': cue_id,
                    'errors': [f"Validation failed: {e}"]
                })

        # Show validation results
        if validation_results['invalid'] > 0:
            error_details = "\n".join([
                f"Cue {err['cue_id']}: {', '.join(err['errors'])}"
                for err in validation_results['errors'][:5]  # Show first 5
            ])

            if len(validation_results['errors']) > 5:
                error_details += f"\n... and {len(validation_results['errors']) - 5} more"

            QMessageBox.warning(
                self,
                "Validation Issues Found",
                f"Found {validation_results['invalid']} invalid cue points:\n\n{error_details}"
            )
        else:
            QMessageBox.information(
                self,
                "Validation Complete",
                f"All {validation_results['valid']} cue points are valid."
            )

        return validation_results

    def show_performance_stats(self) -> None:
        """Show cue manager performance statistics."""
        if not self.cue_manager:
            QMessageBox.information(self, "No Data", "No cue manager available.")
            return

        try:
            stats = self.cue_manager.get_performance_metrics()

            # Format statistics for display
            stats_text = f"""
Cue Manager Performance Statistics:

Cache Performance:
• Hit Ratio: {stats['cache_stats']['hit_ratio']:.1%}
• Cache Size: {stats['cache_stats']['cache_size']} entries
• Hits: {stats['cache_stats']['hits']}
• Misses: {stats['cache_stats']['misses']}

Operations:
• Total Operations: {stats['operations']['total']}
• Average Time: {stats['operations']['avg_time']:.3f}s

Conflicts:
• Total Conflicts: {stats['conflicts']['total_conflicts']}

Memory:
• Cue Points: {stats['memory']['cue_points']}
• Cache Entries: {stats['memory']['cache_entries']}
• History Entries: {stats['memory']['history_entries']}
"""

            QMessageBox.information(self, "Performance Statistics", stats_text)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to get statistics: {e}")

    def clear_cue_cache(self) -> None:
        """Clear cue manager cache."""
        if not self.cue_manager:
            return

        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "Clear cue manager cache? This may temporarily slow down operations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.cue_manager.clear_cache()
            QMessageBox.information(self, "Cache Cleared", "Cue manager cache has been cleared.")

    def export_cue_statistics(self) -> Optional[str]:
        """Export detailed cue statistics to text format."""
        if not self.cue_manager:
            return None

        try:
            stats = self.cue_manager.get_statistics()
            performance = self.cue_manager.get_performance_metrics()

            export_text = f"""CUEpoint - Cue Statistics Export
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

=== CUE POINT SUMMARY ===
Total Cue Points: {stats['total_cues']}
First Cue: {stats.get('first_cue_ms', 0)/1000:.2f}s
Last Cue: {stats.get('last_cue_ms', 0)/1000:.2f}s
Average Spacing: {stats.get('average_spacing_ms', 0)/1000:.2f}s

=== CUE TYPES ===
"""

            for cue_type, count in stats.get('cue_types', {}).items():
                export_text += f"{cue_type}: {count}\n"

            export_text += f"""
=== PERFORMANCE METRICS ===
Cache Hit Ratio: {performance['cache_stats']['hit_ratio']:.1%}
Total Operations: {performance['operations']['total']}
Average Operation Time: {performance['operations']['avg_time']:.3f}s
Total Conflicts: {performance['conflicts']['total_conflicts']}

=== INDIVIDUAL CUE POINTS ===
"""

            for cue in self.cue_manager.get_all_cue_points():
                export_text += f"Cue {cue.id}: {cue.position_seconds:.2f}s - {cue.label} ({cue.color})\n"

            return export_text

        except Exception as e:
            self.logger.error(f"Failed to export statistics: {e}")
            return None

    def set_structure_analyzer(self, structure_analyzer: Any) -> None:
        """Set the structure analyzer reference."""
        self.structure_analyzer = structure_analyzer

    def update_structure_sections(self, structure_sections: List[Any]) -> None:
        """Update the display with structure sections."""
        self.structure_sections = structure_sections
        self._update_structure_display()

    def _update_structure_display(self) -> None:
        """Update the structure section display."""
        # Clear existing widgets
        for widget in self.structure_widgets.values():
            widget.setParent(None)
            widget.deleteLater()
        self.structure_widgets.clear()

        # Add new structure widgets
        for section in self.structure_sections:
            self._add_structure_widget(section)

    def _add_structure_widget(self, section: Any) -> None:
        """Add a structure section widget to the display."""
        widget = StructureSectionWidget(section, self)

        # Connect signals
        widget.section_selected.connect(self._on_structure_selected)
        widget.section_edited.connect(self._on_structure_edited)

        # Insert in correct position (sorted by start time)
        insert_index = 0
        for i in range(self.structure_container_layout.count() - 1):  # -1 for stretch
            item = self.structure_container_layout.itemAt(i)
            if item and item.widget():
                existing_widget = item.widget()
                if isinstance(existing_widget, StructureSectionWidget):
                    if existing_widget.section.start_time > section.start_time:
                        break
                    insert_index = i + 1

        self.structure_container_layout.insertWidget(insert_index, widget)
        section_key = f"{section.type.value}_{section.start_time}"
        self.structure_widgets[section_key] = widget

    def _analyze_structure(self) -> None:
        """Trigger structure analysis."""
        if not hasattr(self, 'structure_analyzer') or not self.structure_analyzer:
            QMessageBox.information(self, "No Analyzer", "Structure analyzer not available.")
            return

        # This will be connected to MainWindow's structure analysis
        self.analyze_structure_button.setText("Analyzing...")
        self.analyze_structure_button.setEnabled(False)

        # Emit signal to trigger analysis (will be connected in MainWindow)
        # For now, show placeholder message
        QMessageBox.information(self, "Analysis", "Structure analysis will be triggered from MainWindow.")

        self.analyze_structure_button.setText("Analyze Structure")
        self.analyze_structure_button.setEnabled(True)

    def _toggle_structure_display(self) -> None:
        """Toggle structure overlay display."""
        # This will be connected to waveform view
        # For now, just toggle button text
        current_text = self.toggle_structure_button.text()
        if "Show" in current_text:
            self.toggle_structure_button.setText("Hide Structure")
        else:
            self.toggle_structure_button.setText("Show Structure")

    def _on_structure_selected(self, section_type: str, start_time: float) -> None:
        """Handle structure section selection."""
        # Jump to structure section
        # This will be connected to waveform view
        self.logger.debug(f"Structure section selected: {section_type} at {start_time}s")

    def _on_structure_edited(self, section_type: str, start_time: float,
                           new_label: str) -> None:
        """Handle structure section editing."""
        # Update structure section label
        for section in self.structure_sections:
            if (section.type.value == section_type and
                abs(section.start_time - start_time) < 0.1):
                section.label = new_label
                break

        self.logger.debug(f"Structure section edited: {section_type} -> {new_label}")


class StructureSectionWidget(QWidget):
    """Individual structure section widget with inline editing."""

    # Signals
    section_selected = pyqtSignal(str, float)  # section_type, start_time
    section_edited = pyqtSignal(str, float, str)  # section_type, start_time, new_label

    def __init__(self, section: Any, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.section = section
        self.editing = False

        self._setup_ui()
        self._update_display()

    def _setup_ui(self) -> None:
        """Setup structure section widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        # Color indicator
        self.color_indicator = QLabel()
        self.color_indicator.setFixedSize(20, 20)
        layout.addWidget(self.color_indicator)

        # Time range label
        self.time_label = QLabel()
        self.time_label.setFixedWidth(80)
        layout.addWidget(self.time_label)

        # Section label (editable)
        self.label_edit = QLineEdit(self.section.label)
        self.label_edit.editingFinished.connect(self._on_label_edited)
        layout.addWidget(self.label_edit)

        # Confidence indicator
        self.confidence_label = QLabel()
        self.confidence_label.setFixedWidth(40)
        layout.addWidget(self.confidence_label)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _update_display(self) -> None:
        """Update widget display."""
        # Update color indicator
        self.color_indicator.setStyleSheet(
            f"background-color: {self.section.color}; border: 1px solid #333;"
        )

        # Update time range
        start_min = int(self.section.start_time // 60)
        start_sec = self.section.start_time % 60
        end_min = int(self.section.end_time // 60)
        end_sec = self.section.end_time % 60

        self.time_label.setText(f"{start_min}:{start_sec:04.1f}-{end_min}:{end_sec:04.1f}")

        # Update confidence
        confidence_percent = int(self.section.confidence * 100)
        self.confidence_label.setText(f"{confidence_percent}%")

        # Update label
        if not self.editing:
            self.label_edit.setText(self.section.label)

    def _on_label_edited(self) -> None:
        """Handle label editing."""
        new_label = self.label_edit.text().strip()
        if new_label and new_label != self.section.label:
            self.section.label = new_label
            self.section_edited.emit(
                self.section.type.value,
                self.section.start_time,
                new_label
            )

        self.editing = False

    def _show_context_menu(self, position) -> None:
        """Show context menu."""
        menu = QMenu(self)

        # Jump to section
        jump_action = QAction("Jump to Section", self)
        jump_action.triggered.connect(
            lambda: self.section_selected.emit(
                self.section.type.value,
                self.section.start_time
            )
        )
        menu.addAction(jump_action)

        # Edit label
        edit_action = QAction("Edit Label", self)
        edit_action.triggered.connect(self._start_editing)
        menu.addAction(edit_action)

        menu.exec(self.mapToGlobal(position))

    def _start_editing(self) -> None:
        """Start editing the label."""
        self.editing = True
        self.label_edit.setFocus()
        self.label_edit.selectAll()

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.section_selected.emit(
                self.section.type.value,
                self.section.start_time
            )
        super().mousePressEvent(event)
