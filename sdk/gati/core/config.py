"""Configuration management for GATI SDK."""
import os
from typing import Optional


class Config:
    """Configuration class for GATI SDK settings.
    
    Manages SDK configuration with support for environment variable overrides.
    Uses singleton pattern to ensure consistent configuration across the SDK.
    """
    
    _instance: Optional['Config'] = None
    _initialized: bool = False
    
    def __new__(cls):
        """Singleton pattern - return existing instance if available."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize configuration with defaults and environment variables."""
        if Config._initialized:
            return
        
        # Required settings
        self.api_key: Optional[str] = os.getenv("GATI_API_KEY")
        self.agent_name: str = os.getenv("GATI_AGENT_NAME", "default_agent")
        self.environment: str = os.getenv("GATI_ENVIRONMENT", "development")
        self.backend_url: str = os.getenv("GATI_BACKEND_URL", "http://localhost:8000")
        
        # Optional settings with defaults
        self.batch_size: int = int(os.getenv("GATI_BATCH_SIZE", "100"))
        self.flush_interval: float = float(os.getenv("GATI_FLUSH_INTERVAL", "5.0"))
        self.telemetry: bool = os.getenv("GATI_TELEMETRY", "true").lower() in ("true", "1", "yes")
        
        # Validate configuration
        self._validate()
        
        Config._initialized = True
    
    def _validate(self) -> None:
        """Validate configuration values."""
        if not self.agent_name or not isinstance(self.agent_name, str):
            raise ValueError("agent_name must be a non-empty string")
        
        if not self.environment or not isinstance(self.environment, str):
            raise ValueError("environment must be a non-empty string")
        
        if not self.backend_url or not isinstance(self.backend_url, str):
            raise ValueError("backend_url must be a non-empty string")
        
        # Validate URL format (basic check)
        if not (self.backend_url.startswith("http://") or self.backend_url.startswith("https://")):
            raise ValueError("backend_url must start with http:// or https://")
        
        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        
        if self.flush_interval <= 0:
            raise ValueError("flush_interval must be greater than 0")
    
    def update(
        self,
        api_key: Optional[str] = None,
        agent_name: Optional[str] = None,
        environment: Optional[str] = None,
        backend_url: Optional[str] = None,
        batch_size: Optional[int] = None,
        flush_interval: Optional[float] = None,
        telemetry: Optional[bool] = None,
    ) -> None:
        """Update configuration values.
        
        Args:
            api_key: Optional API key for authentication
            agent_name: Name of the agent
            environment: Environment name (development, production, etc.)
            backend_url: Backend server URL
            batch_size: Number of events to batch before sending
            flush_interval: Time in seconds between automatic flushes
            telemetry: Whether to enable telemetry
        """
        if api_key is not None:
            self.api_key = api_key
        if agent_name is not None:
            self.agent_name = agent_name
        if environment is not None:
            self.environment = environment
        if backend_url is not None:
            self.backend_url = backend_url
        if batch_size is not None:
            self.batch_size = batch_size
        if flush_interval is not None:
            self.flush_interval = flush_interval
        if telemetry is not None:
            self.telemetry = telemetry
        
        # Re-validate after update
        self._validate()
    
    def reset(self) -> None:
        """Reset configuration to defaults."""
        Config._initialized = False
        Config._instance = None
        self.__init__()
    
    def __repr__(self) -> str:
        """String representation of configuration."""
        return (
            f"Config(agent_name='{self.agent_name}', "
            f"environment='{self.environment}', "
            f"backend_url='{self.backend_url}', "
            f"batch_size={self.batch_size}, "
            f"flush_interval={self.flush_interval}, "
            f"telemetry={self.telemetry})"
        )


# Global config instance for easy access
config = Config()

