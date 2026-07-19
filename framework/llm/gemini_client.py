"""Google Gemini API client wrapper for framework.

Provides a unified interface for calling Gemini models, configuring schema
validation, handling structured JSON output, and handling API exceptions.
"""

import os
from typing import Any, Dict, Optional, Type, Union
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import APIError

from framework.utils.logger import get_logger
from framework.utils.exceptions import LLMError, LLMResponseError
from framework.utils.helpers import safe_parse_json

logger = get_logger(__name__)


class GeminiClient:
    """Wrapper class for Google Gemini GenAI SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-1.5-flash-8b",
    ) -> None:
        """Initializes the Gemini client.

        Args:
            api_key: The Google Gemini API key. If None, reads GEMINI_API_KEY from environment.
            default_model: The model name to use by default.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.default_model = default_model

        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set. Execution will fail unless api_key is passed at runtime or mocked.")

        # Initialize Google GenAI client
        try:
            # Under standard usage, genai.Client reads GEMINI_API_KEY automatically if api_key is None.
            self.client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        except Exception as e:
            logger.error("Failed to initialize Google GenAI Client", error=str(e))
            self.client = None

        # In-memory cache for embedding requests to prevent duplicate calls for identical text
        self._embedding_cache = {}

        # Per-query call log for diagnostics (read by frontend, cleared per query)
        self._call_log = []

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generates a text completion from the Gemini LLM.

        Args:
            prompt: The user prompt input.
            system_instruction: Optional system instruction prompt to guide model behavior.
            model: Optional model name to override the default.
            temperature: Model temperature.

        Returns:
            The raw string response.
        """
        target_model = model or self.default_model
        logger.info("Invoking Gemini Generate", model=target_model, temperature=temperature)

        if not self.client:
            raise LLMError("Gemini client is not initialized. Please configure GEMINI_API_KEY.")

        try:
            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction,
            )
            import time as _t
            _t0 = _t.perf_counter()
            response = self.client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )
            _dur = _t.perf_counter() - _t0
            self._call_log.append({
                "type": "llm",
                "caller": "GeminiClient.generate",
                "model": target_model,
                "duration_s": round(_dur, 3),
                "purpose": f"Text generation (temp={temperature})",
            })
            if not response.text:
                raise LLMResponseError("Gemini returned an empty response.")
            return response.text
        except APIError as e:
            logger.error("Gemini API Error occurred", error=str(e))
            raise LLMError(f"Gemini API error: {e.message}", details={"code": e.code, "status": e.status}) from e
        except Exception as e:
            logger.error("Unexpected error in LLM call", error=str(e))
            err_msg = str(e)
            if "11001" in err_msg or "getaddrinfo" in err_msg or "socket" in err_msg or "connection" in err_msg.lower():
                raise LLMError(
                    "Network Connection Failure: Unable to reach Google Gemini API endpoints. "
                    "Please verify that you are connected to the internet and that your DNS or firewall is not blocking googleapis.com.",
                    details=err_msg
                ) from e
            raise LLMError("An unexpected error occurred during the LLM call.", details=err_msg) from e

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        system_instruction: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> BaseModel:
        """Generates structured content conforming to a specific Pydantic schema.

        Args:
            prompt: The user prompt input.
            response_schema: The Pydantic model class defining the target schema.
            system_instruction: Optional system instructions.
            model: Optional model name to override the default.
            temperature: Model temperature.

        Returns:
            An instance of the response_schema Pydantic model.
        """
        target_model = model or self.default_model
        logger.info("Invoking Gemini Structured Output", model=target_model, schema=response_schema.__name__)

        if not self.client:
            raise LLMError("Gemini client is not initialized. Please configure GEMINI_API_KEY.")

        try:
            # Build config enforcing JSON format and schema mapping
            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
            )
            import time as _t
            _t0 = _t.perf_counter()
            response = self.client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )
            _dur = _t.perf_counter() - _t0
            self._call_log.append({
                "type": "llm",
                "caller": "GeminiClient.generate_structured",
                "model": target_model,
                "duration_s": round(_dur, 3),
                "purpose": f"Structured output → {response_schema.__name__}",
            })

            if not response.text:
                raise LLMResponseError("Gemini returned an empty response during structured call.")

            # Parse text into target Pydantic model
            parsed_data = safe_parse_json(response.text)
            return response_schema.model_validate(parsed_data)
        except APIError as e:
            logger.error("Gemini API Error during structured call", error=str(e))
            raise LLMError(f"Gemini API structured call error: {e.message}", details={"code": e.code, "status": e.status}) from e
        except Exception as e:
            logger.error("Failed to generate or validate structured content", error=str(e))
            err_msg = str(e)
            if "11001" in err_msg or "getaddrinfo" in err_msg or "socket" in err_msg or "connection" in err_msg.lower():
                raise LLMError(
                    "Network Connection Failure: Unable to reach Google Gemini API endpoints. "
                    "Please verify that you are connected to the internet and that your DNS or firewall is not blocking googleapis.com.",
                    details=err_msg
                ) from e
            raise LLMResponseError(
                f"Failed to generate structured content conforming to {response_schema.__name__}.",
                details=err_msg
            ) from e

    def embed(self, text: str, model: str = "text-embedding-004") -> list[float]:
        """Generates an embedding vector using Gemini's embedding API.

        Args:
            text: The input text to embed.
            model: The embedding model to use.

        Returns:
            A list of float values representing the embedding.
        """
        if not self.client:
            raise LLMError("Gemini client is not initialized. Please configure GEMINI_API_KEY.")
            
        cache_key = (text, model)
        if cache_key in self._embedding_cache:
            logger.debug("Loading embedding from in-memory cache", text_preview=text[:40])
            return self._embedding_cache[cache_key]
            
        try:
            import time as _t
            _t0 = _t.perf_counter()
            response = self.client.models.embed_content(
                model=model,
                contents=text
            )
            _dur = _t.perf_counter() - _t0
            if not response.embeddings:
                raise LLMResponseError("Gemini returned empty embeddings.")
            vector = response.embeddings[0].values
            self._embedding_cache[cache_key] = vector
            self._call_log.append({
                "type": "embedding",
                "caller": "GeminiClient.embed",
                "model": model,
                "duration_s": round(_dur, 3),
                "purpose": f"Embed: \"{text[:50]}...\"",
                "cached": False,
            })
            return vector
        except APIError as e:
            logger.error("Gemini API embedding error occurred", error=str(e))
            raise LLMError(f"Gemini API embedding error: {e.message}", details={"code": e.code, "status": e.status}) from e
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise LLMError("Failed to generate embedding from Gemini API.", details=str(e)) from e

    def bind_tools(self, tools: list) -> "BoundLLM":
        """Binds a list of tools to this LLM client.

        Conforms to manager's diagram: llmwithtool = llm.bind_tools([ , , ])

        Args:
            tools: List of tool metadata dicts (from ToolRegistry).

        Returns:
            A BoundLLM instance with the tools attached.
        """
        return BoundLLM(self, tools)


class BoundLLM:
    """LLM wrapper with pre-bound tools.

    Conforms to manager's diagram: query + llmwithtool + System Prompt -> Answer
    """

    def __init__(self, client: GeminiClient, tools: list) -> None:
        self.client = client
        self.tools = tools

    def invoke(
        self,
        prompt: str,
        response_schema: Type[BaseModel],
        system_instruction: Optional[str] = None,
        temperature: float = 0.0,
    ) -> BaseModel:
        """Invokes the LLM with the bound tools injected into the system instruction.

        Args:
            prompt: The user query prompt.
            response_schema: Pydantic model defining expected output structure.
            system_instruction: System prompt template; bound tool schemas are
                substituted in place of the {available_tools_metadata} placeholder.
            temperature: Model temperature (default 0.0 for deterministic planning).

        Returns:
            An instance of the response_schema Pydantic model.
        """
        import json
        tools_str = json.dumps(self.tools, indent=2)

        bound_instruction = system_instruction or ""
        if "{available_tools_metadata}" in bound_instruction:
            bound_instruction = bound_instruction.replace("{available_tools_metadata}", tools_str)
        else:
            bound_instruction += f"\n\nAvailable Tools:\n{tools_str}"

        return self.client.generate_structured(
            prompt=prompt,
            response_schema=response_schema,
            system_instruction=bound_instruction,
            temperature=temperature,
        )
