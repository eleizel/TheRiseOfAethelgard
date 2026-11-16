"""Visual overlay generator for map collisions, triggers, and lights.
Exports annotated overlay images for Oakhaven Village and Briarwood Verge.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render_map_debug_overlay(map_json_path: Path, output_image_path: Path):
    with open(map_json_path, encoding="utf-8") as f:
        data = json.load(f)

    dims = data.get("dimensions", {})
    w, h = dims.get("width", 1280), dims.get("height", 720)

    # 1. Base canvas
    bg_info = data.get("background", {})
    bg_type = bg_info.get("type", "single_composite")
    base_img = Image.new("RGBA", (w, h), (30, 30, 30, 255))

    root_dir = map_json_path.parent.parent.parent.parent  # project root

    if bg_type == "single_composite":
        img_rel = bg_info.get("image")
        img_full = root_dir / img_rel
        if img_full.exists():
            loaded_bg = Image.open(img_full).convert("RGBA")
            if loaded_bg.size != (w, h):
                loaded_bg = loaded_bg.resize((w, h), Image.Resampling.LANCZOS)
            base_img.paste(loaded_bg, (0, 0))
    elif bg_type == "slices":
        for slice_info in bg_info.get("slices", []):
            img_rel = slice_info.get("image")
            img_full = root_dir / img_rel
            sx, sy = slice_info.get("x", 0), slice_info.get("y", 0)
            if img_full.exists():
                loaded_slice = Image.open(img_full).convert("RGBA")
                # Omitted destination dimensions mean native source dimensions.
                sw = int(slice_info.get("w", loaded_slice.width))
                sh = int(slice_info.get("h", loaded_slice.height))
                if sw <= 0 or sh <= 0:
                    raise ValueError(f"Invalid slice dimensions for '{img_rel}': {sw}x{sh}")
                if loaded_slice.size != (sw, sh):
                    loaded_slice = loaded_slice.resize((sw, sh), Image.Resampling.LANCZOS)
                base_img.alpha_composite(loaded_slice, dest=(sx, sy))

    # 2. Transparent overlay layers
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw grid lines faintly (32x32 tiles)
    tile_size = data.get("tile_size", 32)
    grid_color = (255, 255, 255, 25)
    for x in range(0, w, tile_size):
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
    for y in range(0, h, tile_size):
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)

    # Standard font
    try:
        font = ImageFont.truetype("arial.ttf", 11)
        font_large = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
        font_large = ImageFont.load_default()

    # Draw Collisions (Red semi-transparent boxes + solid red outline)
    collisions = data.get("collisions", [])
    for col in collisions:
        cx, cy = col["x"], col["y"]
        cw, ch = col["w"], col["h"]
        cid = col.get("id", "col")

        # Fill
        draw.rectangle([cx, cy, cx + cw, cy + ch], fill=(235, 45, 45, 95), outline=(255, 30, 30, 230), width=2)
        # Label banner
        draw.rectangle([cx + 2, cy + 2, cx + min(cw - 4, len(cid) * 7 + 10), cy + 16], fill=(40, 0, 0, 200))
        draw.text((cx + 4, cy + 3), f"{cid} ({cw}x{ch})", fill=(255, 220, 220, 255), font=font)

    # Draw Triggers (Green / Blue / Purple)
    triggers = data.get("triggers", [])
    for trig in triggers:
        tx, ty = trig["x"], trig["y"]
        tw, th = trig["width"], trig["height"]
        tid = trig.get("id", "trig")
        ttype = trig.get("trigger_type", "trigger")

        if ttype == "transition":
            fill_col = (45, 120, 245, 110)
            outline_col = (80, 160, 255, 255)
            target = trig.get("target_map_id", "")
            label = f"[TRANSITION] {tid} -> {target}"
        elif ttype == "dialogue":
            fill_col = (40, 215, 95, 110)
            outline_col = (60, 255, 120, 255)
            dlg = trig.get("dialogue_id", "")
            label = f"[DIALOGUE] {tid} ({dlg})"
        else:
            fill_col = (230, 180, 30, 110)
            outline_col = (255, 220, 50, 255)
            label = f"[{ttype.upper()}] {tid}"

        draw.rectangle([tx, ty, tx + tw, ty + th], fill=fill_col, outline=outline_col, width=3)
        draw.rectangle([tx + 2, ty + 2, tx + min(tw - 4, len(label) * 7 + 12), ty + 18], fill=(0, 30, 10, 220))
        draw.text((tx + 4, ty + 4), label, fill=(255, 255, 255, 255), font=font)

    # Draw Props / Light markers (Yellow circles / icons)
    props = data.get("props", [])
    for prop in props:
        px, py = prop["x"], prop["y"]
        pw, ph = prop.get("width", 16), prop.get("height", 16)
        pid = prop.get("id", "prop")
        light = prop.get("light")
        if light:
            radius = light.get("radius", 60)
            # draw light halo circle outline
            draw.ellipse([px + pw//2 - radius, py + ph//2 - radius, px + pw//2 + radius, py + ph//2 + radius],
                         outline=(255, 235, 100, 120), width=1)
            # draw core center marker
            draw.rectangle([px, py, px + pw, py + ph], fill=(255, 230, 70, 200), outline=(255, 255, 255, 255), width=2)
            draw.text((px + pw + 4, py), f"* {pid} (r={radius})", fill=(255, 255, 200, 255), font=font)
        else:
            draw.rectangle([px, py, px + pw, py + ph], fill=(200, 100, 255, 160), outline=(240, 200, 255, 255), width=2)
            draw.text((px + pw + 4, py), pid, fill=(240, 200, 255, 255), font=font)

    # 3. Legend / HUD box in top-right or top-left corner
    legend_w, legend_h = 320, 125
    legend_x, legend_y = w - legend_w - 15, 15
    draw.rectangle([legend_x, legend_y, legend_x + legend_w, legend_y + legend_h],
                   fill=(15, 20, 25, 235), outline=(180, 170, 140, 255), width=2)

    draw.text((legend_x + 10, legend_y + 8), f"{data.get('name', 'Map')} - Debug Zones", fill=(255, 235, 180, 255), font=font_large)
    draw.line([(legend_x + 10, legend_y + 28), (legend_x + legend_w - 10, legend_y + 28)], fill=(100, 100, 100, 255), width=1)

    # Collision item
    draw.rectangle([legend_x + 12, legend_y + 36, legend_x + 28, legend_y + 48], fill=(235, 45, 45, 160), outline=(255, 30, 30, 255), width=1)
    draw.text((legend_x + 36, legend_y + 35), "Collision Solid (Impassable)", fill=(255, 200, 200, 255), font=font)

    # Dialogue trigger
    draw.rectangle([legend_x + 12, legend_y + 54, legend_x + 28, legend_y + 66], fill=(40, 215, 95, 160), outline=(60, 255, 120, 255), width=1)
    draw.text((legend_x + 36, legend_y + 53), "Dialogue Trigger (Interaction)", fill=(200, 255, 210, 255), font=font)

    # Transition trigger
    draw.rectangle([legend_x + 12, legend_y + 72, legend_x + 28, legend_y + 84], fill=(45, 120, 245, 160), outline=(80, 160, 255, 255), width=1)
    draw.text((legend_x + 36, legend_y + 71), "Map Transition Zone", fill=(200, 225, 255, 255), font=font)

    # Light marker
    draw.ellipse([legend_x + 14, legend_y + 90, legend_x + 26, legend_y + 102], fill=(255, 230, 70, 220), outline=(255, 255, 255, 255), width=1)
    draw.text((legend_x + 36, legend_y + 89), "Point Light Source & Radius", fill=(255, 255, 210, 255), font=font)

    draw.text((legend_x + 10, legend_y + 108), f"Resolution: {w}x{h} px | Tile: {tile_size}px", fill=(170, 170, 170, 255), font=font)

    # Composite together
    final_img = Image.alpha_composite(base_img, overlay)
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(output_image_path, "PNG")
    print(f"Generated debug overlay: {output_image_path}")

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent

    # 1. Oakhaven Village
    oakhaven_json = project_root / "assets/maps/oakhaven_village/map.json"
    oakhaven_out = project_root / "assets/maps/oakhaven_village/collision_overlay.png"
    render_map_debug_overlay(oakhaven_json, oakhaven_out)

    # 2. Briarwood Verge
    briarwood_json = project_root / "assets/maps/briarwood_verge/map.json"
    briarwood_out = project_root / "assets/maps/briarwood_verge/collision_overlay.png"
    render_map_debug_overlay(briarwood_json, briarwood_out)

    # 3. Oakhaven Village Main
    oakhaven_main_json = project_root / "assets/maps/oakhaven_village_main/map.json"
    oakhaven_main_out = project_root / "assets/maps/oakhaven_village_main/collision_overlay.png"
    render_map_debug_overlay(oakhaven_main_json, oakhaven_main_out)

    # 4. Oakhaven General Shop
    shop_json = project_root / "assets/maps/shop_interior_oakhaven/map.json"
    shop_out = project_root / "assets/maps/shop_interior_oakhaven/collision_overlay.png"
    render_map_debug_overlay(shop_json, shop_out)

    # 5. Oakhaven Armory
    armory_json = project_root / "assets/maps/armory_interior_oakhaven/map.json"
    armory_out = project_root / "assets/maps/armory_interior_oakhaven/collision_overlay.png"
    render_map_debug_overlay(armory_json, armory_out)

    # 6. Oakhaven Tavern & Inn
    inn_json = project_root / "assets/maps/inn_interior_oakhaven/map.json"
    inn_out = project_root / "assets/maps/inn_interior_oakhaven/collision_overlay.png"
    render_map_debug_overlay(inn_json, inn_out)
