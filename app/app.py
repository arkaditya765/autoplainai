"""Main application orchestrator for AutoPlan AI.

Initializes the framework framework, registers tools, handles ChatGPT-like
conversational memory extraction, and runs queries through the LangGraph workflow.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

# Framework imports
# pyrefly: ignore [missing-import]
from framework.llm.gemini_client import GeminiClient
# pyrefly: ignore [missing-import]
from framework.context.context_manager import ContextManager
# pyrefly: ignore [missing-import]
from framework.registry.tool_registry import global_registry
# pyrefly: ignore [missing-import]
from framework.registry.registry_loader import load_tools_from_package
# pyrefly: ignore [missing-import]
from framework.workflow.graph import build_workflow
# pyrefly: ignore [missing-import]
from framework.state.state import create_initial_state

# Application imports
from app import config
# pyrefly: ignore [missing-import]
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class VehicleAdjustment(BaseModel):
    """Represents a specific demand adjustment for a single vehicle model."""
    vehicle: str = Field(..., description="The vehicle model name discussed (e.g. Brezza, Dzire, Swift).")
    demand_change_pct: float = Field(..., description="The percentage demand change discussed (e.g. -10.0 for 10% decrease, 15.0 for 15% increase).")


class QueryContextVariables(BaseModel):
    """Schema for extracting context variables from a planning query."""
    adjustments: Optional[List[VehicleAdjustment]] = Field(
        None, 
        description="List of specific vehicle model demand adjustments discussed in the query. Null if none are mentioned."
    )
    overtime_allowed: Optional[bool] = Field(
        None, 
        description="Whether overtime labor is allowed. Null if not mentioned."
    )


class AutoPlanApp:
    """AutoPlan AI Application instance wrapping the framework workflow."""

    def __init__(self) -> None:
        logger.info("Initializing AutoPlan AI Application")
        
        # 1. Initialize Gemini Client
        self.client = GeminiClient(api_key=config.GEMINI_API_KEY, default_model=config.DEFAULT_MODEL)
        
        # 2. Initialize Memory Manager
        self.context_manager = ContextManager(max_history_turns=10)
        self.context_manager.session_variables["overtime_allowed"] = True
        
        # 3. Dynamic Tool Registry Discovery
        load_tools_from_package("tools", global_registry)
        self.registry = global_registry
        
        # 4. Initialize Tool & Skill Retrievers
        from framework.registry.retriever import ToolRetriever, SkillRetriever
        self.retriever = ToolRetriever(self.client, self.registry)
        self.skill_retriever = SkillRetriever(self.client)
        
        # 5. Compile the LangGraph orchestrator
        self.graph = build_workflow(self.client, self.registry)
        
        logger.info("AutoPlan AI Application initialized successfully")

    def _extract_query_parameters(self, query: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Uses Gemini structured output to extract variables from user query and history.

        This maintains context memory between turns (acting like ChatGPT).
        """
        from framework.utils.helpers import load_prompt
        fallback_instruction = (
            "You are a parameters extractor. Read the user's latest query and the conversation history, "
            "and extract key variables. Extract any demand changes for specific vehicle models "
            "as a list under 'adjustments' (each containing 'vehicle' and 'demand_change_pct'). "
            "Only extract values that are explicitly mentioned in the query or directly referenced in the follow-up turn. "
            "Maintain consistency: if a follow-up query says 'what if overtime is allowed?', extract overtime_allowed=True, "
            "but do not override other fields unless they are being changed."
        )
        system_instruction = load_prompt("parameter_extractor.md", fallback_instruction)

        history_str = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in history[-4:]) if history else "None"
        prompt = f"History:\n{history_str}\n\nLatest Query: {query}"

        try:
            logger.info("Extracting parameters from query")
            extracted: QueryContextVariables = self.client.generate_structured(
                prompt=prompt,
                response_schema=QueryContextVariables,
                system_instruction=system_instruction,
                temperature=0.0
            )
            # Filter out None values
            extracted_dict = {k: v for k, v in extracted.model_dump().items() if v is not None}
            logger.info("Extracted parameters", extracted=extracted_dict)
            return extracted_dict
        except Exception as e:
            logger.warning("Failed to extract query parameters via LLM, falling back to empty extraction", error=str(e))
            return {}

    def run_query(self, query: str) -> Dict[str, Any]:
        """Runs the complete user request pipeline through memory and LangGraph.

        Args:
            query: The user planning request (e.g. 'Increase Brezza demand by 25%').

        Returns:
            A dictionary containing the final strategy, validation, tools run, and traces.
        """
        logger.info("Processing query in AutoPlanApp", query=query)
        
        # 1. Add user query to conversation history
        self.context_manager.add_message("user", query)

        # 2. Form initial LangGraph state
        state = create_initial_state(
            query=query,
            history=self.context_manager.get_history()
        )
        
        # Populate context variables in the state from conversational memory
        state["context"] = self.context_manager.get_variables()

        # 3. Start diagnostics timing and clear previous query's call log
        import time as _t
        _query_t0 = _t.perf_counter()
        state["diagnostics"]["query_start_time"] = datetime.now(timezone.utc).isoformat()
        self.client._call_log.clear()

        # Retrieve tools and skills (embedding API calls are now tracked)
        state["available_tools"] = self.retriever.retrieve(query, top_k=5)
        # Populate skill retriever diagnostics (retrieving semantically matching skills)
        self.skill_retriever.retrieve(query)
        
        # Invoke LangGraph orchestrator
        logger.info("Invoking LangGraph execution pipeline")
        result_state = self.graph.invoke(state)
        
        _query_dur = _t.perf_counter() - _query_t0

        # Finalize diagnostics in result state
        diag = dict(result_state.get("diagnostics", {}))
        diag["query_end_time"] = datetime.now(timezone.utc).isoformat()
        diag["total_duration_s"] = round(_query_dur, 3)

        # Copy client-level call log (generate/generate_structured/embed calls)
        # into diagnostics, separating LLM vs embedding calls
        client_llm = [c for c in self.client._call_log if c.get("type") == "llm"]
        client_embed = [c for c in self.client._call_log if c.get("type") == "embedding"]
        existing_llm = list(diag.get("llm_calls", []))
        existing_llm.extend(client_llm)
        diag["llm_calls"] = existing_llm
        diag["embedding_calls"] = client_embed

        result_state["diagnostics"] = diag

        # 4. Sync context variables and adjustments back to conversational memory manager
        self.context_manager.update_variables(result_state.get("context", {}))

        # 5. Add assistant response to memory manager
        recommendation = result_state.get("recommendation") or "No recommendation generated."
        self.context_manager.add_message("assistant", recommendation)
        
        logger.info("Query processing complete")
        return result_state

    def reset_memory(self) -> None:
        """Resets the conversational memory and variables."""
        self.context_manager.clear()
        self.context_manager.session_variables["overtime_allowed"] = True

    def reset_variables(self) -> None:
        """Resets only the conversational variables/context, keeping history."""
        self.context_manager.clear_variables()
        self.context_manager.session_variables["overtime_allowed"] = True
