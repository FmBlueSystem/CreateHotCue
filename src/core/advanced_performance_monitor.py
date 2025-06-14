"""
Advanced Performance Monitor for Phase 2 Components
Comprehensive monitoring of cue operations, metadata processing, and Serato compatibility
"""

import logging
import time
import threading
import psutil
import gc
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict
import statistics


@dataclass
class PerformanceMetric:
    """Individual performance metric with statistics."""
    name: str
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    total_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    
    def add_measurement(self, value: float) -> None:
        """Add a new measurement."""
        self.values.append(value)
        self.total_count += 1
        self.total_time += value
        self.min_time = min(self.min_time, value)
        self.max_time = max(self.max_time, value)
    
    @property
    def average(self) -> float:
        """Get average time."""
        return self.total_time / max(1, self.total_count)
    
    @property
    def recent_average(self) -> float:
        """Get average of recent measurements."""
        if not self.values:
            return 0.0
        return statistics.mean(self.values)
    
    @property
    def percentile_95(self) -> float:
        """Get 95th percentile of recent measurements."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        index = int(0.95 * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]


class AdvancedPerformanceMonitor:
    """
    Advanced performance monitoring for Phase 2 components.
    Tracks cue operations, metadata processing, and system resources.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Monitoring settings
        self.enabled = config.get('performance', {}).get('advanced_monitoring', True)
        self.sample_interval = config.get('performance', {}).get('sample_interval', 1.0)
        self.memory_tracking = config.get('performance', {}).get('memory_tracking', True)
        self.detailed_logging = config.get('performance', {}).get('detailed_logging', False)
        
        # Performance metrics
        self.metrics: Dict[str, PerformanceMetric] = {}
        self.system_metrics: Dict[str, deque] = {
            'cpu_percent': deque(maxlen=300),  # 5 minutes at 1s intervals
            'memory_percent': deque(maxlen=300),
            'memory_mb': deque(maxlen=300),
            'disk_io_read': deque(maxlen=300),
            'disk_io_write': deque(maxlen=300)
        }
        
        # Component-specific tracking
        self.cue_operations = defaultdict(int)
        self.metadata_operations = defaultdict(int)
        self.serato_operations = defaultdict(int)
        self.ui_operations = defaultdict(int)
        
        # Threading
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._lock = threading.Lock()
        
        # Callbacks for alerts
        self.alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # Performance thresholds
        self.thresholds = {
            'cue_add_time': 0.1,      # 100ms
            'metadata_read_time': 1.0,  # 1s
            'metadata_write_time': 2.0, # 2s
            'serato_parse_time': 0.5,   # 500ms
            'ui_response_time': 0.05,   # 50ms
            'memory_usage_mb': 500,     # 500MB
            'cpu_usage_percent': 80     # 80%
        }
        
        if self.enabled:
            self._start_monitoring()
            self.logger.info("Advanced Performance Monitor initialized")
    
    def _start_monitoring(self) -> None:
        """Start background monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="AdvancedPerfMonitor"
        )
        self._monitoring_thread.start()
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        last_disk_io = psutil.disk_io_counters()
        
        while not self._stop_monitoring.wait(self.sample_interval):
            try:
                # System metrics
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                
                # Disk I/O
                current_disk_io = psutil.disk_io_counters()
                if last_disk_io:
                    read_rate = (current_disk_io.read_bytes - last_disk_io.read_bytes) / self.sample_interval
                    write_rate = (current_disk_io.write_bytes - last_disk_io.write_bytes) / self.sample_interval
                else:
                    read_rate = write_rate = 0
                
                last_disk_io = current_disk_io
                
                with self._lock:
                    self.system_metrics['cpu_percent'].append(cpu_percent)
                    self.system_metrics['memory_percent'].append(memory.percent)
                    self.system_metrics['memory_mb'].append(memory.used / 1024 / 1024)
                    self.system_metrics['disk_io_read'].append(read_rate / 1024 / 1024)  # MB/s
                    self.system_metrics['disk_io_write'].append(write_rate / 1024 / 1024)  # MB/s
                
                # Check thresholds and trigger alerts
                self._check_thresholds(cpu_percent, memory.used / 1024 / 1024)
                
            except Exception as e:
                self.logger.warning(f"Monitoring loop error: {e}")
    
    def measure_operation(self, operation_name: str, component: str = 'general'):
        """Context manager for measuring operation performance."""
        return OperationMeasurer(self, operation_name, component)
    
    def record_measurement(self, operation_name: str, duration: float, 
                          component: str = 'general') -> None:
        """Record a performance measurement."""
        if not self.enabled:
            return
        
        with self._lock:
            # Update metric
            if operation_name not in self.metrics:
                self.metrics[operation_name] = PerformanceMetric(operation_name)
            
            self.metrics[operation_name].add_measurement(duration)
            
            # Update component counters
            if component == 'cue':
                self.cue_operations[operation_name] += 1
            elif component == 'metadata':
                self.metadata_operations[operation_name] += 1
            elif component == 'serato':
                self.serato_operations[operation_name] += 1
            elif component == 'ui':
                self.ui_operations[operation_name] += 1
        
        # Check for performance issues
        threshold_key = f"{operation_name}_time"
        if threshold_key in self.thresholds and duration > self.thresholds[threshold_key]:
            self._trigger_alert('performance_threshold', {
                'operation': operation_name,
                'component': component,
                'duration': duration,
                'threshold': self.thresholds[threshold_key]
            })
        
        if self.detailed_logging:
            self.logger.debug(f"{component}.{operation_name}: {duration:.3f}s")
    
    def _check_thresholds(self, cpu_percent: float, memory_mb: float) -> None:
        """Check system resource thresholds."""
        if cpu_percent > self.thresholds['cpu_usage_percent']:
            self._trigger_alert('high_cpu', {
                'cpu_percent': cpu_percent,
                'threshold': self.thresholds['cpu_usage_percent']
            })
        
        if memory_mb > self.thresholds['memory_usage_mb']:
            self._trigger_alert('high_memory', {
                'memory_mb': memory_mb,
                'threshold': self.thresholds['memory_usage_mb']
            })
    
    def _trigger_alert(self, alert_type: str, data: Dict[str, Any]) -> None:
        """Trigger performance alert."""
        alert_data = {
            'type': alert_type,
            'timestamp': time.time(),
            'data': data
        }
        
        for callback in self.alert_callbacks:
            try:
                callback(alert_type, alert_data)
            except Exception as e:
                self.logger.warning(f"Alert callback failed: {e}")
        
        if self.detailed_logging:
            self.logger.warning(f"Performance alert: {alert_type} - {data}")
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add callback for performance alerts."""
        self.alert_callbacks.append(callback)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        with self._lock:
            # Operation metrics
            operation_stats = {}
            for name, metric in self.metrics.items():
                operation_stats[name] = {
                    'count': metric.total_count,
                    'total_time': metric.total_time,
                    'average': metric.average,
                    'recent_average': metric.recent_average,
                    'min_time': metric.min_time if metric.min_time != float('inf') else 0,
                    'max_time': metric.max_time,
                    'percentile_95': metric.percentile_95
                }
            
            # System metrics
            system_stats = {}
            for name, values in self.system_metrics.items():
                if values:
                    system_stats[name] = {
                        'current': values[-1],
                        'average': statistics.mean(values),
                        'min': min(values),
                        'max': max(values),
                        'samples': len(values)
                    }
            
            # Component summaries
            component_stats = {
                'cue_operations': dict(self.cue_operations),
                'metadata_operations': dict(self.metadata_operations),
                'serato_operations': dict(self.serato_operations),
                'ui_operations': dict(self.ui_operations)
            }
        
        return {
            'timestamp': time.time(),
            'monitoring_enabled': self.enabled,
            'operations': operation_stats,
            'system': system_stats,
            'components': component_stats,
            'thresholds': self.thresholds.copy(),
            'memory_info': self._get_memory_info() if self.memory_tracking else {}
        }
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get detailed memory information."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Force garbage collection for accurate measurement
            gc.collect()
            
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,
                'vms_mb': memory_info.vms / 1024 / 1024,
                'percent': process.memory_percent(),
                'gc_stats': {
                    'collections': gc.get_stats(),
                    'objects': len(gc.get_objects())
                }
            }
        except Exception as e:
            self.logger.warning(f"Failed to get memory info: {e}")
            return {}
    
    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        with self._lock:
            self.metrics.clear()
            for values in self.system_metrics.values():
                values.clear()
            
            self.cue_operations.clear()
            self.metadata_operations.clear()
            self.serato_operations.clear()
            self.ui_operations.clear()
        
        self.logger.info("Performance metrics reset")
    
    def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5.0)
        
        self.logger.info("Advanced Performance Monitor stopped")
    
    def __del__(self):
        """Cleanup on destruction."""
        self.stop_monitoring()


class OperationMeasurer:
    """Context manager for measuring operation performance."""
    
    def __init__(self, monitor: AdvancedPerformanceMonitor, 
                 operation_name: str, component: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.component = component
        self.start_time = 0.0
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        self.monitor.record_measurement(self.operation_name, duration, self.component)
