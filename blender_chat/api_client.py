import json
import queue
import threading

# Conversation state (in-memory only, resets on restart)
_conversation_messages = []

# Thread -> Main thread queue
_result_queue = queue.Queue()

# Main thread -> Thread queue (for tool results and scene context)
_tool_result_queue = queue.Queue()

_SYSTEM_PROMPT = """You are BlenderChat, an AI assistant integrated into Blender {blender_version}.
You help users control Blender through natural language. You have access to tools
that let you create objects, set materials, modify the scene, and execute arbitrary
Python code via bpy.

Guidelines:
- Use the convenience tools (create_object, set_material, etc.) for common operations.
- For anything else, use the discovery workflow:
  1. list_operator_modules — see available bpy.ops modules
  2. list_operators — browse operators in a module (use filter to narrow)
  3. get_operator_info — inspect parameters before calling
  4. call_operator — execute any bpy.ops operator with auto type coercion
- Use query_blender_data to inspect scene state (e.g. bpy.context.active_object.modifiers).
- Use execute_bpy_code only for multi-step logic, loops, or complex property setting.
  Assign any value you want to return to a variable called `result`.
- Always explain what you're doing before and after using tools.
- If an operator poll fails, check the error for current mode/selection and fix context first.
- Be concise but helpful.

Current scene state:
{scene_context}"""

_MAX_CONVERSATION_MESSAGES = 60


def clear_conversation():
    """Reset conversation history."""
    global _conversation_messages
    _conversation_messages = []
    # Drain queues
    _drain_queue(_result_queue)
    _drain_queue(_tool_result_queue)


def send_message_async(user_text, api_key, model, tools_list, blender_version):
    """Start a background thread to send a message to Claude.

    The thread communicates via _result_queue and _tool_result_queue.
    Queue message formats (thread -> main):
        ("need_scene_context", None)
        ("assistant_text", str)
        ("tool_call", {"id": str, "name": str, "input": dict})
        ("final_response", str)
        ("error", str)
    """
    _conversation_messages.append({
        "role": "user",
        "content": user_text,
    })

    t = threading.Thread(
        target=_thread_worker,
        args=(api_key, model, tools_list, blender_version),
        daemon=True,
    )
    t.start()


def _thread_worker(api_key, model, tools_list, blender_version):
    """Background thread: handles API calls and tool-use loop."""
    try:
        import anthropic
    except ImportError:
        _result_queue.put(("error", "anthropic package not available"))
        return

    # Request scene context from main thread
    _result_queue.put(("need_scene_context", None))
    scene_context = _tool_result_queue.get(timeout=30)

    system_prompt = _SYSTEM_PROMPT.format(
        blender_version=blender_version,
        scene_context=scene_context,
    )

    client = anthropic.Anthropic(api_key=api_key)

    # Trim conversation if too long
    _trim_conversation()

    while True:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                tools=tools_list,
                messages=_conversation_messages,
                timeout=90.0,
            )
        except anthropic.AuthenticationError:
            _result_queue.put(("error", "Invalid API key. Check addon preferences."))
            return
        except anthropic.RateLimitError:
            _result_queue.put(("error", "Rate limited. Please wait and try again."))
            return
        except anthropic.APIConnectionError:
            _result_queue.put(("error", "Network error. Check your internet connection."))
            return
        except Exception as e:
            _result_queue.put(("error", f"API error: {e}"))
            return

        # Process response content blocks
        assistant_content = response.content
        text_parts = []
        tool_uses = []

        for block in assistant_content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # Send intermediate text to UI
        combined_text = "\n".join(text_parts)
        if combined_text.strip():
            _result_queue.put(("assistant_text", combined_text))

        # Append the full assistant message to conversation
        _conversation_messages.append({
            "role": "assistant",
            "content": [_block_to_dict(b) for b in assistant_content],
        })

        if response.stop_reason == "end_turn" or not tool_uses:
            # Final response
            _result_queue.put(("final_response", combined_text))
            return

        # Handle tool use
        tool_results = []
        for tool_use in tool_uses:
            # Send tool call to main thread for execution
            _result_queue.put(("tool_call", {
                "id": tool_use.id,
                "name": tool_use.name,
                "input": tool_use.input,
            }))

            # Wait for main thread to execute and return result
            tool_result = _tool_result_queue.get(timeout=60)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result),
            })

        # Append tool results to conversation
        _conversation_messages.append({
            "role": "user",
            "content": tool_results,
        })

        # Loop back to call API again with tool results


def _block_to_dict(block):
    """Convert an API content block to a serializable dict."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    elif block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {"type": block.type}


def _trim_conversation():
    """Trim conversation to stay within token limits."""
    global _conversation_messages
    if len(_conversation_messages) > _MAX_CONVERSATION_MESSAGES:
        # Keep the most recent messages
        _conversation_messages = _conversation_messages[-_MAX_CONVERSATION_MESSAGES:]


def _drain_queue(q):
    """Empty a queue without blocking."""
    while True:
        try:
            q.get_nowait()
        except queue.Empty:
            break
