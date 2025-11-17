"""Framework detector for automatic instrumentation."""
import logging
import sys
from typing import List, Optional, Dict


class FrameworkDetector:
    """Detects available AI frameworks and applies instrumentation.
    
    Automatically detects frameworks like LangChain and LangGraph,
    and applies instrumentation hooks to track events.
    """
    
    def __init__(self) -> None:
        self._log = logging.getLogger("gati")

    def detect_frameworks(self) -> List[str]:
        """Detect available frameworks by inspecting loaded modules.
        
        Returns a list like ["langchain", "langgraph"].
        """
        detected: List[str] = []
        try:
            if "langchain" in sys.modules:
                detected.append("langchain")
        except Exception:
            # Be conservative – never raise
            pass
        try:
            if "langgraph" in sys.modules:
                detected.append("langgraph")
        except Exception:
            pass

        if hasattr(self._log, "info"):
            self._log.info(f"Detected frameworks: {detected}")
        return detected

    def instrument_all(self, frameworks: Optional[List[str]] = None) -> Dict[str, bool]:
        """Instrument all specified or detected frameworks.
        
        Args:
            frameworks: Optional list of framework names to instrument. If None,
                        auto-detects via `detect_frameworks()`.
        Returns:
            Dict mapping framework name to success boolean.
        
        Raises:
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
        
        to_instrument = frameworks if frameworks is not None else self.detect_frameworks()
        results: Dict[str, bool] = {}

        for fw in to_instrument:
            if fw == "langchain":
                success = False
                try:
                    # Import within try so missing deps never crash user code
                    from gati.instrumentation import langchain as gati_langchain  # type: ignore

                    success = bool(getattr(gati_langchain, "instrument_langchain", lambda: False)())
                    if success and hasattr(self._log, "info"):
                        self._log.info("Successfully instrumented: langchain")
                    if not success and hasattr(self._log, "warning"):
                        self._log.warning("Failed to instrument: langchain (unknown error)")
                except Exception:
                    if hasattr(self._log, "warning"):
                        self._log.warning("Failed to instrument: langchain (module not found)")
                    success = False
                results["langchain"] = success
                continue

            if fw == "langgraph":
                success = False
                try:
                    # Stub for now – may not exist yet
                    from gati.instrumentation import langgraph as gati_langgraph  # type: ignore

                    instrument = getattr(gati_langgraph, "instrument_langgraph", None)
                    if callable(instrument):
                        success = bool(instrument())
                    else:
                        success = False
                    if success and hasattr(self._log, "info"):
                        self._log.info("Successfully instrumented: langgraph")
                    if not success and hasattr(self._log, "warning"):
                        self._log.warning("Failed to instrument: langgraph (stub or unknown error)")
                except Exception:
                    if hasattr(self._log, "warning"):
                        self._log.warning("Failed to instrument: langgraph (module not found)")
                    success = False
                results["langgraph"] = success
                continue

            # Unknown framework – mark as failed but continue
            results[fw] = False
            if hasattr(self._log, "warning"):
                self._log.warning(f"Failed to instrument: {fw} (unknown framework)")

        return results
