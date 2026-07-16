# 🏭 AutoPlan AI — Agentic Decision Support System

AutoPlan AI is a premium multi-agent decision support platform built for manufacturing and assembly operations (using a Maruti Suzuki capacity planning use case). It translates natural language operational requests (e.g., *"What happens if we increase Brezza demand by 15%?"*) into validated strategic schedules, cost analyses, and resource checklists.

---

## 🚀 Key Features

* **Multi-Agent Collaborative Pipeline**: Uses a stateful LangGraph workflow containing specialized agents:
  * **Router**: Classifies queries into planning vs. general conversational paths.
  * **Query Planner**: Decomposes complex directives into ordered, executable sub-tasks.
  * **Native Orchestrator**: Runs ReAct loops executing data tools to satisfy each task.
  * **Strategy Synthesizer**: Aggregates raw execution outputs into a cohesive executive report.
  * **Auditor/Validator**: Automatically verifies proposals against business policies and guardrails.
* **Semantic Tool & Skill Retrieval (RAG)**: Dynamically indexes, embeds, and ranks tools/expert personas relevant to queries using `text-embedding-004` to minimize prompt bloat.
* **Real-time Performance Diagnostics**: Embedded dashboard showing total latency, individual LLM inference round-trips, tool executables, and a node execution waterfall chart.
* **Dual-Layer Caching**: Persistent JSON caching for vector embeddings and in-memory session caching to optimize speed and API costs.

---

## 📁 Directory Structure

```
maruti-iteration-1/
├── app/                  # Application layer (FastAPI, Streamlit frontend, datasets)
├── framework/            # Core agent, state, memory, and tool registry packages
├── agents/               # Individual agent node definitions (Router, Orchestrator, etc.)
├── tools/                # Executable data loaders, scrapers, and analytics tools
├── skills/               # Expert system prompts (production analyst, finance expert)
├── prompts/              # System prompt files for workflow coordination
├── guardrails/           # Policy and safety constraint validation documents
├── tests/                # Automated pytest suite
├── run_cli.py            # Interactive CLI REPL console
└── render_report.py      # Script compiling project markdown specifications to HTML
```

---

## 🛠️ Setup & Installation

### 1. Prerequisites
* Python 3.11 or higher
* Google GenAI API Key (Gemini)

### 2. Install Dependencies
Set up your virtual environment and install the required modules:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

---

## 🖥️ Running the Application

### Option A: Interactive CLI Terminal
Start the command-line REPL session:
```bash
venv\Scripts\python run_cli.py
```

### Option B: Streamlit Dashboard (with Diagnostics)
Launch the web interface (serves at [http://localhost:8501](http://localhost:8501)):
```bash
venv\Scripts\streamlit run app\frontend\streamlit_app.py
```

---

## 📊 Viewing the Architecture Report

We have created an interactive HTML report highlighting the technical design and flowcharts.

1. Compile the report:
   ```bash
   venv\Scripts\python render_report.py
   ```
2. Open the generated [project_report_rendered.html](project_report_rendered.html) in your browser. It includes a collapsible table of contents, professional light/dark theme toggles, and live-rendered Mermaid diagrams.
