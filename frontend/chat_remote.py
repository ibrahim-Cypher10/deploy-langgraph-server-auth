import os
import json
import uuid
import httpx
from dotenv import load_dotenv
from colorama import Fore, Style


load_dotenv()


LANGGRAPH_SERVER_URL = os.getenv("LANGGRAPH_SERVER_URL", "")
if not LANGGRAPH_SERVER_URL:
    raise ValueError("LANGGRAPH_SERVER_URL environment variable not found. Please set it in your .env file or environment.")


async def create_thread(user_id: str) -> dict:
    """Create a new thread for the given user."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=f"{LANGGRAPH_SERVER_URL}/threads",
                json={
                    "thread_id": str(uuid.uuid4()),
                    "metadata": {
                        "user_id": user_id
                    },
                    "if_exists": "do_nothing"
                },
                timeout=120.0 # Added timeout to wait for Render spin up
            )
            response.raise_for_status()

            return response.json()
    except Exception as e:
        print(f"Request failed: {e}")
        raise


async def get_thread_state(thread_id: str) -> dict:
    """Get the state of the thread."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url=f"{LANGGRAPH_SERVER_URL}/threads/{thread_id}/state"
            )
            response.raise_for_status()

            return response.json()
    except Exception as e:
        print(f"Request failed: {e}")
        raise


def process_line(line: str, current_event: str) -> str:
    """Process a single data line from the streaming response."""
    result_chunk = ""
    try:
        # Process data lines
        if line.startswith("data: "):
            data_content = line[6:]

            if current_event == "messages":
                message_chunk, metadata = json.loads(data_content)
            
                if "type" in message_chunk and message_chunk["type"] == "AIMessageChunk":
                    if message_chunk["response_metadata"]:
                        finish_reason = message_chunk["response_metadata"].get("finish_reason", "")
                        if finish_reason == "tool_calls":
                            result_chunk += "\n\n"
                        
                    if message_chunk["tool_call_chunks"]:
                        tool_chunk = message_chunk["tool_call_chunks"][0]

                        tool_name = tool_chunk.get("name", "")
                        args = tool_chunk.get("args", "")
                        
                        if tool_name:
                            result_chunk += f"\n\n< TOOL CALL: {tool_name} >\n\n"

                        if args:
                            result_chunk += args
                    else:
                        result_chunk += message_chunk["content"]
                
                # You can handle other event types here
                
            elif current_event == "metadata":
                result_chunk += ""
                
        return result_chunk

    except Exception as e:
        print(f"Error processing line: {type(e).__name__}: {str(e)}")
        raise


async def get_stream(thread_id: str, message: str):
    """Send a message to the thread and process the streaming response.

    Args:
        thread_id: The thread ID to send the message to
        message: The message content
        seen_tool_call_ids: A set of tool call IDs that have already been seen

    Returns:
        str: The complete response from the assistant
    """
    full_content = ""
    current_event = ""

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url=f"{LANGGRAPH_SERVER_URL}/threads/{thread_id}/runs/stream",
                json={
                    "assistant_id": "rocket",
                    "input": {
                        "messages": [
                            {"role": "human", "content": message}
                        ]
                    },
                    "stream_mode": "messages-tuple"
                },
                timeout=60.0
            ) as stream_response:
                async for line in stream_response.aiter_lines():
                    if line:
                        print(line)
                        # Process event lines
                        if line.startswith("event: "):
                            current_event = line[7:].strip()

                        # Process data lines
                        else:
                            message_chunk = process_line(line, current_event)
                            if message_chunk:
                                full_content += message_chunk
                                print(Fore.CYAN + message_chunk + Style.RESET_ALL, end="", flush=True)

        return full_content
    except Exception as e:
        print(f"Error in get_stream: {type(e).__name__}: {str(e)}")
        raise


async def main():
    try:
        # Create a thread
        response = await create_thread(user_id="kenny")
        thread_id = response["thread_id"]

        # Stream responses
        while True:
            user_input = input("User: ")
            if user_input.lower() in ["exit", "quit"]:
                break

            print(f"\n\n ----- 🥷 Human ----- \n\n{user_input}\n")

            print(f"\n ---- 🚀 Rocket ---- \n")
            result = await get_stream(thread_id, user_input)

            # check state after run
            # thread_state = await get_thread_state(thread_id)

    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")
        raise


if __name__ == "__main__":
    import asyncio
    import nest_asyncio
    nest_asyncio.apply()

    asyncio.run(main())