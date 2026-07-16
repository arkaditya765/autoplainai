"""Base agent definition for framework.

Provides the abstract BaseAgent class, establishing the interface for all agents
within the multi-agent framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from framework.llm.gemini_client import GeminiClient


class BaseAgent(ABC):
    """Abstract base class for all framework agents.

    Enforces dependency injection of the GeminiClient and standardizes the 'run'
    method signature to align with LangGraph workflow node execution.
    """

    def __init__(self, client: GeminiClient) -> None:
        """Initializes the agent.

        Args:
            client: The GeminiClient instance to use for LLM operations.
        """
        self.client = client

    @abstractmethod
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the agent's core capability on the workflow state.

        Args:
            state: The current state of the workflow graph.

        Returns:
            A dictionary containing key-value updates to apply to the shared graph state.
        """
        pass
