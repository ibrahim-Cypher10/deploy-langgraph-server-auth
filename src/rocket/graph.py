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
_graph_initialization_lock = asyncio.Lock()


async def build_graph() -> CompiledStateGraph:
    """Build and cache the graph to avoid rebuilding on every request."""
    global _cached_graph

    # Use a lock to prevent multiple concurrent initializations
    async with _graph_initialization_lock:
        # Return cached graph if available (double-check after acquiring lock)
        if _cached_graph is not None:
            return _cached_graph

        print("Building graph for the first time...")

        builder = StateGraph(AgentState)

        print("Initializing MCP client and getting tools...")
        try:
            # Add timeout to prevent indefinite blocking during startup
            client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
            tools = await asyncio.wait_for(client.get_tools(), timeout=30.0)
            print(f"Successfully loaded {len(tools)} tools")
        except asyncio.TimeoutError:
            print("WARNING: MCP client initialization timed out, using empty tools list")
            tools = []
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


async def get_graph() -> CompiledStateGraph:
    """Get the graph, building it lazily if not already built."""
    global _cached_graph
    if _cached_graph is None:
        return await build_graph()
    return _cached_graph


# For LangGraph server compatibility, we need to provide a graph object
# But we'll make it truly lazy to avoid blocking server startup

# Create a simple wrapper that defers graph creation until first access
class LazyCompiledGraph:
    """A minimal wrapper that creates the graph only when first accessed."""

    def __init__(self):
        self._graph: Optional[CompiledStateGraph] = None
        self._building = False

    def _ensure_graph(self) -> CompiledStateGraph:
        """Ensure the graph is built, but only build it once."""
        if self._graph is None and not self._building:
            self._building = True
            try:
                # Use asyncio.run to build the graph synchronously when needed
                self._graph = asyncio.run(build_graph())
                print("Graph built successfully on first access")
            except Exception as e:
                print(f"Failed to build graph: {e}")
                self._building = False
                raise
            finally:
                self._building = False

        if self._graph is None:
            raise RuntimeError("Graph failed to initialize")
        return self._graph

    def __getattr__(self, name):
        """Delegate all attribute access to the actual graph."""
        actual_graph = self._ensure_graph()
        return getattr(actual_graph, name)


# Create the lazy graph that LangGraph server will import
graph = LazyCompiledGraph()

print("Graph module loaded - graph will be initialized when first needed by LangGraph server")
