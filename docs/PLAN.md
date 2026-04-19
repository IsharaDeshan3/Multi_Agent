# Master Implementation Plan (Leader Governance)

## 1. System Architecture: Sequential MAS

The system follows a linear pipeline to keep memory use predictable on local hardware.

Workflow:
1. Parser (Leader): extracts research content.
2. Auditor: validates methodology against schema.
3. Critic: red-teams logic and fallacies.
4. Integrator: synthesizes final critique.

### Governance Rules

1. State Contract: all agents must interact only through ReviewState.
2. Observability: every agent must append to logs in state.
3. Tooling: every tool must include docstrings and type hints.
4. Testing: each member must add a tests/test_agent_x.py file.

## 2. Core Scaffold

### File: src/state.py (Contract)

```python
from typing import TypedDict, List, Dict

class ReviewState(TypedDict):
    """Global state contract for MAS."""
    raw_text: str
    research_data: Dict
    audit_results: Dict
    critique_notes: str
    final_feedback: str
    logs: List[str]
```

### File: src/tools.py (Shared Tools)

Parser tool starts with local file reading. Other members should add tools here.

### File: src/workflow/main.py (Orchestrator)

LangGraph pipeline (sequential): parser -> auditor -> critic -> integrator -> END.

## 3. Leader Component: Parser Agent

Parser responsibilities:
1. Read source text from local input file or state.
2. Extract key sections into research_data.
3. Update raw_text and research_data in ReviewState.
4. Append observability log entry.

## 4. Full Development Plan

### Phase 1: Foundation

1. Initialize Python project and dependencies.
2. Freeze ReviewState schema.
3. Add governance constraints to docs and README.

### Phase 2: Parser-First Runtime

1. Implement parser tools and parser agent.
2. Build workflow scaffold with placeholder teammate nodes.
3. Add state validation boundary checks.

### Phase 3: Team Plug-in Endpoints

Support both endpoint styles.

Agent-centric:
1. GET /api/v1/agents
2. POST /api/v1/agents/{agent_name}/execute

Pipeline-centric:
1. POST /api/v1/pipelines/review/execute
2. POST /api/v1/pipelines/review/execute-until/{stage}
3. POST /api/v1/pipelines/review/resume-from/{stage}

Platform:
1. GET /api/v1/health
2. GET /api/v1/contracts/review-state

### Phase 4: Ollama Integration

1. Use Ollama as local model provider first.
2. Keep minimal provider seam for future model backends.
3. Add mock mode for deterministic testing.

### Phase 5: Test and Handoff

1. Per-agent tests (parser/auditor/critic/integrator).
2. Workflow order and continuity tests.
3. API tests for both endpoint styles.
4. Contributor guide and merge checklist.

## 5. Team Integration Contract

Node function signature:

```python
def some_agent_node(state: ReviewState) -> ReviewState:
    ...
```

Rules:
1. Return valid ReviewState only.
2. Append at least one log entry.
3. No global mutable state.
4. Keep agent logic isolated; use tools for I/O.

## 6. Assignment Checklist

1. Parser node implemented and operational.
2. Workflow compiles with sequential edges.
3. API endpoints available for plug-in development.
4. ReviewState schema published through contract endpoint.
5. Mandatory tests scaffolded for each team member.
