"""Context and Session Memory Manager for framework.

Provides mechanisms to retain conversation history, merge and track
context variables across execution turns, and format variables for LLM consumption.
"""

import copy
from typing import Any, Dict, List
from framework.utils.logger import get_logger
from framework.utils.exceptions import ContextError

logger = get_logger(__name__)


class ContextManager:
    """Manages multi-turn conversation memory and contextual variables.

    Allows variables (e.g. vehicle model, percentage changes) to be
    extracted/stored and automatically fed into downstream agent prompts.
    """

    def __init__(self, max_history_turns: int = 10) -> None:
        """Initializes the ContextManager.

        Args:
            max_history_turns: Maximum number of conversation turns to persist in active memory.
        """
        self.max_history_turns = max_history_turns
        # Session state stores key-value variables across turns (e.g., {"vehicle": "Brezza"})
        self.session_variables: Dict[str, Any] = {}
        # Stores complete message history: [{"role": "user"/"assistant", "content": "..."}]
        self.history: List[Dict[str, Any]] = []

    def add_message(self, role: str, content: str) -> None:
        """Adds a message to the conversation history.

        Args:
            role: The role of the speaker ('user' or 'assistant').
            content: The raw text of the message.
        """
        if role not in ("user", "assistant"):
            raise ContextError(f"Invalid message role '{role}'. Must be 'user' or 'assistant'.")

        self.history.append({"role": role, "content": content})

        # Cap history to keep memory footprint bounded
        if len(self.history) > self.max_history_turns * 2:
            self.history = self.history[-(self.max_history_turns * 2):]
            logger.debug("Truncated conversation history to maintain max turns limits", max_turns=self.max_history_turns)

    def update_variables(self, variables: Dict[str, Any]) -> None:
        """Merges new parameters/variables into the current session context.

        Args:
            variables: Key-value dict of context parameters.
        """
        for key, value in variables.items():
            if value is not None:
                self.session_variables[key] = value
                logger.debug("Updated context variable", key=key, value=value)

    def get_variables(self) -> Dict[str, Any]:
        """Returns a copy of the active session context variables."""
        return copy.deepcopy(self.session_variables)

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns the conversation history."""
        return copy.deepcopy(self.history)

    def clear(self) -> None:
        """Clears all session variables and conversation history."""
        self.session_variables.clear()
        self.history.clear()
        logger.info("Cleared conversation context and memory.")

    def clear_variables(self) -> None:
        """Clears only session variables, leaving message history intact."""
        self.session_variables.clear()
        logger.info("Cleared session variables.")

    def format_context_for_llm(self) -> str:
        """Formats the active context variables into a structured string for prompt insertion.

        Returns:
            A clean formatted string representing active session variables.
        """
        if not self.session_variables:
            return "No active session context variables."

        lines = ["Active Session Context Variables:"]
        for key, val in self.session_variables.items():
            lines.append(f"  - {key}: {val}")
        return "\n".join(lines)
