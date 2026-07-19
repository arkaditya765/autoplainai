"""Chatbot Agent for framework.

Handles general knowledge queries, greetings, and conversational interactions.
Supports dynamic tool calling (e.g., search_tool, weather_tool) when required.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from google.genai import types
from google.genai.errors import APIError

from agents.base_agent import BaseAgent
from framework.registry.tool_registry import ToolRegistry
from framework.utils.logger import get_logger
from framework.utils.helpers import load_prompt

logger = get_logger(__name__)

_CHATBOT_SYSTEM_INSTRUCTION_FALLBACK = """You are the Chatbot Agent. Your job is to respond to general user queries, greetings, and general knowledge questions in a helpful, conversational, and friendly manner.

You have access to search tools and weather query tools. If a user asks a question requiring current info or external search (e.g., "who is the current Prime Minister of India?"), you MUST use the search_tool to retrieve accurate facts. Do not guess or make up details.
"""


class ChatbotAgent(BaseAgent):
    """Chatbot Agent that answers general chatbot queries dynamically using tools if needed."""

    def __init__(self, client, registry: ToolRegistry) -> None:
        super().__init__(client)
        self.registry = registry

    def _execute_single_chatbot_tool(self, fc, query):
        tool_name = fc.name
        fc_args = fc.args or {}
        
        try:
            tool_instance = self.registry.get_tool(tool_name)
            tool_state = {
                "query": query,
                "context": {
                    "search_query": fc_args.get("search_query"),
                    "location": fc_args.get("location")
                }
            }
            tool_result = tool_instance.execute(tool_state)
            status = "success"
        except Exception as e:
            tool_result = {"status": "error", "message": str(e)}
            status = "error"
            
        return {
            "tool_name": tool_name,
            "fc_id": fc.id,
            "fc_args": fc_args,
            "result": tool_result,
            "status": status
        }

    def _build_function_declarations(self, available_tools: List[Dict[str, Any]]) -> List[types.FunctionDeclaration]:
        """Converts tool metadata dicts into Gemini FunctionDeclaration objects."""
        declarations = []
        for tool_meta in available_tools:
            tool_name = tool_meta.get("name", "")
            properties = {}
            required = []
            
            if tool_name == "search_tool":
                properties = {
                    "search_query": {
                        "type": "STRING",
                        "description": "The exact web search query to look up on DuckDuckGo. Keep it short (maximum 3-4 words).",
                    }
                }
            elif tool_name == "weather_tool":
                properties = {
                    "location": {
                        "type": "STRING",
                        "description": "The location/city to query the weather for.",
                    }
                }
            
            declarations.append(
                types.FunctionDeclaration(
                    name=tool_name,
                    description=tool_meta.get("description", ""),
                    parameters={
                        "type": "OBJECT",
                        "properties": properties,
                        "required": required,
                    },
                )
            )
        return declarations

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generates conversational responses, executing tools when requested by the model.

        Args:
            state: The current state of the workflow graph.

        Returns:
            A state update dict containing the final response under 'recommendation'.
        """
        query = state.get("query", "")
        logger.info("Chatbot agent starting response generation", query=query)

        system_instruction = load_prompt("chatbot.md", _CHATBOT_SYSTEM_INSTRUCTION_FALLBACK)

        # Retrieve available tools for general chatbot
        chatbot_tools = []
        for tool_name in ["search_tool", "weather_tool"]:
            try:
                t = self.registry.get_tool(tool_name)
                chatbot_tools.append(t.get_metadata())
            except Exception:
                pass

        function_declarations = self._build_function_declarations(chatbot_tools)
        gemini_tools = [types.Tool(function_declarations=function_declarations)] if function_declarations else []

        # Build conversation history and incorporate decomposed task results if available
        history = state.get("history", [])
        prompt_parts = []
        
        # Include task results gathered by the planner/orchestrator
        task_results = state.get("task_results")
        if task_results:
            history_lines = ["Results from decomposed planning tasks:"]
            for task_id, res in task_results.items():
                history_lines.append(f"  - Task {task_id}: {res}")
            prompt_parts.append("\n".join(history_lines))

        if history:
            history_lines = []
            for h in history[-6:]:
                role = "User" if h.get("role") == "user" else "Assistant"
                history_lines.append(f"{role}: {h.get('content', '')}")
            prompt_parts.append("Conversation history:\n" + "\n".join(history_lines))
        prompt_parts.append(f"Latest User Query: {query}")
        
        contents = [
            types.Content(role="user", parts=[types.Part(text="\n\n".join(prompt_parts))])
        ]

        updated_trace = list(state.get("execution_trace", []))
        max_turns = 3
        final_response = "I encountered an error trying to process your request."

        try:
            for turn in range(max_turns):
                logger.debug("Chatbot Agent ReAct turn", turn=turn + 1)
                
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=gemini_tools,
                    temperature=0.7
                )

                # Call LLM
                response = self.client.client.models.generate_content(
                    model=self.client.default_model,
                    contents=contents,
                    config=config,
                )

                candidate = response.candidates[0]
                response_content = candidate.content

                if not response_content or not response_content.parts:
                    break

                # Append assistant content to history context
                contents.append(response_content)

                text_parts = [p.text for p in response_content.parts if p.text is not None]
                final_response = " ".join(text_parts).strip() if text_parts else ""

                function_calls = [p for p in response_content.parts if p.function_call is not None]
                if not function_calls:
                    # No tool was requested, we have our final text response!
                    break

                # Execute requested function calls
                function_response_parts = []
                
                # Execute requested function calls in parallel using ThreadPoolExecutor
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(self._execute_single_chatbot_tool, fc.function_call, query)
                        for fc in function_calls
                    ]
                    # Wait for all executions to complete
                    parallel_results = [f.result() for f in futures]
                
                # Sequentially process results to merge updates and record traces thread-safely
                for res in parallel_results:
                    tool_name = res["tool_name"]
                    fc_id = res["fc_id"]
                    fc_args = res["fc_args"]
                    tool_result = res["result"]
                    
                    logger.info("Chatbot tool executed successfully (parallel)", tool_name=tool_name, result=tool_result)

                    # Log to execution trace
                    updated_trace.append({
                        "node": "chatbot",
                        "action": f"Called tool '{tool_name}' with args {fc_args}.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "reasoning": f"Retrieved external information to answer query.",
                            "tool_output": tool_result
                        }
                    })

                    function_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=fc_id,
                                name=tool_name,
                                response=tool_result
                            )
                        )
                    )

                # Add the tool responses back to the conversation
                contents.append(types.Content(role="user", parts=function_response_parts))

            # Final trace entry for successful response
            updated_trace.append({
                "node": "chatbot",
                "action": "Generated conversational response.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "reasoning": "Completed chatbot response loop."
                }
            })

            return {
                "recommendation": final_response,
                "execution_trace": updated_trace
            }

        except Exception as e:
            logger.error("Failed to run ChatbotAgent", error=str(e))
            updated_trace.append({
                "node": "chatbot",
                "action": "Chatbot execution failed.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "error": str(e)
                }
            })
            return {
                "recommendation": "I'm sorry, I encountered an error processing your query. How can I help you today?",
                "execution_trace": updated_trace
            }
