import httpx
import os
import json
import uuid
import time
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

# Global state to track tool calls and SSE parsing across chunks
_current_tool_call = None
_sse_buffer = ""
_last_content = ""  # Track the last content to extract deltas

def process_sse_events(events_text: str) -> list:
    """Parse SSE events from accumulated text."""
    events = []
    lines = events_text.split('\n')

    current_event = {}
    for line in lines:
        line = line.rstrip('\r')

        if line == '':
            # Empty line indicates end of event
            if current_event:
                events.append(current_event)
                current_event = {}
        elif line.startswith(':'):
            # Comment line, ignore
            continue
        elif ':' in line:
            field, value = line.split(':', 1)
            field = field.strip()
            value = value.strip()

            if field in current_event:
                # Multiple values for same field
                if isinstance(current_event[field], list):
                    current_event[field].append(value)
                else:
                    current_event[field] = [current_event[field], value]
            else:
                current_event[field] = value
        else:
            # Field with no value
            current_event[line.strip()] = ""

    # Add final event if exists
    if current_event:
        events.append(current_event)

    return events

def process_chunk(chunk) -> str:
    """Process a chunk of data from the streaming response."""
    global _current_tool_call, _sse_buffer
    return_string = ""

    # Decode the byte string to a regular string
    chunk_str = chunk.decode('utf-8')

    # Add to buffer
    _sse_buffer += chunk_str

    # Look for complete events (ending with double newline)
    while '\n\n' in _sse_buffer or '\r\n\r\n' in _sse_buffer:
        # Find the end of the next complete event
        double_newline_pos = _sse_buffer.find('\n\n')
        double_crlf_pos = _sse_buffer.find('\r\n\r\n')

        if double_newline_pos == -1:
            end_pos = double_crlf_pos + 4
        elif double_crlf_pos == -1:
            end_pos = double_newline_pos + 2
        else:
            end_pos = min(double_newline_pos + 2, double_crlf_pos + 4)

        # Extract the complete event
        event_text = _sse_buffer[:end_pos]
        _sse_buffer = _sse_buffer[end_pos:]

        # Parse the event
        events = process_sse_events(event_text)

        for event in events:
            if 'event' in event and 'data' in event:
                event_type = event['event']
                data = event['data']

                # Process the data based on the event type
                if event_type == 'error':
                    return_string += f"\n\n```\nERROR: {data}\n```\n\n"
                elif event_type == 'metadata' or event_type == 'messages/metadata':
                    # Just parse for validation, don't return anything
                    try:
                        json.loads(data)
                    except json.JSONDecodeError:
                        pass
                elif event_type == 'messages' or event_type == 'messages/partial':
                    try:


                        # take the first message because the messages data is an array
                        messages = json.loads(data)
                        if messages and len(messages) > 0:
                            message = messages[0]

                            if message["type"] == "AIMessageChunk" or message["type"] == "ai":
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
                                            return_string += f"\n\n``` Tool Call \nName: {tool_call['name']}\n\nArgs: "

                                        # If we have complete args, show them
                                        if tool_call.get("args") and isinstance(tool_call["args"], dict):
                                            return_string += f"{tool_call['args']}\n```\n\n"
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
                                        return_string += f"{args_dict}\n```\n\n"
                                    except json.JSONDecodeError:
                                        return_string += f"{_current_tool_call['args_str']}\n```\n\n"
                                    _current_tool_call = None

                                # Handle regular content with delta extraction
                                if message.get("content"):
                                    current_content = message["content"]
                                    global _last_content

                                    # Extract only the new part (delta)
                                    if current_content.startswith(_last_content):
                                        delta = current_content[len(_last_content):]
                                        if delta:  # Only yield if there's new content
                                            return_string += delta
                                            _last_content = current_content
                                    else:
                                        # Content doesn't start with last content, yield full content
                                        return_string += current_content
                                        _last_content = current_content

                            # tool responses
                            elif message["type"] == "tool":
                                tool_name = message.get("name", None)
                                tool_call_id = message.get("tool_call_id", None)
                                tool_content = message.get("content", "")

                                return_string += f"\n``` Tool Response Successful \nName: {tool_name}\n```\n\n"

                                # Optional: return the tool output
                                # return_string += f"\n``` Tool Response \nName: {tool_name}\n\nContent: {tool_content}\n```\n\n"
                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        pass

    return return_string


async def run_stream_from_message(thread_id: UUID, assistant_id: str,  message: str, configurable: dict):
    """Stream messages from the langgraph API"""
    try:
        start_time = time.time()
        print(f"[TIMING] Starting request at {start_time:.3f}")

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
                "stream_mode": "messages",  # Changed from messages-tuple for potentially faster streaming
                "stream_subgraphs": False,
            },
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
            timeout=120.0
            ) as stream:

            connection_time = time.time()
            print(f"[TIMING] Connection established at {connection_time:.3f} (+{connection_time - start_time:.3f}s)")

            first_chunk_received = False
            first_content_yielded = False

            for chunk in stream.iter_bytes():
                if not chunk:
                    continue

                if not first_chunk_received:
                    first_chunk_time = time.time()
                    print(f"[TIMING] First chunk received at {first_chunk_time:.3f} (+{first_chunk_time - start_time:.3f}s)")
                    first_chunk_received = True

                try:
                    result = process_chunk(chunk)
                    if result:
                        if not first_content_yielded:
                            first_content_time = time.time()
                            print(f"[TIMING] First content yielded at {first_content_time:.3f} (+{first_content_time - start_time:.3f}s)")
                            first_content_yielded = True
                        yield result
                    else:
                        pass

                except json.JSONDecodeError as e:
                    continue
                except Exception as e:
                    print(f"Error processing chunk: {str(e)}")
                    print(f"Traceback: {traceback.format_exc()}")
                    continue
    except Exception as e:
        print(f"Error in run_stream_from_message: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
