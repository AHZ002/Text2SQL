# NL2SQL Clinic System — Cogninest AI Assignment

A Natural Language to SQL (NL2SQL) chatbot built with **Vanna AI 2.0** and **FastAPI**.
Users ask questions in plain English and get real data from a clinic database — no SQL required.

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Backend language |
| Vanna AI | 2.0.2 | NL2SQL Agent |
| FastAPI | Latest | REST API framework |
| SQLite | Built-in | Database |
| Groq (llama-3.3-70b) | Free tier | LLM for SQL generation |
| Plotly | Latest | Chart generation |
| SlowAPI | Latest | Rate limiting |

---

## Architecture Overview

    User Question (English)
            |
            v
      FastAPI /chat endpoint
      (Input validation: empty check, length check, rate limit 20/min)
            |
            v
      Vanna 2.0 Agent
      ├── OpenAILlmService → Groq API (llama-3.3-70b-versatile)
      ├── DemoAgentMemory (15 pre-seeded Q&A pairs)
      ├── SearchSavedCorrectToolUsesTool (checks memory first)
      ├── RunSqlTool → SqliteRunner → clinic.db
      ├── VisualizeDataTool
      └── SaveQuestionToolArgsTool (saves successful patterns)
            |
            v
      SQL Validation
      (SELECT only, no dangerous keywords, no system tables)
            |
            v
      SQLite Execution
            |
            v
      Plotly Chart Generation (bar or line, auto-detected)
            |
            v
      JSON Response → User

---

## Project Structure

    project/
    ├── setup_database.py   → Creates schema + inserts dummy data
    ├── seed_memory.py      → Seeds 15 Q&A pairs into agent memory
    ├── vanna_setup.py      → Vanna 2.0 Agent initialization
    ├── main.py             → FastAPI application
    ├── test_questions.py   → 20-question automated test script
    ├── requirements.txt    → All dependencies
    ├── README.md           → This file
    ├── RESULTS.md          → Test results for all 20 questions
    └── clinic.db           → Generated SQLite database

---

## Setup Instructions

### 1. Clone the repository

    git clone https://github.com/YOUR_USERNAME/nl2sql-cogninest.git
    cd nl2sql-cogninest/project

### 2. Create and activate virtual environment

    python -m venv venv

    # Windows
    venv\Scripts\activate

    # macOS / Linux
    source venv/bin/activate

### 3. Install dependencies

    pip install -r requirements.txt

### 4. Set up environment variables

Create a `.env` file inside the `project/` folder:

    GROQ_API_KEY=your-groq-api-key-here

Get a free Groq API key at: https://console.groq.com

### 5. Create the database

    python setup_database.py

Expected output:

    Database created: clinic.db
       Doctors      : 15
       Patients     : 200
       Appointments : 500
       Treatments   : 350
       Invoices     : 300

### 6. Start the API server

    uvicorn main:app --port 8000 --reload

Agent memory is automatically seeded with 15 Q&A pairs at startup.

- Server runs at: http://localhost:8000
- API docs at: http://localhost:8000/docs

---

## One-Command Setup

    pip install -r requirements.txt && python setup_database.py && python seed_memory.py && uvicorn main:app --port 8000

---

## API Documentation

### POST /chat

Ask a question in plain English.

**Request:**

    {
      "question": "Show me the top 5 patients by total spending"
    }

**Response:**

    {
      "message": "Found 5 record(s). Columns: first_name, last_name, total_spending.",
      "sql_query": "SELECT p.first_name, p.last_name, SUM(i.total_amount) ...",
      "columns": ["first_name", "last_name", "total_spending"],
      "rows": [["John", "Smith", 4500.0]],
      "row_count": 5,
      "chart": {"data": [...], "layout": {...}},
      "chart_type": "bar",
      "error": null
    }

Rate limit: 20 requests/minute per IP

---

### GET /health

Check server and database status.

**Response:**

    {
      "status": "ok",
      "database": "connected",
      "agent_memory_items": 15
    }

---

## SQL Safety

All AI-generated SQL is validated before execution:

- SELECT only — INSERT, UPDATE, DELETE, DROP are rejected
- No dangerous keywords (EXEC, GRANT, SHUTDOWN, TRUNCATE etc.)
- No system table access (sqlite_master)
- No function-call syntax used as table source

---

## LLM Provider

This project uses **Groq (llama-3.3-70b-versatile)** via Vanna's OpenAI-compatible
integration. Groq exposes an OpenAI-compatible API, so we point `OpenAILlmService`
at Groq's endpoint — no separate Groq SDK needed inside Vanna.

---

## Bonus Features

- Chart generation — Plotly bar/line charts in every multi-row response
- Input validation — empty and >500 char questions rejected
- Rate limiting — 20 requests/minute per IP via SlowAPI
- Structured logging — every step logged with timestamp and level

---

## Test Results

See [RESULTS.md](project/RESULTS.md) — **20/20 questions passed**.