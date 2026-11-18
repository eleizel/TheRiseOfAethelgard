"""Tilemap data structures, collision grids, triggers, and lighting definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TileType(Enum):
    EMPTY = 0
    GRASS = 1
    PATH = 2
    COBBLESTONE = 3
    WATER = 4
    WOOD_FLOOR = 5
    STONE_WALL = 6


@dataclass
class LightSource:
    """Dynamic point light definition for HD-2D lighting pipeline."""
    x: float
    y: float
    radius: float = 80.0
    color: tuple[int, int, int] = (255, 200, 120)  # Warm torch orange
    intensity: float = 1.0
    flicker: bool = True


@dataclass
class MapProp:
    """Environment decoration with depth sorting and optional collision/light."""
    id: str
    prop_type: str  # "tree", "lantern", "house", "fountain", "signpost"
    x: float
    y: float
    width: float
    height: float
    solid_rect: tuple[float, float, float, float] | None = None  # (rel_x, rel_y, w, h)
    light: LightSource | None = None
    sprite: str | None = None

    @property
    def sort_y(self) -> float:
        """Y position used for depth sorting (feet/base of the prop)."""
        return self.y + self.height


@dataclass
class TriggerZone:
    """Interactive or boundary zone (door, chest, map transition)."""
    id: str
    trigger_type: str  # "transition", "dialogue", "chest", "sign"
    x: float
    y: float
    width: float
    height: float
    target_map_id: str | None = None
    target_x: float | None = None
    target_y: float | None = None
    dialogue_id: str | None = None

    def contains_point(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height

    def intersects_rect(self, rx: float, ry: float, rw: float, rh: float) -> bool:
        return (
            self.x < rx + rw
            and self.x + self.width > rx
            and self.y < ry + rh
            and self.y + self.height > ry
        )

    def distance_to(self, px: float, py: float) -> float:
        cx = self.x + self.width / 2.0
        cy = self.y + self.height / 2.0
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


@dataclass
class CollisionBox:
    """Axis-aligned collision volume for geometric / image-based map zones."""
    id: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class Tilemap:
    """2D tilemap or composite image zone with collision, props, triggers, and atmosphere."""
    id: str
    name: str
    width_tiles: int
    height_tiles: int
    tile_size: int = 32
    ground_layer: list[list[int]] = field(default_factory=list)
    collision_mask: list[list[bool]] = field(default_factory=list)
    props: list[MapProp] = field(default_factory=list)
    triggers: list[TriggerZone] = field(default_factory=list)
    ambient_light: tuple[int, int, int] = (180, 190, 220)  # RGB tint
    ambient_particles: str = "dust"  # "dust", "leaves", "spores"
    background_image: str | None = None
    background_slices: list[dict[str, Any]] = field(default_factory=list)
    collision_boxes: list[CollisionBox] = field(default_factory=list)
    pixel_width_override: int | None = None
    pixel_height_override: int | None = None

    @property
    def pixel_width(self) -> int:
        if self.pixel_width_override is not None:
            return self.pixel_width_override
        return self.width_tiles * self.tile_size

    @property
    def pixel_height(self) -> int:
        if self.pixel_height_override is not None:
            return self.pixel_height_override
        return self.height_tiles * self.tile_size

    def is_tile_solid(self, tx: int, ty: int) -> bool:
        if tx < 0 or tx >= self.width_tiles or ty < 0 or ty >= self.height_tiles:
            return True
        if self.collision_mask and ty < len(self.collision_mask) and tx < len(self.collision_mask[ty]):
            return self.collision_mask[ty][tx]
        if self.collision_boxes:
            tile_rx = tx * self.tile_size
            tile_ry = ty * self.tile_size
            return any(
                tile_rx < b.x + b.width
                and tile_rx + self.tile_size > b.x
                and tile_ry < b.y + b.height
                and tile_ry + self.tile_size > b.y
                for b in self.collision_boxes
            )
        return False

    def is_rect_colliding(self, rx: float, ry: float, rw: float, rh: float) -> bool:
        """Check if an AABB bounding box collides with map bounds, collision boxes, solid tiles, or props."""
        # Check map boundaries
        if rx < 0 or rx + rw > self.pixel_width or ry < 0 or ry + rh > self.pixel_height:
            return True

        # Check explicit geometric collision boxes
        for box in self.collision_boxes:
            if (
                rx < box.x + box.width
                and rx + rw > box.x
                and ry < box.y + box.height
                and ry + rh > box.y
            ):
                return True

        # Check tile collision grid if populated
        if self.collision_mask and self.tile_size > 0:
            start_tx = max(0, int(rx // self.tile_size))
            end_tx = min(self.width_tiles - 1, int((rx + rw) // self.tile_size))
            start_ty = max(0, int(ry // self.tile_size))
            end_ty = min(self.height_tiles - 1, int((ry + rh) // self.tile_size))

            for ty in range(start_ty, end_ty + 1):
                if ty < len(self.collision_mask):
                    row = self.collision_mask[ty]
                    for tx in range(start_tx, end_tx + 1):
                        if tx < len(row) and row[tx]:
                            return True

        # Check prop solid rects
        for prop in self.props:
            if prop.solid_rect:
                px, py, pw, ph = prop.solid_rect
                world_px = prop.x + px
                world_py = prop.y + py
                if (
                    rx < world_px + pw
                    and rx + rw > world_px
                    and ry < world_py + ph
                    and ry + rh > world_py
                ):
                    return True

        return False


def build_oakhaven_village_map() -> Tilemap:
    """Build the starter village of Oakhaven (30x20 tiles = 960x640 pixels)."""
    width, height = 30, 20
    tile_size = 32

    # Initialize ground with grass (1)
    ground: list[list[int]] = [[TileType.GRASS.value for _ in range(width)] for _ in range(height)]
    collision: list[list[bool]] = [[False for _ in range(width)] for _ in range(height)]

    # Main cobblestone central road (horizontally through middle, row 10-11)
    for x in range(width):
        ground[9][x] = TileType.COBBLESTONE.value
        ground[10][x] = TileType.COBBLESTONE.value

    # Path branching north to tavern/inn
    for y in range(4, 10):
        ground[y][14] = TileType.PATH.value
        ground[y][15] = TileType.PATH.value

    # Path branching south to Briarwood entrance
    for y in range(11, height):
        ground[y][14] = TileType.PATH.value
        ground[y][15] = TileType.PATH.value

    # Village water pond in top-left
    for y in range(2, 6):
        for x in range(2, 7):
            ground[y][x] = TileType.WATER.value
            collision[y][x] = True

    # Props & Buildings
    props: list[MapProp] = []

    # Rowan's Cottage / Frontier Inn (Top-Center)
    props.append(
        MapProp(
            id="cottage_rowan",
            prop_type="house",
            x=12 * tile_size,
            y=2 * tile_size,
            width=160,
            height=128,
            solid_rect=(8, 48, 144, 76),
            light=LightSource(x=14 * tile_size + 16, y=5 * tile_size + 16, radius=70, color=(255, 190, 100)),
        )
    )

    # Street Lanterns along the main road
    lantern_positions = [(6, 8), (12, 8), (18, 8), (24, 8)]
    for idx, (lx, ly) in enumerate(lantern_positions):
        props.append(
            MapProp(
                id=f"lantern_{idx}",
                prop_type="lantern",
                x=lx * tile_size,
                y=ly * tile_size,
                width=32,
                height=48,
                solid_rect=(8, 28, 16, 18),
                light=LightSource(x=lx * tile_size + 16, y=ly * tile_size + 16, radius=90, color=(255, 210, 130), flicker=True),
            )
        )

    # Oak trees bordering the village
    tree_positions = [
        (0, 8), (0, 13), (0, 16),
        (8, 2), (9, 3), (20, 2), (25, 2),
        (28, 6), (28, 12), (28, 16),
        (4, 16), (9, 16), (20, 16), (24, 16),
    ]
    for idx, (tx, ty) in enumerate(tree_positions):
        props.append(
            MapProp(
                id=f"tree_{idx}",
                prop_type="tree",
                x=tx * tile_size,
                y=ty * tile_size,
                width=64,
                height=96,
                solid_rect=(16, 64, 32, 28),
            )
        )

    # Village Elder Tomas (Standing near lantern in square)
    props.append(
        MapProp(
            id="npc_elder_tomas",
            prop_type="npc_elder",
            x=17 * tile_size,
            y=9 * tile_size,
            width=24,
            height=32,
            solid_rect=(4, 16, 16, 12),
        )
    )

    # Triggers
    triggers: list[TriggerZone] = [
        # Elder Tomas dialogue trigger (generous area around NPC)
        TriggerZone(
            id="talk_elder_tomas",
            trigger_type="dialogue",
            x=16 * tile_size,
            y=8 * tile_size + 16,
            width=72,
            height=72,
            dialogue_id="elder_tomas",
        ),
        # South exit to Briarwood Forest (generous corridor across columns 12..17)
        TriggerZone(
            id="exit_briarwood",
            trigger_type="transition",
            x=12 * tile_size,
            y=18 * tile_size + 16,
            width=6 * tile_size,
            height=48,
            target_map_id="briarwood_edge",
            target_x=14 * tile_size,
            target_y=2 * tile_size,
        ),
        # Rowan's Cottage door interaction
        TriggerZone(
            id="door_rowan",
            trigger_type="dialogue",
            x=14 * tile_size,
            y=5 * tile_size,
            width=48,
            height=48,
            dialogue_id="rowan_house_inspect",
        ),
    ]

    return Tilemap(
        id="oakhaven_village",
        name="Oakhaven Village",
        width_tiles=width,
        height_tiles=height,
        tile_size=tile_size,
        ground_layer=ground,
        collision_mask=collision,
        props=props,
        triggers=triggers,
        ambient_light=(210, 215, 240),  # Morning dawn sunlight
        ambient_particles="dust",
    )


def build_briarwood_map() -> Tilemap:
    """Build Briarwood Forest Edge (moody dark forest with bioluminescent glow)."""
    width, height = 28, 22
    tile_size = 32

    ground: list[list[int]] = [[TileType.GRASS.value for _ in range(width)] for _ in range(height)]
    collision: list[list[bool]] = [[False for _ in range(width)] for _ in range(height)]

    # Winding dirt trail from north to south
    path_coords = [
        (14, 0), (14, 1), (14, 2), (13, 3), (12, 4), (12, 5),
        (11, 6), (11, 7), (12, 8), (13, 9), (14, 10), (15, 11),
        (16, 12), (17, 13), (17, 14), (16, 15), (15, 16), (14, 17),
        (14, 18), (14, 19), (14, 20), (14, 21)
    ]
    for px, py in path_coords:
        ground[py][px] = TileType.PATH.value

    # Stone ruins / corrupted monoliths
    props: list[MapProp] = []
    # Dense corrupted briar trees
    for x in range(0, width, 3):
        if x not in (12, 13, 14, 15, 16):
            props.append(
                MapProp(
                    id=f"briar_n_{x}",
                    prop_type="tree",
                    x=x * tile_size,
                    y=1 * tile_size,
                    width=64,
                    height=96,
                    solid_rect=(16, 64, 32, 28),
                )
            )

    # Corrupted Root Spores emitting eerie teal/purple bioluminescence
    spore_lights = [(11, 7), (16, 13), (13, 18)]
    for idx, (sx, sy) in enumerate(spore_lights):
        props.append(
            MapProp(
                id=f"spore_crystal_{idx}",
                prop_type="crystal",
                x=sx * tile_size + 8,
                y=sy * tile_size + 8,
                width=24,
                height=32,
                solid_rect=(4, 16, 16, 12),
                light=LightSource(
                    x=sx * tile_size + 16,
                    y=sy * tile_size + 16,
                    radius=75,
                    color=(80, 240, 190),  # Bioluminescent eerie teal
                    intensity=1.2,
                    flicker=True,
                ),
            )
        )

    # Corrupted Treant Boss at clearing
    props.append(
        MapProp(
            id="boss_treant",
            prop_type="boss_treant",
            x=13 * tile_size,
            y=18 * tile_size,
            width=48,
            height=64,
            solid_rect=(8, 32, 32, 28),
        )
    )

    # North exit back to Oakhaven Village
    triggers: list[TriggerZone] = [
        TriggerZone(
            id="talk_treant_boss",
            trigger_type="dialogue",
            x=12 * tile_size,
            y=17 * tile_size,
            width=64,
            height=64,
            dialogue_id="treant_boss",
        ),
        TriggerZone(
            id="exit_to_oakhaven",
            trigger_type="transition",
            x=12 * tile_size,
            y=0,
            width=6 * tile_size,
            height=48,
            target_map_id="oakhaven_village",
            target_x=14 * tile_size,
            target_y=18 * tile_size,
        )
    ]

    return Tilemap(
        id="briarwood_edge",
        name="Briarwood Verge",
        width_tiles=width,
        height_tiles=height,
        tile_size=tile_size,
        ground_layer=ground,
        collision_mask=collision,
        props=props,
        triggers=triggers,
        ambient_light=(80, 75, 110),  # Deep twilight indigo/moss ambience
        ambient_particles="spores",
    )


MAP_REGISTRY = {
    "oakhaven_village": build_oakhaven_village_map,
    "briarwood_edge": build_briarwood_map,
}


def load_zone_map_from_json(file_path: Path | str) -> Tilemap:
    """Deserialize a data-driven zone map JSON descriptor into a Tilemap object."""
    path = Path(file_path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    map_id = data["id"]
    name = data.get("name", map_id)
    dims = data.get("dimensions", {})
    pixel_w = dims.get("width", 640)
    pixel_h = dims.get("height", 360)
    tile_size = data.get("tile_size", 32)
    width_tiles = (pixel_w + tile_size - 1) // tile_size
    height_tiles = (pixel_h + tile_size - 1) // tile_size

    bg_info = data.get("background", {})
    bg_image = bg_info.get("image")
    bg_slices = bg_info.get("slices", [])

    atmosphere = data.get("atmosphere", {})
    ambient_light = tuple(atmosphere.get("ambient_light", [200, 200, 220]))
    ambient_particles = atmosphere.get("ambient_particles", "dust")

    collision_boxes: list[CollisionBox] = []
    for c in data.get("collisions", []):
        collision_boxes.append(
            CollisionBox(
                id=c.get("id", "col"),
                x=float(c["x"]),
                y=float(c["y"]),
                width=float(c.get("w", c.get("width", 32))),
                height=float(c.get("h", c.get("height", 32))),
            )
        )

    props: list[MapProp] = []
    for p in data.get("props", []):
        light_obj = None
        if "light" in p and p["light"]:
            l_data = p["light"]
            pw = float(p.get("width", p.get("w", 32)))
            ph = float(p.get("height", p.get("h", 32)))
            lx = float(l_data.get("x", p["x"] + pw / 2))
            ly = float(l_data.get("y", p["y"] + ph / 2))
            light_obj = LightSource(
                x=lx,
                y=ly,
                radius=float(l_data.get("radius", 80.0)),
                color=tuple(l_data.get("color", [255, 200, 120])),
                intensity=float(l_data.get("intensity", 1.0)),
                flicker=bool(l_data.get("flicker", True)),
            )

        solid_rect = None
        if "solid_rect" in p and p["solid_rect"]:
            solid_rect = tuple(p["solid_rect"])

        props.append(
            MapProp(
                id=p["id"],
                prop_type=p.get("prop_type", p.get("type", "prop")),
                x=float(p["x"]),
                y=float(p["y"]),
                width=float(p.get("width", p.get("w", 32))),
                height=float(p.get("height", p.get("h", 32))),
                solid_rect=solid_rect,
                light=light_obj,
                sprite=p.get("sprite"),
            )
        )

    triggers: list[TriggerZone] = []
    for t in data.get("triggers", []):
        triggers.append(
            TriggerZone(
                id=t["id"],
                trigger_type=t.get("trigger_type", t.get("type", "transition")),
                x=float(t["x"]),
                y=float(t["y"]),
                width=float(t.get("width", t.get("w", 32))),
                height=float(t.get("height", t.get("h", 32))),
                target_map_id=t.get("target_map_id"),
                target_x=float(t["target_x"]) if "target_x" in t and t["target_x"] is not None else None,
                target_y=float(t["target_y"]) if "target_y" in t and t["target_y"] is not None else None,
                dialogue_id=t.get("dialogue_id"),
            )
        )

    return Tilemap(
        id=map_id,
        name=name,
        width_tiles=width_tiles,
        height_tiles=height_tiles,
        tile_size=tile_size,
        props=props,
        triggers=triggers,
        ambient_light=ambient_light,
        ambient_particles=ambient_particles,
        background_image=bg_image,
        background_slices=bg_slices,
        collision_boxes=collision_boxes,
        pixel_width_override=pixel_w,
        pixel_height_override=pixel_h,
    )


def load_map(map_id: str) -> Tilemap:
    # 1. Discover JSON descriptor in assets/maps/{map_id}/map.json
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    json_path = project_root / "assets" / "maps" / map_id / "map.json"
    if json_path.exists():
        return load_zone_map_from_json(json_path)

    # Check folder name aliases (e.g. briarwood_edge -> briarwood_verge)
    if map_id in ("briarwood_edge", "briarwood_verge"):
        alias_path = project_root / "assets" / "maps" / "briarwood_verge" / "map.json"
        if alias_path.exists():
            return load_zone_map_from_json(alias_path)

    # 2. Fall back to programmatic registry
    if map_id in MAP_REGISTRY:
        return MAP_REGISTRY[map_id]()

    raise ValueError(f"Unknown map id: '{map_id}'")
