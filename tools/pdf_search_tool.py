"""PDF search tool for AutoPlan AI.

Uses vector embeddings to run semantic search query on the Maruti Suzuki Safety Policy manual.
"""

import os
from typing import Any, Dict, List
import numpy as np
from pypdf import PdfReader

from framework.registry.tool_registry import BaseTool
from framework.llm.gemini_client import GeminiClient
from app import config as app_config
from framework.utils.logger import get_logger

logger = get_logger(__name__)


class PDFSearchTool(BaseTool):
    """Tool that queries the Maruti Suzuki Safety Policy manual (PDF) using RAG."""

    name = "pdf_search_tool"
    description = (
        "Searches the Maruti Suzuki Factory Safety Manual (PDF document) to retrieve "
        "relevant safety policy regulations, speed limits, audit guidelines, or PPE wear policies. "
        "Use this tool whenever the user's request asks about factory policies, safety rules, "
        "speed limits, jackets, shoes, or audits."
    )
    version = "1.0.0"
    category = "document_search"
    tags = ["safety", "policy", "pdf", "audit", "ppe"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs semantic search on the safety manual PDF.

        Args:
            state: The active workflow state containing active context variables.
        """
        logger.info("Executing PDF Search Tool")

        context = state.get("context", {})
        search_query = context.get("search_query") or state.get("query", "")

        if not search_query:
            return {
                "status": "error",
                "message": "No query provided for PDF search.",
                "matches": []
            }

        # Resolve PDF file path dynamically from configuration
        pdf_path = str(app_config.SAFETY_POLICY_PDF)
        if not os.path.exists(pdf_path):
            return {
                "status": "error",
                "message": f"Safety policy PDF manual not found at {pdf_path}.",
                "matches": []
            }

        try:
            import hashlib
            import json

            def get_file_md5(file_path: str) -> str:
                hasher = hashlib.md5()
                with open(file_path, "rb") as f:
                    buf = f.read()
                    hasher.update(buf)
                return hasher.hexdigest()

            current_hash = get_file_md5(pdf_path)
            
            # Segregate cache files dynamically per PDF filename
            pdf_filename = os.path.basename(pdf_path)
            cache_filename = f"{os.path.splitext(pdf_filename)[0]}_vector_cache.json"
            
            # Prevent unit tests from contaminating production cache
            import sys
            is_testing = "pytest" in sys.modules or "unittest" in sys.modules
            cache_path = None if is_testing else os.path.join(app_config.DATA_DIR, cache_filename)
            
            cached_data = None
            if cache_path and os.path.exists(cache_path):
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("pdf_hash") == current_hash:
                        cached_data = data
                        logger.info(f"Loaded {pdf_filename} embeddings from local cache.")
                except Exception as e:
                    logger.warning("Failed to load PDF vector cache, rebuilding.", error=str(e))

            # Initialize Gemini Client to get embeddings
            client = GeminiClient(
                api_key=app_config.GEMINI_API_KEY,
                default_model=app_config.DEFAULT_MODEL
            )

            if cached_data:
                chunks = cached_data["chunks"]
            else:
                logger.info("Cache miss or PDF changed. Regenerating safety manual embeddings...")
                # 1. Parse PDF and extract chunks
                paragraphs = []
                reader = PdfReader(pdf_path)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        lines = [line.strip() for line in text.split("\n") if line.strip()]
                        paragraphs.extend(lines)

                if not paragraphs:
                    return {
                        "status": "success",
                        "message": "Safety manual PDF is empty.",
                        "matches": []
                    }

                # Generate embeddings for all paragraph chunks
                chunks = []
                for p in paragraphs:
                    p_emb = client.embed(p)
                    chunks.append({
                        "text": p,
                        "vector": p_emb
                    })

                # Save cache to disk
                if cache_path:
                    try:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump({"pdf_hash": current_hash, "chunks": chunks}, f, indent=2)
                        logger.info("Successfully updated PDF safety manual vector cache.")
                    except Exception as e:
                        logger.warning("Failed to save PDF vector cache to disk.", error=str(e))

            # 3. Generate embedding for query
            query_emb = client.embed(search_query)
            query_vec = np.array(query_emb, dtype=np.float32)

            scored_paragraphs = []
            for item in chunks:
                p_text = item["text"]
                p_emb = item["vector"]
                p_vec = np.array(p_emb, dtype=np.float32)

                dot_product = np.dot(query_vec, p_vec)
                norm_q = np.linalg.norm(query_vec)
                norm_v = np.linalg.norm(p_vec)
                score = float(dot_product / (norm_q * norm_v)) if norm_q > 0 and norm_v > 0 else 0.0

                scored_paragraphs.append({
                    "text": p_text,
                    "similarity_score": round(score, 4)
                })

            # Sort by similarity score descending
            scored_paragraphs.sort(key=lambda x: x["similarity_score"], reverse=True)

            # Retrieve top 2 matches
            top_matches = scored_paragraphs[:2]

            logger.info("PDF Search completed successfully", matches_count=len(top_matches))
            return {
                "status": "success",
                "matches": top_matches
            }

        except Exception as e:
            logger.error("Error executing PDF Search Tool", error=str(e))
            return {
                "status": "error",
                "message": f"Failed to execute PDF Search: {str(e)}",
                "matches": []
            }
