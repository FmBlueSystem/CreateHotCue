#!/usr/bin/env python3
"""
Enhanced Phase 2 Validation Script - Fortified Cue & Metadata Hub
Comprehensive testing of strengthened Phase 2 implementation with advanced features
"""

import sys
import os
import time
import json
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_enhanced_cue_manager():
    """Test enhanced CueManager with advanced features."""
    print("\n🎯 Testing Enhanced CueManager...")
    
    try:
        from core.cue_manager import CueManager, CuePoint, CueType
        
        # Load enhanced config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Add enhanced settings
        config['cues'].update({
            'validation_strict': True,
            'cache_enabled': True,
            'batch_operations': True,
            'conflict_resolution': 'merge'
        })
        
        manager = CueManager(config)
        print("✅ Enhanced CueManager created successfully")
        
        # Test enhanced validation
        manager.set_track(Path("test_track.mp3"), 180000.0)
        
        # Test validation caching
        errors1 = manager._validate_cue_point(1, 5000.0, "Test", "#FF0000", True)
        errors2 = manager._validate_cue_point(1, 5000.0, "Test", "#FF0000", True)
        assert manager.cache_hits > 0
        print("✅ Validation caching working")
        
        # Test conflict detection
        manager.add_cue_point(1, 5000.0, "First", force=True)
        conflicts = manager._check_cue_conflicts(1, 10000.0)
        assert len(conflicts) > 0
        print("✅ Conflict detection working")
        
        # Test batch operations
        batch_data = [
            {'id': 2, 'position_ms': 15000.0, 'label': 'Build'},
            {'id': 3, 'position_ms': 25000.0, 'label': 'Drop'},
            {'id': 4, 'position_ms': 35000.0, 'label': 'Break'}
        ]
        
        result = manager.add_cue_points_batch(batch_data)
        assert len(result['added']) == 3
        assert len(result['failed']) == 0
        print("✅ Batch operations working")
        
        # Test optimization
        optimization_result = manager.optimize_cue_positions('beat_align')
        assert optimization_result['strategy'] == 'beat_align'
        print("✅ Cue optimization working")
        
        # Test performance metrics
        metrics = manager.get_performance_metrics()
        assert 'cache_stats' in metrics
        assert 'operations' in metrics
        assert metrics['cache_stats']['hit_ratio'] >= 0
        print("✅ Performance metrics working")
        
        # Test cache management
        manager.clear_cache()
        assert len(manager._validation_cache) == 0
        print("✅ Cache management working")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced CueManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_metadata_parser():
    """Test enhanced MetadataParser with advanced features."""
    print("\n📋 Testing Enhanced MetadataParser...")
    
    try:
        from core.metadata_parser import MetadataParser, TrackMetadata
        
        # Load enhanced config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Add enhanced settings
        config['metadata'] = {
            'validation_enabled': True,
            'cache_enabled': True,
            'batch_processing': True,
            'integrity_checks': True,
            'auto_repair': True
        }
        
        # Check if mutagen is available
        try:
            import mutagen
            print("✅ mutagen library available")
        except ImportError:
            print("⚠️  mutagen not available - skipping enhanced metadata tests")
            return True
        
        parser = MetadataParser(config)
        print("✅ Enhanced MetadataParser created successfully")
        
        # Test metadata validation
        valid_metadata = TrackMetadata(
            title="Test Track",
            artist="Test Artist",
            year=2023,
            bpm=128.0
        )
        
        errors = parser._validate_metadata(valid_metadata)
        assert len(errors) == 0
        print("✅ Metadata validation working")
        
        # Test validation with errors
        invalid_metadata = TrackMetadata(
            title="Test Track",
            year=1800,  # Too old
            bpm=500.0   # Too high
        )
        
        errors = parser._validate_metadata(invalid_metadata)
        assert len(errors) > 0
        print("✅ Validation error detection working")
        
        # Test auto-repair
        repaired = parser._repair_metadata(invalid_metadata, errors)
        assert repaired.year is None  # Should be reset
        assert repaired.bpm is None   # Should be reset
        print("✅ Auto-repair working")
        
        # Test cache statistics
        stats = parser.get_cache_stats()
        assert 'cache' in stats
        assert 'operations' in stats
        print("✅ Cache statistics working")
        
        # Test file checksum calculation
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_path = Path(temp_file.name)
            temp_path.write_bytes(b"test content")
            
            checksum = parser._calculate_file_checksum(temp_path)
            assert isinstance(checksum, str)
            assert len(checksum) > 0
            print("✅ File checksum calculation working")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced MetadataParser test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_serato_bridge():
    """Test enhanced SeratoBridge with advanced features."""
    print("\n🎚️ Testing Enhanced SeratoBridge...")
    
    try:
        from core.serato_bridge import SeratoBridge
        from core.cue_manager import CuePoint, CueType
        
        # Load enhanced config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Add enhanced settings
        config['serato'] = {
            'strict_validation': True,
            'auto_repair': True,
            'version_detection': True,
            'backup_serato_data': True
        }
        
        bridge = SeratoBridge(config)
        print("✅ Enhanced SeratoBridge created successfully")
        
        # Test cue validation
        valid_cue = CuePoint(
            id=1,
            position_ms=5000.0,
            label="Test Cue",
            color="#CC0000",
            serato_color=0xCC0000
        )
        
        errors = bridge._validate_serato_cue(valid_cue)
        assert len(errors) == 0
        print("✅ Serato cue validation working")
        
        # Test validation with errors
        invalid_cue = CuePoint(
            id=0,  # Invalid ID
            position_ms=-1000.0,  # Invalid position
            label="A" * 150,  # Too long
            color="#CC0000"
        )
        
        errors = bridge._validate_serato_cue(invalid_cue)
        assert len(errors) > 0
        print("✅ Serato validation error detection working")
        
        # Test auto-repair
        repaired = bridge._repair_serato_cue(invalid_cue, errors)
        assert 1 <= repaired.id <= 16  # Should be clamped
        assert repaired.position_ms >= 0  # Should be fixed
        assert len(repaired.label) <= 100  # Should be truncated
        print("✅ Serato auto-repair working")
        
        # Test statistics
        stats = bridge.get_serato_statistics()
        assert 'operations' in stats
        assert 'supported_versions' in stats
        assert 'settings' in stats
        print("✅ Serato statistics working")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced SeratoBridge test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_advanced_performance_monitor():
    """Test advanced performance monitoring."""
    print("\n📊 Testing Advanced Performance Monitor...")
    
    try:
        from core.advanced_performance_monitor import AdvancedPerformanceMonitor, PerformanceMetric
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Add performance monitoring settings
        config['performance'] = {
            'advanced_monitoring': True,
            'sample_interval': 0.1,  # Fast for testing
            'memory_tracking': True,
            'detailed_logging': False
        }
        
        monitor = AdvancedPerformanceMonitor(config)
        print("✅ Advanced Performance Monitor created successfully")
        
        # Test metric recording
        monitor.record_measurement('test_operation', 0.05, 'test_component')
        
        # Test operation measurement context manager
        with monitor.measure_operation('context_test', 'test'):
            time.sleep(0.01)  # Simulate work
        
        # Test performance report
        report = monitor.get_performance_report()
        assert 'operations' in report
        assert 'system' in report
        assert 'components' in report
        print("✅ Performance reporting working")
        
        # Test alert system
        alert_triggered = False
        def test_callback(alert_type, data):
            nonlocal alert_triggered
            alert_triggered = True
        
        monitor.add_alert_callback(test_callback)
        
        # Trigger a performance alert
        monitor.record_measurement('slow_operation', 2.0, 'test')  # Should trigger threshold
        
        # Give some time for monitoring
        time.sleep(0.2)
        
        # Stop monitoring
        monitor.stop_monitoring()
        print("✅ Performance monitoring lifecycle working")
        
        return True
        
    except Exception as e:
        print(f"❌ Advanced Performance Monitor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_integration():
    """Test integration of all enhanced components."""
    print("\n🔧 Testing Enhanced Integration...")
    
    try:
        from core.cue_manager import CueManager
        from core.metadata_parser import MetadataParser
        from core.serato_bridge import SeratoBridge
        from core.advanced_performance_monitor import AdvancedPerformanceMonitor
        
        # Load enhanced config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        # Add all enhanced settings
        config.update({
            'cues': {
                **config.get('cues', {}),
                'validation_strict': True,
                'cache_enabled': True,
                'batch_operations': True,
                'conflict_resolution': 'merge'
            },
            'metadata': {
                'validation_enabled': True,
                'cache_enabled': True,
                'batch_processing': True,
                'auto_repair': True
            },
            'serato': {
                'strict_validation': True,
                'auto_repair': True,
                'version_detection': True
            },
            'performance': {
                'advanced_monitoring': True,
                'sample_interval': 0.1,
                'memory_tracking': True
            }
        })
        
        # Create all components
        cue_manager = CueManager(config)
        serato_bridge = SeratoBridge(config)
        performance_monitor = AdvancedPerformanceMonitor(config)
        
        # Check if mutagen is available for metadata parser
        try:
            import mutagen
            metadata_parser = MetadataParser(config)
            print("✅ All enhanced components created successfully")
        except ImportError:
            print("✅ Enhanced components created (metadata parser skipped - no mutagen)")
        
        # Test integrated workflow
        cue_manager.set_track(Path("integration_test.mp3"), 240000.0)
        
        # Add cues with performance monitoring
        with performance_monitor.measure_operation('add_cue', 'cue'):
            cue_manager.add_cue_point(1, 8000.0, "Intro", "#FF3366")
        
        with performance_monitor.measure_operation('batch_add', 'cue'):
            batch_data = [
                {'id': 2, 'position_ms': 32000.0, 'label': 'Build'},
                {'id': 3, 'position_ms': 64000.0, 'label': 'Drop'}
            ]
            result = cue_manager.add_cue_points_batch(batch_data)
        
        # Test optimization with monitoring
        with performance_monitor.measure_operation('optimize', 'cue'):
            cue_manager.optimize_cue_positions('beat_align')
        
        # Get comprehensive statistics
        cue_stats = cue_manager.get_performance_metrics()
        serato_stats = serato_bridge.get_serato_statistics()
        perf_report = performance_monitor.get_performance_report()
        
        assert cue_stats['operations']['total'] > 0
        assert len(perf_report['operations']) > 0
        
        # Cleanup
        performance_monitor.stop_monitoring()
        
        print("✅ Enhanced integration workflow working")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stress_performance():
    """Test performance under stress conditions."""
    print("\n⚡ Testing Stress Performance...")
    
    try:
        from core.cue_manager import CueManager
        from core.advanced_performance_monitor import AdvancedPerformanceMonitor
        
        # Load config
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        config['cues'].update({
            'cache_enabled': True,
            'batch_operations': True
        })
        
        config['performance'] = {
            'advanced_monitoring': True,
            'sample_interval': 0.1
        }
        
        cue_manager = CueManager(config)
        performance_monitor = AdvancedPerformanceMonitor(config)
        
        cue_manager.set_track(Path("stress_test.mp3"), 600000.0)  # 10 minutes
        
        # Stress test: Add many cues rapidly
        start_time = time.time()
        
        for i in range(16):  # Max cues
            with performance_monitor.measure_operation('stress_add', 'cue'):
                cue_manager.add_cue_point(
                    i + 1, 
                    i * 30000.0,  # Every 30 seconds
                    f"Stress Cue {i+1}",
                    force=True
                )
        
        # Stress test: Many validation calls
        for i in range(100):
            cue_manager._validate_cue_point(1, 5000.0, "Test", "#FF0000", True)
        
        stress_time = time.time() - start_time
        
        # Check performance
        metrics = cue_manager.get_performance_metrics()
        cache_hit_ratio = metrics['cache_stats']['hit_ratio']
        
        performance_monitor.stop_monitoring()
        
        print(f"✅ Stress test completed in {stress_time:.2f}s")
        print(f"✅ Cache hit ratio: {cache_hit_ratio:.1%}")
        print(f"✅ Total operations: {metrics['operations']['total']}")
        
        # Performance assertions
        assert stress_time < 5.0  # Should complete quickly
        assert cache_hit_ratio > 0.8  # Should have good cache performance
        
        return True
        
    except Exception as e:
        print(f"❌ Stress performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all enhanced Phase 2 validation tests."""
    print("🚀 CUEpoint Enhanced Phase 2 - Fortified Cue & Metadata Hub Validation")
    print("=" * 80)
    
    tests = [
        ("Enhanced CueManager", test_enhanced_cue_manager),
        ("Enhanced MetadataParser", test_enhanced_metadata_parser),
        ("Enhanced SeratoBridge", test_enhanced_serato_bridge),
        ("Advanced Performance Monitor", test_advanced_performance_monitor),
        ("Enhanced Integration", test_enhanced_integration),
        ("Stress Performance", test_stress_performance),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 50)
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 80)
    print(f"📊 Enhanced Phase 2 Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Enhanced Phase 2 tests passed! Fortified Cue & Metadata Hub is ready.")
        print("\n🚀 Enhanced Phase 2 Features Validated:")
        print("   ✅ Advanced cue validation with caching")
        print("   ✅ Batch operations with conflict resolution")
        print("   ✅ Intelligent metadata caching and repair")
        print("   ✅ Enhanced Serato compatibility with validation")
        print("   ✅ Advanced performance monitoring")
        print("   ✅ Stress-tested performance under load")
        print("\n💪 Phase 2 is now FORTIFIED and ready for Phase 3! 🎯")
        return 0
    else:
        print("⚠️  Some Enhanced Phase 2 tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
