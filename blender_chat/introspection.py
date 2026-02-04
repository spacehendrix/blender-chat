import bpy
import traceback


# ---------------------------------------------------------------------------
# Module / Operator Discovery
# ---------------------------------------------------------------------------

def list_op_modules():
    """List all bpy.ops submodules with operator counts.

    Returns list of {"name": str, "operator_count": int}.
    """
    modules = []
    for name in sorted(dir(bpy.ops)):
        if name.startswith("_"):
            continue
        submod = getattr(bpy.ops, name, None)
        if submod is None:
            continue
        try:
            count = len(dir(submod))
        except Exception:
            count = 0
        modules.append({"name": name, "operator_count": count})
    return modules


def list_ops_in_module(module_name, filter_str=None):
    """List operators in a bpy.ops submodule.

    Args:
        module_name: e.g. "mesh", "object", "cloth"
        filter_str: optional substring filter on name or description

    Returns list of {"name": str, "description": str}, or None if module
    not found. Truncated to 100 entries with total count included.
    """
    submod = getattr(bpy.ops, module_name, None)
    if submod is None:
        return None

    ops = []
    for op_name in sorted(dir(submod)):
        if op_name.startswith("_"):
            continue
        try:
            op_func = getattr(submod, op_name)
            rna = op_func.get_rna_type()
            desc = rna.description or ""
        except Exception:
            desc = ""

        if filter_str:
            lower_filter = filter_str.lower()
            if lower_filter not in op_name.lower() and lower_filter not in desc.lower():
                continue

        ops.append({"name": op_name, "description": desc})

    total = len(ops)
    truncated = ops[:100]
    if total > 100:
        truncated.append({"name": "...", "description": f"Truncated. {total} total operators, showing first 100. Use filter to narrow."})
    return truncated


# ---------------------------------------------------------------------------
# Operator Introspection
# ---------------------------------------------------------------------------

_RNA_TYPE_MAP = {
    "BOOLEAN": "BOOLEAN",
    "INT": "INT",
    "FLOAT": "FLOAT",
    "STRING": "STRING",
    "ENUM": "ENUM",
    "POINTER": "POINTER",
    "COLLECTION": "COLLECTION",
}


def _prop_info(prop):
    """Extract parameter info from an RNA property."""
    info = {
        "name": prop.identifier,
        "type": _rna_type_string(prop),
        "description": prop.description or "",
        "is_required": not prop.is_skip_save,
    }

    rna_type = prop.type

    if rna_type in ("INT", "FLOAT"):
        info["default"] = prop.default
        if hasattr(prop, "hard_min"):
            info["min"] = prop.hard_min
            info["max"] = prop.hard_max

    elif rna_type == "BOOLEAN":
        info["default"] = prop.default

    elif rna_type == "STRING":
        info["default"] = prop.default

    elif rna_type == "ENUM":
        items = []
        try:
            for item in prop.enum_items:
                items.append({"id": item.identifier, "name": item.name, "description": item.description})
        except Exception:
            pass
        info["enum_items"] = items
        if hasattr(prop, "default"):
            info["default"] = prop.default

    # Vector types have array_length
    if hasattr(prop, "array_length") and prop.array_length > 0:
        info["array_length"] = prop.array_length
        if hasattr(prop, "default_array"):
            info["default"] = list(prop.default_array)

    return info


def _rna_type_string(prop):
    """Map RNA property to a type string."""
    rna_type = prop.type
    if hasattr(prop, "array_length") and prop.array_length > 0:
        prefix_map = {"FLOAT": "FLOAT_VECTOR", "INT": "INT_VECTOR", "BOOLEAN": "BOOL_VECTOR"}
        return prefix_map.get(rna_type, rna_type)
    return _RNA_TYPE_MAP.get(rna_type, rna_type)


def get_op_info(module_name, op_name):
    """Full parameter schema for a bpy.ops operator via RNA introspection.

    Returns dict with idname, description, parameters list, or None if not found.
    """
    submod = getattr(bpy.ops, module_name, None)
    if submod is None:
        return None

    op_func = getattr(submod, op_name, None)
    if op_func is None:
        return None

    try:
        rna = op_func.get_rna_type()
    except Exception:
        return None

    params = []
    for prop in rna.properties:
        if prop.identifier == "rna_type":
            continue
        try:
            params.append(_prop_info(prop))
        except Exception:
            params.append({"name": prop.identifier, "type": "UNKNOWN", "description": ""})

    return {
        "idname": f"{module_name}.{op_name}",
        "description": rna.description or "",
        "parameters": params,
    }


# ---------------------------------------------------------------------------
# Generic Operator Dispatch
# ---------------------------------------------------------------------------

def call_op(module_name, op_name, params=None):
    """Call bpy.ops.{module_name}.{op_name}(**params) with type coercion.

    Returns {"success": bool, "result": str}.
    """
    submod = getattr(bpy.ops, module_name, None)
    if submod is None:
        return {"success": False, "result": f"Module 'bpy.ops.{module_name}' not found."}

    op_func = getattr(submod, op_name, None)
    if op_func is None:
        return {"success": False, "result": f"Operator 'bpy.ops.{module_name}.{op_name}' not found."}

    coerced = {}
    if params:
        try:
            rna = op_func.get_rna_type()
            rna_props = {p.identifier: p for p in rna.properties}
        except Exception:
            rna_props = {}

        for key, value in params.items():
            prop = rna_props.get(key)
            if prop is None:
                coerced[key] = value
                continue
            try:
                coerced[key] = _coerce_value(value, prop)
            except Exception as e:
                return {
                    "success": False,
                    "result": f"Type coercion failed for param '{key}': {e}. Expected type: {_rna_type_string(prop)}",
                }

    try:
        result = op_func(**coerced)
        return {"success": True, "result": f"Operator {module_name}.{op_name} returned {result!r}"}
    except RuntimeError as e:
        mode = getattr(bpy.context, "mode", "UNKNOWN")
        active = getattr(bpy.context, "active_object", None)
        active_name = active.name if active else "None"
        return {
            "success": False,
            "result": f"RuntimeError: {e}. Current mode: {mode}, active object: {active_name}",
        }
    except Exception as e:
        return {"success": False, "result": f"Error calling operator: {e}\n{traceback.format_exc()}"}


def _coerce_value(value, prop):
    """Coerce a JSON value to the type expected by an RNA property."""
    rna_type = prop.type
    is_array = hasattr(prop, "array_length") and prop.array_length > 0

    if is_array and isinstance(value, (list, tuple)):
        if rna_type == "FLOAT":
            return tuple(float(v) for v in value)
        elif rna_type == "INT":
            return tuple(int(v) for v in value)
        elif rna_type == "BOOLEAN":
            return tuple(bool(v) for v in value)
        return tuple(value)

    if rna_type == "INT":
        return int(value)
    elif rna_type == "FLOAT":
        return float(value)
    elif rna_type == "BOOLEAN":
        return bool(value)
    elif rna_type == "STRING":
        return str(value)
    elif rna_type == "ENUM":
        valid = {item.identifier for item in prop.enum_items}
        sv = str(value)
        if valid and sv not in valid:
            raise ValueError(f"'{sv}' not in valid enum values: {sorted(valid)}")
        return sv

    return value


# ---------------------------------------------------------------------------
# Safe Data Expression Evaluation
# ---------------------------------------------------------------------------

_EXPR_BLACKLIST = ("__", "import", "exec(", "eval(", "compile(", "open(", "os.", "sys.", "subprocess")


def evaluate_data_expression(expression, max_depth=1):
    """Safely evaluate a bpy.data or bpy.context expression.

    Returns {"success": bool, "result": str}.
    """
    expr = expression.strip()

    if not (expr.startswith("bpy.data") or expr.startswith("bpy.context")):
        return {
            "success": False,
            "result": "Expression must start with 'bpy.data' or 'bpy.context'.",
        }

    for pattern in _EXPR_BLACKLIST:
        if pattern in expr:
            return {
                "success": False,
                "result": f"Expression contains forbidden pattern: '{pattern}'",
            }

    try:
        result = eval(expr, {"__builtins__": {}, "bpy": bpy})  # noqa: S307
    except Exception as e:
        return {"success": False, "result": f"Evaluation error: {e}"}

    serialized = _serialize_result(result, max_depth=max_depth)
    return {"success": True, "result": serialized}


def _serialize_result(value, depth=0, max_depth=1):
    """Serialize a bpy value to a string, respecting depth limits."""
    MAX_CHARS = 4000

    if isinstance(value, (bool, int, float)):
        return str(value)

    if isinstance(value, str):
        return repr(value)

    if value is None:
        return "None"

    # bpy ID types (Object, Mesh, Material, etc.)
    if hasattr(value, "bl_rna"):
        if depth >= max_depth:
            name = getattr(value, "name", None)
            return f"<{value.__class__.__name__} '{name}'>" if name else f"<{value.__class__.__name__}>"
        props = {}
        try:
            for prop in value.bl_rna.properties:
                if prop.identifier == "rna_type":
                    continue
                try:
                    v = getattr(value, prop.identifier)
                    props[prop.identifier] = _serialize_result(v, depth + 1, max_depth)
                except Exception:
                    pass
                if len(str(props)) > MAX_CHARS:
                    props["..."] = "truncated"
                    break
        except Exception:
            return repr(value)
        return str(props)

    # bpy collection types
    type_name = type(value).__name__
    if "bpy_prop_collection" in type_name or hasattr(value, "values"):
        try:
            items = []
            for i, item in enumerate(value):
                if i >= 50:
                    items.append(f"... ({len(value)} total)")
                    break
                items.append(_serialize_result(item, depth + 1, max_depth))
                if sum(len(s) for s in items) > MAX_CHARS:
                    items.append("... truncated")
                    break
            return f"[{', '.join(items)}]"
        except Exception:
            return repr(value)

    # Lists / tuples
    if isinstance(value, (list, tuple)):
        items = [_serialize_result(v, depth + 1, max_depth) for v in value[:50]]
        result = f"[{', '.join(items)}]"
        if len(result) > MAX_CHARS:
            return result[:MAX_CHARS] + "... truncated"
        return result

    # Dicts
    if isinstance(value, dict):
        parts = []
        for k, v in list(value.items())[:50]:
            parts.append(f"{k!r}: {_serialize_result(v, depth + 1, max_depth)}")
        result = "{" + ", ".join(parts) + "}"
        if len(result) > MAX_CHARS:
            return result[:MAX_CHARS] + "... truncated"
        return result

    # Fallback
    result = repr(value)
    if len(result) > MAX_CHARS:
        return result[:MAX_CHARS] + "... truncated"
    return result
