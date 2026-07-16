"""Custom exceptions for the framework framework.

This module defines a clean hierarchy of exceptions to allow components
(agents, tools, executors, workflows) to raise typed errors that can
be handled gracefully by the orchestrator or application layer.
"""

from typing import Any, Optional


class frameworkError(Exception):
    """Base exception class for all framework-related errors."""

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


# Registry Errors
class RegistryError(frameworkError):
    """Base exception for all tool registry operations."""


class ToolNotFoundError(RegistryError):
    """Raised when a requested tool cannot be found in the registry."""


class ToolRegistrationError(RegistryError):
    """Raised when a tool fails to register properly due to invalid schema, duplicate names, etc."""


# Execution Errors
class ToolExecutionError(frameworkError):
    """Raised when execution of a specific tool fails or throws an exception."""

    def __init__(self, tool_name: str, message: str, original_exception: Optional[Exception] = None) -> None:
        details = {"tool_name": tool_name, "original_exception": str(original_exception)} if original_exception else {"tool_name": tool_name}
        super().__init__(f"Error executing tool '{tool_name}': {message}", details=details)
        self.tool_name = tool_name
        self.original_exception = original_exception


# LLM Errors
class LLMError(frameworkError):
    """Base exception for LLM operations."""


class LLMResponseError(LLMError):
    """Raised when the LLM response is malformed, missing, or fails to parse against a requested schema."""


# Workflow Errors
class WorkflowError(frameworkError):
    """Base exception for workflow state, execution, and graph routing errors."""


class ContextError(frameworkError):
    """Raised when memory operations, session management, or history context aggregation fails."""
