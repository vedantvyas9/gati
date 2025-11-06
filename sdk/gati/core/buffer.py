"""Event buffer for batching events before sending."""
import threading
import time
from typing import List, Callable, Optional
from datetime import datetime

from gati.core.event import Event
from gati.core.config import config


class EventBuffer:
    """Thread-safe event buffer that batches events before sending.
    
    Automatically flushes events when batch_size is reached or flush_interval
    has elapsed. Uses a background thread for interval-based flushing.
    """
    
    def __init__(
        self,
        flush_callback: Callable[[List[Event]], None],
        batch_size: Optional[int] = None,
        flush_interval: Optional[float] = None,
    ):
        """Initialize event buffer.
        
        Args:
            flush_callback: Function to call with flushed events
            batch_size: Maximum number of events before auto-flush (default from config)
            flush_interval: Time in seconds between automatic flushes (default from config)
        """
        self.flush_callback = flush_callback
        self.batch_size = batch_size or config.batch_size
        self.flush_interval = flush_interval or config.flush_interval
        
        # Thread-safe event storage
        self._events: List[Event] = []
        self._lock = threading.Lock()
        
        # Background thread management
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        # Track last flush time
        self._last_flush_time = time.time()
    
    def add_event(self, event: Event) -> None:
        """Add an event to the buffer.
        
        Args:
            event: Event to add to the buffer
        """
        if not isinstance(event, Event):
            raise ValueError("event must be an instance of Event")
        
        with self._lock:
            self._events.append(event)
            
            # Check if we should flush due to batch size
            if len(self._events) >= self.batch_size:
                self._flush_locked()
    
    def flush(self) -> None:
        """Manually flush all events in the buffer."""
        with self._lock:
            self._flush_locked()
    
    def _flush_locked(self) -> None:
        """Flush events (must be called with lock held).
        
        Creates a copy of events and clears the buffer, then calls the callback.
        """
        if not self._events:
            return
        
        # Copy events and clear buffer
        events_to_send = self._events.copy()
        self._events.clear()
        self._last_flush_time = time.time()
        
        # Release lock before calling callback to avoid blocking
        # The callback might take time (e.g., HTTP request)
        try:
            self.flush_callback(events_to_send)
        except Exception as e:
            # Log error but don't crash - we've already removed events from buffer
            # In a production system, you might want to re-add events to a retry queue
            print(f"Error in flush callback: {e}")
    
    def _flush_worker(self) -> None:
        """Background worker thread that flushes on interval."""
        while not self._stop_event.is_set():
            # Wait for flush_interval or until stop event is set
            if self._stop_event.wait(timeout=self.flush_interval):
                # Stop event was set, break loop
                break
            
            # Check if we should flush
            with self._lock:
                time_since_flush = time.time() - self._last_flush_time
                if time_since_flush >= self.flush_interval and self._events:
                    self._flush_locked()
    
    def start(self) -> None:
        """Start the background flush thread."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._flush_worker, daemon=True)
        self._thread.start()
    
    def stop(self, timeout: Optional[float] = None) -> None:
        """Stop the background flush thread and flush remaining events.
        
        Args:
            timeout: Maximum time to wait for thread to stop (default: None)
        """
        if not self._running:
            return
        
        self._running = False
        
        # Signal thread to stop
        self._stop_event.set()
        
        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        
        # Flush any remaining events
        self.flush()
    
    def __len__(self) -> int:
        """Get current number of events in buffer."""
        with self._lock:
            return len(self._events)
    
    def __enter__(self):
        """Context manager entry - start the buffer."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop and flush the buffer."""
        self.stop()






