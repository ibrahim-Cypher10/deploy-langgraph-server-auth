from langgraph.graph import StateGraph, add_messages, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from typing import Annotated, List, Optional, Dict, Any
from langchain_mcp_adapters.client import MultiServerMCPClient
from rocket.my_mcp.config import mcp_config
import json
# from composio_langchain import ComposioToolSet, App, Action
from dotenv import load_dotenv
import os
from rocket.prompts import rocket_system_prompt


load_dotenv()


class AgentState(BaseModel):
    messages: Annotated[List, add_messages] = []
    video_search_result: List[dict] = []


async def build_graph() -> CompiledStateGraph:
    builder = StateGraph(AgentState)

    client = MultiServerMCPClient(connections=mcp_config["mcpServers"])
    tools1 = await client.get_tools()

    # toolset = ComposioToolSet(api_key=os.environ.get("COMPOSIO_API_KEY"))
    # tools2 = toolset.get_tools(apps=[App.GOOGLESHEETS])

    tools = tools1 #+ tools2

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
    
    # def parse_tool_output(state: AgentState) -> AgentState:
    #     last_message = state.messages[-1]
    #     if isinstance(last_message, ToolMessage):
    #         state.video_search_result.append(json.loads(last_message.content))
    #     return state

    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    # builder.add_node("parse_tool_output", parse_tool_output)

    builder.set_entry_point("assistant")
    builder.add_conditional_edges("assistant", assistant_router)
    builder.add_edge("tools", "assistant")
    # builder.add_edge("parse_tool_output", "assistant")

    return builder.compile(checkpointer=MemorySaver())
