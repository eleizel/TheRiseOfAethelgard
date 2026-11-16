"""The Rise of Aethelgard - Interactive Visual Map Editor.

Launch with:
    .venv\\Scripts\\python src/tools/map_editor.py [map_id]

Features:
- Pan (Middle click or Space+Drag or Arrow keys) and Zoom (Mouse Wheel or +/-).
- Snap-to-Grid toggle (Freeform, 8px, 16px, 32px).
- Click & Drag to create boxes in active mode:
    [1] Collision Box (Red)
    [2] Dialogue Trigger (Green)
    [3] Map Transition Trigger (Blue)
    [4] Point Light Prop (Yellow)
- Selection & Editing:
    - Click to select an element.
    - Drag body to move, drag bottom-right corner handle to resize.
    - Delete / Backspace to remove selected element.
    - Sidebar fields to edit ID, dialogue_id, target_map_id, target_x/y, radius, flicker.
- Fast map switcher dropdown: switch between Oakhaven Village, Briarwood Verge, etc.
- 1-Click Save (Ctrl+S or Save Button) which updates map.json (with automatic backup)
  and regenerates collision_overlay.png.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pygame

if __package__:
    from .map_editor_utils import next_unique_id, validate_map_data
else:
    from map_editor_utils import next_unique_id, validate_map_data

# Initialize pygame
pygame.init()
pygame.font.init()

# Setup fonts
FONT_SMALL = pygame.font.SysFont("consolas", 12)
FONT_MED = pygame.font.SysFont("arial", 14, bold=True)
FONT_TITLE = pygame.font.SysFont("arial", 16, bold=True)

# Colors
COLOR_BG = (24, 26, 32)
COLOR_PANEL = (32, 35, 45)
COLOR_PANEL_BORDER = (55, 60, 75)
COLOR_TEXT = (220, 225, 235)
COLOR_TEXT_DIM = (140, 145, 160)
COLOR_TEXT_ACCENT = (255, 205, 90)

COLOR_COLLISION_FILL = (235, 45, 45, 90)
COLOR_COLLISION_LINE = (255, 50, 50, 240)
COLOR_DIALOGUE_FILL = (40, 215, 95, 95)
COLOR_DIALOGUE_LINE = (60, 255, 120, 240)
COLOR_TRANSITION_FILL = (45, 120, 245, 95)
COLOR_TRANSITION_LINE = (80, 160, 255, 240)
COLOR_LIGHT_FILL = (255, 230, 70, 130)
COLOR_LIGHT_LINE = (255, 240, 100, 240)

MODE_COLLISION = "collision"
MODE_DIALOGUE = "dialogue"
MODE_TRANSITION = "transition"
MODE_LIGHT = "light"


class VisualMapEditor:
    def __init__(self, project_root: Path, initial_map_id: str = "oakhaven_village"):
        self.project_root = project_root
        self.maps_dir = project_root / "assets" / "maps"
        self.available_maps = self._discover_maps()

        self.screen_w = 1280
        self.screen_h = 768
        self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
        pygame.display.set_caption("Aethelgard Map Editor - [Gideon Edition]")

        self.clock = pygame.time.Clock()
        self.running = True

        # Editor Viewport State
        self.zoom_levels = [0.25, 0.35, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        self.zoom_idx = 4  # 1.0 default
        self.zoom = self.zoom_levels[self.zoom_idx]
        self.camera_x = 40.0
        self.camera_y = 60.0
        self.is_panning = False
        self.pan_start_mouse = (0, 0)
        self.pan_start_cam = (0.0, 0.0)

        # Snapping: 0 (Off), 8, 16, 32
        self.snap_options = [0, 8, 16, 32]
        self.snap_idx = 3  # 32px snap default

        # Modes & Creation
        self.current_mode = MODE_COLLISION
        self.drag_start_world: tuple[int, int] | None = None
        self.is_drawing_rect = False
        self.current_drag_rect: tuple[int, int, int, int] | None = None

        # Selection & Resizing
        self.selected_item: dict[str, Any] | None = None
        self.selected_category: str | None = None  # "collisions", "triggers", "props"
        self.is_moving_selection = False
        self.is_resizing_selection = False
        self.move_offset = (0, 0)

        # Status / Feedback
        self.status_message = "Ready. Select a mode [1-4], draw boxes or click to edit."
        self.status_timer = 0

        # UI Input Field active
        self.active_text_field: str | None = None
        self.active_text_val: str = ""

        # Load Map Data
        self.map_id = initial_map_id if initial_map_id in self.available_maps else (self.available_maps[0] if self.available_maps else "")
        self.map_data: dict[str, Any] = {}
        self.bg_surface: pygame.Surface | None = None
        self.load_map(self.map_id)

    def _discover_maps(self) -> list[str]:
        if not self.maps_dir.exists():
            return []
        maps = []
        for d in self.maps_dir.iterdir():
            if d.is_dir() and (d / "map.json").exists():
                maps.append(d.name)
        return sorted(maps)

    def load_map(self, map_id: str):
        self.map_id = map_id
        map_json_path = self.maps_dir / map_id / "map.json"
        if not map_json_path.exists():
            self.set_status(f"Error: map.json not found for '{map_id}'")
            return

        with open(map_json_path, encoding="utf-8") as f:
            self.map_data = json.load(f)

        # Ensure expected arrays exist
        self.map_data.setdefault("collisions", [])
        self.map_data.setdefault("triggers", [])
        self.map_data.setdefault("props", [])

        # Stitch or load background
        dims = self.map_data.get("dimensions", {"width": 1280, "height": 720})
        w, h = dims.get("width", 1280), dims.get("height", 720)
        self.bg_surface = pygame.Surface((w, h))
        self.bg_surface.fill((20, 24, 30))

        bg_info = self.map_data.get("background", {})
        bg_type = bg_info.get("type", "single_composite")

        bg_warning: str | None = None
        try:
            if bg_type == "single_composite":
                rel = bg_info.get("image", "")
                full = self.project_root / rel if rel else None
                if full is not None and full.exists():
                    loaded = pygame.image.load(str(full)).convert_alpha()
                    if loaded.get_size() != (w, h):
                        loaded = pygame.transform.smoothscale(loaded, (w, h))
                    self.bg_surface.blit(loaded, (0, 0))
                else:
                    bg_warning = f"Background image not found: '{rel}'"
            elif bg_type == "slices":
                for sl in bg_info.get("slices", []):
                    rel = sl.get("image", "")
                    full = self.project_root / rel if rel else None
                    sx, sy = sl.get("x", 0), sl.get("y", 0)
                    if full is not None and full.exists():
                        loaded = pygame.image.load(str(full)).convert_alpha()
                        # If w/h are omitted, use each source image's native dimensions.
                        sw = int(sl.get("w", loaded.get_width()))
                        sh = int(sl.get("h", loaded.get_height()))
                        if sw <= 0 or sh <= 0:
                            bg_warning = f"Invalid background slice dimensions: '{rel}'"
                            continue
                        if loaded.get_size() != (sw, sh):
                            loaded = pygame.transform.smoothscale(loaded, (sw, sh))
                        self.bg_surface.blit(loaded, (sx, sy))
                    else:
                        bg_warning = f"Background slice not found: '{rel}'"
        except Exception as e:
            bg_warning = f"Warning loading background: {e}"

        self.selected_item = None
        self.selected_category = None
        if bg_warning:
            self.set_status(bg_warning)
        else:
            self.set_status(f"Loaded '{self.map_data.get('name', map_id)}' ({w}x{h} px)")

    def set_status(self, msg: str):
        self.status_message = msg
        self.status_timer = 240  # frames (~4 sec)

    def save_map(self):
        map_json_path = self.maps_dir / self.map_id / "map.json"
        bak_path = self.maps_dir / self.map_id / "map.json.bak"

        # Validate before making any backup or modifying the source JSON.
        errors, warnings = validate_map_data(self.map_data)
        if errors:
            details = errors[0]
            if len(errors) > 1:
                details += f" (+{len(errors) - 1} more)"
            self.set_status(f"Save blocked: {details}")
            return False

        # Backup current
        if map_json_path.exists():
            with open(map_json_path, encoding="utf-8") as f_in:
                with open(bak_path, "w", encoding="utf-8") as f_bak:
                    f_bak.write(f_in.read())

        # Write formatted json
        with open(map_json_path, "w", encoding="utf-8") as f_out:
            json.dump(self.map_data, f_out, indent=2)

        # Trigger overlay regeneration
        try:
            if __package__:
                from .generate_collision_overlay import render_map_debug_overlay
            else:
                from generate_collision_overlay import render_map_debug_overlay
            out_overlay = self.maps_dir / self.map_id / "collision_overlay.png"
            render_map_debug_overlay(map_json_path, out_overlay)
        except Exception as e:
            print("Note: overlay update:", e)

        status = "Saved successfully! Backup saved to map.json.bak."
        if warnings:
            status += f" Review {len(warnings)} out-of-bounds warning(s)."
        self.set_status(status)
        return True

    # ---------------- Coordinate Transformations ----------------
    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        sx = int((wx * self.zoom) + self.camera_x)
        sy = int((wy * self.zoom) + self.camera_y)
        return sx, sy

    def screen_to_world(self, sx: int, sy: int) -> tuple[int, int]:
        wx = int((sx - self.camera_x) / self.zoom)
        wy = int((sy - self.camera_y) / self.zoom)
        return wx, wy

    def snap(self, val: int) -> int:
        step = self.snap_options[self.snap_idx]
        if step <= 0:
            return val
        return int(round(val / step) * step)

    # ---------------- Selection Helpers ----------------
    def get_element_rect(self, item: dict[str, Any], cat: str) -> pygame.Rect:
        x = item.get("x", 0)
        y = item.get("y", 0)
        w = item.get("w", item.get("width", 16))
        h = item.get("h", item.get("height", 16))
        return pygame.Rect(x, y, w, h)

    def find_item_at_world(self, wx: int, wy: int) -> tuple[dict[str, Any] | None, str | None]:
        # 1. Props first (smallest)
        for p in reversed(self.map_data.get("props", [])):
            r = self.get_element_rect(p, "props")
            if r.collidepoint(wx, wy):
                return p, "props"
        # 2. Triggers
        for t in reversed(self.map_data.get("triggers", [])):
            r = self.get_element_rect(t, "triggers")
            if r.collidepoint(wx, wy):
                return t, "triggers"
        # 3. Collisions
        for c in reversed(self.map_data.get("collisions", [])):
            r = self.get_element_rect(c, "collisions")
            if r.collidepoint(wx, wy):
                return c, "collisions"
        return None, None

    # ---------------- Event Handling ----------------
    def handle_events(self):
        sidebar_w = 320
        canvas_w = self.screen_w - sidebar_w

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            elif event.type == pygame.VIDEORESIZE:
                self.screen_w = max(900, event.w)
                self.screen_h = max(600, event.h)
                self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if mx < canvas_w:
                    self._handle_canvas_mouse_down(event, mx, my)
                else:
                    self._handle_sidebar_click(mx, my)

            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_canvas_mouse_up(event)

            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event)

            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if mx < canvas_w:
                    # Zoom centered around mouse
                    old_wx, old_wy = self.screen_to_world(mx, my)
                    if event.y > 0 and self.zoom_idx < len(self.zoom_levels) - 1:
                        self.zoom_idx += 1
                    elif event.y < 0 and self.zoom_idx > 0:
                        self.zoom_idx -= 1
                    self.zoom = self.zoom_levels[self.zoom_idx]
                    # Readjust camera to keep mouse over same world point
                    self.camera_x = mx - (old_wx * self.zoom)
                    self.camera_y = my - (old_wy * self.zoom)

    def _handle_keydown(self, event: pygame.event.Event):
        # Text input handling
        if self.active_text_field is not None and self.selected_item is not None:
            if event.key == pygame.K_RETURN or event.key == pygame.K_ESCAPE:
                self._commit_text_field()
            elif event.key == pygame.K_BACKSPACE:
                self.active_text_val = self.active_text_val[:-1]
            else:
                if event.unicode and event.unicode.isprintable():
                    self.active_text_val += event.unicode
            return

        # Shortcuts
        ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL
        if ctrl and event.key == pygame.K_s:
            self.save_map()
        elif event.key == pygame.K_1:
            self.current_mode = MODE_COLLISION
            self.set_status("Switched to [1] Collision Box mode.")
        elif event.key == pygame.K_2:
            self.current_mode = MODE_DIALOGUE
            self.set_status("Switched to [2] Dialogue Trigger mode.")
        elif event.key == pygame.K_3:
            self.current_mode = MODE_TRANSITION
            self.set_status("Switched to [3] Map Transition Trigger mode.")
        elif event.key == pygame.K_4:
            self.current_mode = MODE_LIGHT
            self.set_status("Switched to [4] Point Light Prop mode.")
        elif event.key == pygame.K_g:
            self.snap_idx = (self.snap_idx + 1) % len(self.snap_options)
            self.set_status(f"Snap Grid: {self.snap_options[self.snap_idx]} px")
        elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self._delete_selected()
        elif event.key == pygame.K_ESCAPE:
            self.selected_item = None
            self.selected_category = None
            self.set_status("Deselected.")
        elif event.key == pygame.K_LEFT:
            self.camera_x += 40
        elif event.key == pygame.K_RIGHT:
            self.camera_x -= 40
        elif event.key == pygame.K_UP:
            self.camera_y += 40
        elif event.key == pygame.K_DOWN:
            self.camera_y -= 40

    def _handle_canvas_mouse_down(self, event: pygame.event.Event, mx: int, my: int):
        # Middle click or Alt/Space + Click -> Pan
        keys = pygame.key.get_pressed()
        if event.button == 2 or (event.button == 1 and keys[pygame.K_SPACE]):
            self.is_panning = True
            self.pan_start_mouse = (mx, my)
            self.pan_start_cam = (self.camera_x, self.camera_y)
            return

        if event.button == 1:
            wx, wy = self.screen_to_world(mx, my)

            # Check if clicking on resize handle of currently selected item
            if self.selected_item is not None:
                r = self.get_element_rect(self.selected_item, self.selected_category or "")
                handle_size = max(10, int(12 / self.zoom))
                handle_rect = pygame.Rect(r.right - handle_size, r.bottom - handle_size, handle_size * 2, handle_size * 2)
                if handle_rect.collidepoint(wx, wy):
                    self.is_resizing_selection = True
                    return

            # Check if selecting an existing item
            hit_item, hit_cat = self.find_item_at_world(wx, wy)
            if hit_item is not None:
                self.selected_item = hit_item
                self.selected_category = hit_cat
                self.is_moving_selection = True
                r = self.get_element_rect(hit_item, hit_cat or "")
                self.move_offset = (wx - r.x, wy - r.y)
                self.set_status(f"Selected {hit_cat}: '{hit_item.get('id', '')}'")
                return

            # Otherwise, start drawing a new rectangle
            self.selected_item = None
            self.selected_category = None
            self.is_drawing_rect = True
            snapped_wx = self.snap(wx)
            snapped_wy = self.snap(wy)
            self.drag_start_world = (snapped_wx, snapped_wy)
            self.current_drag_rect = (snapped_wx, snapped_wy, 0, 0)

    def _handle_canvas_mouse_up(self, event: pygame.event.Event):
        if event.button in (1, 2) and self.is_panning:
            self.is_panning = False

        if event.button == 1:
            if self.is_moving_selection:
                self.is_moving_selection = False

            if self.is_resizing_selection:
                self.is_resizing_selection = False

            if self.is_drawing_rect and self.drag_start_world and self.current_drag_rect:
                self.is_drawing_rect = False
                rx, ry, rw, rh = self.current_drag_rect
                # Require min 8x8 size
                if rw >= 8 and rh >= 8:
                    self._create_new_element(rx, ry, rw, rh)
                self.drag_start_world = None
                self.current_drag_rect = None

    def _handle_mouse_motion(self, event: pygame.event.Event):
        mx, my = event.pos
        if self.is_panning:
            dx = mx - self.pan_start_mouse[0]
            dy = my - self.pan_start_mouse[1]
            self.camera_x = self.pan_start_cam[0] + dx
            self.camera_y = self.pan_start_cam[1] + dy

        elif self.is_drawing_rect and self.drag_start_world:
            wx, wy = self.screen_to_world(mx, my)
            sx = min(self.drag_start_world[0], self.snap(wx))
            sy = min(self.drag_start_world[1], self.snap(wy))
            ex = max(self.drag_start_world[0], self.snap(wx))
            ey = max(self.drag_start_world[1], self.snap(wy))
            self.current_drag_rect = (sx, sy, max(8, ex - sx), max(8, ey - sy))

        elif self.is_moving_selection and self.selected_item is not None:
            wx, wy = self.screen_to_world(mx, my)
            new_x = self.snap(wx - self.move_offset[0])
            new_y = self.snap(wy - self.move_offset[1])
            self.selected_item["x"] = new_x
            self.selected_item["y"] = new_y

        elif self.is_resizing_selection and self.selected_item is not None:
            wx, wy = self.screen_to_world(mx, my)
            rx = self.selected_item.get("x", 0)
            ry = self.selected_item.get("y", 0)
            new_w = max(8, self.snap(wx - rx))
            new_h = max(8, self.snap(wy - ry))
            if "w" in self.selected_item:
                self.selected_item["w"] = new_w
                self.selected_item["h"] = new_h
            else:
                self.selected_item["width"] = new_w
                self.selected_item["height"] = new_h

    def _create_new_element(self, x: int, y: int, w: int, h: int):
        if self.current_mode == MODE_COLLISION:
            item = {"id": next_unique_id(self.map_data, "col"), "x": x, "y": y, "w": w, "h": h}
            self.map_data["collisions"].append(item)
            self.selected_item = item
            self.selected_category = "collisions"
            self.set_status(f"Created Collision '{item['id']}' ({w}x{h})")

        elif self.current_mode == MODE_DIALOGUE:
            item = {
                "id": next_unique_id(self.map_data, "dlg_trigger"),
                "trigger_type": "dialogue",
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "dialogue_id": "elder_tomas",
            }
            self.map_data["triggers"].append(item)
            self.selected_item = item
            self.selected_category = "triggers"
            self.set_status(f"Created Dialogue Trigger '{item['id']}'")

        elif self.current_mode == MODE_TRANSITION:
            item = {
                "id": next_unique_id(self.map_data, "trans_exit"),
                "trigger_type": "transition",
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "target_map_id": "briarwood_edge",
                "target_x": 320,
                "target_y": 64,
            }
            self.map_data["triggers"].append(item)
            self.selected_item = item
            self.selected_category = "triggers"
            self.set_status(f"Created Map Transition '{item['id']}'")

        elif self.current_mode == MODE_LIGHT:
            item = {
                "id": next_unique_id(self.map_data, "light_lamp"),
                "prop_type": "light_marker",
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "light": {
                    "radius": max(50, int((w + h) * 1.2)),
                    "color": [255, 210, 130],
                    "intensity": 1.0,
                    "flicker": True,
                },
            }
            self.map_data["props"].append(item)
            self.selected_item = item
            self.selected_category = "props"
            self.set_status(f"Created Light Source '{item['id']}'")

    def _delete_selected(self):
        if not self.selected_item or not self.selected_category:
            return
        cat = self.selected_category
        if cat in self.map_data and self.selected_item in self.map_data[cat]:
            item_id = self.selected_item.get("id", "")
            self.map_data[cat].remove(self.selected_item)
            self.selected_item = None
            self.selected_category = None
            self.set_status(f"Deleted {cat} item '{item_id}'.")

    # ---------------- Sidebar Interaction ----------------
    def _handle_sidebar_click(self, mx: int, my: int):
        sidebar_x = self.screen_w - 320
        rel_x = mx - sidebar_x

        # Save Button (y: 10 - 45)
        if 15 <= rel_x <= 150 and 12 <= my <= 44:
            self.save_map()
            return

        # Map Switcher buttons (y: 60 - 90)
        btn_y = 65
        for m in self.available_maps:
            if 15 <= rel_x <= 300 and btn_y <= my <= btn_y + 24:
                if m != self.map_id:
                    self.load_map(m)
                return
            btn_y += 28

        # Mode Selector Buttons
        mode_y = btn_y + 20
        modes = [
            (MODE_COLLISION, "[1] Collision", COLOR_COLLISION_LINE),
            (MODE_DIALOGUE, "[2] Dialogue", COLOR_DIALOGUE_LINE),
            (MODE_TRANSITION, "[3] Transition", COLOR_TRANSITION_LINE),
            (MODE_LIGHT, "[4] Light Prop", COLOR_LIGHT_LINE),
        ]
        for mode_key, mode_name, col in modes:
            if 15 <= rel_x <= 300 and mode_y <= my <= mode_y + 26:
                self.current_mode = mode_key
                self.set_status(f"Switched mode to {mode_name}")
                return
            mode_y += 30

        # Snap toggles
        snap_y = mode_y + 20
        snap_x = 15
        for s_idx, s_val in enumerate(self.snap_options):
            label = "Free" if s_val == 0 else f"{s_val}px"
            if snap_x <= rel_x <= snap_x + 60 and snap_y <= my <= snap_y + 24:
                self.snap_idx = s_idx
                self.set_status(f"Snap Grid: {label}")
                return
            snap_x += 70

        # Property Field clicks (when an item is selected)
        if self.selected_item is not None:
            fields_y = snap_y + 80
            fields = self._get_editable_fields()
            for f_name, f_val in fields:
                if 15 <= rel_x <= 300 and fields_y <= my <= fields_y + 24:
                    self.active_text_field = f_name
                    self.active_text_val = str(f_val)
                    return
                fields_y += 34

            # Delete button
            if 15 <= rel_x <= 300 and fields_y + 10 <= my <= fields_y + 40:
                self._delete_selected()

    def _get_editable_fields(self) -> list[tuple[str, Any]]:
        if not self.selected_item:
            return []
        item = self.selected_item
        res = [
            ("id", item.get("id", "")),
            ("x", item.get("x", 0)),
            ("y", item.get("y", 0)),
            ("width", item.get("w", item.get("width", 0))),
            ("height", item.get("h", item.get("height", 0))),
        ]
        if self.selected_category == "triggers":
            res.append(("dialogue_id", item.get("dialogue_id", "")))
            res.append(("target_map_id", item.get("target_map_id", "")))
            res.append(("target_x", item.get("target_x", 0)))
            res.append(("target_y", item.get("target_y", 0)))
        elif self.selected_category == "props" and "light" in item:
            light = item["light"]
            res.append(("light.radius", light.get("radius", 60)))
            res.append(("light.flicker", str(light.get("flicker", True))))
        return res

    def _commit_text_field(self):
        if not self.selected_item or not self.active_text_field:
            self.active_text_field = None
            return

        f = self.active_text_field
        v = self.active_text_val.strip()

        try:
            if f in ("x", "y", "target_x", "target_y"):
                self.selected_item[f] = int(v)
            elif f == "width":
                if "w" in self.selected_item:
                    self.selected_item["w"] = int(v)
                else:
                    self.selected_item["width"] = int(v)
            elif f == "height":
                if "h" in self.selected_item:
                    self.selected_item["h"] = int(v)
                else:
                    self.selected_item["height"] = int(v)
            elif f == "light.radius":
                self.selected_item["light"]["radius"] = int(v)
            elif f == "light.flicker":
                self.selected_item["light"]["flicker"] = v.lower() in ("true", "1", "yes")
            else:
                self.selected_item[f] = v
            self.set_status(f"Updated {f} -> {v}")
        except Exception as e:
            self.set_status(f"Invalid input: {e}")

        self.active_text_field = None
        self.active_text_val = ""

    # ---------------- Rendering ----------------
    def render(self):
        sidebar_w = 320
        canvas_w = self.screen_w - sidebar_w
        canvas_h = self.screen_h

        # 1. Clear background
        self.screen.fill(COLOR_BG)

        # 2. Render Map Canvas
        canvas_rect = pygame.Rect(0, 0, canvas_w, canvas_h)
        self.screen.set_clip(canvas_rect)

        # Map Surface
        if self.bg_surface:
            scaled_w = int(self.bg_surface.get_width() * self.zoom)
            scaled_h = int(self.bg_surface.get_height() * self.zoom)
            # Simple zoom blit
            scaled_bg = pygame.transform.scale(self.bg_surface, (scaled_w, scaled_h))
            self.screen.blit(scaled_bg, (self.camera_x, self.camera_y))

            # Map outer boundary border
            pygame.draw.rect(
                self.screen,
                (200, 200, 200),
                (self.camera_x, self.camera_y, scaled_w, scaled_h),
                2,
            )

        # Draw Grid if snap active
        grid_step = self.snap_options[self.snap_idx]
        if grid_step > 0 and self.zoom >= 0.5:
            grid_surf = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
            dims = self.map_data.get("dimensions", {"width": 1280, "height": 720})
            gw, gh = dims.get("width", 1280), dims.get("height", 720)
            for wx in range(0, gw + 1, grid_step):
                sx, sy = self.world_to_screen(wx, 0)
                _, ey = self.world_to_screen(wx, gh)
                pygame.draw.line(grid_surf, (255, 255, 255, 18), (sx, sy), (sx, ey), 1)
            for wy in range(0, gh + 1, grid_step):
                sx, sy = self.world_to_screen(0, wy)
                ex, _ = self.world_to_screen(gw, wy)
                pygame.draw.line(grid_surf, (255, 255, 255, 18), (sx, sy), (ex, sy), 1)
            self.screen.blit(grid_surf, (0, 0))

        # Render Zones (Collisions, Triggers, Props)
        overlay_surf = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)

        # Collisions
        for col in self.map_data.get("collisions", []):
            self._render_box(overlay_surf, col, "collisions", COLOR_COLLISION_FILL, COLOR_COLLISION_LINE)

        # Triggers
        for trig in self.map_data.get("triggers", []):
            ttype = trig.get("trigger_type", "dialogue")
            fill_c = COLOR_TRANSITION_FILL if ttype == "transition" else COLOR_DIALOGUE_FILL
            line_c = COLOR_TRANSITION_LINE if ttype == "transition" else COLOR_DIALOGUE_LINE
            self._render_box(overlay_surf, trig, "triggers", fill_c, line_c)

        # Props / Lights
        for prop in self.map_data.get("props", []):
            self._render_box(overlay_surf, prop, "props", COLOR_LIGHT_FILL, COLOR_LIGHT_LINE)
            if "light" in prop:
                px = prop.get("x", 0) + prop.get("width", 16) / 2
                py = prop.get("y", 0) + prop.get("height", 16) / 2
                rad = prop["light"].get("radius", 60)
                spx, spy = self.world_to_screen(px, py)
                srad = int(rad * self.zoom)
                pygame.draw.circle(overlay_surf, (255, 240, 100, 70), (spx, spy), srad, 1)

        # Active Drag-to-Draw Box
        if self.is_drawing_rect and self.current_drag_rect:
            dx, dy, dw, dh = self.current_drag_rect
            sx, sy = self.world_to_screen(dx, dy)
            sw, sh = int(dw * self.zoom), int(dh * self.zoom)
            draw_color = (
                COLOR_COLLISION_LINE
                if self.current_mode == MODE_COLLISION
                else (
                    COLOR_DIALOGUE_LINE
                    if self.current_mode == MODE_DIALOGUE
                    else (COLOR_TRANSITION_LINE if self.current_mode == MODE_TRANSITION else COLOR_LIGHT_LINE)
                )
            )
            pygame.draw.rect(overlay_surf, (*draw_color[:3], 90), (sx, sy, sw, sh))
            pygame.draw.rect(overlay_surf, draw_color, (sx, sy, sw, sh), 2)

        self.screen.blit(overlay_surf, (0, 0))
        self.screen.set_clip(None)

        # 3. Render Status Bar
        self._render_status_bar(canvas_w)

        # 4. Render Right Sidebar
        self._render_sidebar(sidebar_w, canvas_w)

        pygame.display.flip()

    def _render_box(self, surf: pygame.Surface, item: dict[str, Any], cat: str, fill_col: tuple, line_col: tuple):
        r = self.get_element_rect(item, cat)
        sx, sy = self.world_to_screen(r.x, r.y)
        sw, sh = int(r.w * self.zoom), int(r.h * self.zoom)

        is_selected = item is self.selected_item

        # Fill & Border
        pygame.draw.rect(surf, fill_col, (sx, sy, sw, sh))
        pygame.draw.rect(surf, (255, 255, 255, 255) if is_selected else line_col, (sx, sy, sw, sh), 3 if is_selected else 2)

        # Draw Label tag
        label = item.get("id", "")
        if self.zoom >= 0.5:
            txt_surf = FONT_SMALL.render(label, True, (255, 255, 255))
            badge_rect = pygame.Rect(sx + 2, sy + 2, txt_surf.get_width() + 6, txt_surf.get_height() + 2)
            pygame.draw.rect(surf, (15, 18, 24, 220), badge_rect)
            surf.blit(txt_surf, (sx + 5, sy + 3))

        # If selected, draw bottom-right corner resize handle
        if is_selected:
            handle_size = max(8, int(10 * self.zoom))
            hx = sx + sw - handle_size
            hy = sy + sh - handle_size
            pygame.draw.rect(surf, (255, 255, 255), (hx, hy, handle_size, handle_size))
            pygame.draw.rect(surf, (20, 20, 20), (hx, hy, handle_size, handle_size), 1)

    def _render_status_bar(self, canvas_w: int):
        bar_h = 32
        bar_y = self.screen_h - bar_h
        pygame.draw.rect(self.screen, (15, 17, 22), (0, bar_y, canvas_w, bar_h))
        pygame.draw.line(self.screen, COLOR_PANEL_BORDER, (0, bar_y), (canvas_w, bar_y), 1)

        # Message
        msg_col = COLOR_TEXT_ACCENT if self.status_timer > 0 else COLOR_TEXT_DIM
        msg_surf = FONT_SMALL.render(self.status_message, True, msg_col)
        self.screen.blit(msg_surf, (12, bar_y + 8))

        if self.status_timer > 0:
            self.status_timer -= 1

        # Mouse coords
        mx, my = pygame.mouse.get_pos()
        if mx < canvas_w:
            wx, wy = self.screen_to_world(mx, my)
            coord_str = f"World: ({wx}, {wy}) | Zoom: {int(self.zoom * 100)}%"
            coord_surf = FONT_SMALL.render(coord_str, True, COLOR_TEXT_DIM)
            self.screen.blit(coord_surf, (canvas_w - coord_surf.get_width() - 15, bar_y + 8))

    def _render_sidebar(self, sidebar_w: int, canvas_w: int):
        sx = canvas_w
        sy = 0
        pygame.draw.rect(self.screen, COLOR_PANEL, (sx, sy, sidebar_w, self.screen_h))
        pygame.draw.line(self.screen, COLOR_PANEL_BORDER, (sx, sy), (sx, self.screen_h), 2)

        # Top Header / Save Button
        save_btn_rect = pygame.Rect(sx + 15, 12, 130, 32)
        pygame.draw.rect(self.screen, (40, 140, 80), save_btn_rect, border_radius=4)
        pygame.draw.rect(self.screen, (70, 210, 120), save_btn_rect, 1, border_radius=4)
        save_lbl = FONT_MED.render("Save (Ctrl+S)", True, (255, 255, 255))
        self.screen.blit(save_lbl, (save_btn_rect.x + 16, save_btn_rect.y + 7))

        title = FONT_TITLE.render("Map Editor", True, COLOR_TEXT_ACCENT)
        self.screen.blit(title, (sx + 165, 16))

        # Map Selector
        lbl = FONT_SMALL.render("ACTIVE MAP:", True, COLOR_TEXT_DIM)
        self.screen.blit(lbl, (sx + 15, 52))
        btn_y = 70
        for m in self.available_maps:
            is_cur = m == self.map_id
            m_btn = pygame.Rect(sx + 15, btn_y, 290, 24)
            pygame.draw.rect(self.screen, (50, 70, 100) if is_cur else (40, 44, 55), m_btn, border_radius=3)
            if is_cur:
                pygame.draw.rect(self.screen, (90, 150, 240), m_btn, 1, border_radius=3)
            txt = FONT_SMALL.render(m, True, (255, 255, 255) if is_cur else COLOR_TEXT_DIM)
            self.screen.blit(txt, (m_btn.x + 8, m_btn.y + 4))
            btn_y += 28

        # Tool Mode Selector
        btn_y += 10
        lbl = FONT_SMALL.render("DRAW TOOL / MODE:", True, COLOR_TEXT_DIM)
        self.screen.blit(lbl, (sx + 15, btn_y))
        btn_y += 18
        modes = [
            (MODE_COLLISION, "[1] Collision Solid", COLOR_COLLISION_LINE),
            (MODE_DIALOGUE, "[2] Dialogue Trigger", COLOR_DIALOGUE_LINE),
            (MODE_TRANSITION, "[3] Map Transition", COLOR_TRANSITION_LINE),
            (MODE_LIGHT, "[4] Point Light Prop", COLOR_LIGHT_LINE),
        ]
        for mode_key, mode_name, col in modes:
            is_active = self.current_mode == mode_key
            r = pygame.Rect(sx + 15, btn_y, 290, 26)
            pygame.draw.rect(self.screen, (45, 50, 65) if is_active else (35, 38, 48), r, border_radius=4)
            pygame.draw.rect(self.screen, col if is_active else (60, 65, 80), r, 2 if is_active else 1, border_radius=4)
            t = FONT_SMALL.render(mode_name, True, col if is_active else COLOR_TEXT)
            self.screen.blit(t, (r.x + 10, r.y + 5))
            btn_y += 30

        # Snap to grid selector
        btn_y += 8
        lbl = FONT_SMALL.render("GRID SNAP (G):", True, COLOR_TEXT_DIM)
        self.screen.blit(lbl, (sx + 15, btn_y))
        btn_y += 18
        snap_x = sx + 15
        for s_idx, s_val in enumerate(self.snap_options):
            is_sel = s_idx == self.snap_idx
            btn = pygame.Rect(snap_x, btn_y, 60, 24)
            pygame.draw.rect(self.screen, (60, 80, 110) if is_sel else (40, 44, 55), btn, border_radius=3)
            t = FONT_SMALL.render("Free" if s_val == 0 else f"{s_val}px", True, (255, 255, 255) if is_sel else COLOR_TEXT_DIM)
            self.screen.blit(t, (btn.x + 12, btn.y + 4))
            snap_x += 68

        # Divider
        btn_y += 38
        pygame.draw.line(self.screen, COLOR_PANEL_BORDER, (sx + 15, btn_y), (sx + sidebar_w - 15, btn_y), 1)

        # Selection Inspector
        btn_y += 12
        if self.selected_item is not None:
            cat_name = self.selected_category or "element"
            hdr = FONT_MED.render(f"Inspector: {cat_name.capitalize()}", True, COLOR_TEXT_ACCENT)
            self.screen.blit(hdr, (sx + 15, btn_y))
            btn_y += 24

            fields = self._get_editable_fields()
            for f_name, f_val in fields:
                is_editing = self.active_text_field == f_name
                lbl = FONT_SMALL.render(f"{f_name}:", True, COLOR_TEXT_DIM)
                self.screen.blit(lbl, (sx + 15, btn_y + 4))

                input_box = pygame.Rect(sx + 120, btn_y, 185, 24)
                pygame.draw.rect(self.screen, (20, 22, 28) if is_editing else (28, 30, 38), input_box, border_radius=3)
                pygame.draw.rect(self.screen, COLOR_TEXT_ACCENT if is_editing else (60, 65, 80), input_box, 1, border_radius=3)

                val_str = self.active_text_val if is_editing else str(f_val)
                # Truncate if long
                if len(val_str) > 22:
                    val_str = val_str[:20] + "..."
                txt = FONT_SMALL.render(val_str, True, (255, 255, 255) if is_editing else COLOR_TEXT)
                self.screen.blit(txt, (input_box.x + 6, input_box.y + 4))
                btn_y += 32

            # Delete button
            btn_y += 8
            del_btn = pygame.Rect(sx + 15, btn_y, 290, 28)
            pygame.draw.rect(self.screen, (160, 40, 40), del_btn, border_radius=4)
            pygame.draw.rect(self.screen, (220, 70, 70), del_btn, 1, border_radius=4)
            del_lbl = FONT_MED.render("Delete Selected (Del)", True, (255, 255, 255))
            self.screen.blit(del_lbl, (del_btn.x + 65, del_btn.y + 5))
        else:
            txt1 = FONT_SMALL.render("No element selected.", True, COLOR_TEXT_DIM)
            txt2 = FONT_SMALL.render("Click an existing box to inspect,", True, COLOR_TEXT_DIM)
            txt3 = FONT_SMALL.render("or drag on the map to create one.", True, COLOR_TEXT_DIM)
            self.screen.blit(txt1, (sx + 15, btn_y))
            self.screen.blit(txt2, (sx + 15, btn_y + 18))
            self.screen.blit(txt3, (sx + 15, btn_y + 36))

    def run(self):
        while self.running:
            self.handle_events()
            self.render()
            self.clock.tick(60)
        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="The Rise of Aethelgard - Visual Map Editor")
    parser.add_argument("map_id", nargs="?", default="oakhaven_village", help="Initial map ID to edit")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent
    editor = VisualMapEditor(project_root, args.map_id)
    editor.run()


if __name__ == "__main__":
    main()
