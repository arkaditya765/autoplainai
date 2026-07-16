"""FastAPI route handlers for AutoPlan AI.

Exposes endpoints for querying the agent graph, checking system status, 
and resetting conversational memory.
"""

from fastapi import APIRouter, HTTPException, Depends, FastAPI
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import uvicorn

from app.app import AutoPlanApp
from app import config
from framework.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Instantiate global application runner (singleton for the server instance)
app_runner = AutoPlanApp()

# Compile the FastAPI application
app = FastAPI(
    title="AutoPlan AI - Decision Support API",
    description="Enterprise REST API for multi-agent manufacturing decision planning",
    version="1.0.0"
)
app.include_router(router, prefix="/api")


class PlanRequest(BaseModel):
    """Schema for planning request inputs."""
    query: str = Field(..., description="The user query to run (e.g. 'What if we increase Swift demand by 10%?')")


class ResetResponse(BaseModel):
    """Schema for memory reset confirmations."""
    status: str = Field("success")
    message: str = Field("Conversational context and memory cleared.")


@router.post("/plan", response_model=Dict[str, Any])
def execute_planning_flow(request: PlanRequest) -> Dict[str, Any]:
    """Triggers the Multi-Agent planning flow for a user request."""
    logger.info("Received plan API request", query=request.query)
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        result = app_runner.run_query(request.query)
        return result
    except Exception as e:
        logger.error("API error during workflow execution", error=str(e))
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred executing the workflow: {str(e)}"
        )


@router.post("/reset", response_model=ResetResponse)
def reset_conversation_history() -> ResetResponse:
    """Clears conversation context and resets parameters to defaults."""
    logger.info("Received memory reset API request")
    try:
        app_runner.reset_memory()
        return ResetResponse()
    except Exception as e:
        logger.error("Failed to clear memory", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to reset memory: {str(e)}")


@router.get("/status", response_model=Dict[str, Any])
def get_system_status() -> Dict[str, Any]:
    """Returns the registered tools and variables status."""
    logger.info("Received system status API request")
    try:
        tools = app_runner.registry.get_all_metadata()
        variables = app_runner.context_manager.get_variables()
        return {
            "status": "healthy",
            "registered_tools_count": len(tools),
            "registered_tools": [t.get("name") for t in tools],
            "active_context_variables": variables
        }
    except Exception as e:
        logger.error("Failed to retrieve system status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info("Starting API server via uvicorn")
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
