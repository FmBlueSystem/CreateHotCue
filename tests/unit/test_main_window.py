"""
Unit tests for MainWindow class
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.gui.main_window import MainWindow


class TestMainWindow:
    """Test cases for MainWindow class."""
    
    def test_main_window_creation(self, qapp, test_config):
        """Test that MainWindow can be created successfully."""
        window = MainWindow(test_config)
        assert window is not None
        assert window.config == test_config
        assert window.current_file is None
    
    def test_window_title_and_size(self, qapp, test_config):
        """Test window title and size configuration."""
        window = MainWindow(test_config)
        
        expected_title = f"{test_config['app']['name']} v{test_config['app']['version']}"
        assert expected_title in window.windowTitle()
        
        # Check size
        expected_width = test_config['app']['window']['width']
        expected_height = test_config['app']['window']['height']
        assert window.size().width() == expected_width
        assert window.size().height() == expected_height
    
    def test_menu_bar_creation(self, qapp, test_config):
        """Test that menu bar is created with expected menus."""
        window = MainWindow(test_config)
        
        menubar = window.menuBar()
        assert menubar is not None
        
        # Check for expected menus
        menu_titles = [action.text() for action in menubar.actions()]
        expected_menus = ["File", "Edit", "View", "Analysis"]
        
        for menu in expected_menus:
            assert menu in menu_titles
    
    def test_central_widget_creation(self, qapp, test_config):
        """Test that central widget components are created."""
        window = MainWindow(test_config)
        
        # Check that main components exist
        assert hasattr(window, 'waveform_view')
        assert hasattr(window, 'sidebar')
        assert hasattr(window, 'transport_bar')
        
        # Check that central widget is set
        assert window.centralWidget() is not None
    
    def test_status_bar_creation(self, qapp, test_config):
        """Test that status bar is created."""
        window = MainWindow(test_config)
        
        status_bar = window.statusBar()
        assert status_bar is not None
        assert "Ready" in status_bar.currentMessage()
    
    def test_drag_drop_enabled(self, qapp, test_config):
        """Test that drag and drop is enabled."""
        window = MainWindow(test_config)
        assert window.acceptDrops() is True
    
    def test_supported_audio_file_detection(self, qapp, test_config):
        """Test detection of supported audio file formats."""
        window = MainWindow(test_config)
        
        # Test supported formats
        supported_formats = test_config['audio']['supported_formats']
        for fmt in supported_formats:
            test_file = Path(f"test.{fmt}")
            assert window._is_supported_audio_file(test_file) is True
        
        # Test unsupported format
        unsupported_file = Path("test.txt")
        assert window._is_supported_audio_file(unsupported_file) is False
    
    @patch('src.gui.main_window.QFileDialog.getOpenFileName')
    def test_open_file_dialog(self, mock_dialog, qapp, test_config):
        """Test opening file dialog."""
        window = MainWindow(test_config)
        
        # Mock file dialog to return a test file
        test_file = "/path/to/test.mp3"
        mock_dialog.return_value = (test_file, "")
        
        with patch.object(window, '_load_audio_file') as mock_load:
            window._open_file_dialog()
            mock_load.assert_called_once_with(Path(test_file))
    
    def test_file_loaded_signal(self, qapp, test_config):
        """Test that file_loaded signal is emitted correctly."""
        window = MainWindow(test_config)
        
        # Connect signal to mock handler
        mock_handler = Mock()
        window.file_loaded.connect(mock_handler)
        
        # Simulate loading a file
        test_file = Path("/path/to/test.mp3")
        window._load_audio_file(test_file)
        
        # Check signal was emitted
        mock_handler.assert_called_once_with(str(test_file))
        assert window.current_file == test_file
    
    def test_zoom_actions(self, qapp, test_config):
        """Test zoom action methods."""
        window = MainWindow(test_config)
        
        # Mock waveform view methods
        window.waveform_view.zoom_in = Mock()
        window.waveform_view.zoom_out = Mock()
        window.waveform_view.fit_to_window = Mock()
        
        # Test zoom actions
        window._zoom_in()
        window.waveform_view.zoom_in.assert_called_once()
        
        window._zoom_out()
        window.waveform_view.zoom_out.assert_called_once()
        
        window._fit_to_window()
        window.waveform_view.fit_to_window.assert_called_once()
    
    def test_keyboard_shortcuts(self, qapp, test_config):
        """Test that keyboard shortcuts are properly configured."""
        window = MainWindow(test_config)
        window.show()
        
        # Test that window can receive key events
        # Note: Full keyboard shortcut testing would require more complex setup
        assert window.isVisible()
        
        # Test a simple key press (space for play/pause would be tested in integration)
        QTest.keyPress(window, Qt.Key.Key_Space)
        
        # If we get here without exception, basic key handling works
        assert True
    
    def test_performance_monitoring_setup(self, qapp, test_config):
        """Test performance monitoring timer setup."""
        # Enable performance monitoring in config
        test_config['performance']['log_fps'] = True
        test_config['performance']['memory_monitoring'] = True
        
        window = MainWindow(test_config)
        
        # Check that timers are created (they exist as attributes)
        assert hasattr(window, 'fps_timer')
        assert hasattr(window, 'memory_timer')
    
    def test_window_cleanup(self, qapp, test_config):
        """Test that window cleans up properly."""
        window = MainWindow(test_config)
        window.show()
        
        # Close window
        window.close()
        
        # Window should be closed
        assert not window.isVisible()


@pytest.mark.integration
class TestMainWindowIntegration:
    """Integration tests for MainWindow with actual file operations."""
    
    def test_load_audio_file_integration(self, qapp, test_config, temp_audio_file):
        """Test loading an actual audio file."""
        window = MainWindow(test_config)
        
        # Load the temporary audio file
        window._load_audio_file(temp_audio_file)
        
        # Check that file was loaded
        assert window.current_file == temp_audio_file
        assert temp_audio_file.name in window.statusBar().currentMessage()
    
    def test_drag_drop_integration(self, qapp, test_config, temp_audio_file):
        """Test drag and drop functionality with actual file."""
        window = MainWindow(test_config)
        window.show()
        
        # Create mock drag event
        from PyQt6.QtCore import QMimeData, QUrl
        from PyQt6.QtGui import QDragEnterEvent, QDropEvent
        
        mime_data = QMimeData()
        mime_data.setUrls([QUrl.fromLocalFile(str(temp_audio_file))])
        
        # Test drag enter
        drag_enter_event = QDragEnterEvent(
            window.rect().center(),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        
        window.dragEnterEvent(drag_enter_event)
        assert drag_enter_event.isAccepted()
        
        # Test drop
        drop_event = QDropEvent(
            window.rect().center(),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        
        window.dropEvent(drop_event)
        
        # File should be loaded
        assert window.current_file == temp_audio_file
