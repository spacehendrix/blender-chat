import bpy
import textwrap


_ROLE_ICONS = {
    "user": "USER",
    "assistant": "LIGHT",
    "tool": "SCRIPT",
    "status": "INFO",
}

_WRAP_WIDTH = 45


class BLENDERCHAT_UL_Messages(bpy.types.UIList):
    bl_idname = "BLENDERCHAT_UL_Messages"

    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        role_icon = _ROLE_ICONS.get(item.role, "INFO")

        if item.is_error:
            role_icon = "ERROR"

        col = layout.column(align=True)
        # Role header
        row = col.row()

        # For tool messages, add a disclosure toggle
        if item.role == "tool":
            icon = "DISCLOSURE_TRI_RIGHT" if item.is_collapsed else "DISCLOSURE_TRI_DOWN"
            row.prop(item, "is_collapsed", text="", icon=icon, emboss=False, invert_checkbox=True)

        row.label(text=item.role.upper(), icon=role_icon)

        # Undo button or "UNDONE" label for tool messages
        if item.role == "tool":
            if item.is_undone:
                sub = row.row()
                sub.alert = True
                sub.label(text="UNDONE")
            elif item.content.startswith("Result:"):
                op = row.operator("blenderchat.undo_tool_call", text="", icon="LOOP_BACK")
                op.message_index = index

        # Word-wrapped content lines (skip if collapsed)
        if not (item.role == "tool" and item.is_collapsed):
            lines = _wrap_text(item.content, _WRAP_WIDTH)
            for line in lines:
                col.label(text=line)


class BLENDERCHAT_PT_ChatPanel(bpy.types.Panel):
    bl_label = "BlenderChat"
    bl_idname = "BLENDERCHAT_PT_ChatPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chat"

    def draw(self, context):
        layout = self.layout
        from . import HAS_ANTHROPIC

        # Dependency gate
        if not HAS_ANTHROPIC:
            box = layout.box()
            box.label(text="anthropic package not installed", icon="ERROR")
            box.operator("blenderchat.install_dependencies", icon="IMPORT")
            box.label(text="After install, restart Blender.")
            return

        # API key gate
        prefs = context.preferences.addons[__package__].preferences
        if not prefs.api_key:
            box = layout.box()
            box.label(text="Set your API key in addon preferences", icon="ERROR")
            box.operator(
                "preferences.addon_show",
                text="Open Preferences",
                icon="PREFERENCES",
            ).module = __package__
            return

        props = context.scene.blenderchat

        # Message list — fill ~95% of sidebar height dynamically
        region_height = context.region.height
        available = int(region_height * 0.95) - 80
        dynamic_rows = max(5, available // 20)

        row = layout.row()
        row.template_list(
            "BLENDERCHAT_UL_Messages",
            "",
            props,
            "messages",
            props,
            "active_message_index",
            rows=dynamic_rows,
            maxrows=dynamic_rows,
        )

        # Input area
        row = layout.row(align=True)
        row.enabled = not props.is_busy
        row.prop(props, "input_text", text="")
        row.operator("blenderchat.send_message", text="", icon="PLAY")

        # Status / action row
        row = layout.row(align=True)
        if props.is_busy:
            row.label(text="Thinking...", icon="SORTTIME")
        row.operator("blenderchat.clear_chat", text="Clear", icon="TRASH")


def _wrap_text(text, width):
    """Wrap text to fit panel width, handling newlines."""
    result = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            result.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=width)
        result.extend(wrapped if wrapped else [""])
    # Limit displayed lines to avoid UI explosion
    if len(result) > 40:
        result = result[:38] + ["...", f"({len(result)} lines total)"]
    return result


_classes = [
    BLENDERCHAT_UL_Messages,
    BLENDERCHAT_PT_ChatPanel,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
