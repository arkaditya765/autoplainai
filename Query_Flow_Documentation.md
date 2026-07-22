# AutoPlan AI — Query Processing Flowchart & Lifecycle Documentation

This document provides a detailed breakdown of the complete lifecycle of a user query in AutoPlan AI. It documents every file, class, and function triggered, from the initial user input down to local CSV data fetches and LLM validation checks.

---

## 1. Complete Query Flow Diagram (Mermaid)

```mermaid
flowchart TD
    %% User Input Layer
    Start([User Query Input]) -->|CLI: run_cli.py| CLI["run_cli.py / main()"]
    Start -->|Streamlit: streamlit_app.py| GUI["streamlit_app.py / main()"]

    %% App Core Orchestrator
    CLI -->|Calls| AppRun["AutoPlanApp.run_query(query)"]
    GUI -->|Calls| AppRun
    
    subgraph AppOrchestration ["File: app/app.py"]
        AppRun --> AppInit["Initialize AgentState / create_initial_state()"]
        AppInit --> RunIndex["Build vector index of tools & skills / build_index()"]
        RunIndex --> RetrieveTools["ToolRetriever.retrieve()"]
        RetrieveTools --> InvokeGraph["workflow.invoke(state)"]
    end

    %% RAG Retrieval Layer
    subgraph RAGRetrieval ["File: framework/registry/retriever.py"]
        RetrieveTools -->|Embed query| EmbedCall["GeminiClient.embed(text)"]
        EmbedCall -->|Cosine Similarity| FilterTools["Filter & select top-5 tools"]
        FilterTools -->|Update state| AvailTools["state['available_tools']"]
    end

    %% LangGraph Routing Workflow
    InvokeGraph -->|Route to| GraphStart["framework/workflow/graph.py"]
    
    subgraph RoutingWorkflow ["File: framework/workflow/graph.py"]
        GraphStart -->|Node 1| RouterNode["RouterAgentNode"]
        RouterNode -->|Conditional Route| RouterDecision{"route_query(state)"}
    end

    %% Router Agent Decision
    subgraph RouterAgent ["File: agents/router_agent.py"]
        RouterNode -->|Calls| RouterRun["RouterAgent.run()"]
        RouterRun -->|LLM Structured Route| RouterLLM["GeminiClient.generate_structured(..., schema=RouteDecision)"]
        RouterLLM -->|Sets| StateRoute["state['route_decision']"]
    end

    %% Path A: General Chatbot
    RouterDecision -->|category == 'general'| ChatbotNode["ChatbotAgentNode"]
    subgraph ChatbotAgent ["File: agents/chatbot_agent.py"]
        ChatbotNode -->|Calls| ChatbotRun["ChatbotAgent.run()"]
        ChatbotRun -->|ReAct Turn Loop| ChatbotLLM["GeminiClient.generate()"]
        ChatbotLLM -->|Parallel Tool Execution| ChatbotExec["ThreadPoolExecutor / self._execute_single_tool()"]
    end
    ChatbotExec --> StrategyNode

    %% Path B: Planning Pipeline
    RouterDecision -->|category == 'planning'| PlannerNode["QueryPlannerNode"]
    subgraph QueryPlanner ["File: agents/query_planner.py"]
        PlannerNode -->|Calls| PlannerRun["QueryPlannerAgent.run()"]
        PlannerRun -->|LLM Structured Decompose| PlannerLLM["GeminiClient.generate_structured(..., schema=ExecutionPlan)"]
        PlannerLLM -->|Sets| StatePlan["state['execution_plan']"]
    end

    %% Orchestrator Node
    StatePlan -->|Route to| OrchestratorNode["NativeOrchestratorNode"]
    
    subgraph NativeOrchestrator ["File: agents/native_orchestrator_agent.py"]
        OrchestratorNode -->|Calls| OrchRun["NativeOrchestratorAgent.run()"]
        OrchRun -->|1. Topological Batching| BatchLoop["Identify ready tasks (met dependencies)"]
        
        %% Cascade Failure Path
        BatchLoop -->|Dependency Failed| FailureProp["Propagate downstream task failures to failed_tasks"]
        
        %% Parallel Execution Path
        BatchLoop -->|Submit tasks| ThreadExec["ThreadPoolExecutor / run_task_in_thread()"]
        
        subgraph WorkerThread ["Worker Thread Scope"]
            ThreadExec -->|2. Safe Read| ReadLock["Acquire state_lock (Mutex) & Snapshot State variables"]
            ReadLock -->|3. ReAct loop| TaskLLM["GeminiClient.generate(..., temperature=0.0)"]
            TaskLLM -->|4. Parallel Tools| ToolsExec["ThreadPoolExecutor / self._execute_single_tool()"]
            ToolsExec -->|5. Local Accumulate| Accumulate["Save results to stack variables"]
            Accumulate -->|6. Safe Write| WriteLock["Acquire state_lock (Mutex) & Merge results, traces, adjustments"]
        end
    end

    %% Tools execution layer
    ToolsExec -->|Call tool| ToolPkg["tools/ package"]
    subgraph ToolsPackage ["Package: tools/"]
        ToolPkg -->|capacity_tool.py| ToolCap["CapacityTool.execute() -> Reads app/data/vehicles.csv"]
        ToolPkg -->|cost_tool.py| ToolCost["CostTool.execute() -> Reads app/data/costs.csv"]
        ToolPkg -->|inventory_tool.py| ToolInv["InventoryTool.execute() -> Reads app/data/inventory.csv"]
        ToolPkg -->|supplier_tool.py| ToolSup["SupplierTool.execute() -> Reads app/data/suppliers.csv"]
        ToolPkg -->|search_tool.py| ToolSearch["SearchTool.execute() -> Runs Google search query"]
        ToolPkg -->|load_skill_tool.py| ToolSkill["LoadSkillTool.execute() -> Dynamically loads skills/"]
    end
    ToolCap --> Accumulate
    ToolCost --> Accumulate
    ToolInv --> Accumulate
    ToolSup --> Accumulate
    ToolSearch --> Accumulate
    ToolSkill --> Accumulate

    %% Strategy Aggregator Node
    WriteLock -->|Batch Complete / Route to| StrategyNode["StrategyNode"]
    subgraph StrategyAgent ["File: agents/strategy_agent.py"]
        StrategyNode -->|Calls| StrategyRun["StrategyAgent.run()"]
        StrategyRun -->|Read gathered metrics| StratRead["Gather state.tool_outputs & state.context"]
        StratRead -->|LLM Synthesis| StrategyLLM["GeminiClient.generate(..., temperature=0.4)"]
        StrategyLLM -->|Sets| StateStrategy["state['response'] & state['strategy_report']"]
    end

    %% Validator Guardrails Node
    StateStrategy -->|Route to| ValidatorNode["ValidatorNode"]
    subgraph ValidatorAgent ["File: agents/validator_agent.py"]
        ValidatorNode -->|Calls| ValidatorRun["ValidatorAgent.run()"]
        ValidatorRun -->|Read business rules| AuditPolicy["Load guardrails/production_policy.txt"]
        AuditPolicy -->|LLM Audit check| ValidatorLLM["GeminiClient.generate_structured(..., schema=ValidationResult)"]
        ValidatorLLM -->|Sets| StateAudit["state['validation']"]
    end

    %% Loop / Exit Decision
    StateAudit --> AuditDecision{"Is validation PASSED?"}
    AuditDecision -->|"No (Violated) and attempts < 3"| StrategyNode
    AuditDecision -->|"Yes (Passed) or Max attempts reached"| End([Output Final Strategy Response])

    %% Custom Client Layer
    RouterLLM -->|Thread-safe API call| ClientLock["File: framework/llm/gemini_client.py\nAcquire self._lock Mutex"]
    PlannerLLM --> ClientLock
    TaskLLM --> ClientLock
    StrategyLLM --> ClientLock
    ValidatorLLM --> ClientLock
    EmbedCall --> ClientLock
    
    ClientLock -->|Invoke| GeminiAPI["Google Gemini GenAI SDK endpoints"]
    GeminiAPI --> ClientLock
```

---

## 2. File-by-File & Function-by-Function Flow Details

### Phase 1: Entry Point & Initialization
1.  **File**: [run_cli.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/run_cli.py)
    *   **Function**: `main()`
        *   Instantiates `app = AutoPlanApp()`.
        *   Accepts user text input query inside a REPL loop.
        *   Invokes `app.run_query(query)`.
2.  **File**: [streamlit_app.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/app/frontend/streamlit_app.py)
    *   **Function**: `main()`
        *   Renders the Streamlit frontend.
        *   On button click, instantiates `app = AutoPlanApp()` and invokes `app.run_query(query)`.
3.  **File**: [app.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/app/app.py)
    *   **Function**: `AutoPlanApp.run_query(query)`
        *   Calls `create_initial_state(query)` from `framework.state.state` to initialize the blackboard `AgentState` dictionary.
        *   Triggers `self.tool_retriever.build_index()` and `self.skill_retriever.build_index()` to scan registered tools and local skills files.
        *   Invokes `self.tool_retriever.retrieve(query)` to embed the query (via `GeminiClient.embed`) and calculate cosine similarity rankings against tool metadata. Stores the top 5 match parameters into `state["available_tools"]`.
        *   Compiles and invokes the LangGraph state machine: `self.workflow.invoke(state)`.

---

### Phase 2: Router Agent
1.  **File**: [graph.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/framework/workflow/graph.py)
    *   Directs initial state execution to the `router` node.
2.  **File**: [router_agent.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/agents/router_agent.py)
    *   **Function**: `RouterAgent.run(state)`
        *   Constructs a classification prompt containing the user query and available tools.
        *   Calls `GeminiClient.generate_structured(..., response_schema=RouteDecision)` to select the optimal path: `"planning"` (multi-task planning pipeline) or `"general"` (general chatbot conversation).
        *   Writes the output back to `state["route_decision"]`.
3.  **File**: [graph.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/framework/workflow/graph.py)
    *   **Function**: `route_query(state)` (conditional router)
        *   Checks `state["route_decision"].category`.
        *   If `"planning"`, routes state to `planner` node.
        *   If `"general"`, routes state to `chatbot` node.

---

### Phase 3: Path A — General Chatbot Agent (Fallback/Direct)
1.  **File**: [chatbot_agent.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/agents/chatbot_agent.py)
    *   **Function**: `ChatbotAgent.run(state)`
        *   Runs a ReAct turn loop using `GeminiClient.generate()` to generate natural reasoning and tool calls.
        *   If Gemini requests tool calls, dispatches them in parallel using a local `ThreadPoolExecutor` and merges their outcomes before the next reasoning turn.
        *   Bypasses task scheduling and routes state directly to the final `strategy` node.

---

### Phase 4: Path B — Query Planner Agent
1.  **File**: [query_planner.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/agents/query_planner.py)
    *   **Function**: `QueryPlannerAgent.run(state)`
        *   Loads the system instructions explaining decomposition conventions.
        *   Calls `GeminiClient.generate_structured(..., response_schema=ExecutionPlan)`.
        *   The model returns a structured execution plan containing a list of sub-tasks, priorities, and dependency parameters (`depends_on` containing prerequisite task IDs).
        *   Saves the plan to `state["execution_plan"]` and directs state to `orchestrator` node.

---

### Phase 5: Native Orchestrator Agent (Topological Scheduler)
1.  **File**: [native_orchestrator_agent.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/agents/native_orchestrator_agent.py)
    *   **Function**: `NativeOrchestratorAgent.run(state)`
        *   Enters the topological batching scheduling loop.
        *   *Check Loop Step*: Identifies pending tasks where all prerequisite task IDs in `depends_on` are present in the `completed_tasks` list.
        *   *Cascade Failure Step*: If any prerequisite task is in `failed_tasks`, the target task status is instantly updated to `"failed"` with a dependency check failure notification, and is added to `failed_tasks` without starting an execution thread.
        *   *ThreadPool Execution Step*: Ready tasks are submitted to a `ThreadPoolExecutor` and executed concurrently by running `run_task_in_thread(task)`.
    *   **Function**: `run_task_in_thread(task)` (Concurrently executed)
        *   **Acquires `state_lock`**: Performs a thread-safe read of state variables, updates task status to `"running"`, and snapshots the current context variables and prior task results.
        *   **Formulates Prompt**: Appends preceding task results to focus the ReAct loop on this task's specific goals.
        *   **ReAct Loop Execution**: Iteratively generates reasoning and tool calls via `GeminiClient.generate()`.
            *   *Tool Calling Concurrency*: Multiple tool calls requested in a single model turn are executed concurrently via another local `ThreadPoolExecutor` calling `self._execute_single_tool()`.
            *   *Local Accumulator*: Tool outputs, durations, execution traces, and context modifications are appended to thread-local stack variables.
        *   **Acquires `state_lock`**: Merges local traces, diagnostics, and context variables back into global shared structures. Vehicle-specific production `adjustments` are mapped by vehicle name to merge updates without losing concurrent edits.

---

### Phase 6: Core Tools Execution
1.  **File**: `tools/` directory
    *   **Function**: `ToolClass.execute(state)` (called by `_execute_single_tool`)
        *   **Capacity Tool** ([capacity_tool.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/tools/capacity_tool.py)): Reads vehicle capacities from [vehicles.csv](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/app/data/vehicles.csv) to evaluate assembly lines.
        *   **Cost Tool** ([cost_tool.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/tools/cost_tool.py)): Reads manufacturing costs from [costs.csv](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/app/data/costs.csv) to compute part expenses.
        *   **Inventory Tool** ([inventory_tool.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/tools/inventory_tool.py)): Reads warehouse balances from [inventory.csv](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/app/data/inventory.csv) to extract vehicle stock status.
        *   **Supplier Tool** ([supplier_tool.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/tools/supplier_tool.py)): Reads parts limitations from [suppliers.csv](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/app/data/suppliers.csv) to check parts thresholds.
        *   **Search Tool** ([search_tool.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/tools/search_tool.py)): Executes a search query via Google search wrapper.
        *   **Load Skill Tool** ([load_skill_tool.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/tools/load_skill_tool.py)): Evaluates active task parameters, queries the `SkillRetriever` to select the best match, and loads the skill files under `skills/` directly into the agent context.

---

### Phase 7: Strategy Agent
1.  **File**: [strategy_agent.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/agents/strategy_agent.py)
    *   **Function**: `StrategyAgent.run(state)`
        *   Gathers all data collected by orchestrator tasks (`state["tool_outputs"]` and context updates).
        *   Invokes `GeminiClient.generate()` to formulate a final manufacturing decision support plan (including production changes, supplier audits, and safety summaries).
        *   Writes the output report to `state["response"]` and `state["strategy_report"]`.

---x    

### Phase 8: Validator Agent
1.  **File**: [validator_agent.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/agents/validator_agent.py)
    *   **Function**: `ValidatorAgent.run(state)`
        *   Loads the manufacturing policy guidelines from [production_policy.txt](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/guardrails/production_policy.txt).
        *   Calls `GeminiClient.generate_structured(..., response_schema=ValidationResult)`.
        *   The model checks the strategy report against the business policies (such as limits on overtime, safety checks, and supplier minimums).
        *   Writes the status and safety violations to `state["validation"]`.
2.  **File**: [graph.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/framework/workflow/graph.py)
    *   **Function**: `check_validation(state)` (conditional router)
        *   Evaluates `state["validation"].status`.
        *   If `"FAILED"` and validation attempts < 3, routes state **back to the `strategy` node** to correct violations using audit feedback.
        *   If `"PASSED"` or maximum validation attempts are reached, routes state to the **end node**, completing the query lifecycle.

---

### Support Layer: Gemini API Client
1.  **File**: [gemini_client.py](file:///c:/Users/hazo7/Downloads/maruti%20iteration%201/framework/llm/gemini_client.py)
    *   All LLM interactions pass through this wrapper.
    *   **Function**: `generate(...)` / `generate_structured(...)` / `embed(...)`
        *   **Locking Step**: Acquires `self._lock` when reading/writing embedding cache (`self._embedding_cache`) and appending call metrics to `self._call_log` to prevent race conditions during concurrent task executions.
        *   **Invocation Step**: Calls the Google GenAI SDK `client.models.generate_content` using the active model (such as `gemini-flash-lite-latest`).
