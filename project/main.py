import re
import sqlite3
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from vanna.core.user import RequestContext
from vanna_setup import build_agent, agent_memory, DB_PATH

# Lifespan: build agent once at startup 
agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    print("🚀 Starting Vanna 2.0 Agent...")
    agent = build_agent()

    # Seed memory at startup so it's always ready
    from seed_memory import seed
    await seed()

    print("✅ Agent ready.")
    yield
    print("🛑 Shutting down.")

# App 
app = FastAPI(
    title="NL2SQL Clinic API",
    description="Natural Language to SQL system for clinic management",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request / Response schemas
class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    message: str
    sql_query: Optional[str] = None
    columns: Optional[list] = None
    rows: Optional[list] = None
    row_count: Optional[int] = None
    error: Optional[str] = None

# SQL Validation
DANGEROUS_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE|GRANT|REVOKE|SHUTDOWN"
    r"|TRUNCATE|REPLACE|CREATE|xp_|sp_)\b",
    re.IGNORECASE,
)
SYSTEM_TABLES = re.compile(r"\bsqlite_master\b|\bsqlite_temp_master\b", re.IGNORECASE)

def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Returns (is_valid, error_message).
    Empty error_message means valid.
    """
    stripped = sql.strip().upper()

    # Must start with SELECT
    if not stripped.startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    # No dangerous keywords
    if DANGEROUS_KEYWORDS.search(sql):
        return False, "Query contains forbidden keywords."

    # No system tables
    if SYSTEM_TABLES.search(sql):
        return False, "Access to system tables is not allowed."

    return True, ""

# SQL extractor from agent response text
SQL_BLOCK = re.compile(r"```(?:sql)?\s*(SELECT[\s\S]+?)```", re.IGNORECASE)
SQL_BARE  = re.compile(r"(SELECT\s+[\s\S]+?;)", re.IGNORECASE)

def extract_sql(text: str) -> Optional[str]:
    """Pull the first SELECT statement out of the agent's response text."""
    m = SQL_BLOCK.search(text)
    if m:
        return m.group(1).strip()
    m = SQL_BARE.search(text)
    if m:
        return m.group(1).strip()
    # Last resort: everything after 'SELECT'
    idx = text.upper().find("SELECT")
    if idx != -1:
        return text[idx:].strip()
    return None

# Database execution
def run_query(sql: str) -> tuple[list, list]:
    """Execute SQL and return (columns, rows)."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description] if cur.description else []
    rows    = [list(row) for row in cur.fetchall()]
    con.close()
    return columns, rows

async def collect_agent_response(question: str) -> str:
    ctx = RequestContext(
        metadata={"user_id": "default_user", "source": "api"}
    )
    parts = []
    async for component in agent.send_message(
        request_context=ctx,
        message=question,
    ):
        if component.simple_component and component.simple_component.text:
            parts.append(component.simple_component.text)
    return "\n".join(parts)

# Endpoints

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    question = request.question.strip()

    # Input validation
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="Question too long (max 500 chars).")

    try:
        # 1. Get agent response
        raw_text = await collect_agent_response(question)

        if not raw_text:
            return ChatResponse(
                message="The agent did not return a response. Please rephrase your question.",
                error="Empty agent response",
            )

        # 2. Extract SQL from response
        sql = extract_sql(raw_text)

        if not sql:
            # Agent answered in plain text (e.g. clarification needed)
            return ChatResponse(message=raw_text)

        # 3. Validate SQL before execution
        is_valid, validation_error = validate_sql(sql)
        if not is_valid:
            return ChatResponse(
                message=f"The generated query was rejected: {validation_error}",
                sql_query=sql,
                error=validation_error,
            )

        # 4. Execute SQL
        try:
            columns, rows = run_query(sql)
        except Exception as db_err:
            return ChatResponse(
                message="The query failed to execute. Please rephrase your question.",
                sql_query=sql,
                error=str(db_err),
            )

        # 5. No results
        if not rows:
            return ChatResponse(
                message="No data found for your query.",
                sql_query=sql,
                columns=columns,
                rows=[],
                row_count=0,
            )

        # 6. Build summary
        summary = (
            f"Found {len(rows)} record(s). "
            f"Columns: {', '.join(columns)}."
        )

        return ChatResponse(
            message=summary,
            sql_query=sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )

    except Exception as e:
        return ChatResponse(
            message="An unexpected error occurred.",
            error=str(e),
        )


@app.get("/health")
async def health():
    # Check DB connection
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("SELECT 1")
        con.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Count seeded memory items
    memory_items = len(agent_memory._memories) if agent_memory else 0

    return {
        "status": "ok",
        "database": db_status,
        "agent_memory_items": memory_items,
    }