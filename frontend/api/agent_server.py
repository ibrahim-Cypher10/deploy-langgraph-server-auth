import httpx
import os
import json
import uuid
from uuid import UUID
from dotenv import load_dotenv
from colorama import Fore, Style
from typing import List, Dict, Any
from pydantic import BaseModel
import traceback


load_dotenv()


LANGGRAPH_SERVER_URL = os.getenv("LANGGRAPH_SERVER_URL", "http://localhost:2024")
if not LANGGRAPH_SERVER_URL:
    raise ValueError("LANGGRAPH_SERVER_URL environment variable not found. Please set it in your .env file or environment.")


# ----------------------------
# Thread Management
# ----------------------------


async def create_thread(user_id: UUID) -> UUID:
    """Create a new thread for the given user."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=f"{LANGGRAPH_SERVER_URL}/threads",
                json={
                    "thread_id": str(uuid.uuid4()),
                    "metadata": {
                        "user_id": str(user_id)
                    },
                    "if_exists": "do_nothing" # returns existing thread
                },
                timeout=120.0 # Added timeout to wait for Render spin up
            )
            response.raise_for_status()
            thread_id = response.json().get("thread_id")

            return UUID(thread_id)
    except Exception as e:
        print(f"Request failed: {e}")
        raise


async def search_threads(user_id: UUID) -> List[UUID]:
    """Create a new thread for the given user."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=f"{LANGGRAPH_SERVER_URL}/threads/search",
                json={
                    "metadata": {
                        "user_id": str(user_id)
                    },
                },
                timeout=120.0 # Added timeout to wait for Render spin up
            )
            response.raise_for_status()

            return [UUID(thread["thread_id"]) for thread in response.json()]
    except Exception as e:
        print(f"Request failed: {e}")
        raise


async def delete_thread(thread_id: UUID) -> None:
    """Delete a thread by its ID."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url=f"{LANGGRAPH_SERVER_URL}/threads/{thread_id}",
                timeout=120.0 # Added timeout to wait for Render spin up
            )
            response.raise_for_status()

            # DELETE requests might not return JSON content
            if response.status_code == 200:
                return None
    except Exception as e:
        print(f"Request failed: {e}")
        raise


# ----------------------------
# Thread Runs
# ----------------------------


class Event(BaseModel):
    event_type: str
    data: Dict[str, Any]

# Global state to track tool calls across chunks
_current_tool_call = None

def process_chunk(chunk) -> str:
    """Process a chunk of data from the streaming response."""
    global _current_tool_call
    return_string = ""

    # Decode the byte string to a regular string
    chunk_str = chunk.decode('utf-8')

    # Split the chunk into lines
    lines = chunk_str.split('\r\n')

    # Iterate over the lines to find event and data
    event_type = None
    data = None
    for line in lines:
        if line.startswith('event:'):
            event_type = line.split('event: ')[1]
        elif line.startswith('data:'):
            data = line.split('data: ')[1]

    if event_type and data:
        # Process the data based on the event type
        if event_type == 'error':
            return_string = f"\n\n```\nERROR: {data}\n```\n\n"
        elif event_type == 'metadata':
            event = Event(event_type=event_type, data=json.loads(data))
        elif event_type == 'messages':
            # take the first message because the messages data is an array
            message = json.loads(data)[0]

            event = Event(event_type=event_type, data=message)

            if message["type"] == "AIMessageChunk":
                # Handle tool calls
                if message.get("tool_calls"):
                    tool_call = message["tool_calls"][0]
                    # Check if this is the start of a new tool call (has name and id)
                    if tool_call.get("name") and tool_call.get("id"):
                        if _current_tool_call is None:
                            _current_tool_call = {
                                "name": tool_call["name"],
                                "id": tool_call["id"],
                                "args_str": ""
                            }
                            return_string = f"\n\n``` Tool Call \nName: {tool_call['name']}\n\nArgs: "

                        # If we have complete args, show them
                        if tool_call.get("args") and isinstance(tool_call["args"], dict):
                            return_string = f"{tool_call['args']}\n```\n\n"
                            _current_tool_call = None

                # Handle tool call chunks (streaming arguments)
                if message.get("tool_call_chunks"):
                    chunk_data = message["tool_call_chunks"][0]
                    if _current_tool_call and chunk_data.get("args"):
                        _current_tool_call["args_str"] += chunk_data["args"]

                # Check if tool call is complete
                if (message.get("response_metadata", {}).get("finish_reason") == "tool_calls"
                    and _current_tool_call):
                    try:
                        # Try to parse the accumulated arguments
                        args_dict = json.loads(_current_tool_call["args_str"])
                        return_string = f"{args_dict}\n```\n\n"
                    except json.JSONDecodeError:
                        return_string = f"{_current_tool_call['args_str']}\n```\n\n"
                    _current_tool_call = None

                # Handle regular content
                if message.get("content"):
                    return_string = message["content"]

            # tool responses
            if message["type"] == "tool":
                tool_name = message.get("name", None)
                tool_call_id = message.get("tool_call_id", None)
                tool_content = message.get("content", "")

                return_string = f"\n``` Tool Response Successful \nName: {tool_name}\n```\n\n"

                # Optional: return the tool output
                # return_string = f"\n``` Tool Response \nName: {tool_name}\n\nContent: {tool_content}\n```\n\n"

    return return_string


async def run_stream_from_message(thread_id: UUID, assistant_id: str,  message: str, configurable: dict):
    """Stream messages from the langgraph API"""
    try:
        with httpx.stream(
            method="POST",
            url=f"{LANGGRAPH_SERVER_URL}/threads/{str(thread_id)}/runs/stream",
            json={
                "assistant_id": assistant_id,
                "input": {
                    "messages": [message]
                    },
                "config": {
                    "recursion_limit": 15,
                    "configurable": configurable
                    },
                "stream_mode": "messages-tuple",
                "stream_subgraphs": False,
            },
            timeout=120.0
            ) as stream:
            for chunk in stream.iter_bytes():
                if not chunk:
                    continue

                try:
                    result = process_chunk(chunk)
                    if result:
                        yield result

                except json.JSONDecodeError as e:
                    continue
                except Exception as e:
                    print(f"Error processing chunk: {str(e)}")
                    print(f"Traceback: {traceback.format_exc()}")
                    continue
    except Exception as e:
        print(f"Error in run_stream_from_message: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
