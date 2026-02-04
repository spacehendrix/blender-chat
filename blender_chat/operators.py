import bpy
import json
import queue

from . import api_client
from .properties import add_message
from .tools import BLENDER_TOOLS, execute_tool


class BLENDERCHAT_OT_SendMessage(bpy.types.Operator):
    bl_idname = "blenderchat.send_message"
    bl_label = "Send Message"
    bl_description = "Send a message to Claude"

    _timer = None

    def invoke(self, context, event):
        props = context.scene.blenderchat

        # Guard: busy
        if props.is_busy:
            self.report({"WARNING"}, "Already processing a message.")
            return {"CANCELLED"}

        # Guard: empty input
        text = props.input_text.strip()
        if not text:
            return {"CANCELLED"}

        # Guard: API key
        prefs = context.preferences.addons[__package__].preferences
        if not prefs.api_key:
            self.report({"ERROR"}, "Set your API key in addon preferences.")
            return {"CANCELLED"}

        # Guard: anthropic available
        from . import HAS_ANTHROPIC
        if not HAS_ANTHROPIC:
            self.report({"ERROR"}, "anthropic package not installed.")
            return {"CANCELLED"}

        # Add user message to UI
        add_message(context, "user", text)
        props.input_text = ""
        props.is_busy = True

        # Read blender version on main thread (bpy is not thread-safe)
        blender_version = ".".join(str(v) for v in bpy.app.version)

        # Start async API call
        api_client.send_message_async(
            user_text=text,
            api_key=prefs.api_key,
            model=prefs.model,
            tools_list=BLENDER_TOOLS,
            blender_version=blender_version,
            max_messages=prefs.max_conversation_messages,
        )

        # Start modal timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        self._tag_redraw(context)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        props = context.scene.blenderchat
        prefs = context.preferences.addons[__package__].preferences

        # Poll the result queue (non-blocking)
        try:
            msg_type, msg_data = api_client._result_queue.get_nowait()
        except queue.Empty:
            return {"PASS_THROUGH"}

        if msg_type == "need_scene_context":
            from .scene_context import get_scene_summary
            scene_ctx = get_scene_summary()
            api_client._tool_result_queue.put(scene_ctx)
            return {"PASS_THROUGH"}

        elif msg_type == "assistant_text":
            add_message(context, "assistant", msg_data)
            self._tag_redraw(context)
            return {"PASS_THROUGH"}

        elif msg_type == "tool_call":
            tool_id = msg_data["id"]
            tool_name = msg_data["name"]
            tool_input = msg_data["input"]

            # Show tool call in UI if enabled
            if prefs.show_tool_calls:
                input_str = json.dumps(tool_input, indent=2)
                msg = add_message(
                    context,
                    "tool",
                    f"Tool: {tool_name}\n{input_str}",
                    is_code=True,
                )
                msg.is_collapsed = True

            # Execute tool on main thread
            result = execute_tool(tool_name, tool_input)

            # Show tool result in UI if enabled
            if prefs.show_tool_calls:
                msg = add_message(
                    context,
                    "tool",
                    f"Result: {result.get('result', '')}",
                    is_error=not result.get("success", False),
                )
                msg.is_collapsed = True

            # Send result back to thread
            api_client._tool_result_queue.put(result)
            self._tag_redraw(context)
            return {"PASS_THROUGH"}

        elif msg_type == "final_response":
            # final_response text may already have been shown via assistant_text
            # Only add if it wasn't already shown (empty final after tool-only response)
            if msg_data and msg_data.strip():
                # Check if we already showed this exact text
                if not self._last_message_matches(props, msg_data):
                    add_message(context, "assistant", msg_data)

            self._finish(context)
            return {"FINISHED"}

        elif msg_type == "error":
            add_message(context, "status", msg_data, is_error=True)
            self._finish(context)
            return {"FINISHED"}

        return {"PASS_THROUGH"}

    def cancel(self, context):
        self._finish(context)

    def _finish(self, context):
        props = context.scene.blenderchat
        props.is_busy = False

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        self._tag_redraw(context)

    def _tag_redraw(self, context):
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def _last_message_matches(self, props, text):
        """Check if the last assistant message already has this text."""
        if len(props.messages) == 0:
            return False
        last = props.messages[len(props.messages) - 1]
        return last.role == "assistant" and last.content == text


class BLENDERCHAT_OT_ClearChat(bpy.types.Operator):
    bl_idname = "blenderchat.clear_chat"
    bl_label = "Clear Chat"
    bl_description = "Clear all chat messages and reset conversation"

    def execute(self, context):
        props = context.scene.blenderchat

        if props.is_busy:
            self.report({"WARNING"}, "Cannot clear while processing.")
            return {"CANCELLED"}

        props.messages.clear()
        props.active_message_index = 0
        api_client.clear_conversation()

        self.report({"INFO"}, "Chat cleared.")
        return {"FINISHED"}


_classes = [
    BLENDERCHAT_OT_SendMessage,
    BLENDERCHAT_OT_ClearChat,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
