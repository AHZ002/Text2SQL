import os
from typing import Optional
from dotenv import load_dotenv

from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver
from vanna.core.user.resolver import UserResolver as BaseUserResolver
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.tools.agent_memory import (
    SaveQuestionToolArgsTool,
    SearchSavedCorrectToolUsesTool,
)
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.openai import OpenAILlmService  # Groq is OpenAI-compatible

load_dotenv()

# config
DB_PATH       = "clinic.db"
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL    = "llama-3.3-70b-versatile"

# Module-level memory — shared between vanna_setup and seed_memory
agent_memory = DemoAgentMemory()


def build_agent() -> Agent:
    """
    Assemble and return a fully configured Vanna 2.0 Agent.
    Call this once at startup and reuse the returned object.
    """

    # 1. LLM Service — Groq via OpenAI-compatible endpoint
    llm_service = OpenAILlmService(
        api_key=GROQ_API_KEY,
        base_url=GROQ_BASE_URL,
        model=GROQ_MODEL,
    )

    # 2. SQLite Runner — Vanna's built-in database executor
    sql_runner = SqliteRunner(database_path=DB_PATH)

    # 3. Tools
    run_sql_tool    = RunSqlTool(sql_runner=sql_runner)
    visualize_tool  = VisualizeDataTool()
    save_tool       = SaveQuestionToolArgsTool()
    search_tool     = SearchSavedCorrectToolUsesTool()

    # 4. Tool Registry — access_groups controls who can use each tool
    registry = ToolRegistry()
    registry.register_local_tool(run_sql_tool,   access_groups=["user", "admin"])
    registry.register_local_tool(visualize_tool, access_groups=["user", "admin"])
    registry.register_local_tool(save_tool,      access_groups=["user", "admin"])
    registry.register_local_tool(search_tool,    access_groups=["user", "admin"])

    # 5. User Resolver — always identifies caller as a default clinic user
    class DefaultUserResolver(BaseUserResolver):
        def resolve_user(self, *args, **kwargs):
            from vanna.core.user import User
            return User(id="default_user", name="Clinic User")

    user_resolver = DefaultUserResolver()

    # 6. Agent config — keep streaming off for simple REST responses
    config = AgentConfig(
        stream_responses=False,
        max_tool_iterations=10,
        temperature=0.2,        # Lower = more deterministic SQL
    )

    # 7. Assemble the Agent
    agent = Agent(
        llm_service=llm_service,
        tool_registry=registry,
        user_resolver=user_resolver,
        agent_memory=agent_memory,
        config=config,
    )

    return agent