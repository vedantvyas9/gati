"""Context manager for tracking execution context."""
import contextvars
import uuid
from typing import Optional, List
from contextlib import contextmanager, asynccontextmanager

from gati.core.event import generate_run_id, generate_run_name


class RunContext:
    """Represents a single run context with parent-child relationships."""

    def __init__(self, run_id: str, run_name: str, parent_id: Optional[str] = None, parent_name: Optional[str] = None, parent_event_id: Optional[str] = None):
        """Initialize a run context.

        Args:
            run_id: Unique ID for this run (UUID)
            run_name: Name for this run (e.g., 'run 1', 'run 2')
            parent_id: Optional parent run ID for nested contexts
            parent_name: Optional parent run name for nested contexts
            parent_event_id: Optional parent event ID for event hierarchy
        """
        self.run_id = run_id
        self.run_name = run_name
        self.parent_id = parent_id
        self.parent_name = parent_name
        self.parent_event_id = parent_event_id
        self.depth = 0
        if parent_name:
            # Depth will be set by the context manager
            self.depth = 1

    def __repr__(self) -> str:
        """String representation of run context."""
        return f"RunContext(run_id='{self.run_id}', run_name='{self.run_name}', parent_id='{self.parent_id}', parent_name='{self.parent_name}', parent_event_id='{self.parent_event_id}', depth={self.depth})"


# Context variable for storing the run context stack
# Uses None as default and initializes to empty list on first access
_RUN_CONTEXT_STACK: contextvars.ContextVar[Optional[List[RunContext]]] = contextvars.ContextVar(
    'gati_run_stack', default=None
)


class RunContextManager:
    """Context manager for tracking execution context with task-local storage.

    Supports nested contexts (parent-child relationships) and tracks execution
    stack for distributed tracing. Each async task and thread maintains its own
    context stack via contextvars.
    """

    @classmethod
    def _get_stack(cls) -> List[RunContext]:
        """Get the context stack for the current execution context.

        Returns:
            List of RunContext objects representing the execution stack
        """
        stack = _RUN_CONTEXT_STACK.get()
        if stack is None:
            stack = []
            _RUN_CONTEXT_STACK.set(stack)
        return stack
    
    @classmethod
    def get_current_run_id(cls) -> Optional[str]:
        """Get the current run ID from the context stack.

        Returns:
            Current run ID if available, None otherwise
        """
        stack = cls._get_stack()
        if stack:
            return stack[-1].run_id
        return None

    @classmethod
    def get_current_run_name(cls) -> Optional[str]:
        """Get the current run name from the context stack.

        Returns:
            Current run name if available, None otherwise
        """
        stack = cls._get_stack()
        if stack:
            return stack[-1].run_name
        return None

    @classmethod
    def set_run_name(cls, run_name: str) -> None:
        """Set the current run name (replaces top of stack).

        Args:
            run_name: Run name to set as current
        """
        stack = cls._get_stack()
        if stack:
            # Replace the top of the stack - keep existing run_id
            current_run_id = stack[-1].run_id
            parent_id = stack[-1].parent_id
            parent_name = stack[-1].parent_name if len(stack) > 1 else None
            depth = len(stack) - 1
            stack[-1] = RunContext(current_run_id, run_name, parent_id, parent_name)
            stack[-1].depth = depth
        else:
            # Create new context at root level
            run_id = generate_run_id()
            stack.append(RunContext(run_id, run_name, None, None))

    @classmethod
    def create_child_run(cls, run_name: Optional[str] = None, agent_name: str = "") -> str:
        """Create a child run context.

        Generates a run_name for a child context (with current context as parent).
        The context is not automatically entered - use run_context() to enter it.

        Args:
            run_name: Optional run name for the child (auto-generated if not provided)
            agent_name: Name of the agent (for run name generation)

        Returns:
            The run name (generated or provided)
        """
        if run_name is None:
            run_name = generate_run_name(agent_name)

        # The parent relationship will be established when the context is entered
        # via run_context(). This method just generates/prepares the run_name.
        return run_name
    
    @classmethod
    def get_execution_stack(cls) -> List[RunContext]:
        """Get the full execution stack for distributed tracing.
        
        Returns:
            List of RunContext objects representing the complete execution stack
        """
        return cls._get_stack().copy()
    
    @classmethod
    def get_parent_run_name(cls) -> Optional[str]:
        """Get the parent run name of the current context.

        Returns:
            Parent run name if available, None otherwise
        """
        stack = cls._get_stack()
        if stack:
            return stack[-1].parent_name
        return None

    @classmethod
    def get_parent_event_id(cls) -> Optional[str]:
        """Get the parent event ID from the current context.

        Returns:
            Parent event ID if available, None otherwise
        """
        stack = cls._get_stack()
        if stack:
            return stack[-1].parent_event_id
        return None

    @classmethod
    def set_parent_event_id(cls, event_id: str) -> None:
        """Set the parent event ID in the current context.

        Args:
            event_id: Event ID to set as parent for subsequent events
        """
        stack = cls._get_stack()
        if stack:
            stack[-1].parent_event_id = event_id
    
    @classmethod
    @contextmanager
    def run_context(cls, run_name: Optional[str] = None, run_id: Optional[str] = None, parent_name: Optional[str] = None, agent_name: str = ""):
        """Context manager for entering a run context.

        This context manager is task-safe and works correctly with both sync
        and async code. Each task gets its own isolated context stack.

        Args:
            run_name: Optional run name (auto-generated if not provided)
            run_id: Optional run ID (auto-generated if not provided)
            parent_name: Optional parent run name (uses current context if not provided)
            agent_name: Name of the agent (for run name generation)

        Yields:
            The run ID for this context
        """
        # Generate run_id if not provided
        if run_id is None:
            run_id = generate_run_id(agent_name)

        # Generate run_name if not provided
        if run_name is None:
            run_name = generate_run_name(agent_name)

        # Get parent from current context if not provided
        if parent_name is None:
            parent_name = cls.get_current_run_name()

        parent_id = cls.get_current_run_id() if parent_name else None

        # Create context
        context = RunContext(run_id, run_name, parent_id, parent_name)
        current_stack = cls._get_stack()
        context.depth = len(current_stack)

        # Create new stack with the new context appended
        # This creates isolation for concurrent tasks
        new_stack = current_stack + [context]
        token = _RUN_CONTEXT_STACK.set(new_stack)

        try:
            yield run_id
        finally:
            # Restore the previous stack using the token
            _RUN_CONTEXT_STACK.reset(token)
    
    @classmethod
    @asynccontextmanager
    async def arun_context(cls, run_name: Optional[str] = None, run_id: Optional[str] = None, parent_name: Optional[str] = None, agent_name: str = ""):
        """Async context manager for entering a run context.

        This is the async-equivalent of run_context() and should be used in async functions.
        It provides the same task-safe isolation as run_context() for async code.

        Args:
            run_name: Optional run name (auto-generated if not provided)
            run_id: Optional run ID (auto-generated if not provided)
            parent_name: Optional parent run name (uses current context if not provided)
            agent_name: Name of the agent (for run name generation)

        Yields:
            The run ID for this context
        """
        # Generate run_id if not provided
        if run_id is None:
            run_id = generate_run_id(agent_name)

        # Generate run_name if not provided
        if run_name is None:
            run_name = generate_run_name(agent_name)

        # Get parent from current context if not provided
        if parent_name is None:
            parent_name = cls.get_current_run_name()

        parent_id = cls.get_current_run_id() if parent_name else None

        # Create context
        context = RunContext(run_id, run_name, parent_id, parent_name)
        current_stack = cls._get_stack()
        context.depth = len(current_stack)

        # Create new stack with the new context appended
        # This creates isolation for concurrent tasks
        new_stack = current_stack + [context]
        token = _RUN_CONTEXT_STACK.set(new_stack)

        try:
            yield run_id
        finally:
            # Restore the previous stack using the token
            _RUN_CONTEXT_STACK.reset(token)

    @classmethod
    def clear_context(cls) -> None:
        """Clear the context stack for the current execution context.

        Useful for testing or cleanup. Clears the context for the current
        async task or thread.
        """
        _RUN_CONTEXT_STACK.set([])

    @classmethod
    def get_depth(cls) -> int:
        """Get the depth of the current context stack.

        Returns:
            Depth of the context stack (0 for root level)
        """
        return len(cls._get_stack())


# Convenience functions for easier access
def get_current_run_id() -> Optional[str]:
    """Get the current run ID.

    Returns:
        Current run ID if available, None otherwise
    """
    return RunContextManager.get_current_run_id()


def get_current_run_name() -> Optional[str]:
    """Get the current run name.

    Returns:
        Current run name if available, None otherwise
    """
    return RunContextManager.get_current_run_name()


def set_run_name(run_name: str) -> None:
    """Set the current run name.

    Args:
        run_name: Run name to set as current
    """
    RunContextManager.set_run_name(run_name)


def create_child_run(run_name: Optional[str] = None, agent_name: str = "") -> str:
    """Create a child run context.

    Args:
        run_name: Optional run name for the child (auto-generated if not provided)
        agent_name: Name of the agent (for run name generation)

    Returns:
        The run name (generated or provided)
    """
    return RunContextManager.create_child_run(run_name, agent_name)


def run_context(run_name: Optional[str] = None, parent_name: Optional[str] = None, agent_name: str = ""):
    """Context manager for entering a run context.

    Args:
        run_name: Optional run name (auto-generated if not provided)
        parent_name: Optional parent run name (uses current context if not provided)
        agent_name: Name of the agent (for run name generation)

    Yields:
        The run name for this context

    Example:
        >>> with run_context() as run_name:
        ...     # Code executed within this run context
        ...     pass
    """
    return RunContextManager.run_context(run_name, parent_name, agent_name)


@asynccontextmanager
async def arun_context(run_name: Optional[str] = None, parent_name: Optional[str] = None, agent_name: str = ""):
    """Async context manager for entering a run context.

    This is the async-equivalent of run_context() and should be used in async functions.

    Args:
        run_name: Optional run name (auto-generated if not provided)
        parent_name: Optional parent run name (uses current context if not provided)
        agent_name: Name of the agent (for run name generation)

    Yields:
        The run name for this context

    Example:
        >>> async with arun_context() as run_name:
        ...     # Code executed within this run context
        ...     pass
    """
    async with RunContextManager.arun_context(run_name, parent_name, agent_name) as run_name:
        yield run_name


def get_parent_event_id() -> Optional[str]:
    """Get the parent event ID from the current context.

    Returns:
        Parent event ID if available, None otherwise
    """
    return RunContextManager.get_parent_event_id()


def set_parent_event_id(event_id: str) -> None:
    """Set the parent event ID in the current context.

    Args:
        event_id: Event ID to set as parent for subsequent events
    """
    RunContextManager.set_parent_event_id(event_id)

