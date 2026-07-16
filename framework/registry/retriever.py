"""Vector search-based tool retriever for framework framework.

Allows scaling tool count to hundreds of tools by dynamically retrieving
only the top-K relevant tool metadata using vector embeddings.
"""

from typing import Any, Dict, List
import numpy as np
import hashlib
import json
from pathlib import Path

from framework.llm.gemini_client import GeminiClient
from framework.registry.tool_registry import ToolRegistry, BaseTool
from framework.utils.logger import get_logger

logger = get_logger(__name__)


import sys

def _get_cache_path() -> Path:
    try:
        from app.config import WORKSPACE_ROOT
        return WORKSPACE_ROOT / ".tool_vector_cache.json"
    except Exception:
        return Path(".tool_vector_cache.json")


def _load_cache() -> dict:
    if "pytest" in sys.modules or "unittest" in sys.modules:
        return {}
    cache_path = _get_cache_path()
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    if "pytest" in sys.modules or "unittest" in sys.modules:
        return
    cache_path = _get_cache_path()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save tool vector cache", error=str(e))


def _get_cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class ToolRetriever:
    """Handles semantic tool retrieval using Google Gemini embeddings API."""

    def __init__(
        self,
        gemini_client: GeminiClient,
        registry: ToolRegistry,
        embedding_model: str = "gemini-embedding-2",
    ) -> None:
        """Initializes the Tool Retriever.

        Args:
            gemini_client: The GeminiClient instance.
            registry: The tool registry to retrieve tools from.
            embedding_model: Gemini embedding model name.
        """
        self.client = gemini_client
        self.registry = registry
        self.embedding_model = embedding_model
        self._tool_embeddings: List[Dict[str, Any]] = []
        self._is_indexed = False
        
        # Diagnostics fields for frontend visualization
        self.last_query: str = ""
        self.last_query_embedding: List[float] = []
        self.last_matches: List[tuple[float, str]] = []

    def build_index(self) -> None:
        """Generates embeddings for all currently registered tools.

        This indexes tool definitions at startup or when tools are registered.
        """
        import time as _time
        t_start = _time.perf_counter()
        logger.info("Building vector index for registered tools")
        self._tool_embeddings.clear()
        
        tools = self.registry.list_tools()
        if not tools:
            logger.warning("No tools registered to build index.")
            self._is_indexed = True
            return

        cache = _load_cache()
        cache_updated = False
        cache_hits = 0
        api_calls = 0

        for tool in tools:
            # Combine tool details into a descriptive indexable document
            tags_str = ", ".join(tool.tags)
            document = f"Tool Name: {tool.name}. Description: {tool.description}. Category: {tool.category}. Tags: {tags_str}"
            
            try:
                cache_key = _get_cache_key(document)
                if cache_key in cache:
                    embedding = cache[cache_key]
                    cache_hits += 1
                    logger.debug("Tool embedding loaded from FILE CACHE", tool_name=tool.name)
                else:
                    embedding = self.client.embed(document, model=self.embedding_model)
                    cache[cache_key] = embedding
                    cache_updated = True
                    api_calls += 1
                    logger.info("Tool embedding fetched from API (cache MISS)", tool_name=tool.name)

                self._tool_embeddings.append({
                    "name": tool.name,
                    "metadata": tool.get_metadata(),
                    "vector": np.array(embedding, dtype=np.float32)
                })
            except Exception as e:
                logger.error("Failed to index tool", tool_name=tool.name, error=str(e))
                # Skip tool if embedding fails to prevent crashing completely
                continue
                
        if cache_updated:
            _save_cache(cache)

        elapsed = _time.perf_counter() - t_start
        self._is_indexed = True
        logger.info("Successfully built tool vector index", num_tools=len(self._tool_embeddings), cache_hits=cache_hits, api_calls=api_calls, elapsed_seconds=round(elapsed, 4))

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Retrieves the Top-K most semantically relevant tool metadata for a user query.

        If the index is not yet built, builds it on the fly.
        If no tools are registered or index is empty, returns an empty list.

        Args:
            query: The user prompt query.
            top_k: Number of candidate tools to retrieve.

        Returns:
            A list of serialized tool metadata dicts.
        """
        if not self._is_indexed:
            self.build_index()

        self.last_query = query
        self.last_query_embedding = []
        self.last_matches = []

        if not self._tool_embeddings:
            logger.warning("Tool index is empty, returning no tools.")
            return []

        try:
            # Generate embedding for query
            raw_emb = self.client.embed(query, model=self.embedding_model)
            self.last_query_embedding = [float(v) for v in raw_emb]
            query_vector = np.array(raw_emb, dtype=np.float32)
        except Exception as e:
            logger.warning("Failed to generate query embedding, falling back to returning first top_k tools", error=str(e))
            return [item["metadata"] for item in self._tool_embeddings[:top_k]]

        # Compute cosine similarity
        scored_tools = []
        for item in self._tool_embeddings:
            vec = item["vector"]
            dot_product = np.dot(query_vector, vec)
            norm_q = np.linalg.norm(query_vector)
            norm_v = np.linalg.norm(vec)
            
            similarity = dot_product / (norm_q * norm_v) if (norm_q * norm_v) > 0 else 0.0
            scored_tools.append((similarity, item["name"], item["metadata"]))

        # Sort by similarity descending
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        
        # Save diagnostics matches
        self.last_matches = [(float(score), name) for score, name, _ in scored_tools]
        
        logger.info("Tool retriever matches", matches=[(m[1], round(m[0], 4)) for m in scored_tools[:top_k]])
        
        # Extract metadata for Top-K
        return [metadata for score, name, metadata in scored_tools[:top_k]]


class SkillRetriever:
    """Handles semantic skill retrieval from the skills directory using Google Gemini embeddings API."""

    def __init__(
        self,
        gemini_client: GeminiClient,
        skills_dir: str = None,
        embedding_model: str = "gemini-embedding-2",
    ) -> None:
        """Initializes the Skill Retriever.

        Args:
            gemini_client: The GeminiClient instance.
            skills_dir: Optional path to skills directory.
            embedding_model: Gemini embedding model name.
        """
        self.client = gemini_client
        self.embedding_model = embedding_model
        self._skill_embeddings: List[Dict[str, Any]] = []
        self._is_indexed = False
        
        # Locate skills directory
        from pathlib import Path
        import os
        workspace_root = None
        for parent in Path(__file__).resolve().parents:
            if (parent / "skills").exists():
                workspace_root = parent
                break
        if not workspace_root:
            workspace_root = Path(os.getcwd())
        self.skills_dir = Path(skills_dir) if skills_dir else workspace_root / "skills"

        # Diagnostics fields for frontend visualization
        self.last_query: str = ""
        self.last_query_embedding: List[float] = []
        self.last_matches: List[tuple[float, str]] = []

    def _parse_yaml_metadata(self, content: str) -> Dict[str, str]:
        """Parses simple YAML front-matter from a markdown file."""
        metadata = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                yaml_block = parts[1]
                for line in yaml_block.split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        metadata[k.strip()] = v.strip()
        return metadata

    def build_index(self) -> None:
        """Generates embeddings for all markdown files in the skills directory."""
        import time as _time
        t_start = _time.perf_counter()
        logger.info("Building vector index for skills directory", path=str(self.skills_dir))
        self._skill_embeddings.clear()
        
        if not self.skills_dir.exists():
            logger.warning("Skills directory does not exist, cannot build index.", path=str(self.skills_dir))
            self._is_indexed = True
            return

        cache = _load_cache()
        cache_updated = False
        cache_hits = 0
        api_calls = 0

        for filepath in self.skills_dir.glob("*.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                meta = self._parse_yaml_metadata(content)
                name = meta.get("name") or filepath.stem
                description = meta.get("description") or ""

                # Build document to represent this skill in the vector space
                document = f"Skill Name: {name}. Description: {description}. Full Content:\n{content}"
                
                cache_key = _get_cache_key(document)
                if cache_key in cache:
                    embedding = cache[cache_key]
                    cache_hits += 1
                    logger.debug("Skill embedding loaded from FILE CACHE", name=name)
                else:
                    embedding = self.client.embed(document, model=self.embedding_model)
                    cache[cache_key] = embedding
                    cache_updated = True
                    api_calls += 1
                    logger.info("Skill embedding fetched from API (cache MISS)", name=name)

                self._skill_embeddings.append({
                    "name": name,
                    "filepath": str(filepath),
                    "description": description,
                    "content": content,
                    "vector": np.array(embedding, dtype=np.float32)
                })
            except Exception as e:
                logger.error("Failed to index skill file", path=str(filepath), error=str(e))
                continue

        if cache_updated:
            _save_cache(cache)

        elapsed = _time.perf_counter() - t_start
        self._is_indexed = True
        logger.info("Successfully built skills vector index", num_skills=len(self._skill_embeddings), cache_hits=cache_hits, api_calls=api_calls, elapsed_seconds=round(elapsed, 4))

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Retrieves the Top-K most semantically relevant skills for a given query.

        Args:
            query: The user prompt or sub-query.
            top_k: Number of skill matches to return.

        Returns:
            A list of dictionary skill metadata definitions.
        """
        if not self._is_indexed:
            self.build_index()

        self.last_query = query
        self.last_query_embedding = []
        self.last_matches = []

        if not self._skill_embeddings:
            logger.warning("Skills index is empty, returning no skills.")
            return []

        try:
            raw_emb = self.client.embed(query, model=self.embedding_model)
            self.last_query_embedding = [float(v) for v in raw_emb]
            query_vector = np.array(raw_emb, dtype=np.float32) 
        except Exception as e:
            logger.warning("Failed to generate query embedding for skills search", error=str(e))
            # Return fallback first top_k
            return [item for item in self._skill_embeddings[:top_k]]

        scored_skills = []
        for item in self._skill_embeddings:
            vec = item["vector"]
            dot_product = np.dot(query_vector, vec)
            norm_q = np.linalg.norm(query_vector)
            norm_v = np.linalg.norm(vec)
            
            similarity = dot_product / (norm_q * norm_v) if (norm_q * norm_v) > 0 else 0.0
            scored_skills.append((similarity, item))

        # Sort by similarity descending
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        
        # Save diagnostics matches
        self.last_matches = [(float(score), item["name"]) for score, item in scored_skills]

        logger.info("Skill retriever matches", matches=[(item["name"], round(score, 4)) for score, item in scored_skills[:top_k]])
        
        # Return Top-K skills metadata
        return [
            {
                "name": item["name"],
                "filepath": item["filepath"],
                "description": item["description"],
                "content": item["content"],
                "similarity_score": score
            }
            for score, item in scored_skills[:top_k]
        ]
