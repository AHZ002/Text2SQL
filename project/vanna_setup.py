import os
import sqlite3
from dotenv import load_dotenv

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user.resolver import UserResolver as BaseUserResolver
from vanna.core.user import User
from vanna.core.system_prompt.default import DefaultSystemPromptBuilder
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
)
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.openai import OpenAILlmService

load_dotenv()

# config
DB_PATH       = "clinic.db"
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL    = "llama-3.3-70b-versatile"

# Module-level memory — shared with seed_memory.py
agent_memory = DemoAgentMemory()


def get_schema_prompt() -> str:
    """Read the live schema from clinic.db and format it for the system prompt."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    schema_lines = [
        "You are Vanna, an AI data analyst for a clinic management system.",
        "You have access to a SQLite database called clinic.db with the following schema:",
        "",
    ]

    for table in tables:
        cur.execute(f"PRAGMA table_info({table})")
        columns = cur.fetchall()
        col_defs = ", ".join(
            f"{col[1]} {col[2]}" for col in columns
        )
        schema_lines.append(f"Table: {table}")
        schema_lines.append(f"  Columns: {col_defs}")
        schema_lines.append("")

    con.close()

    schema_lines += [
        "Rules:" ,
        "- ALWAYS use the run_sql tool to answer data questions. Never make up numbers.",
        "- Only generate SELECT queries — never INSERT, UPDATE, DELETE, or DROP.",
        "- Use proper SQLite syntax (use strftime() for date functions).",
        "- Before running SQL, call search_saved_correct_tool_uses to check memory.",
        "- After a successful query, call save_question_tool_args to save the pattern.",
        "- When query results are returned, summarize them clearly for the user.",
        "- Today's date context: use date('now') for current date in SQLite.",
        "- Invoice status values are exactly: 'Paid', 'Pending', 'Overdue' (case sensitive).",
        "- Appointment status values are exactly: 'Scheduled', 'Completed', 'Cancelled', 'No-Show' (case sensitive).",
        "- For 'unpaid invoices' use: status IN ('Pending', 'Overdue')",
        "- For 'no-show' appointments use: status = 'No-Show'",
        "- strftime('%w') returns 0=Sunday, 1=Monday ... 6=Saturday as text strings.",
    ]

    return "\n".join(schema_lines)


def build_agent() -> Agent:
    """Assemble and return a fully configured Vanna 2.0 Agent."""

    # 1. LLM — Groq via OpenAI-compatible endpoint
    llm_service = OpenAILlmService(
        api_key=GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
        model=GROQ_MODEL,
    )

    # 2.  SQLite Runner
    sql_runner = SqliteRunner(database_path=DB_PATH)

    # 3. Tools
    run_sql_tool   = RunSqlTool(sql_runner=sql_runner)
    visualize_tool = VisualizeDataTool()
    save_tool      = SaveQuestionToolArgsTool()
    search_tool    = SearchSavedCorrectToolUsesTool()

    # 4. Tool Registry
    registry = ToolRegistry()
    registry.register_local_tool(run_sql_tool,   access_groups=["user", "admin"])
    registry.register_local_tool(visualize_tool, access_groups=["user", "admin"])
    registry.register_local_tool(save_tool,      access_groups=["user", "admin"])
    registry.register_local_tool(search_tool,    access_groups=["user", "admin"])

    # 5. User Resolver
    class DefaultUserResolver(BaseUserResolver):
        async def resolve_user(self, *args, **kwargs):
            return User(id="default_user", name="Clinic User")

    # 6. System Prompt — inject full schema so agent knows our tables
    system_prompt_builder = DefaultSystemPromptBuilder(
        base_prompt=get_schema_prompt()
    )

    # 7. Agent Config
    config = AgentConfig(
        stream_responses=False,
        max_tool_iterations=10,
        temperature=0.2,
    )

    # 8. Assemble Agent
    agent = Agent(
        llm_service=llm_service,
        tool_registry=registry,
        user_resolver=DefaultUserResolver(),
        agent_memory=agent_memory,
        system_prompt_builder=system_prompt_builder,
        config=config,
    )

    return agent