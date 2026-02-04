import bpy
import subprocess
import sys
import os


class BLENDERCHAT_OT_InstallDependencies(bpy.types.Operator):
    bl_idname = "blenderchat.install_dependencies"
    bl_label = "Install Dependencies"
    bl_description = "Install the anthropic Python package into Blender's user modules"

    def execute(self, context):
        modules_path = os.path.join(bpy.utils.script_path_user(), "modules")
        os.makedirs(modules_path, exist_ok=True)

        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    modules_path,
                    "anthropic",
                ],
                timeout=120,
            )
        except FileNotFoundError:
            self.report(
                {"ERROR"},
                "pip not found in Blender's Python. Cannot install dependencies.",
            )
            return {"CANCELLED"}
        except subprocess.CalledProcessError as e:
            self.report({"ERROR"}, f"pip install failed: {e}")
            return {"CANCELLED"}
        except subprocess.TimeoutExpired:
            self.report({"ERROR"}, "pip install timed out after 120 seconds.")
            return {"CANCELLED"}

        # Add to path and refresh flag
        if modules_path not in sys.path:
            sys.path.insert(0, modules_path)

        import blender_chat as pkg
        pkg.HAS_ANTHROPIC = pkg._check_anthropic()

        if pkg.HAS_ANTHROPIC:
            self.report({"INFO"}, "anthropic package installed successfully.")
        else:
            self.report(
                {"ERROR"},
                "Installation completed but anthropic still not importable.",
            )
            return {"CANCELLED"}

        return {"FINISHED"}


class BlenderChatPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    api_key: bpy.props.StringProperty(
        name="Claude API Key",
        description="Your Anthropic API key",
        subtype="PASSWORD",
        default="",
    )

    model: bpy.props.EnumProperty(
        name="Model",
        description="Claude model to use",
        items=[
            ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5", "Balanced speed and capability"),
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5", "Lesser, faster, cheaper model."),
        ],
        default="claude-sonnet-4-5-20250929",
    )

    show_tool_calls: bpy.props.BoolProperty(
        name="Show Tool Calls",
        description="Display tool call details in the chat",
        default=True,
    )

    max_conversation_messages: bpy.props.IntProperty(
        name="Prior messages included as context (incl. user/assistant/tools, less is faster/cheaper)",
        description="Maximum number of messages kept in conversation history",
        default=60,
        min=10,
        max=200,
    )

    def draw(self, context):
        layout = self.layout

        from . import HAS_ANTHROPIC
        if not HAS_ANTHROPIC:
            box = layout.box()
            box.label(text="Required: anthropic package not found", icon="ERROR")
            box.operator(
                "blenderchat.install_dependencies", icon="IMPORT"
            )
            box.label(text="Click above to install, then restart Blender.")
            layout.separator()

        layout.label(text="Manage Credits and Private API Keys on 'platform.claude.com'.")
        layout.prop(self, "api_key")
        layout.prop(self, "model")
        layout.prop(self, "show_tool_calls")
        layout.prop(self, "max_conversation_messages")


_classes = [
    BLENDERCHAT_OT_InstallDependencies,
    BlenderChatPreferences,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
