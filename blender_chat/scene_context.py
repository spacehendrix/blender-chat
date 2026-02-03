import bpy


def get_scene_summary():
    """Return a text summary of the current Blender scene state."""
    scene = bpy.context.scene
    lines = []

    lines.append(f"Scene: {scene.name}")
    lines.append(f"Frame range: {scene.frame_start}-{scene.frame_end} (current: {scene.frame_current})")
    lines.append(f"Render engine: {scene.render.engine}")
    lines.append(f"Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
    lines.append("")

    objects = list(scene.objects)
    lines.append(f"Objects ({len(objects)}):")

    for obj in objects:
        active_marker = " [ACTIVE]" if obj == bpy.context.view_layer.objects.active else ""
        selected_marker = " [SELECTED]" if obj.select_get() else ""
        loc = f"({obj.location.x:.2f}, {obj.location.y:.2f}, {obj.location.z:.2f})"
        lines.append(f"  - {obj.name} (type={obj.type}) at {loc}{active_marker}{selected_marker}")

        if obj.scale.x != 1 or obj.scale.y != 1 or obj.scale.z != 1:
            lines.append(f"    Scale: ({obj.scale.x:.2f}, {obj.scale.y:.2f}, {obj.scale.z:.2f})")

        if obj.rotation_euler.x != 0 or obj.rotation_euler.y != 0 or obj.rotation_euler.z != 0:
            import math
            rx = math.degrees(obj.rotation_euler.x)
            ry = math.degrees(obj.rotation_euler.y)
            rz = math.degrees(obj.rotation_euler.z)
            lines.append(f"    Rotation: ({rx:.1f}, {ry:.1f}, {rz:.1f}) degrees")

        if not obj.visible_get():
            lines.append("    Visibility: hidden")

        # Materials
        if obj.data and hasattr(obj.data, "materials") and obj.data.materials:
            mat_names = [m.name if m else "None" for m in obj.data.materials]
            lines.append(f"    Materials: {', '.join(mat_names)}")

        # Modifiers
        if obj.modifiers:
            mod_names = [f"{m.name}({m.type})" for m in obj.modifiers]
            lines.append(f"    Modifiers: {', '.join(mod_names)}")

    # World info
    if scene.world:
        lines.append(f"\nWorld: {scene.world.name}")

    # Camera info
    if scene.camera:
        cam = scene.camera
        lines.append(f"\nActive camera: {cam.name}")
        if cam.data:
            lines.append(f"  Focal length: {cam.data.lens}mm")

    return "\n".join(lines)
