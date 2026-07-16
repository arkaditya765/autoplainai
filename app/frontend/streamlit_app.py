"""Streamlit Frontend dashboard for AutoPlan AI.

Provides a premium conversational planning user interface with live 
execution trace timelines, validation status reports, and active memory views.
"""

import sys
from pathlib import Path

# Resolve project import paths dynamically
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(WORKSPACE_ROOT))
sys.path.append(str(WORKSPACE_ROOT / "framework"))
sys.path.append(str(WORKSPACE_ROOT / "app"))

# pyrefly: ignore [missing-import]
import streamlit as st
import datetime
import json
from typing import Any, Dict, List

# Directly import the application to run queries inline
from app.app import AutoPlanApp
# pyrefly: ignore [missing-import]
from framework.utils.logger import get_logger

logger = get_logger(__name__)

# --- Core libraries ---
import time


# Page configuration
st.set_page_config(
    page_title="AutoPlan AI - Manufacturing Support",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #FF8008 0%, #FFC837 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .main-header {
        font-size: 2.5rem;
        margin-bottom: 0.2rem;
    }
    .subheader {
        font-size: 1.1rem;
        color: #8892B0;
        margin-bottom: 2rem;
    }
    .badge-passed {
        background-color: #05C46B;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-failed {
        background-color: #FF5E57;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.85rem;
        display: inline-block;
    }
    .trace-card {
        background-color: #1E272E;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 4px solid #FF8008;
    }
    .trace-node {
        font-weight: bold;
        color: #FFC837;
        font-family: 'Outfit', sans-serif;
    }
    .trace-time {
        font-size: 0.8rem;
        color: #8892B0;
    }
    .sidebar-var-card {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 6px;
        padding: 10px;
        margin-bottom: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State App
if "app" not in st.session_state:
    with st.spinner("Initializing AutoPlan AI Agent orchestrator..."):
        st.session_state.app = AutoPlanApp()
    st.success("Orchestrator ready!")

app = st.session_state.app

# Initialize Chat messages
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_response_state" not in st.session_state:
    st.session_state.last_response_state = None


# Sidebar
with st.sidebar:
    st.markdown("<h2 style='font-size: 1.8rem; background: linear-gradient(135deg, #12C2E9 0%, #C471ED 50%, #F64F59 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>System State Memory</h2>", unsafe_allow_html=True)
    st.write("Active parameters stored in the conversational memory context (ChatGPT-like persistence):")

    # Display active context variables
    context_vars = app.context_manager.get_variables()
    if context_vars:
        for key, value in context_vars.items():
            st.markdown(f"""
            <div class="sidebar-var-card">
                <span style="font-size: 0.8rem; color: #8892B0; display:block;">{key.upper().replace('_', ' ')}</span>
                <span style="font-size: 1.0rem; font-weight: 600; color: #EAF0F6;">{value}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No parameters in memory. Start chatting to extract context parameters.")

    # Reset Variables Button (keeping history)
    if st.button("🧹 Clear Active Parameters", use_container_width=True):
        app.reset_variables()
        st.success("Active parameters context cleared!")
        st.rerun()

    # Reset Full Memory Button
    if st.button("🔄 Clear Conversational Memory", use_container_width=True):
        app.reset_memory()
        st.session_state.chat_history = []
        st.session_state.last_response_state = None
        st.success("Memory cleared!")
        st.rerun()

    st.markdown("---")
    st.markdown("### Registered Tools")
    st.write("These tools were dynamically discovered from the application registry:")
    for tool_meta in app.registry.get_all_metadata():
        st.markdown(f"**🛠️ {tool_meta['name']}**  \n*{tool_meta['description']}*")

# Main Title Header
st.markdown("<h1 class='main-header'>AutoPlan AI</h1>", unsafe_allow_html=True)
st.markdown("<div class='subheader'>Enterprise-grade decision support assistant powered by the framework Multi-Agent Framework.</div>", unsafe_allow_html=True)

# Main layout split
col_chat, col_trace = st.columns([1.2, 0.8])

with col_chat:
    st.markdown("### Interactive Planning Chat")
    
    # Render historical conversation from st.session_state
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if user_query := st.chat_input("Ask a planning question (e.g. 'Increase Brezza demand by 25%')"):
        # Display user message
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.chat_history.append({"role": "user", "content": user_query})

        # Run query through the Agent Graph
        with st.spinner("Agent orchestrator thinking... (Orchestrator -> Strategy -> Validator)"):
            try:
                result_state = app.run_query(user_query)
                
                st.session_state.last_response_state = result_state
                
                # Fetch recommendation
                recommendation = result_state.get("recommendation", "No recommendation produced.")
                
                # Render recommendation
                with st.chat_message("assistant"):
                    st.markdown(recommendation)
                st.session_state.chat_history.append({"role": "assistant", "content": recommendation})
                st.rerun()
            except Exception as e:
                st.error(f"Error executing request: {e}")
                logger.error("Error running query", error=str(e))

with col_trace:
    st.markdown("### Framework Execution Trace")
    
    if st.session_state.last_response_state is not None:
        state = st.session_state.last_response_state
        
        # Display Query Planner Execution Plan
        plan = state.get("execution_plan")
        if plan:
            st.markdown("#### 📋 Query Plan & Task Decomposition")
            st.markdown(f"**Goal:** {plan.get('goal', '')}")
            st.markdown(f"**Reasoning:** *{plan.get('planner_reasoning', '')}*")
            
            for task in plan.get("tasks", []):
                status = task.get("status", "pending")
                status_icon = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
                depends_on = f" *(depends on: {', '.join(task.get('depends_on'))})*" if task.get("depends_on") else ""
                st.markdown(f"{status_icon} **{task.get('title')}** ({task.get('id')}){depends_on}")
                st.markdown(f"  - *Sub-Query:* `{task.get('sub_query')}`")
            st.markdown("---")

        # Display Validation Status Block
        validation = state.get("validation")
        if validation:
            status = validation.get("status", "FAILED")
            feedback = validation.get("feedback", "")
            violations = validation.get("violations", [])
            
            if status == "PASSED":
                st.markdown("#### Validation Result: <span class='badge-passed'>PASSED</span>", unsafe_allow_html=True)
            else:
                st.markdown("#### Validation Result: <span class='badge-failed'>FAILED</span>", unsafe_allow_html=True)
            
            st.markdown(f"**Audit Feedback:** {feedback}")
            if violations:
                st.warning("⚠️ Constraints Violations:")
                for v in violations:
                    st.markdown(f"- {v}")
            st.markdown("---")

        # Display Tool RAG Retrieval Diagnostics
        if hasattr(app, "retriever") and app.retriever.last_query:
            st.markdown("#### 🔍 Semantic Tool RAG Diagnostics")
            st.markdown(f"**Query Embedded**: *\"{app.retriever.last_query}\"*")
            
            # Show a snippet of the vector embedding
            embedding_snippet = app.retriever.last_query_embedding[:6]
            if embedding_snippet:
                embedding_str = ", ".join(f"{val:.4f}" for val in embedding_snippet) + ", ..."
                st.markdown("**Query Embedding Vector (Dimension 768)**:")
                st.code(f"[{embedding_str}]")
            
            # Show the ranked similarity scores
            if app.retriever.last_matches:
                st.markdown("**Tool Candidate Search Rankings (gemini-embedding-2)**:")
                for idx, (score, name) in enumerate(app.retriever.last_matches):
                    # Style based on rank (top-5 are candidate selections passed to Planner)
                    is_candidate = idx < 5
                    badge_style = "color:#05C46B; font-weight:bold;" if is_candidate else "color:#8892B0; font-style:italic;"
                    badge_label = " [Candidate]" if is_candidate else " [Filtered Out]"
                    
                    st.markdown(
                        f"- **{name}**: <span style='{badge_style}'>{score:.4f}</span> {badge_label}", 
                        unsafe_allow_html=True
                    )
            st.markdown("---")

        # Display Skill RAG Retrieval Diagnostics
        if hasattr(app, "skill_retriever") and app.skill_retriever.last_query:
            st.markdown("#### 🎓 Semantic Skill RAG Diagnostics")
            st.markdown(f"**Query Embedded**: *\"{app.skill_retriever.last_query}\"*")
            
            # Show a snippet of the vector embedding
            embedding_snippet = app.skill_retriever.last_query_embedding[:6]
            if embedding_snippet:
                embedding_str = ", ".join(f"{val:.4f}" for val in embedding_snippet) + ", ..."
                st.markdown("**Query Embedding Vector (Dimension 768)**:")
                st.code(f"[{embedding_str}]")
            
            # Show the ranked similarity scores
            if app.skill_retriever.last_matches:
                st.markdown("**Skill Candidate Search Rankings (gemini-embedding-2)**:")
                for idx, (score, name) in enumerate(app.skill_retriever.last_matches):
                    badge_style = "color:#05C46B; font-weight:bold;" if idx == 0 else "color:#8892B0; font-style:italic;"
                    badge_label = " [Top Match]" if idx == 0 else " [Candidate]"
                    st.markdown(
                        f"- **{name}**: <span style='{badge_style}'>{score:.4f}</span> {badge_label}", 
                        unsafe_allow_html=True
                    )
            st.markdown("---")

        # Display Selected Tools
        selected_tools = state.get("selected_tools", [])
        if selected_tools:
            st.markdown("#### 🔧 Tools Executed in Sequence:")
            st.code(", ".join(selected_tools))
            st.markdown("---")



        # Display Timeline Trace
        trace = state.get("execution_trace", [])
        if trace:
            st.markdown("#### ⏳ Step-by-Step execution timeline:")
            for idx, step in enumerate(trace):
                node = step.get("node", "unknown").upper()
                action = step.get("action", "")
                timestamp_str = step.get("timestamp", "")
                metadata = step.get("metadata", {})
                
                # Parse timestamp for clean display
                try:
                    dt = datetime.datetime.fromisoformat(timestamp_str.replace("Z", ""))
                    time_display = dt.strftime("%H:%M:%S")
                except:
                    time_display = timestamp_str

                # Render reasoning if present
                reasoning = metadata.get("reasoning", "")
                reasoning_html = f'<p style="margin-top: 5px; margin-bottom: 5px; font-size: 0.9rem; color: #10ac84; font-style: italic;">💡 <b>Reasoning:</b> {reasoning}</p>' if reasoning else ""

                st.markdown(f"""
                <div class="trace-card">
                    <span class="trace-node">{idx+1}. {node}</span> &nbsp;|&nbsp; <span class="trace-time">{time_display}</span>
                    <p style="margin-top: 5px; margin-bottom: 5px; font-size: 0.95rem;">{action}</p>
                    {reasoning_html}
                </div>
                """, unsafe_allow_html=True)
                
                if metadata:
                    with st.expander("View step output details", expanded=False):
                        st.json(metadata)
        else:
            st.info("Timeline trace is empty.")

        # ──────────────────────────────────────────────────────────
        # DIAGNOSTICS & PERFORMANCE METRICS (from state pipeline)
        # ──────────────────────────────────────────────────────────
        diag = state.get("diagnostics", {})
        if diag and diag.get("total_duration_s") is not None:
            st.markdown("---")
            with st.expander("📊 Performance & Diagnostics Metrics", expanded=True):
                # --- Summary Metrics Row ---
                total_time = diag.get("total_duration_s", 0)
                llm_calls = diag.get("llm_calls", [])
                embed_calls = diag.get("embedding_calls", [])
                tool_execs = diag.get("tool_executions", [])
                node_timings = diag.get("node_timings", [])

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("⏱️ Total Query Time", f"{total_time:.2f}s")
                m2.metric("🤖 LLM API Calls", str(len(llm_calls)))
                m3.metric("🔧 Tools Executed", str(len(tool_execs)))
                m4.metric("📐 Embedding Calls", str(len(embed_calls)))

                # --- Node Execution Waterfall ---
                if node_timings:
                    st.markdown("##### 🏗️ Node Execution Waterfall")
                    max_dur = max(nt["duration_s"] for nt in node_timings) if node_timings else 1
                    for nt in node_timings:
                        node_name = nt["node"].replace("_node", "").replace("_", " ").title()
                        dur = nt["duration_s"]
                        bar_pct = min(int((dur / max_dur) * 100), 100) if max_dur > 0 else 0
                        bar_color = "#FF8008" if dur == max_dur else "#FFC837"
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; margin-bottom: 6px;">
                            <span style="width: 140px; font-size: 0.85rem; color: #CCD6F6; font-weight: 600;">{node_name}</span>
                            <div style="flex: 1; background: rgba(255,255,255,0.05); border-radius: 4px; height: 22px; overflow: hidden;">
                                <div style="width: {bar_pct}%; background: linear-gradient(90deg, {bar_color}, #F64F59); height: 100%; border-radius: 4px; transition: width 0.5s ease;"></div>
                            </div>
                            <span style="width: 70px; text-align: right; font-size: 0.85rem; color: #8892B0; margin-left: 8px;">{dur:.3f}s</span>
                        </div>
                        """, unsafe_allow_html=True)

                # --- LLM Call Details Table ---
                if llm_calls:
                    st.markdown("##### 🤖 LLM API Call Details")
                    llm_table_rows = ""
                    for call in llm_calls:
                        caller = call.get("caller", "—")
                        model = call.get("model", "—")
                        dur = call.get("duration_s", 0)
                        purpose = call.get("purpose", "—")
                        llm_table_rows += f"<tr><td>{caller}</td><td>{model}</td><td>{dur:.3f}s</td><td>{purpose}</td></tr>"
                    
                    st.markdown(f"""
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                        <thead>
                            <tr style="border-bottom: 2px solid rgba(255,255,255,0.15); color: #FFC837;">
                                <th style="text-align: left; padding: 6px;">Caller</th>
                                <th style="text-align: left; padding: 6px;">Model</th>
                                <th style="text-align: left; padding: 6px;">Duration</th>
                                <th style="text-align: left; padding: 6px;">Purpose</th>
                            </tr>
                        </thead>
                        <tbody style="color: #CCD6F6;">
                            {llm_table_rows}
                        </tbody>
                    </table>
                    """, unsafe_allow_html=True)

                # --- Tool Execution Table ---
                if tool_execs:
                    st.markdown("##### 🔧 Tool Execution Details")
                    tool_table_rows = ""
                    for te in tool_execs:
                        tname = te.get("tool", "—")
                        tdur = te.get("duration_s", 0)
                        tstatus = te.get("status", "—")
                        ttask = te.get("task_id", "—")
                        status_color = "#05C46B" if tstatus == "success" else "#FF5E57"
                        tool_table_rows += f"<tr><td>{tname}</td><td>{ttask}</td><td>{tdur:.3f}s</td><td><span style='color:{status_color}; font-weight:bold;'>{tstatus.upper()}</span></td></tr>"
                    
                    st.markdown(f"""
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                        <thead>
                            <tr style="border-bottom: 2px solid rgba(255,255,255,0.15); color: #FFC837;">
                                <th style="text-align: left; padding: 6px;">Tool</th>
                                <th style="text-align: left; padding: 6px;">Task</th>
                                <th style="text-align: left; padding: 6px;">Duration</th>
                                <th style="text-align: left; padding: 6px;">Status</th>
                            </tr>
                        </thead>
                        <tbody style="color: #CCD6F6;">
                            {tool_table_rows}
                        </tbody>
                    </table>
                    """, unsafe_allow_html=True)

                # --- Embedding Calls ---
                if embed_calls:
                    st.markdown("##### 📐 Embedding API Calls")
                    for ec in embed_calls:
                        purpose = ec.get("purpose", "—")
                        edur = ec.get("duration_s", 0)
                        emodel = ec.get("model", "—")
                        st.markdown(f"- **{emodel}** — {purpose} (`{edur:.3f}s`)")
    else:
        st.info("Run a query to view execution traces and audit checks in real-time.")
