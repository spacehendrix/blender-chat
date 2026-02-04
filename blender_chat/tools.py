import bpy
import json
import math
import traceback


# ---------------------------------------------------------------------------
# Tool JSON Schemas (Anthropic format)
# ---------------------------------------------------------------------------

BLENDER_TOOLS = [
    {
        "name": "get_scene_info",
        "description": "Get information about the current Blender scene, including objects, materials, and settings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detail_level": {
                    "type": "string",
                    "enum": ["summary", "full"],
                    "description": "Level of detail. 'summary' for overview, 'full' for complete details.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_object",
        "description": "Create a primitive mesh object in the scene.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["CUBE", "SPHERE", "CYLINDER", "CONE", "TORUS", "PLANE", "CIRCLE", "MONKEY"],
                    "description": "The type of primitive to create.",
                },
                "name": {
                    "type": "string",
                    "description": "Name for the new object. Optional.",
                },
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Location as [x, y, z]. Default [0, 0, 0].",
                },
                "scale": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Scale as [x, y, z]. Default [1, 1, 1].",
                },
                "rotation": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Rotation in degrees as [x, y, z]. Default [0, 0, 0].",
                },
            },
            "required": ["type"],
        },
    },
    {
        "name": "modify_object",
        "description": "Modify properties of an existing object (location, rotation, scale, visibility).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the object to modify.",
                },
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "New location [x, y, z].",
                },
                "rotation": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "New rotation in degrees [x, y, z].",
                },
                "scale": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "New scale [x, y, z].",
                },
                "visible": {
                    "type": "boolean",
                    "description": "Set viewport visibility.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "delete_object",
        "description": "Delete one or more objects from the scene by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of object names to delete.",
                },
            },
            "required": ["names"],
        },
    },
    {
        "name": "set_material",
        "description": "Create or assign a material to an object with Principled BSDF properties.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Name of the object to assign the material to.",
                },
                "material_name": {
                    "type": "string",
                    "description": "Name for the material. If it exists, it will be reused.",
                },
                "base_color": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 4,
                    "description": "Base color as [R, G, B] or [R, G, B, A], values 0-1.",
                },
                "metallic": {
                    "type": "number",
                    "description": "Metallic value 0-1.",
                },
                "roughness": {
                    "type": "number",
                    "description": "Roughness value 0-1.",
                },
            },
            "required": ["object_name", "material_name"],
        },
    },
    {
        "name": "add_modifier",
        "description": "Add a modifier to an object.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Name of the object.",
                },
                "modifier_type": {
                    "type": "string",
                    "enum": ["SUBSURF", "MIRROR", "ARRAY", "BEVEL", "SOLIDIFY", "BOOLEAN", "DECIMATE", "WIREFRAME"],
                    "description": "Type of modifier to add.",
                },
                "properties": {
                    "type": "object",
                    "description": "Modifier-specific properties as key-value pairs (e.g., {\"levels\": 2} for SUBSURF).",
                },
            },
            "required": ["object_name", "modifier_type"],
        },
    },
    {
        "name": "set_camera",
        "description": "Position and configure the active camera.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Camera location [x, y, z].",
                },
                "rotation": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Camera rotation in degrees [x, y, z].",
                },
                "focal_length": {
                    "type": "number",
                    "description": "Focal length in mm.",
                },
                "look_at": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Point the camera at this location [x, y, z]. Overrides rotation if set.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "add_light",
        "description": "Add a light to the scene.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["POINT", "SUN", "SPOT", "AREA"],
                    "description": "Light type.",
                },
                "name": {
                    "type": "string",
                    "description": "Name for the light.",
                },
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Light location [x, y, z].",
                },
                "energy": {
                    "type": "number",
                    "description": "Light energy/power.",
                },
                "color": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "Light color [R, G, B], values 0-1.",
                },
            },
            "required": ["type"],
        },
    },
    {
        "name": "execute_bpy_code",
        "description": "Execute arbitrary Python code with access to bpy, mathutils, and math modules. "
                       "Assign any return value to a variable called 'result'. "
                       "Use this for operations not covered by other tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Has access to bpy, mathutils, and math.",
                },
            },
            "required": ["code"],
        },
    },
    # ----- Discovery + Dispatch tools -----
    {
        "name": "list_operator_modules",
        "description": "List all bpy.ops submodules (e.g. mesh, object, cloth) with operator counts.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_operators",
        "description": "List operators in a bpy.ops submodule with their descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "The bpy.ops submodule name (e.g. 'mesh', 'object', 'cloth').",
                },
                "filter": {
                    "type": "string",
                    "description": "Optional substring filter on operator name or description.",
                },
            },
            "required": ["module"],
        },
    },
    {
        "name": "get_operator_info",
        "description": "Get full parameter schema for a bpy.ops operator via RNA introspection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "The bpy.ops submodule name (e.g. 'mesh').",
                },
                "operator": {
                    "type": "string",
                    "description": "The operator name (e.g. 'primitive_cube_add').",
                },
            },
            "required": ["module", "operator"],
        },
    },
    {
        "name": "call_operator",
        "description": "Call any bpy.ops operator by module and name with optional parameters. "
                       "Parameters are automatically coerced to the correct types.",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "The bpy.ops submodule name (e.g. 'object').",
                },
                "operator": {
                    "type": "string",
                    "description": "The operator name (e.g. 'modifier_add').",
                },
                "params": {
                    "type": "object",
                    "description": "Operator parameters as key-value pairs.",
                },
            },
            "required": ["module", "operator"],
        },
    },
    {
        "name": "query_blender_data",
        "description": "Read from bpy.data or bpy.context via a safe expression. "
                       "Expression must start with 'bpy.data' or 'bpy.context'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A Python expression starting with 'bpy.data' or 'bpy.context' (e.g. 'bpy.context.active_object.modifiers[-1].settings').",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Max depth for serializing nested objects. Default 1.",
                },
            },
            "required": ["expression"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Execution Handlers
# ---------------------------------------------------------------------------

def execute_tool(name, tool_input):
    """Dispatch a tool call to the appropriate handler.

    Returns: {"success": bool, "result": str}
    """
    handlers = {
        "get_scene_info": _handle_get_scene_info,
        "create_object": _handle_create_object,
        "modify_object": _handle_modify_object,
        "delete_object": _handle_delete_object,
        "set_material": _handle_set_material,
        "add_modifier": _handle_add_modifier,
        "set_camera": _handle_set_camera,
        "add_light": _handle_add_light,
        "execute_bpy_code": _handle_execute_bpy_code,
        "list_operator_modules": _handle_list_operator_modules,
        "list_operators": _handle_list_operators,
        "get_operator_info": _handle_get_operator_info,
        "call_operator": _handle_call_operator,
        "query_blender_data": _handle_query_blender_data,
    }

    handler = handlers.get(name)
    if not handler:
        return {"success": False, "result": f"Unknown tool: {name}"}

    try:
        return handler(tool_input)
    except Exception as e:
        return {
            "success": False,
            "result": f"Error executing {name}: {e}\n{traceback.format_exc()}",
        }


def _handle_get_scene_info(params):
    from .scene_context import get_scene_summary
    return {"success": True, "result": get_scene_summary()}


def _handle_create_object(params):
    obj_type = params["type"]
    location = tuple(params.get("location", [0, 0, 0]))
    scale = tuple(params.get("scale", [1, 1, 1]))
    rotation_deg = params.get("rotation", [0, 0, 0])
    rotation = tuple(math.radians(r) for r in rotation_deg)
    name = params.get("name")

    _ensure_object_mode()

    # Deselect all first
    bpy.ops.object.select_all(action="DESELECT")

    ops_map = {
        "CUBE": bpy.ops.mesh.primitive_cube_add,
        "SPHERE": bpy.ops.mesh.primitive_uv_sphere_add,
        "CYLINDER": bpy.ops.mesh.primitive_cylinder_add,
        "CONE": bpy.ops.mesh.primitive_cone_add,
        "TORUS": bpy.ops.mesh.primitive_torus_add,
        "PLANE": bpy.ops.mesh.primitive_plane_add,
        "CIRCLE": bpy.ops.mesh.primitive_circle_add,
        "MONKEY": bpy.ops.mesh.primitive_monkey_add,
    }

    op = ops_map.get(obj_type)
    if not op:
        return {"success": False, "result": f"Unknown object type: {obj_type}"}

    if obj_type == "TORUS":
        op(location=location, rotation=rotation)
    else:
        op(location=location, rotation=rotation)

    obj = bpy.context.active_object
    obj.scale = scale

    if name:
        obj.name = name
        if obj.data:
            obj.data.name = name

    return {"success": True, "result": f"Created {obj_type} '{obj.name}' at {list(location)}"}


def _handle_modify_object(params):
    name = params["name"]
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"success": False, "result": f"Object '{name}' not found"}

    changes = []

    if "location" in params:
        obj.location = tuple(params["location"])
        changes.append(f"location={list(params['location'])}")

    if "rotation" in params:
        rot = tuple(math.radians(r) for r in params["rotation"])
        obj.rotation_euler = rot
        changes.append(f"rotation={list(params['rotation'])}deg")

    if "scale" in params:
        obj.scale = tuple(params["scale"])
        changes.append(f"scale={list(params['scale'])}")

    if "visible" in params:
        obj.hide_viewport = not params["visible"]
        obj.hide_render = not params["visible"]
        changes.append(f"visible={params['visible']}")

    return {"success": True, "result": f"Modified '{name}': {', '.join(changes)}"}


def _handle_delete_object(params):
    names = params["names"]
    deleted = []
    not_found = []

    _ensure_object_mode()
    bpy.ops.object.select_all(action="DESELECT")

    for name in names:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)
            deleted.append(name)
        else:
            not_found.append(name)

    if deleted:
        bpy.ops.object.delete()

    parts = []
    if deleted:
        parts.append(f"Deleted: {', '.join(deleted)}")
    if not_found:
        parts.append(f"Not found: {', '.join(not_found)}")

    return {"success": len(not_found) == 0, "result": ". ".join(parts)}


def _handle_set_material(params):
    obj_name = params["object_name"]
    mat_name = params["material_name"]

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"success": False, "result": f"Object '{obj_name}' not found"}

    if not hasattr(obj.data, "materials"):
        return {"success": False, "result": f"Object '{obj_name}' does not support materials"}

    # Get or create material
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    principled = None
    for node in nodes:
        if node.type == "BSDF_PRINCIPLED":
            principled = node
            break

    if not principled:
        principled = nodes.new("ShaderNodeBsdfPrincipled")

    if "base_color" in params:
        color = list(params["base_color"])
        if len(color) == 3:
            color.append(1.0)
        principled.inputs["Base Color"].default_value = color

    if "metallic" in params:
        principled.inputs["Metallic"].default_value = params["metallic"]

    if "roughness" in params:
        principled.inputs["Roughness"].default_value = params["roughness"]

    # Assign to object
    if mat.name not in [m.name for m in obj.data.materials if m]:
        obj.data.materials.append(mat)
    else:
        for i, m in enumerate(obj.data.materials):
            if m and m.name == mat.name:
                obj.data.materials[i] = mat
                break

    return {"success": True, "result": f"Material '{mat_name}' applied to '{obj_name}'"}


def _handle_add_modifier(params):
    obj_name = params["object_name"]
    mod_type = params["modifier_type"]
    props = params.get("properties", {})

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"success": False, "result": f"Object '{obj_name}' not found"}

    modifier = obj.modifiers.new(name=mod_type, type=mod_type)

    # Apply properties
    for key, value in props.items():
        if hasattr(modifier, key):
            setattr(modifier, key, value)

    return {"success": True, "result": f"Added {mod_type} modifier to '{obj_name}'"}


def _handle_set_camera(params):
    camera = bpy.context.scene.camera
    if not camera:
        return {"success": False, "result": "No active camera in scene"}

    changes = []

    if "location" in params:
        camera.location = tuple(params["location"])
        changes.append(f"location={list(params['location'])}")

    if "look_at" in params:
        from mathutils import Vector, Matrix
        target = Vector(params["look_at"])
        cam_loc = camera.location
        direction = target - cam_loc
        rot_quat = direction.to_track_quat("-Z", "Y")
        camera.rotation_euler = rot_quat.to_euler()
        changes.append(f"looking at {list(params['look_at'])}")
    elif "rotation" in params:
        rot = tuple(math.radians(r) for r in params["rotation"])
        camera.rotation_euler = rot
        changes.append(f"rotation={list(params['rotation'])}deg")

    if "focal_length" in params and camera.data:
        camera.data.lens = params["focal_length"]
        changes.append(f"focal_length={params['focal_length']}mm")

    return {"success": True, "result": f"Camera updated: {', '.join(changes)}"}


def _handle_add_light(params):
    light_type = params["type"]
    name = params.get("name", f"{light_type.title()}Light")
    location = tuple(params.get("location", [0, 0, 5]))
    energy = params.get("energy", 1000)
    color = params.get("color", [1.0, 1.0, 1.0])

    light_data = bpy.data.lights.new(name=name, type=light_type)
    light_data.energy = energy
    light_data.color = tuple(color)

    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = location

    return {"success": True, "result": f"Added {light_type} light '{light_obj.name}' at {list(location)}"}


def _handle_execute_bpy_code(params):
    code = params["code"]
    import mathutils

    namespace = {
        "bpy": bpy,
        "mathutils": mathutils,
        "math": math,
        "result": None,
    }

    try:
        exec(code, namespace)
    except Exception as e:
        return {
            "success": False,
            "result": f"Code execution error: {e}\n{traceback.format_exc()}",
        }

    result_val = namespace.get("result")
    if result_val is not None:
        return {"success": True, "result": str(result_val)}

    return {"success": True, "result": "Code executed successfully (no result variable set)"}


# ---------------------------------------------------------------------------
# Discovery + Dispatch Handlers
# ---------------------------------------------------------------------------

def _handle_list_operator_modules(params):
    from .introspection import list_op_modules
    modules = list_op_modules()
    return {"success": True, "result": json.dumps(modules)}


def _handle_list_operators(params):
    from .introspection import list_ops_in_module
    module_name = params["module"]
    filter_str = params.get("filter")
    ops = list_ops_in_module(module_name, filter_str)
    if ops is None:
        return {"success": False, "result": f"Module 'bpy.ops.{module_name}' not found."}
    return {"success": True, "result": json.dumps(ops)}


def _handle_get_operator_info(params):
    from .introspection import get_op_info
    info = get_op_info(params["module"], params["operator"])
    if info is None:
        return {"success": False, "result": f"Operator 'bpy.ops.{params['module']}.{params['operator']}' not found."}
    return {"success": True, "result": json.dumps(info)}


def _handle_call_operator(params):
    from .introspection import call_op
    return call_op(params["module"], params["operator"], params.get("params"))


def _handle_query_blender_data(params):
    from .introspection import evaluate_data_expression
    return evaluate_data_expression(params["expression"], params.get("max_depth", 1))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_object_mode():
    """Switch to Object mode if not already, handling context safely."""
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
