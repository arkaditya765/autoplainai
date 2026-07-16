"""Tool Registry and BaseTool definitions for framework.

Provides the abstract base class for tools and a centralized registry
to support dynamic tool discovery and access.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type, Union
from framework.utils.logger import get_logger
from framework.utils.exceptions import ToolNotFoundError, ToolRegistrationError

logger = get_logger(__name__)


class BaseTool(ABC):
    """Abstract base class for all tools in the framework ecosystem.

    Every tool must implement a single atomic capability, return structured JSON
    data, and avoid calling the LLM or performing advanced reasoning.
    """

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: str = "general"
    tags: List[str] = []

    def __init__(self) -> None:
        if not self.name or not self.description:
            raise ToolRegistrationError(
                f"Tool class {self.__class__.__name__} must define non-empty 'name' and 'description' class attributes."
            )

    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the tool's core logic.

        Args:
            state: The active workflow state dictionary.

        Returns:
            A dictionary containing structured JSON output data.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Returns metadata about the tool to assist the Planner Agent in tool selection."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "tags": self.tags,
        }


class ToolRegistry:
    """Centralized registry keeping track of all available tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: Union[BaseTool, Type[BaseTool]]) -> None:
        """Registers a tool instance or class.

        Args:
            tool: An instance of BaseTool or a subclass type of BaseTool.
        """
        # If it's a class type, instantiate it
        if isinstance(tool, type) and issubclass(tool, BaseTool):
            try:
                tool_instance = tool()
            except Exception as e:
                raise ToolRegistrationError(f"Failed to instantiate tool class '{tool.__name__}': {e}") from e
        elif isinstance(tool, BaseTool):
            tool_instance = tool
        else:
            raise ToolRegistrationError("Registered object must be a subclass or instance of BaseTool.")

        name = tool_instance.name
        if name in self._tools:
            logger.warning("Overwriting existing tool registration", tool_name=name)

        self._tools[name] = tool_instance
        logger.info("Successfully registered tool", tool_name=name, version=tool_instance.version)

    def get_tool(self, name: str) -> BaseTool:
        """Retrieves a tool by name.

        Args:
            name: The registered tool's unique identifier.

        Raises:
            ToolNotFoundError: If no tool is registered under this name.
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self) -> List[BaseTool]:
        """Lists all registered tool instances."""
        return list(self._tools.values())

    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """Returns metadata for all registered tools, useful for LLM planning."""
        return [tool.get_metadata() for tool in self._tools.values()]

    def clear(self) -> None:
        """Clears all registered tools."""
        self._tools.clear()
        logger.info("Cleared all registered tools.")


# Singleton registry instance for global framework-wide use
global_registry = ToolRegistry()
