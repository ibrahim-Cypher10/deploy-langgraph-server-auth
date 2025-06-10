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


load_dotenv()


class AgentState(BaseModel):
    messages: Annotated[List, add_messages] = []


# Global cache for the compiled graph
_cached_graph: Optional[CompiledStateGraph] = None


async def build_graph() -> CompiledStateGraph:
    """Build and cache the graph to avoid rebuilding on every request."""
    global _cached_graph

    # Return cached graph if available
    if _cached_graph is not None:
        return _cached_graph
    print("Building graph for the first time...")

    builder = StateGraph(AgentState)

    print("Initializing MCP client and getting tools...")
    client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
    tools = await client.get_tools()
    print(f"Successfully loaded {len(tools)} tools")

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

    print("Compiling graph...")
    _cached_graph = builder.compile(checkpointer=MemorySaver())
    print("Graph compiled and cached successfully!")

    return _cached_graph


async def main():
    graph = await build_graph()
    print(graph.get_graph().draw_mermaid())
    

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
