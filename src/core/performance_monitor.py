"""
Performance Monitor - Real-time performance tracking and optimization
Monitors FPS, memory usage, and provides automatic optimizations
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import deque
import psutil
import os

import numpy as np


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    fps: float = 0.0
    avg_fps: float = 0.0
    min_fps: float = 0.0
    max_fps: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0
    render_time_ms: float = 0.0
    frame_drops: int = 0
    timestamp: float = field(default_factory=time.time)


class PerformanceMonitor:
    """
    Real-time performance monitoring and optimization system.
    Tracks FPS, memory usage, and provides automatic performance tuning.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Performance settings
        self.target_fps = config.get('waveform', {}).get('rendering', {}).get('target_fps', 60)
        self.memory_limit_mb = config.get('audio', {}).get('memory_limit_mb', 100)
        self.enable_monitoring = config.get('performance', {}).get('memory_monitoring', True)
        
        # Metrics storage
        self.fps_history = deque(maxlen=100)  # Last 100 FPS measurements
        self.memory_history = deque(maxlen=50)  # Last 50 memory measurements
        self.render_times = deque(maxlen=50)  # Last 50 render times
        
        # Current metrics
        self.current_metrics = PerformanceMetrics()
        
        # Performance callbacks
        self.fps_callbacks: List[Callable[[float], None]] = []
        self.memory_callbacks: List[Callable[[float], None]] = []
        self.optimization_callbacks: List[Callable[[str], None]] = []
        
        # Monitoring thread
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Frame timing
        self._last_frame_time = time.time()
        self._frame_count = 0
        
        # Process handle for system metrics
        self._process = psutil.Process(os.getpid())
        
        self.logger.info("PerformanceMonitor initialized")
    
    def start_monitoring(self) -> None:
        """Start background performance monitoring."""
        if not self.enable_monitoring:
            return
        
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="PerformanceMonitor"
        )
        self._monitoring_thread.start()
        
        self.logger.info("Performance monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background performance monitoring."""
        self._stop_monitoring.set()
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=1.0)
        
        self.logger.info("Performance monitoring stopped")
    
    def record_frame(self) -> float:
        """Record a frame for FPS calculation."""
        current_time = time.time()
        frame_time = current_time - self._last_frame_time
        
        if frame_time > 0:
            fps = 1.0 / frame_time
            self.fps_history.append(fps)
            
            # Update current metrics
            self.current_metrics.fps = fps
            if len(self.fps_history) > 0:
                self.current_metrics.avg_fps = np.mean(self.fps_history)
                self.current_metrics.min_fps = np.min(self.fps_history)
                self.current_metrics.max_fps = np.max(self.fps_history)
            
            # Check for frame drops
            if fps < self.target_fps * 0.8:  # 20% below target
                self.current_metrics.frame_drops += 1
            
            # Notify callbacks
            for callback in self.fps_callbacks:
                try:
                    callback(fps)
                except Exception as e:
                    self.logger.warning(f"FPS callback failed: {e}")
        
        self._last_frame_time = current_time
        self._frame_count += 1
        
        return self.current_metrics.fps
    
    def record_render_time(self, render_time_ms: float) -> None:
        """Record render time for performance analysis."""
        self.render_times.append(render_time_ms)
        self.current_metrics.render_time_ms = render_time_ms
        
        # Check if render time is too high
        if render_time_ms > 16.67:  # More than 60 FPS budget
            self._suggest_optimization("render_time_high")
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage."""
        try:
            memory_info = self._process.memory_info()
            memory_percent = self._process.memory_percent()
            
            usage = {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': memory_percent
            }
            
            # Update current metrics
            self.current_metrics.memory_mb = usage['rss_mb']
            self.current_metrics.memory_percent = usage['percent']
            
            # Store in history
            self.memory_history.append(usage['rss_mb'])
            
            # Check memory limit
            if usage['rss_mb'] > self.memory_limit_mb:
                self._suggest_optimization("memory_high")
            
            # Notify callbacks
            for callback in self.memory_callbacks:
                try:
                    callback(usage['rss_mb'])
                except Exception as e:
                    self.logger.warning(f"Memory callback failed: {e}")
            
            return usage
            
        except Exception as e:
            self.logger.warning(f"Failed to get memory usage: {e}")
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}
    
    def get_cpu_usage(self) -> float:
        """Get current CPU usage."""
        try:
            cpu_percent = self._process.cpu_percent()
            self.current_metrics.cpu_percent = cpu_percent
            return cpu_percent
        except Exception as e:
            self.logger.warning(f"Failed to get CPU usage: {e}")
            return 0.0
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        self.current_metrics.timestamp = time.time()
        return self.current_metrics
    
    def add_fps_callback(self, callback: Callable[[float], None]) -> None:
        """Add callback for FPS updates."""
        self.fps_callbacks.append(callback)
    
    def add_memory_callback(self, callback: Callable[[float], None]) -> None:
        """Add callback for memory updates."""
        self.memory_callbacks.append(callback)
    
    def add_optimization_callback(self, callback: Callable[[str], None]) -> None:
        """Add callback for optimization suggestions."""
        self.optimization_callbacks.append(callback)
    
    def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitoring.wait(1.0):  # Check every second
            try:
                # Update system metrics
                self.get_memory_usage()
                self.get_cpu_usage()
                
                # Check for performance issues
                self._check_performance_issues()
                
            except Exception as e:
                self.logger.warning(f"Monitoring loop error: {e}")
    
    def _check_performance_issues(self) -> None:
        """Check for performance issues and suggest optimizations."""
        # Check sustained low FPS
        if len(self.fps_history) >= 10:
            recent_fps = list(self.fps_history)[-10:]
            avg_recent_fps = np.mean(recent_fps)
            
            if avg_recent_fps < self.target_fps * 0.7:  # 30% below target
                self._suggest_optimization("sustained_low_fps")
        
        # Check memory growth
        if len(self.memory_history) >= 10:
            recent_memory = list(self.memory_history)[-10:]
            if len(recent_memory) > 1:
                memory_trend = np.polyfit(range(len(recent_memory)), recent_memory, 1)[0]
                if memory_trend > 1.0:  # Growing by more than 1MB per measurement
                    self._suggest_optimization("memory_leak")
        
        # Check high render times
        if len(self.render_times) >= 5:
            recent_render_times = list(self.render_times)[-5:]
            avg_render_time = np.mean(recent_render_times)
            
            if avg_render_time > 20.0:  # More than 50 FPS budget
                self._suggest_optimization("slow_rendering")
    
    def _suggest_optimization(self, issue_type: str) -> None:
        """Suggest optimization based on detected issue."""
        optimizations = {
            "render_time_high": "Consider reducing zoom level or enabling GPU acceleration",
            "memory_high": "Consider clearing waveform cache or reducing audio quality",
            "sustained_low_fps": "Try disabling OpenGL or reducing visual effects",
            "memory_leak": "Restart application if memory usage continues to grow",
            "slow_rendering": "Consider reducing waveform resolution or disabling RMS display"
        }
        
        suggestion = optimizations.get(issue_type, f"Performance issue detected: {issue_type}")
        
        self.logger.warning(f"Performance optimization suggested: {suggestion}")
        
        # Notify callbacks
        for callback in self.optimization_callbacks:
            try:
                callback(suggestion)
            except Exception as e:
                self.logger.warning(f"Optimization callback failed: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        metrics = self.get_current_metrics()
        
        report = {
            'current_fps': metrics.fps,
            'average_fps': metrics.avg_fps,
            'fps_range': [metrics.min_fps, metrics.max_fps],
            'memory_mb': metrics.memory_mb,
            'memory_percent': metrics.memory_percent,
            'cpu_percent': metrics.cpu_percent,
            'render_time_ms': metrics.render_time_ms,
            'frame_drops': metrics.frame_drops,
            'total_frames': self._frame_count,
            'target_fps': self.target_fps,
            'memory_limit_mb': self.memory_limit_mb,
            'performance_score': self._calculate_performance_score()
        }
        
        return report
    
    def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-100)."""
        score = 100.0
        
        # FPS score (40% weight)
        if self.current_metrics.avg_fps > 0:
            fps_ratio = min(1.0, self.current_metrics.avg_fps / self.target_fps)
            score *= 0.6 + 0.4 * fps_ratio
        
        # Memory score (30% weight)
        if self.current_metrics.memory_mb > 0:
            memory_ratio = min(1.0, self.memory_limit_mb / self.current_metrics.memory_mb)
            score *= 0.7 + 0.3 * memory_ratio
        
        # Frame drops penalty (30% weight)
        if self._frame_count > 0:
            drop_ratio = self.current_metrics.frame_drops / self._frame_count
            score *= max(0.7, 1.0 - drop_ratio)
        
        return max(0.0, min(100.0, score))
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_monitoring()
        self.fps_callbacks.clear()
        self.memory_callbacks.clear()
        self.optimization_callbacks.clear()
        
        self.logger.info("PerformanceMonitor cleanup complete")
