from langgraph.graph import StateGraph, add_messages, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from typing import Annotated, List, Optional
from langchain_mcp_adapters.client import MultiServerMCPClient
from rocket.my_mcp.config import mcp_config
from dotenv import load_dotenv
from rocket.prompts.prompts import rocket_system_prompt
import asyncio


load_dotenv()


class AgentState(BaseModel):
    messages: Annotated[List, add_messages] = []


# Global cache for the compiled graph
_cached_graph: Optional[CompiledStateGraph] = None
_graph_built = False


def build_graph() -> CompiledStateGraph:
    """Build and cache the graph to avoid rebuilding on every request."""
    global _cached_graph, _graph_built

    # Return cached graph if available
    if _cached_graph is not None:
        return _cached_graph

    # Prevent multiple concurrent initializations
    if _graph_built:
        # Another thread is building, wait a bit and check again
        import time
        time.sleep(0.1)
        if _cached_graph is not None:
            return _cached_graph

    _graph_built = True
    print("Building graph...")

    builder = StateGraph(AgentState)

    print("Initializing MCP client and getting tools...")
    try:
        # Initialize MCP client and get tools synchronously
        client = MultiServerMCPClient(connections=mcp_config["mcpServers"])

        # Create a new event loop for this operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tools = loop.run_until_complete(
                asyncio.wait_for(client.get_tools(), timeout=30.0)
            )
            print(f"Successfully loaded {len(tools)} tools")
        finally:
            loop.close()

    except Exception as e:
        print(f"WARNING: MCP client initialization failed: {e}, using empty tools list")
        tools = []

    llm = ChatOpenAI(model="gpt-4.1-mini-2025-04-14", temperature=0.1).bind_tools(tools)

    def assistant(state: AgentState) -> AgentState:
        response = llm.invoke(
            [SystemMessage(content=rocket_system_prompt)] +
            state.messages
            )
        state.messages.append(response)
        return state

    def assistant_router(state: AgentState) -> str:
        if state.messages[-1].tool_calls:
            return "tools"
        return END

    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))

    builder.set_entry_point("assistant")
    builder.add_conditional_edges("assistant", assistant_router, ["tools", END])
    builder.add_edge("tools", "assistant")

    compiled_graph = builder.compile(checkpointer=MemorySaver())
    _cached_graph = compiled_graph
    print("Graph built and cached successfully")
    return compiled_graph


def get_graph() -> CompiledStateGraph:
    """Get the graph, building it lazily if not already built."""
    return build_graph()


# Provide the graph as a factory function for LangGraph server
# This is the recommended approach for LangGraph server integration
graph = build_graph

print("Graph module loaded - build_graph() serves as both factory function and direct access method")
