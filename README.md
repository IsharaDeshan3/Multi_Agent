# Multi-Agent Research Review (LangGraph)

This project currently implements the parser stage of a sequential multi-agent system (MAS) for academic paper review using LangGraph.

## Architecture

Current implementation:
1. Parser (Leader)

Auditor, Critic, and Integrator are intentionally left for other team members.

All stages operate on one shared state contract: ReviewState.

## Governance Rules

1. State contract is mandatory. Agents must accept ReviewState and return ReviewState.
2. No arbitrary payload passing between agents.
3. Every agent must append at least one message to state.logs for observability.
4. Every tool function must include docstrings and type hints.
5. Every teammate must add one test file in tests/ named test_agent_x.py.
6. Do not use global mutable variables in agent modules.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. (Optional for live extraction) start Ollama and pull a model.

```bash
ollama pull llama3.1
```

4. Run the API server.

```bash
uvicorn src.api.server:app --reload
```

## Endpoints for Team Development

1. GET /api/v1/health
2. GET /api/v1/contracts/review-state
3. GET /api/v1/agents
4. POST /api/v1/agents/{agent_name}/execute
5. POST /api/v1/pipelines/review/execute
6. POST /api/v1/pipelines/review/execute-until/{stage}
7. POST /api/v1/pipelines/review/resume-from/{stage}

## Handshake for Teammates

I have built the Parser Node. Your node must accept ReviewState as input and return ReviewState as output. Do not save global variables.

## Project Structure

- src/state.py: shared state contract
- src/tools.py: shared tools (typed + documented)
- src/agents/: parser + teammate agent modules
- src/workflow/main.py: LangGraph orchestrator
- src/api/: FastAPI routes
- tests/: unit and integration tests
- docs/PLAN.md: master implementation plan
