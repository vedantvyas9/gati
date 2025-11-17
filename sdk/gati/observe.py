"""Main Observe class - user-facing API for GATI SDK."""
import logging
import threading
import atexit
from typing import Optional, Dict, Any, List

from gati.core.config import Config
from gati.core.buffer import EventBuffer
from gati.core.client import EventClient
from gati.core.event import Event
from gati.instrumentation.detector import FrameworkDetector


class Observe:
    """Main Observe class - singleton user-facing API for GATI SDK.

    This is the primary interface that users interact with. It provides methods
    for initializing the SDK, tracking events, and managing the SDK lifecycle.

    Quick Start (LangChain 0.2+ and 1.0+) - Automatic Tracking:
        from gati import observe
        from langchain_openai import ChatOpenAI

        # Initialize - that's it! All LLM/agent calls are auto-tracked
        observe.init(name="my_agent")

        # Use LLMs normally - no callbacks parameter needed
        llm = ChatOpenAI(model="gpt-3.5-turbo")
        response = llm.invoke("What's 2+2?")  # ← Automatically tracked!

    For agents:
        from langchain.agents import AgentExecutor, create_tool_calling_agent

        agent = create_tool_calling_agent(llm, tools, prompt)
        executor = AgentExecutor(agent=agent, tools=tools)
        result = executor.invoke({"input": "Use the tools..."})  # ← Auto-tracked!

    How it works:
        - observe.init(name="...", auto_inject=True) enables automatic callback injection
        - All LangChain Runnables (LLMs, agents, chains) automatically get GATI callbacks
        - Zero code changes to your LangChain usage
        - Works with any LangChain component

    Manual mode (if auto-injection disabled):
        observe.init(name="my_agent", auto_inject=False)
        llm = ChatOpenAI(callbacks=observe.get_callbacks())
    """
    
    _instance: Optional['Observe'] = None
    _lock = threading.Lock()
    _initialized: bool = False
    
    def __new__(cls):
        """Singleton pattern - return existing instance if available."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Observe, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Observe instance (only runs once due to singleton)."""
        if Observe._initialized:
            return
        
        self._config: Optional[Config] = None
        self._buffer: Optional[EventBuffer] = None
        self._client: Optional[EventClient] = None
        self._detector: Optional[FrameworkDetector] = None
        self._instrumented_frameworks: Dict[str, bool] = {}
        self._instrumentation_status: Dict[str, Any] = {}
        self._initialized = False
        self._global_run_id: Optional[str] = None
        self._global_run_name: Optional[str] = None
        self._agent_name: Optional[str] = None
        self._run_context: Optional[Any] = None

        Observe._initialized = True
    
    def init(
        self,
        name: str,
        auto_inject: bool = True,
        **config: Any
    ) -> None:
        """Initialize the SDK with configuration.

        Args:
            name: Name of the agent/application (REQUIRED)
            auto_inject: Automatically inject GATI callbacks into LangChain Runnables
                        (default: True). When enabled, LLMs and agents automatically
                        track their execution without requiring callbacks parameter.
            **config: Additional configuration options (api_key, environment,
                     batch_size, flush_interval, telemetry, etc.)

        Note:
            The backend URL is configured via the GATI_BACKEND_URL environment variable
            or defaults to http://localhost:8000 (as configured in docker-compose).

        Raises:
            ValueError: If name is not provided or is empty
            RuntimeError: If user is not authenticated
        """
        # MANDATORY AUTHENTICATION CHECK
        from gati.cli.auth import AuthManager
        auth = AuthManager()
        if not auth.is_authenticated():
            raise RuntimeError(
                "GATI requires authentication before use. "
                "Please run 'gati auth' to authenticate with your email address."
            )
        
        # Validate required parameter
        if not name or not isinstance(name, str) or not name.strip():
            raise ValueError(
                "The 'name' parameter is required and must be a non-empty string. "
                "Usage: observe.init(name='my_agent')"
            )

        # Get or create config instance
        self._config = Config()

        # Update config with provided values
        update_kwargs: Dict[str, Any] = {}

        # Set agent_name from the required name parameter
        update_kwargs['agent_name'] = name.strip()

        # Add any additional config options
        update_kwargs.update(config)

        # Update config
        if update_kwargs:
            self._config.update(**update_kwargs)

        # Initialize client
        self._client = EventClient(
            backend_url=self._config.backend_url,
            api_key=self._config.api_key,
        )

        # Initialize buffer with flush callback
        self._buffer = EventBuffer(
            flush_callback=self._client.send_events,
            batch_size=self._config.batch_size,
            flush_interval=self._config.flush_interval,
        )

        # Initialize framework detector
        self._detector = FrameworkDetector()

        # Start buffer background thread
        self._buffer.start()

        # Create a global run context for custom decorators
        # This allows @track_tool to work without @track_agent
        from gati.core.event import generate_run_id, generate_run_name
        from gati.core.context import RunContextManager

        self._global_run_id = generate_run_id(agent_name=name.strip())
        self._global_run_name = generate_run_name(agent_name=name.strip())

        # Store in instance for access by decorators
        self._agent_name = name.strip()

        # Initialize the run context that will persist for the lifetime of the script
        self._run_context = RunContextManager.run_context(
            run_id=self._global_run_id,
            run_name=self._global_run_name,
            agent_name=name.strip()
        )
        # Enter the context
        self._run_context.__enter__()

        # Enable automatic callback injection for LangChain if requested
        if auto_inject:
            try:
                from gati.instrumentation.langchain import enable_auto_injection
                enable_auto_injection()
            except Exception as e:
                logging.getLogger("gati").debug(f"Failed to enable auto-injection: {e}")

            # Auto-instrument LangGraph if available
            try:
                from gati.instrumentation.langgraph import instrument_langgraph
                instrument_langgraph()
            except Exception as e:
                logging.getLogger("gati").debug(f"Failed to instrument LangGraph: {e}")

            # Auto-instrument Tools if available
            # Skip if LangChain is available, since LangChain callback handles tool tracking
            langchain_available = False
            try:
                import langchain_core
                langchain_available = True
            except ImportError:
                try:
                    import langchain
                    langchain_available = True
                except ImportError:
                    pass

            if not langchain_available:
                try:
                    from gati.instrumentation.tools import instrument_tools
                    instrument_tools()
                except Exception as e:
                    logging.getLogger("gati").debug(f"Failed to instrument Tools: {e}")

        # Register automatic shutdown on program exit
        # Use shutdown instead of flush to ensure thread is properly stopped
        atexit.register(self.shutdown)

        self._initialized = True
    
    def auto_instrument(self, frameworks: Optional[List[str]] = None):
        """Auto-detect and instrument frameworks.

        Special handling for LangChain 1.0+:
        - Attempts best-effort global registration.
        - If not possible, logs a clear warning with the explicit callbacks pattern.
        """
        if not self._initialized:
            raise RuntimeError("Must call init() before auto_instrument()")
        
        detector = FrameworkDetector()

        # Idempotency: if frameworks list provided, skip ones already instrumented successfully
        frameworks_to_try: Optional[List[str]] = None
        if frameworks is not None:
            frameworks_to_try = [f for f in frameworks if not self._instrumented_frameworks.get(f, False)]
        
        # Detect what's present so we can tailor messages (esp. LangChain)
        detected = detector.detect_frameworks()
        results = detector.instrument_all(frameworks_to_try)
        
        # Log results
        log = logging.getLogger("gati")
        for framework, success in results.items():
            if success:
                log.info(f"\u2713 Instrumented {framework}")
            else:
                log.warning(f"\u2717 Failed to instrument {framework}")
            # store cumulative results; once True, keep True
            if success or framework not in self._instrumented_frameworks:
                self._instrumented_frameworks[framework] = success
            # also store latest status detail
            self._instrumentation_status[framework] = {"success": bool(success)}

        # Provide a targeted guidance message for modern LangChain when auto fails
        if ("langchain" in detected) and (not results.get("langchain", False)):
            example = (
                "LangChain 1.0+ detected. Auto-instrumentation limited. Use callbacks parameter:\n"
                "from gati import observe\n"
                "from langchain_openai import ChatOpenAI\n\n"
                "observe.init(name=\"my_agent\")\n"
                "llm = ChatOpenAI(model=\"gpt-3.5-turbo\", callbacks=observe.get_callbacks())"
            )
            log.warning(example)
        
        return results

    def get_callbacks(self) -> List[Any]:
        """Return a list of active callbacks to pass into frameworks.

        Example (LangChain 1.0+):
            from gati import observe
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(model="gpt-3.5-turbo", callbacks=observe.get_callbacks())
        """
        callbacks: List[Any] = []
        # LangChain callbacks
        try:
            from gati.instrumentation.langchain import get_gati_callbacks  # type: ignore

            callbacks.extend(list(get_gati_callbacks()))
        except Exception:
            pass

        # Future: add other frameworks' callbacks here
        return callbacks
    
    def track_event(self, event: Event) -> None:
        """Manually track an event.

        Args:
            event: Event object to track
        """
        if not self._initialized:
            raise RuntimeError("Observe not initialized. Call init() first.")

        if self._buffer is None:
            raise RuntimeError("Event buffer not initialized.")

        # Set run_name from context if not already set
        from gati.core.context import get_current_run_name
        current_run_name = get_current_run_name()

        if not event.run_name and current_run_name:
            event.run_name = current_run_name

        # Set agent_name from config if not already set
        if not event.agent_name and self._config:
            event.agent_name = self._config.agent_name

        # Add event to buffer
        try:
            self._buffer.add_event(event)
            # Debug logging
            logger = logging.getLogger("gati")
            event_desc = f"{event.event_type}"
            if hasattr(event, 'data') and isinstance(event.data, dict):
                node_name = event.data.get('node_name')
                if node_name:
                    event_desc += f" ({node_name})"
            logger.debug(f"Event tracked: {event_desc} [event_id={event.event_id[:8]}...] (buffer size: {len(self._buffer)})")
        except Exception as e:
            logger = logging.getLogger("gati")
            logger.error(f"Failed to track event: {e}", exc_info=True)
            raise
    
    def flush(self) -> None:
        """Force flush buffered events to the backend.

        Immediately sends all buffered events to the backend and waits for
        all pending send operations to complete. This ensures that all events
        are delivered before the function returns.
        """
        if not self._initialized:
            raise RuntimeError("Observe not initialized. Call init() first.")

        if self._buffer is None:
            raise RuntimeError("Event buffer not initialized.")

        # Flush the buffer (triggers send)
        self._buffer.flush()

        # Wait for all background send threads to complete
        # Use a reasonable timeout to avoid hanging indefinitely
        if self._client:
            self._client.wait_for_pending_sends(timeout=30.0)
    
    def shutdown(self) -> None:
        """Clean shutdown of the SDK.

        Stops the background buffer thread, flushes remaining events, and
        closes the HTTP client session.
        """
        if not self._initialized:
            return

        try:
            # Stop buffer (this will also flush remaining events)
            if self._buffer:
                # Wait up to 10 seconds for thread to stop and all events to flush
                self._buffer.stop(timeout=10.0)

                # Ensure any stragglers are flushed
                if len(self._buffer) > 0:
                    self._buffer.flush()

            # Wait for all pending sends to complete
            if self._client:
                self._client.wait_for_pending_sends(timeout=10.0)
        except Exception as e:
            logging.getLogger("gati").debug(f"Error stopping buffer: {e}")

        try:
            # Close client session
            if self._client:
                self._client.close()
        except Exception as e:
            logging.getLogger("gati").debug(f"Error closing client: {e}")

        # Reset state
        self._buffer = None
        self._client = None
        self._detector = None
        self._initialized = False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - shutdown on exit."""
        self.shutdown()
    
    def __repr__(self) -> str:
        """String representation of Observe instance."""
        status = "initialized" if self._initialized else "not initialized"
        return f"Observe({status})"


# Global singleton instance for easy access
observe = Observe()

