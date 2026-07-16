"""Load skill tool for AutoPlan AI.

Loads specialized prompt-driven expert skills/personas from skills/ directory.
"""

from typing import Any, Dict
from framework.registry.tool_registry import BaseTool
from app.config import WORKSPACE_ROOT
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class LoadSkillTool(BaseTool):
    """Tool that dynamically loads specialized prompt-driven expert skills/personas."""

    name = "load_skill_tool"
    description = (
        "Loads specialized domain expert skills/personas (such as production_analyst, financial_analyst, "
        "supply_chain_analyst, or communications_expert) on-demand to augment the agent's behavior. "
        "Use this when you need additional expert context, guidelines, specific calculation formulas, "
        "or specialized prompts to perform deep domain analysis for the current task."
    )
    version = "1.0.0"
    category = "expert_skills"
    tags = ["skills", "skill", "prompt", "analyst", "financial", "production", "supply chain", "communications"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Loads a specialized skill prompt.

        Args:
            state: The current state containing active context variables.
        """
        logger.info("Executing Load Skill Tool")
        context = state.get("context", {})
        skill_name = context.get("skill_name")

        # Available skills mapped to their md filename
        available_skills = {
            "production_analyst": "production_analyst.md",
            "financial_analyst": "financial_analyst.md",
        }

        # Resolve search query from task context or skill name
        search_query = ""
        current_task_id = state.get("current_task")
        execution_plan = state.get("execution_plan")
        if current_task_id and execution_plan:
            tasks = execution_plan.get("tasks", [])
            for t in tasks:
                if t.get("id") == current_task_id:
                    search_query = t.get("sub_query") or t.get("title") or ""
                    break
        
        # If no task query found, or if skill_name is meaningful, use it
        if skill_name and skill_name.strip().lower() not in ("skill", "appropriate", "appropriate_skill", "load_skill_tool", "generic"):
            search_query = skill_name
            
        if not search_query:
            search_query = state.get("query", "")

        normalized_name = (skill_name or "").strip().lower()

        # Use SkillRetriever to semantically resolve skill_name if not directly matched
        if normalized_name not in available_skills:
            from framework.llm.gemini_client import GeminiClient
            from framework.registry.retriever import SkillRetriever
            from app import config as app_config

            if search_query:
                try:
                    gemini_client = GeminiClient(api_key=app_config.GEMINI_API_KEY, default_model=app_config.DEFAULT_MODEL)
                    retriever = SkillRetriever(gemini_client)
                    matches = retriever.retrieve(search_query, top_k=1)
                    if matches and matches[0]["similarity_score"] >= 0.7:
                        normalized_name = matches[0]["name"]
                        logger.info("Resolved skill name semantically via RAG", query=search_query, resolved_name=normalized_name, score=matches[0]["similarity_score"])
                except Exception as e:
                    logger.warning("Semantic skill lookup fallback failed", error=str(e))

        if normalized_name not in available_skills:
            # Maintain backward compatibility with unit test assertions
            if skill_name and skill_name.strip().lower() not in ("skill", "appropriate", "appropriate_skill", "load_skill_tool", "generic"):
                message = f"Skill '{skill_name}' is not recognized."
            else:
                message = "No skill_name was specified. You must provide a skill_name."
            return {
                "status": "error",
                "message": message,
                "available_skills": list(available_skills.keys())
            }

        filename = available_skills[normalized_name]
        skills_dir = WORKSPACE_ROOT / "skills"
        filepath = skills_dir / filename

        try:
            if not filepath.exists():
                return {
                    "status": "error",
                    "message": f"Skill prompt file for '{normalized_name}' not found at {filepath}."
                }
            
            with open(filepath, "r", encoding="utf-8") as f:
                prompt_content = f.read()

            # Store in context so downstream nodes can access loaded skills
            loaded_skills = dict(context.get("loaded_skills", {}))
            loaded_skills[normalized_name] = prompt_content
            context["loaded_skills"] = loaded_skills

            logger.info("Successfully loaded skill", skill_name=normalized_name)
            return {
                "status": "success",
                "skill_name": normalized_name,
                "prompt": prompt_content,
                "message": f"Skill '{normalized_name}' loaded successfully. Apply these instructions to your current task."
            }
        except Exception as e:
            logger.error("Failed to load skill file", skill_name=normalized_name, error=str(e))
            return {
                "status": "error",
                "message": f"Failed to load skill: {str(e)}"
            }
