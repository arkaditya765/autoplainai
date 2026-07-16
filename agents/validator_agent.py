"""Validator Agent implementation for framework.

Audits generated strategies against active context rules and constraints, returning
a structured validation status (PASSED/FAILED) with feedback.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from framework.llm.prompts import VALIDATOR_SYSTEM_INSTRUCTION, VALIDATOR_PROMPT_TEMPLATE
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationResult(BaseModel):
    """Pydantic model representing the output of the Validator Agent."""
    status: str = Field(
        ..., 
        description="The validation status. MUST be either 'PASSED' (no constraint violations) or 'FAILED' (contains violations)."
    )
    feedback: str = Field(
        ..., 
        description="Detailed feedback describing why the validation passed or failed."
    )
    violations: List[str] = Field(
        default_factory=list,
        description="List of specific business constraints or safety violations found. Empty if status is PASSED."
    )


class ValidatorAgent(BaseAgent):
    """Validator Agent that acts as a quality assurance gate for strategies."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the validator agent.

        Args:
            state: The current AgentState dictionary.

        Returns:
            A dictionary updating 'validation' and 'execution_trace'.
        """
        query = state.get("query", "")
        context_vars = state.get("context", {})
        recommendation = state.get("recommendation", "")

        logger.info("Validator Agent running validation checks")

        # Format context variables for the prompt
        context_str = "\n".join(f"  - {k}: {v}" for k, v in context_vars.items()) if context_vars else "No active context variables."

        # Load active guardrails from root guardrails directory dynamically
        import os
        from pathlib import Path
        workspace_root = None
        for parent in Path(__file__).resolve().parents:
            if (parent / "guardrails").exists():
                workspace_root = parent
                break
        if not workspace_root:
            workspace_root = Path(os.getcwd())

        guardrails_dir = workspace_root / "guardrails"
        guardrails_content = ""
        try:
            if guardrails_dir.exists():
                for filepath in guardrails_dir.glob("*.md"):
                    with open(filepath, "r", encoding="utf-8") as f:
                        guardrails_content += f"\n--- {filepath.name} ---\n"
                        guardrails_content += f.read() + "\n"
        except Exception as e:
            logger.warning("Failed to load guardrail files in ValidatorAgent", error=str(e))

        # Interpolate variables into instructions and templates
        system_instruction = VALIDATOR_SYSTEM_INSTRUCTION.format(
            context_variables=context_str,
            recommendation=recommendation or "No recommendation generated."
        )
        if guardrails_content:
            system_instruction += f"\n\nActive System Guardrails (You MUST enforce these safety and business rules strictly):\n{guardrails_content}"

        route_decision = state.get("route_decision", "planning")
        if route_decision == "general":
            system_instruction += (
                "\n\nIMPORTANT CONTEXT: The user's query is classified as a general/chatbot query. "
                "Because of this, you MUST ignore the 'Out-of-Domain Topic Control' safety guardrail. "
                "Topics like general search, public news, weather, or market reports are fully permitted. "
                "Simply validate the professionalism of tone, lack of slang, and that no internal data paths "
                "or credentials are leaked."
            )

        prompt = VALIDATOR_PROMPT_TEMPLATE.format(query=query)

        # Execute structured LLM check
        logger.debug("Requesting Gemini to audit strategy recommendation")
        validation: ValidationResult = self.client.generate_structured(
            prompt=prompt,
            response_schema=ValidationResult,
            system_instruction=system_instruction,
            temperature=0.0  # Zero temperature for deterministic auditing
        )

        logger.info("Validator Agent completed audit", status=validation.status, num_violations=len(validation.violations))

        # Log trace step
        trace_step = {
            "node": "validator",
            "action": f"Validation complete. Status: {validation.status}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "status": validation.status,
                "feedback": validation.feedback,
                "violations": validation.violations
            }
        }

        updated_trace = list(state.get("execution_trace", []))
        updated_trace.append(trace_step)

        return {
            "validation": {
                "status": validation.status,
                "feedback": validation.feedback,
                "violations": validation.violations
            },
            "execution_trace": updated_trace
        }
