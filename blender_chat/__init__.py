bl_info = {
    "name": "BlenderChat",
    "author": "BlenderChat Contributors",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Chat",
    "description": "Chat with Claude AI to control Blender",
    "category": "Interface",
}

import importlib
import sys
import os


def _ensure_user_modules_on_path():
    """Add Blender user modules directory to sys.path if not present."""
    user_modules = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "modules",
    )
    if os.path.isdir(user_modules) and user_modules not in sys.path:
        sys.path.insert(0, user_modules)

    scripts_modules = os.path.join(
        __import__("bpy").utils.script_path_user(), "modules"
    )
    if os.path.isdir(scripts_modules) and scripts_modules not in sys.path:
        sys.path.insert(0, scripts_modules)


def _check_anthropic():
    """Return True if the anthropic package is importable."""
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


# Module-level flag, refreshed on register
HAS_ANTHROPIC = False

# Submodules in registration order
_submodule_names = [
    "preferences",
    "properties",
    "panels",
    "operators",
]

_submodules = []


def _import_submodules():
    global _submodules
    _submodules = []
    for name in _submodule_names:
        full = f"{__package__}.{name}"
        if full in sys.modules:
            mod = importlib.reload(sys.modules[full])
        else:
            mod = importlib.import_module(full)
        _submodules.append(mod)


def register():
    import bpy

    global HAS_ANTHROPIC

    _ensure_user_modules_on_path()
    HAS_ANTHROPIC = _check_anthropic()

    _import_submodules()

    for mod in _submodules:
        if hasattr(mod, "register"):
            mod.register()

    from .properties import BlenderChatSceneProperties
    bpy.types.Scene.blenderchat = bpy.props.PointerProperty(
        type=BlenderChatSceneProperties
    )


def unregister():
    import bpy

    if hasattr(bpy.types.Scene, "blenderchat"):
        del bpy.types.Scene.blenderchat

    for mod in reversed(_submodules):
        if hasattr(mod, "unregister"):
            mod.unregister()
