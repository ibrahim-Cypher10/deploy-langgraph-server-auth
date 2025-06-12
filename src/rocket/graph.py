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


async def build_graph() -> CompiledStateGraph:
    """Build the graph for the Rocket agent."""

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

    return builder.compile(checkpointer=MemorySaver())

graph = asyncio.run(build_graph())
