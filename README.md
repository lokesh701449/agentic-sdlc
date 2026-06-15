# AgenticSDLC

AI-powered multi-agent Software Development Life Cycle (SDLC) automation system that converts natural language requirements into structured engineering workflows, autonomous code generation pipelines, runtime validation, testing, and workflow orchestration.

---

# Features

- Multi-Agent AI Architecture
- Requirement Analysis & Task Planning
- Autonomous Code Generation
- Runtime Validation
- Human Approval Workflow
- Workflow State Persistence
- Task Dependency Management
- AI-powered Testing & Review
- Retry & Rate-Limit Stabilization
- Modular Backend Architecture
- SQLite Workflow Memory
- Async Workflow Execution

---

# Architecture

```text
User Requirement
        ↓
Planner Agent
        ↓
Human Approval
        ↓
Coding Agent
        ↓
Testing Agent
        ↓
Review Agent
        ↓
Monitoring Agent
        ↓
Runtime Validation
        ↓
Generated Project Files
```

---

# Tech Stack

## Backend
- Python
- FastAPI
- AsyncIO
- SQLite

## AI / GenAI
- Gemini API
- Prompt Engineering
- Multi-Agent Systems
- Workflow Orchestration

## Validation & Testing
- Runtime Validation
- Dynamic Module Loading
- Automated Testing Pipelines

---

# AI Agents

## Planner Agent
Converts natural language requirements into structured engineering tasks with dependencies and acceptance criteria.

## Coding Agent
Generates modular backend code, APIs, services, database models, and project structures using LLMs.

## Testing Agent
Creates validation workflows and executes runtime verification for generated code.

## Review Agent
Reviews generated outputs for structural and quality validation.

## Monitoring Agent
Tracks orchestration execution, workflow state transitions, retries, and failures.

---

# Human-in-the-Loop Approval

The workflow pauses after planning and asks the user to approve or reject the generated engineering plan before code generation begins.

---

# Runtime Validation

Generated Python modules are dynamically imported and executed to validate:
- Syntax correctness
- Import resolution
- Runtime execution
- Module integrity

---

# Workflow Features

- Task dependency execution
- Async orchestration pipeline
- Workflow persistence
- Rate-limit stabilization
- Exponential backoff retries
- Intelligent task caching
- Structured orchestration summaries

---

# Project Structure

```text
backend/
│
├── agents/
│   ├── planner.py
│   ├── coder.py
│   ├── tester.py
│   ├── reviewer.py
│   └── monitoring.py
│
├── orchestrator/
│   ├── workflow.py
│   └── workflow_orchestrator.py
│
├── memory/
│   └── workflow_memory.py
│
├── llm/
│   ├── base_client.py
│   └── gemini_client.py
│
├── generated_projects/
│
├── requirements.txt
└── main.py
```

---

# Setup

## Clone Repository

```bash
git clone https://github.com/lokesh701449/agentic-sdlc.git
cd agentic-sdlc
```

---

## Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment Variables

Create `.env`

```env
GEMINI_API_KEY=your_api_key
GEMINI_MODEL_NAME=gemini-3.5-flash
GEMINI_USE_MOCK_FALLBACK=false
```

---

# Run Workflow Verification

```bash
./venv/bin/python backend/orchestrator/workflow.py
```

---

# Example Requirement

```text
Build a Proof-of-Concept full-stack application using Next.js frontend and Node.js backend with authentication, APIs, modular architecture, and runtime validation.
```

---

# Sample Output

```json
{
  "workflow_status": "completed",
  "db_validation": "success",
  "runtime_validation": "success"
}
```

---

# Future Improvements

- Next.js frontend generation
- Docker sandbox execution
- LangGraph integration
- Kubernetes deployment
- Vector database memory
- RAG-enhanced planning
- Autonomous debugging loops

---

# Author

Lokesh Chalasani
