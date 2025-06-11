import httpx
import os
import json
import uuid
from uuid import UUID
from dotenv import load_dotenv

from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import traceback


load_dotenv()


LANGGRAPH_SERVER_URL = os.getenv("LANGGRAPH_SERVER_URL", "http://localhost:8000")
if not LANGGRAPH_SERVER_URL:
    raise ValueError("LANGGRAPH_SERVER_URL environment variable not found. Please set it in your .env file or environment.")

ROCKET_API_KEY = os.getenv('ROCKET_API_KEY', "")
if not ROCKET_API_KEY:
    raise ValueError("ROCKET_API_KEY environment variable not found. Please set it in your .env file or environment.")


# ----------------------------
# Thread Management
# ----------------------------


async def create_thread(user_id: UUID) -> UUID:
    """Create a new thread for the given user."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=f"{LANGGRAPH_SERVER_URL}/threads",
                headers={"x-api-key": ROCKET_API_KEY},
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
                headers={"x-api-key": ROCKET_API_KEY},
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
                headers={"x-api-key": ROCKET_API_KEY},
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


class SSEParser:
    """Proper SSE (Server-Sent Events) parser that handles event boundaries correctly."""

    def __init__(self):
        self.buffer = ""
        self.current_tool_call = None
        self.seen_message_ids = set()  # Track processed messages to avoid duplicates

    def parse_chunk(self, chunk: bytes) -> List[str]:
        """Parse a chunk of SSE data and return complete events."""
        # Decode and add to buffer
        chunk_str = chunk.decode('utf-8')
        self.buffer += chunk_str

        results = []

        # Split on double CRLF to separate events (SSE uses \r\n\r\n)
        while '\r\n\r\n' in self.buffer:
            event_data, self.buffer = self.buffer.split('\r\n\r\n', 1)

            # Parse the event
            result = self._parse_event(event_data)
            if result:
                results.append(result)

        return results

    def _parse_event(self, event_data: str) -> str:
        """Parse a single SSE event."""
        lines = event_data.strip().split('\n')

        event_type = None
        data = None

        for line in lines:
            line = line.strip()
            if line.startswith('event:'):
                event_type = line[6:].strip()
            elif line.startswith('data:'):
                data = line[5:].strip()

        if not event_type or not data:
            return ""

        return self._process_event(event_type, data)

    def _process_event(self, event_type: str, data: str) -> str:
        """Process a parsed SSE event."""
        if event_type == 'error':
            return f"\n\n```\nERROR: {data}\n```\n\n"

        elif event_type == 'metadata':
            # Just log metadata, don't return anything
            return ""

        elif event_type == 'messages':
            try:
                # For messages-tuple mode, data is a tuple [node_name, message]
                parsed_data = json.loads(data)

                # Handle both tuple format and direct message format
                if isinstance(parsed_data, list) and len(parsed_data) == 2:
                    message, _ = parsed_data  # message is first, metadata is second
                    if isinstance(message, dict):
                        return self._process_message(message)
                else:
                    # Fallback for direct message format
                    if isinstance(parsed_data, dict):
                        return self._process_message(parsed_data)

                return ""

            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                print(f"Data: {data}")
                return ""

        return ""

    def _process_message(self, message: Dict[str, Any]) -> str:
        """Process a message from the stream."""
        message_type = message.get("type")

        # Only deduplicate tool messages, not AI message chunks
        if message_type == "tool":
            message_id = message.get("id")
            if message_id and message_id in self.seen_message_ids:
                return ""  # Skip duplicate tool messages

            # Mark this tool message as seen
            if message_id:
                self.seen_message_ids.add(message_id)

            return self._process_tool_message(message)

        elif message_type == "AIMessageChunk":
            return self._process_ai_message_chunk(message)

        return ""

    def _process_ai_message_chunk(self, message: Dict[str, Any]) -> str:
        """Process an AI message chunk."""
        result = ""

        # Handle tool calls
        if message.get("tool_calls"):
            tool_call = message["tool_calls"][0]

            if tool_call.get("name") and tool_call.get("id"):
                # Start of a new tool call
                self.current_tool_call = {
                    "name": tool_call["name"],
                    "id": tool_call["id"],
                    "args": '{"'  # Initialize with opening brace and quote for JSON
                }
                result = f"\n🔧 **Tool Call: {tool_call['name']}**\n\n"

                # If args are complete in this chunk
                if tool_call.get("args"):
                    result += f"```json\n{json.dumps(tool_call['args'], indent=2)}\n```\n\n"
                    self.current_tool_call = None

        # Handle tool call chunks (streaming arguments)
        elif message.get("tool_call_chunks"):
            chunk_data = message["tool_call_chunks"][0]
            if self.current_tool_call and chunk_data.get("args"):
                self.current_tool_call["args"] += chunk_data["args"]


        # Check if tool call is complete
        elif (message.get("response_metadata", {}).get("finish_reason") == "tool_calls"
              and self.current_tool_call):
            try:
                args_dict = json.loads(self.current_tool_call["args"])
                result = f"```json\n{json.dumps(args_dict, indent=2)}\n```\n\n"
            except json.JSONDecodeError:
                result = f"```\n{self.current_tool_call['args']}\n```\n\n"
            self.current_tool_call = None

        # Handle regular content
        elif message.get("content"):
            result = message["content"]

        return result

    def _process_tool_message(self, message: Dict[str, Any]) -> str:
        """Process a tool response message."""
        tool_name = message.get("name", "Unknown")
        # tool_response = message.get("content", "No response") # optionally can include tool output

        return f"✅ **Tool Response: {tool_name}**\n\n"


async def run_stream_from_message(thread_id: UUID, assistant_id: str,  message: str, configurable: dict, parser: Optional[SSEParser] = None):
    """Stream messages from the langgraph API"""
    if parser is None:
        parser = SSEParser()

    try:
        with httpx.stream(
            method="POST",
            headers={"x-api-key": ROCKET_API_KEY},
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
                    # Parse the chunk and get any complete events
                    results = parser.parse_chunk(chunk)
                    for result in results:
                        if result:
                            yield result

                except Exception as e:
                    # Log errors but continue processing
                    print(f"Error processing chunk: {str(e)}")
                    continue

    except Exception as e:
        print(f"Error in run_stream_from_message: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        