"""HD-2D rendering engine: procedural pixel art, Y-sorted depth, and dynamic lighting."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from pathlib import Path

import pygame

from src.systems.exploration.map_data import LightSource, MapProp, Tilemap, TileType


class HD2DRenderer:
    """Renders layered tilemaps with Y-sorting depth, dynamic point lights, and atmosphere."""

    def __init__(self, view_width: int = 640, view_height: int = 360) -> None:
        self.width = view_width
        self.height = view_height
        self._tile_cache: dict[int, pygame.Surface] = {}
        self._prop_cache: dict[str, pygame.Surface] = {}
        self._light_cache: dict[tuple[int, tuple[int, int, int]], pygame.Surface] = {}
        self._bg_cache: dict[str, pygame.Surface] = {}
        self._vignette: pygame.Surface | None = None
        self._particles: list[dict] = []
        self._character_animations: dict[str, dict[str, list[pygame.Surface]]] = {}

        self._init_tile_textures()
        self._init_vignette()
        self._init_particles(count=35)
        self._init_character_animations()

    def _init_character_animations(self) -> None:
        """Load and slice animated walk sprite sheets for player characters."""
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        rowan_dir = project_root / "assets" / "sprites" / "characters" / "rowan"
        matrix_path = rowan_dir / "rowan_walk_matrix.png"

        if matrix_path.exists():
            try:
                sheet = pygame.image.load(str(matrix_path))
                if pygame.display.get_surface() is not None:
                    try:
                        sheet = sheet.convert_alpha()
                    except pygame.error:
                        pass
                sw, sh = sheet.get_size()
                cols, rows = 4, 4
                fw, fh = sw // cols, sh // rows
                row_keys = ["down", "up", "right", "left"]
                rowan_anims: dict[str, list[pygame.Surface]] = {}

                for r_idx, r_key in enumerate(row_keys):
                    frames: list[pygame.Surface] = []
                    for c_idx in range(cols):
                        rect = pygame.Rect(c_idx * fw, r_idx * fh, fw, fh)
                        frame_surf = sheet.subsurface(rect).copy()
                        frames.append(frame_surf)
                    rowan_anims[r_key] = frames

                self._character_animations["rowan"] = rowan_anims
            except (pygame.error, ValueError):
                pass

    def _get_background_surface(self, image_path: str) -> pygame.Surface | None:
        """Load, cache, and convert pre-rendered composite map background surfaces."""
        if image_path in self._bg_cache:
            return self._bg_cache[image_path]

        p = Path(image_path)
        if not p.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            p = project_root / image_path

        if p.exists():
            try:
                loaded = pygame.image.load(str(p)).convert()
                self._bg_cache[image_path] = loaded
                return loaded
            except pygame.error:
                return None
        return None

    def _init_tile_textures(self) -> None:
        """Procedurally generate authentic 16-bit SNES style 32x32 tile textures."""
        # Grass
        grass = pygame.Surface((32, 32))
        grass.fill((56, 128, 48))
        for x, y in [(4, 6), (12, 18), (22, 10), (16, 26), (28, 22), (8, 14)]:
            pygame.draw.line(grass, (76, 160, 60), (x, y), (x, y - 3), 1)
            pygame.draw.line(grass, (40, 96, 36), (x + 1, y), (x + 1, y - 2), 1)
        self._tile_cache[TileType.GRASS.value] = grass

        # Dirt Path
        path = pygame.Surface((32, 32))
        path.fill((168, 124, 82))
        for x, y in [(6, 8), (18, 14), (10, 24), (24, 26), (14, 4)]:
            pygame.draw.circle(path, (140, 100, 64), (x, y), 2)
            pygame.draw.circle(path, (190, 148, 104), (x + 1, y - 1), 1)
        self._tile_cache[TileType.PATH.value] = path

        # Cobblestone
        cobble = pygame.Surface((32, 32))
        cobble.fill((100, 105, 115))
        stones = [
            (2, 2, 12, 6), (16, 2, 14, 6),
            (2, 10, 14, 6), (18, 10, 12, 6),
            (2, 18, 12, 6), (16, 18, 14, 6),
            (2, 26, 14, 5), (18, 26, 12, 5),
        ]
        for sx, sy, sw, sh in stones:
            pygame.draw.rect(cobble, (130, 135, 145), (sx, sy, sw, sh))
            pygame.draw.rect(cobble, (80, 85, 95), (sx, sy, sw, sh), 1)
            pygame.draw.line(cobble, (155, 160, 170), (sx + 1, sy + 1), (sx + sw - 2, sy + 1), 1)
        self._tile_cache[TileType.COBBLESTONE.value] = cobble

        # Water
        water = pygame.Surface((32, 32))
        water.fill((40, 88, 160))
        for y in [6, 14, 22, 28]:
            pygame.draw.line(water, (72, 124, 204), (4, y), (14, y), 1)
            pygame.draw.line(water, (72, 124, 204), (18, y + 2), (28, y + 2), 1)
        self._tile_cache[TileType.WATER.value] = water

        # Stone Wall
        wall = pygame.Surface((32, 32))
        wall.fill((65, 70, 80))
        for y in range(0, 32, 8):
            pygame.draw.line(wall, (45, 50, 60), (0, y), (32, y), 1)
            offset = 16 if (y // 8) % 2 == 1 else 0
            pygame.draw.line(wall, (45, 50, 60), (offset, y), (offset, y + 8), 1)
            pygame.draw.line(wall, (45, 50, 60), (offset + 16, y), (offset + 16, y + 8), 1)
        self._tile_cache[TileType.STONE_WALL.value] = wall

    def _init_vignette(self) -> None:
        """Create a soft radial vignette surface to give dramatic HD-2D depth."""
        vignette = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        center_x, center_y = self.width / 2.0, self.height / 2.0
        max_dist = math.sqrt(center_x ** 2 + center_y ** 2)

        # Draw concentric rings with progressive darkness towards edges
        step = 6
        for r in range(int(center_x * 0.6), int(max_dist), step):
            factor = (r - center_x * 0.6) / (max_dist - center_x * 0.6)
            alpha = int(min(180, factor ** 2 * 190))
            pygame.draw.circle(vignette, (10, 10, 18, alpha), (int(center_x), int(center_y)), r, step)

        self._vignette = vignette

    def _init_particles(self, count: int = 35) -> None:
        """Initialize ambient drifting particles (dust motes / forest embers)."""
        self._particles = [
            {
                "x": random.uniform(0, self.width),
                "y": random.uniform(0, self.height),
                "speed_x": random.uniform(-8, -2),
                "speed_y": random.uniform(2, 6),
                "size": random.choice([1, 2, 2]),
                "alpha": random.randint(70, 160),
                "phase": random.uniform(0, 6.28),
            }
            for _ in range(count)
        ]

    def _get_light_texture(self, radius: int, color: tuple[int, int, int]) -> pygame.Surface:
        """Generate or retrieve cached radial gradient light mask."""
        cache_key = (radius, color)
        if cache_key in self._light_cache:
            return self._light_cache[cache_key]

        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = radius, radius
        r, g, b = color

        # Soft radial gradient
        for dist in range(radius, 0, -2):
            norm = dist / radius
            alpha = int(255 * (1.0 - norm) ** 1.8)
            col = (r, g, b, alpha)
            pygame.draw.circle(surf, col, (cx, cy), dist)

        self._light_cache[cache_key] = surf
        return surf

    def draw_player_sprite(self, surf: pygame.Surface, screen_x: int, screen_y: int, is_moving: bool, facing: str, time_sec: float) -> None:
        """Render player character using animated sprite sheet when available, or procedural fallback."""
        if "rowan" not in self._character_animations:
            self._init_character_animations()
        rowan_anims = self._character_animations.get("rowan")
        if rowan_anims and facing in rowan_anims:
            frames = rowan_anims[facing]
            if is_moving:
                frame_idx = int(time_sec * 6.5) % len(frames)
            else:
                frame_idx = 0

            sprite = frames[frame_idx]
            sw, sh = sprite.get_size()

            # Dynamic grounded drop shadow at feet
            shadow_w, shadow_h = 24, 8
            shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surf, (15, 15, 25, 90), (0, 0, shadow_w, shadow_h))
            surf.blit(shadow_surf, (screen_x - shadow_w // 2, screen_y - shadow_h // 2))

            # Blit sprite grounded at screen_y
            draw_x = screen_x - sw // 2
            draw_y = screen_y - sh + 4
            surf.blit(sprite, (draw_x, draw_y))
            return

        w, h = 24, 32
        px = screen_x - w // 2
        py = screen_y - h

        # Bobbing walking animation
        bob = int(math.sin(time_sec * 12.0) * 2) if is_moving else 0

        # Shadow
        shadow = pygame.Surface((20, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (15, 15, 25, 90), (0, 0, 20, 8))
        surf.blit(shadow, (px + 2, py + h - 5))

        # Blue Cape
        pygame.draw.rect(surf, (35, 60, 130), (px + 4, py + 12 + bob, 16, 14))

        # Plate Armor Body
        pygame.draw.rect(surf, (150, 155, 165), (px + 6, py + 10 + bob, 12, 13))
        # Gold trim
        pygame.draw.rect(surf, (215, 175, 55), (px + 6, py + 10 + bob, 12, 3))

        # Knight Helmet / Face
        pygame.draw.rect(surf, (170, 175, 185), (px + 7, py + 3 + bob, 10, 8))
        # Visor slit
        pygame.draw.line(surf, (30, 30, 40), (px + 8, py + 7 + bob), (px + 15, py + 7 + bob), 1)

        # Legs / Greaves
        pygame.draw.rect(surf, (110, 115, 125), (px + 6, py + 23 + bob, 4, 8))
        pygame.draw.rect(surf, (110, 115, 125), (px + 14, py + 23 - bob, 4, 8))

        # Broadsword (Side)
        sword_x = px + 19 if facing in ("right", "down") else px + 1
        pygame.draw.line(surf, (200, 205, 215), (sword_x, py + 8 + bob), (sword_x, py + 22 + bob), 2)
        pygame.draw.rect(surf, (215, 175, 55), (sword_x - 2, py + 12 + bob, 5, 2))

    def draw_prop(self, surf: pygame.Surface, prop: MapProp, screen_x: int, screen_y: int, time_sec: float) -> None:
        """Render environment prop based on prop_type."""
        if prop.prop_type in ("light_marker", "invisible", "none", "collision_only"):
            # Functional or lighting marker only; visual is baked into composite background
            return

        if prop.prop_type == "tree":
            # Oak Trunk
            pygame.draw.rect(surf, (85, 55, 35), (screen_x + 22, screen_y + 45, 20, 48))
            # Canopy Layers (bottom dark green to top brighter green)
            pygame.draw.circle(surf, (35, 80, 40), (screen_x + 32, screen_y + 40), 28)
            pygame.draw.circle(surf, (45, 105, 50), (screen_x + 32, screen_y + 28), 24)
            pygame.draw.circle(surf, (60, 130, 65), (screen_x + 30, screen_y + 18), 18)

        elif prop.prop_type == "house":
            # Cottage base
            pygame.draw.rect(surf, (160, 145, 130), (screen_x, screen_y + 36, prop.width, prop.height - 36))
            # Timber frames
            for tx in (screen_x, screen_x + prop.width - 8, screen_x + 48, screen_x + 104):
                pygame.draw.rect(surf, (90, 60, 40), (tx, screen_y + 36, 8, prop.height - 36))
            # Wooden door
            pygame.draw.rect(surf, (110, 70, 45), (screen_x + 64, screen_y + prop.height - 40, 28, 40))
            pygame.draw.circle(surf, (215, 175, 55), (screen_x + 88, screen_y + prop.height - 18), 2)
            # Roof
            roof_pts = [
                (screen_x - 8, screen_y + 40),
                (screen_x + prop.width // 2, screen_y),
                (screen_x + prop.width + 8, screen_y + 40),
            ]
            pygame.draw.polygon(surf, (135, 60, 50), roof_pts)

        elif prop.prop_type == "lantern":
            # Iron post
            pygame.draw.rect(surf, (45, 45, 55), (screen_x + 13, screen_y + 16, 6, 32))
            # Lamp cage
            pygame.draw.rect(surf, (30, 30, 40), (screen_x + 9, screen_y + 4, 14, 16))
            # Glowing flame inside
            flicker = 1.0 + 0.15 * math.sin(time_sec * 8.0)
            glow_col = (min(255, int(255 * flicker)), min(255, int(200 * flicker)), 110)
            pygame.draw.rect(surf, glow_col, (screen_x + 11, screen_y + 7, 10, 10))

        elif prop.prop_type == "crystal":
            # Bioluminescent spire
            flicker = 1.0 + 0.2 * math.sin(time_sec * 5.0 + prop.x)
            col = (int(70 * flicker), min(255, int(230 * flicker)), min(255, int(190 * flicker)))
            pts = [
                (screen_x + 12, screen_y + 4),
                (screen_x + 22, screen_y + 26),
                (screen_x + 2, screen_y + 26),
            ]
            pygame.draw.polygon(surf, col, pts)

        elif prop.prop_type == "npc_elder":
            # Elder Tomas sprite
            pygame.draw.rect(surf, (110, 75, 45), (screen_x + 6, screen_y + 12, 12, 20))  # Robe
            pygame.draw.circle(surf, (235, 195, 165), (screen_x + 12, screen_y + 8), 6)   # Head
            pygame.draw.polygon(surf, (215, 215, 225), [(screen_x + 9, screen_y + 10), (screen_x + 15, screen_y + 10), (screen_x + 12, screen_y + 17)])  # Beard

        elif prop.prop_type == "boss_treant":
            # Corrupted Treant Boss sprite
            pygame.draw.rect(surf, (55, 35, 20), (screen_x + 10, screen_y + 16, 28, 48))  # Trunk
            pygame.draw.circle(surf, (40, 25, 15), (screen_x + 24, screen_y + 14), 16)     # Head
            # Glowing corrupted red eyes
            pygame.draw.circle(surf, (255, 40, 40), (screen_x + 18, screen_y + 14), 3)
            pygame.draw.circle(surf, (255, 40, 40), (screen_x + 28, screen_y + 14), 3)
            # Twisted branches
            pygame.draw.line(surf, (45, 28, 16), (screen_x + 10, screen_y + 24), (screen_x - 2, screen_y + 8), 4)
            pygame.draw.line(surf, (45, 28, 16), (screen_x + 38, screen_y + 24), (screen_x + 50, screen_y + 8), 4)

    def render_map(
        self,
        dest_surf: pygame.Surface,
        tilemap: Tilemap,
        cam_x: float,
        cam_y: float,
        player_x: float,
        player_y: float,
        player_moving: bool,
        player_facing: str,
        time_sec: float,
    ) -> None:
        """Render complete HD-2D frame with Y-sorting, dynamic lighting, and particles."""
        # 1. Ground / Background Canvas Layer
        if tilemap.background_image:
            bg_surf = self._get_background_surface(tilemap.background_image)
            if bg_surf:
                bg_w, bg_h = bg_surf.get_size()
                src_x = max(0, min(int(cam_x), bg_w - self.width))
                src_y = max(0, min(int(cam_y), bg_h - self.height))
                view_w = min(self.width, bg_w - src_x)
                view_h = min(self.height, bg_h - src_y)
                dest_surf.blit(bg_surf, (0, 0), area=pygame.Rect(src_x, src_y, view_w, view_h))
            else:
                dest_surf.fill((30, 45, 30))
        elif tilemap.background_slices:
            dest_surf.fill((20, 30, 20))
            for sl in tilemap.background_slices:
                sl_img = sl.get("image")
                if not sl_img:
                    continue
                s_surf = self._get_background_surface(sl_img)
                if not s_surf:
                    continue
                sl_x = float(sl.get("x", 0.0))
                sl_y = float(sl.get("y", 0.0))
                sl_w = float(sl.get("w", s_surf.get_width()))
                sl_h = float(sl.get("h", s_surf.get_height()))
                if (
                    sl_x + sl_w >= cam_x
                    and sl_x <= cam_x + self.width
                    and sl_y + sl_h >= cam_y
                    and sl_y <= cam_y + self.height
                ):
                    dest_surf.blit(s_surf, (int(sl_x - cam_x), int(sl_y - cam_y)))
        elif tilemap.ground_layer and len(tilemap.ground_layer) > 0:
            start_tx = max(0, int(cam_x // tilemap.tile_size))
            end_tx = min(tilemap.width_tiles - 1, int((cam_x + self.width) // tilemap.tile_size) + 1)
            start_ty = max(0, int(cam_y // tilemap.tile_size))
            end_ty = min(tilemap.height_tiles - 1, int((cam_y + self.height) // tilemap.tile_size) + 1)

            for ty in range(start_ty, min(end_ty, len(tilemap.ground_layer))):
                row = tilemap.ground_layer[ty]
                for tx in range(start_tx, min(end_tx, len(row))):
                    tile_val = row[tx]
                    tex = self._tile_cache.get(tile_val, self._tile_cache[TileType.GRASS.value])
                    sx = int(tx * tilemap.tile_size - cam_x)
                    sy = int(ty * tilemap.tile_size - cam_y)
                    dest_surf.blit(tex, (sx, sy))
        else:
            dest_surf.fill((30, 45, 30))

        # 2. Y-Sorted Depth Entity Gathering
        draw_queue: list[tuple[float, Callable[[], None]]] = []

        # Add Props
        for prop in tilemap.props:
            if (
                prop.x + prop.width >= cam_x
                and prop.x <= cam_x + self.width
                and prop.y + prop.height >= cam_y
                and prop.y <= cam_y + self.height
            ):
                sx = int(prop.x - cam_x)
                sy = int(prop.y - cam_y)
                draw_queue.append(
                    (prop.sort_y, lambda p=prop, x=sx, y=sy: self.draw_prop(dest_surf, p, x, y, time_sec))
                )

        # Add Player Character
        player_screen_x = int(player_x - cam_x)
        player_screen_y = int(player_y - cam_y)
        draw_queue.append(
            (
                player_y,
                lambda: self.draw_player_sprite(
                    dest_surf,
                    player_screen_x,
                    player_screen_y,
                    player_moving,
                    player_facing,
                    time_sec,
                ),
            )
        )

        # Sort strictly by feet Y coordinate and execute draw calls
        draw_queue.sort(key=lambda item: item[0])
        for _, draw_fn in draw_queue:
            draw_fn()

        # 3. HD-2D Dynamic Lighting Pass
        darkness = pygame.Surface((self.width, self.height))
        darkness.fill(tilemap.ambient_light)

        # Gather point lights from map props + player lantern
        lights: list[LightSource] = []
        for prop in tilemap.props:
            if prop.light:
                lights.append(prop.light)

        # Player torch/lantern
        lights.append(
            LightSource(
                x=player_x,
                y=player_y - 12,
                radius=90,
                color=(255, 215, 140),
                intensity=1.1,
                flicker=True,
            )
        )

        # Render lights onto darkness mask
        for light in lights:
            lx = int(light.x - cam_x)
            ly = int(light.y - cam_y)

            # Flicker modifier
            flicker_mod = (
                1.0 + 0.08 * math.sin(time_sec * 9.0 + light.x)
                if light.flicker
                else 1.0
            )
            r = max(10, int(light.radius * flicker_mod))
            light_tex = self._get_light_texture(r, light.color)
            dest_rect = light_tex.get_rect(center=(lx, ly))
            darkness.blit(light_tex, dest_rect, special_flags=pygame.BLEND_RGBA_ADD)

        # Blend lighting darkness surface over world
        dest_surf.blit(darkness, (0, 0), special_flags=pygame.BLEND_MULT)

        # 4. Vignette Layer
        if self._vignette:
            dest_surf.blit(self._vignette, (0, 0))

        # 5. Ambient Floating Particles
        for p in self._particles:
            p["x"] += p["speed_x"] * 0.016
            p["y"] += p["speed_y"] * 0.016 + 0.3 * math.sin(time_sec * 2.0 + p["phase"])
            if p["x"] < 0:
                p["x"] = self.width
            if p["y"] > self.height:
                p["y"] = 0

            p_color = (
                (120, 240, 200, p["alpha"])
                if tilemap.ambient_particles == "spores"
                else (245, 230, 180, p["alpha"])
            )
            part_surf = pygame.Surface((p["size"] * 2, p["size"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(part_surf, p_color, (p["size"], p["size"]), p["size"])
            dest_surf.blit(part_surf, (int(p["x"]), int(p["y"])))
