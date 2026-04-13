import re
import sqlite3
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional
import json

import pandas as pd
import plotly.express as px
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from vanna.core.user import RequestContext
from vanna_setup import build_agent, agent_memory, DB_PATH

# Logging setup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nl2sql")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Lifespan
agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    logger.info("Starting Vanna 2.0 Agent...")
    agent = build_agent()
    from seed_memory import seed
    await seed()
    logger.info("Agent ready.")
    yield
    logger.info("Shutting down.")

# App
app = FastAPI(
    title="NL2SQL Clinic API",
    description="Natural Language to SQL system for clinic management",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schemas
class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    message: str
    sql_query: Optional[str] = None
    columns: Optional[list] = None
    rows: Optional[list] = None
    row_count: Optional[int] = None
    chart: Optional[dict] = None
    chart_type: Optional[str] = None
    error: Optional[str] = None

# SQL Validation
DANGEROUS_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE|GRANT|REVOKE|SHUTDOWN"
    r"|TRUNCATE|REPLACE|CREATE|xp_|sp_)\b",
    re.IGNORECASE,
)
SYSTEM_TABLES = re.compile(
    r"\bsqlite_master\b|\bsqlite_temp_master\b",
    re.IGNORECASE,
)

# Real tables in our database
VALID_TABLES = {"patients", "doctors", "appointments", "treatments", "invoices"}

def validate_sql(sql: str) -> tuple[bool, str]:
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

    # Reject tool call syntax masquerading as SQL
    if re.search(r"FROM\s+\w+\s*\(", sql, re.IGNORECASE):
        return False, "Invalid SQL — function calls are not allowed as table sources."

    return True, ""

# SQL extractor
SQL_BLOCK = re.compile(r"```(?:sql)?\s*(SELECT[\s\S]+?)```", re.IGNORECASE)
SQL_BARE  = re.compile(r"(SELECT\s+[\s\S]+?;)", re.IGNORECASE)

def extract_sql(text: str) -> Optional[str]:
    m = SQL_BLOCK.search(text)
    if m:
        return m.group(1).strip()
    m = SQL_BARE.search(text)
    if m:
        return m.group(1).strip()
    idx = text.upper().find("SELECT")
    if idx != -1:
        return text[idx:].strip()
    return None

# Database execution
def run_query(sql: str) -> tuple[list, list]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description] if cur.description else []
    rows    = [list(row) for row in cur.fetchall()]
    con.close()
    return columns, rows

# Chart generation 
def generate_chart(columns: list, rows: list) -> tuple[Optional[dict], Optional[str]]:
    """
    Auto-generate a Plotly chart from query results.
    Returns (chart_json, chart_type) or (None, None) if not applicable.
    """
    if not rows or not columns or len(columns) < 2:
        return None, None

    try:
        df = pd.DataFrame(rows, columns=columns)

        # Identify numeric columns
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        text_cols    = df.select_dtypes(exclude="number").columns.tolist()

        if not numeric_cols:
            return None, None

        x_col = text_cols[0]  if text_cols  else columns[0]
        y_col = numeric_cols[0]

        # Choose chart type based on column name hints
        col_names_lower = " ".join(columns).lower()
        if any(w in col_names_lower for w in ["month", "date", "trend", "time"]):
            fig        = px.line(df, x=x_col, y=y_col, title=f"{y_col} over {x_col}")
            chart_type = "line"
        elif len(rows) == 1:
            # Single value — no chart needed
            return None, None
        else:
            fig        = px.bar(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
            chart_type = "bar"

        # Convert via JSON to eliminate all numpy types
        chart_json = json.loads(fig.to_json())
        return chart_json, chart_type

    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")
        return None, None

# Agent response collector
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
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    question = body.question.strip()
    logger.info(f"Question received: {question}")

    # Input validation
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="Question too long (max 500 chars).")

    try:
        # 1. Get agent response
        raw_text = await collect_agent_response(question)
        logger.info(f"Agent response length: {len(raw_text)} chars")

        if not raw_text:
            return ChatResponse(
                message="The agent did not return a response. Please rephrase.",
                error="Empty agent response",
            )

        # 2. Extract SQL
        sql = extract_sql(raw_text)
        logger.info(f"Extracted SQL: {sql}")

        if not sql:
            return ChatResponse(message=raw_text)

        # 3. Validate SQL
        is_valid, validation_error = validate_sql(sql)
        if not is_valid:
            logger.warning(f"SQL validation failed: {validation_error}")
            return ChatResponse(
                message=f"The generated query was rejected: {validation_error}",
                sql_query=sql,
                error=validation_error,
            )

        # 4. Execute SQL
        try:
            columns, rows = run_query(sql)
            logger.info(f"Query returned {len(rows)} rows")
        except Exception as db_err:
            logger.error(f"Database error: {db_err}")
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

        # 6. Generate chart
        chart, chart_type = generate_chart(columns, rows)

        # 7. Build summary
        summary = f"Found {len(rows)} record(s). Columns: {', '.join(columns)}."
        logger.info(f"Response ready. Rows: {len(rows)}, Chart: {chart_type}")

        return ChatResponse(
            message=summary,
            sql_query=sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            chart=chart,
            chart_type=chart_type,
        )

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return ChatResponse(
            message="An unexpected error occurred.",
            error=str(e),
        )


@app.get("/health")
async def health():
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("SELECT 1")
        con.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    memory_items = len(agent_memory._memories) if agent_memory else 0

    return {
        "status": "ok",
        "database": db_status,
        "agent_memory_items": memory_items,
    }