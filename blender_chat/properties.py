import bpy
import time


class BlenderChatMessageItem(bpy.types.PropertyGroup):
    role: bpy.props.EnumProperty(
        name="Role",
        items=[
            ("user", "User", ""),
            ("assistant", "Assistant", ""),
            ("tool", "Tool", ""),
            ("status", "Status", ""),
        ],
        default="user",
    )

    content: bpy.props.StringProperty(
        name="Content",
        default="",
    )

    timestamp: bpy.props.FloatProperty(
        name="Timestamp",
        default=0.0,
    )

    is_code: bpy.props.BoolProperty(
        name="Is Code",
        default=False,
    )

    is_error: bpy.props.BoolProperty(
        name="Is Error",
        default=False,
    )

    is_collapsed: bpy.props.BoolProperty(
        name="Collapsed",
        default=False,
    )

    is_undone: bpy.props.BoolProperty(
        name="Undone",
        default=False,
    )


def _on_input_confirmed(self, context):
    """Send message when the input field is confirmed (Enter key)."""
    if not self.input_text.strip():
        return
    if self.is_busy:
        return
    bpy.ops.blenderchat.send_message('INVOKE_DEFAULT')


class BlenderChatSceneProperties(bpy.types.PropertyGroup):
    messages: bpy.props.CollectionProperty(
        type=BlenderChatMessageItem
    )

    active_message_index: bpy.props.IntProperty(
        name="Active Message",
        default=0,
    )

    input_text: bpy.props.StringProperty(
        name="Message",
        default="",
        update=_on_input_confirmed,
    )

    is_busy: bpy.props.BoolProperty(
        name="Is Busy",
        default=False,
    )


def add_message(context, role, content, is_code=False, is_error=False):
    """Helper to add a message to the chat and auto-scroll."""
    props = context.scene.blenderchat
    msg = props.messages.add()
    msg.role = role
    msg.content = content
    msg.timestamp = time.time()
    msg.is_code = is_code
    msg.is_error = is_error
    props.active_message_index = len(props.messages) - 1
    return msg


_classes = [
    BlenderChatMessageItem,
    BlenderChatSceneProperties,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
