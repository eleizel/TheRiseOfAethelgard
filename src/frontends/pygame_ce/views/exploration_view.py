"""Exploration view managing 2D world movement, collision, camera, and map transitions."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from src.core.events import QuestCompletedEvent, QuestUpdatedEvent
from src.core.fsm import GameMode
from src.data.enemies import generate_encounter_for_map
from src.frontends.pygame_ce.camera import Camera
from src.frontends.pygame_ce.hd2d_renderer import HD2DRenderer
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine, MusicContext
from src.frontends.pygame_ce.ui_manager import GameUIManager, StatBar
from src.systems.combat.round_combat import RoundCombat
from src.systems.exploration.encounter_system import EncounterSystem
from src.systems.exploration.map_data import Tilemap, load_map

if TYPE_CHECKING:
    from pygame_gui.elements import UILabel, UIPanel

    from src.core.session import GameSession


class ExplorationView:
    """Exploration screen with camera tracking, smooth collision, and HD pygame-gui HUD."""

    def __init__(
        self,
        session: GameSession,
        music_engine: DynamicMusicEngine | None = None,
        view_width: int = 640,
        view_height: int = 360,
        ui_manager: GameUIManager | None = None,
    ) -> None:
        self.session = session
        self.music_engine = music_engine
        self.view_width = view_width
        self.view_height = view_height
        self.ui_manager = ui_manager or GameUIManager()

        self.camera = Camera(view_width=view_width, view_height=view_height)
        self.renderer = HD2DRenderer(view_width=view_width, view_height=view_height)
        self.encounter_system = EncounterSystem(seed=session.seed)

        self.current_map: Tilemap = load_map(session.map_id)
        self.player_x: float = float(session.player_x * self.current_map.tile_size + 16)
        self.player_y: float = float(session.player_y * self.current_map.tile_size + 16)
        self.player_speed: float = 120.0  # Pixels per second
        self.is_moving: bool = False
        self.walk_animation_time: float = 0.0
        self.facing: str = "down"
        self.time_sec: float = 0.0
        self.transition_cooldown: float = 0.0

        # Collision bounding box around feet (width 16, height 10)
        self.col_w = 16.0
        self.col_h = 10.0

        # HUD widgets
        self._area_panel: UIPanel | None = None
        self._area_label: UILabel | None = None
        self._leader_panel: UIPanel | None = None
        self._leader_label: UILabel | None = None
        self._hp_bar: StatBar | None = None
        self._mp_bar: StatBar | None = None
        self._bottom_panel: UIPanel | None = None
        self._gold_label: UILabel | None = None
        self._controls_label: UILabel | None = None
        self._quest_panel: UIPanel | None = None
        self._quest_title_label: UILabel | None = None
        self._quest_step_label: UILabel | None = None
        self._toast_panel: UIPanel | None = None
        self._toast_label: UILabel | None = None
        self._toast_timer: float = 0.0
        self._toast_text: str = ""

        self.session.event_bus.subscribe(QuestUpdatedEvent, self._on_quest_updated)
        self.session.event_bus.subscribe(QuestCompletedEvent, self._on_quest_completed)

    def _on_quest_updated(self, event: QuestUpdatedEvent) -> None:
        prefix = "New Quest" if event.is_new else "Quest Updated"
        self._toast_text = f"{prefix}: {event.quest_title}"
        self._toast_timer = 3.5

    def _on_quest_completed(self, event: QuestCompletedEvent) -> None:
        suffix = f" ({event.reward_summary})" if event.reward_summary else ""
        self._toast_text = f"Quest Completed: {event.quest_title}!{suffix}"
        self._toast_timer = 4.5

    def _build_hud(self) -> None:
        from pygame_gui.core import ObjectID
        from pygame_gui.elements import UILabel, UIPanel, UITextBox

        self.on_exit()
        mgr = self.ui_manager.manager
        r = self.ui_manager.rect

        # 1. Top-Left Area Banner
        self._area_panel = UIPanel(
            relative_rect=r(20, 18, 280, 52),
            starting_height=1,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        self._area_label = UILabel(
            relative_rect=r(12, 8, 256, 36),
            text=self.current_map.name,
            manager=mgr,
            container=self._area_panel,
            object_id=ObjectID(class_id="@area_banner"),
        )

        # 2. Top-Right Party Leader Card
        if self.session.party.active_members:
            self._leader_panel = UIPanel(
                relative_rect=r(920, 18, 340, 102),
                starting_height=1,
                manager=mgr,
                object_id=ObjectID(class_id="@rpg_panel_gold"),
            )
            self._leader_label = UILabel(
                relative_rect=r(16, 8, 308, 28),
                text="",
                manager=mgr,
                container=self._leader_panel,
                object_id=ObjectID(class_id="@sub_header_label"),
            )
            self._hp_bar = StatBar(
                relative_rect=r(16, 40, 308, 22),
                manager=mgr,
                prefix="HP",
                container=self._leader_panel,
                object_id=ObjectID(object_id="#hp_bar"),
            )
            self._mp_bar = StatBar(
                relative_rect=r(16, 68, 308, 22),
                manager=mgr,
                prefix="MP",
                container=self._leader_panel,
                object_id=ObjectID(object_id="#mp_bar"),
            )

        # 3. Active Quest Tracker (below Area Banner)
        self._quest_panel = UIPanel(
            relative_rect=r(20, 76, 360, 96),
            starting_height=1,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel"),
        )
        self._quest_title_label = UILabel(
            relative_rect=r(12, 6, 336, 24),
            text="",
            manager=mgr,
            container=self._quest_panel,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        self._quest_step_label = UITextBox(
            html_text="",
            relative_rect=r(12, 30, 336, 60),
            manager=mgr,
            container=self._quest_panel,
            object_id=ObjectID(class_id="@rpg_textbox_clean"),
        )

        # 4. Top-Center Quest Notification Toast
        self._toast_panel = UIPanel(
            relative_rect=r(396, 18, 488, 48),
            starting_height=3,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        self._toast_label = UILabel(
            relative_rect=r(12, 8, 464, 32),
            text="",
            manager=mgr,
            container=self._toast_panel,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        if self._toast_timer <= 0.0:
            self._toast_panel.hide()

        # 5. Bottom Bar: Gold & Controls
        self._bottom_panel = UIPanel(
            relative_rect=r(20, 658, 1240, 44),
            starting_height=1,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel"),
        )
        self._gold_label = UILabel(
            relative_rect=r(18, 7, 220, 28),
            text="",
            manager=mgr,
            container=self._bottom_panel,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        self._controls_label = UILabel(
            relative_rect=r(380, 7, 840, 28),
            text="[WASD / Arrows] Move   [Shift] Dash   [Space / Enter] Interact   [M] Mute   [ESC] Menu",
            manager=mgr,
            container=self._bottom_panel,
            object_id=ObjectID(class_id="@footer_label"),
        )
        self._sync_hud()

    def _sync_hud(self) -> None:
        if self._area_label is not None and self._area_label.text != self.current_map.name:
            self._area_label.set_text(self.current_map.name)

        if self.session.party.active_members and self._leader_label is not None:
            leader = self.session.party.active_members[0]
            self._leader_label.set_text(f"{leader.name} (Lv. {leader.level})")
            max_hp = max(1, leader.base_stats.max_hp)
            max_mp = max(1, leader.base_stats.max_mp)
            if self._hp_bar is not None:
                self._hp_bar.set_values(leader.current_hp, max_hp)
            if self._mp_bar is not None:
                self._mp_bar.set_values(leader.current_mp, max_mp)

        if self._gold_label is not None:
            self._gold_label.set_text(f"Gold: {self.session.party.gold} G")

        if self._quest_panel is not None and self._quest_title_label is not None and self._quest_step_label is not None:
            tracked = self.session.quest_manager.get_tracked_quest()
            if tracked is None:
                self._quest_panel.hide()
            else:
                defn, prog, step = tracked
                tag = "MAIN" if defn.category.name == "MAIN" else "SIDE"
                self._quest_title_label.set_text(f"[{tag}] {defn.title}")
                step_txt = self.session.quest_manager.format_step_label(prog, step)
                if getattr(self, "_last_quest_step_txt", None) != step_txt:
                    self._last_quest_step_txt = step_txt
                    self._quest_step_label.set_text(f"<font color='#C8CEDE'>{step_txt}</font>")
                self._quest_panel.show()

        if self._toast_panel is not None and self._toast_label is not None:
            if self._toast_timer > 0.0 and self._toast_text:
                self._toast_label.set_text(self._toast_text)
                self._toast_panel.show()
            else:
                self._toast_panel.hide()

    def on_enter(self) -> None:
        pending = getattr(self.session, "pending_map_transition", None)
        if pending is not None:
            self.session.pending_map_transition = None
            map_id, spawn_x, spawn_y = pending
            self.switch_map(map_id, spawn_x, spawn_y)
            self.transition_cooldown = 0.8
        if self.music_engine:
            self.music_engine.set_context(MusicContext.EXPLORATION)
        self._build_hud()

    def on_exit(self) -> None:
        for attr in ("_area_panel", "_leader_panel", "_bottom_panel", "_quest_panel", "_toast_panel"):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.kill()
                setattr(self, attr, None)
        self._area_label = None
        self._leader_label = None
        self._hp_bar = None
        self._mp_bar = None
        self._gold_label = None
        self._controls_label = None
        self._quest_title_label = None
        self._quest_step_label = None
        self._toast_label = None

    def on_resize(self, width: int, height: int) -> None:
        self._build_hud()

    def switch_map(self, map_id: str, spawn_x: float, spawn_y: float) -> None:
        self.walk_animation_time = 0.0
        self.is_moving = False
        self.current_map = load_map(map_id)
        self.session.map_id = map_id
        self.player_x = spawn_x
        self.player_y = spawn_y
        self.session.player_x = int(spawn_x // self.current_map.tile_size)
        self.session.player_y = int(spawn_y // self.current_map.tile_size)
        self.camera.update(
            self.player_x,
            self.player_y,
            self.current_map.pixel_width,
            self.current_map.pixel_height,
            dt=1.0,
        )

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                # Check dialogue triggers from any direction: direct point, facing reach, or proximity
                reach = 24.0
                facing_x = self.player_x + (reach if self.facing == "right" else (-reach if self.facing == "left" else 0.0))
                facing_y = self.player_y + (reach if self.facing == "down" else (-reach if self.facing == "up" else 0.0))

                for trigger in self.current_map.triggers:
                    if trigger.trigger_type == "dialogue" and trigger.dialogue_id:
                        if (
                            trigger.contains_point(self.player_x, self.player_y)
                            or trigger.contains_point(facing_x, facing_y)
                            or trigger.distance_to(self.player_x, self.player_y) <= 48.0
                        ):
                            self.session.pending_dialogue_id = trigger.dialogue_id
                            self.session.transition_to(GameMode.DIALOGUE)
                            return
            elif event.key == pygame.K_m and self.music_engine:
                self.music_engine.toggle_mute()
            elif event.key == pygame.K_ESCAPE:
                self.session.transition_to(GameMode.MENU)

    def update(self, dt: float) -> None:
        self.time_sec += dt
        self.session.play_time_seconds += dt

        # Read movement keys
        keys = pygame.key.get_pressed()
        move_x = 0.0
        move_y = 0.0

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_x -= 1.0
            self.facing = "left"
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_x += 1.0
            self.facing = "right"
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move_y -= 1.0
            self.facing = "up"
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move_y += 1.0
            self.facing = "down"

        # Sprint toggle
        speed = self.player_speed * 1.5 if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) else self.player_speed

        # Normalize diagonal movement
        length = math.sqrt(move_x ** 2 + move_y ** 2)
        if length > 0.0:
            move_x /= length
            move_y /= length

        delta_x = move_x * speed * dt
        delta_y = move_y * speed * dt
        movement_start = (self.player_x, self.player_y)

        # Smooth axis-separated collision resolution (enables wall sliding)
        if delta_x != 0.0:
            next_x = self.player_x + delta_x
            box_x = next_x - self.col_w / 2.0
            box_y = self.player_y - self.col_h
            if not self.current_map.is_rect_colliding(box_x, box_y, self.col_w, self.col_h):
                self.player_x = next_x

        if delta_y != 0.0:
            next_y = self.player_y + delta_y
            box_x = self.player_x - self.col_w / 2.0
            box_y = next_y - self.col_h
            if not self.current_map.is_rect_colliding(box_x, box_y, self.col_w, self.col_h):
                self.player_y = next_y

        # Animate only when collision resolution produced actual movement.
        moved_distance = math.hypot(
            self.player_x - movement_start[0],
            self.player_y - movement_start[1],
        )
        self.is_moving = moved_distance > 0.01
        if self.is_moving:
            self.walk_animation_time += max(0.0, dt)
        else:
            self.walk_animation_time = 0.0

        # Update session position & quest proximity/map objectives
        self.session.player_x = int(self.player_x // self.current_map.tile_size)
        self.session.player_y = int(self.player_y // self.current_map.tile_size)
        trigger_centers = {
            t.id: (t.x + t.width / 2.0, t.y + t.height / 2.0)
            for t in self.current_map.triggers
        }
        unlocked_dialogues = self.session.quest_manager.on_player_moved(
            self.current_map.id,
            self.player_x,
            self.player_y,
            target_positions=trigger_centers,
        )
        if unlocked_dialogues:
            self.session.pending_dialogue_id = unlocked_dialogues[0]
            self.session.transition_to(GameMode.DIALOGUE)
            return
        if self._toast_timer > 0.0:
            self._toast_timer = max(0.0, self._toast_timer - dt)

        # Check map transitions (AABB overlap or point containment)
        if self.transition_cooldown > 0.0:
            self.transition_cooldown = max(0.0, self.transition_cooldown - dt)
        else:
            feet_box_x = self.player_x - self.col_w / 2.0
            feet_box_y = self.player_y - self.col_h
            for trigger in self.current_map.triggers:
                if trigger.trigger_type == "transition" and trigger.target_map_id:
                    if (
                        trigger.intersects_rect(feet_box_x, feet_box_y, self.col_w, self.col_h)
                        or trigger.contains_point(self.player_x, self.player_y)
                    ):
                        self.switch_map(
                            trigger.target_map_id,
                            trigger.target_x or 64.0,
                            trigger.target_y or 64.0,
                        )
                        self.transition_cooldown = 0.8  # Grace period prevents ping-pong double transitions
                        break

        # Check random encounter
        if self.is_moving:
            dist = math.sqrt(delta_x ** 2 + delta_y ** 2)
            if self.encounter_system.record_movement(dist, self.current_map.id):
                enemies = generate_encounter_for_map(self.current_map.id)
                self.session.combat = RoundCombat(
                    party=self.session.party,
                    enemies=enemies,
                    event_bus=self.session.event_bus,
                    seed=self.session.rng.randint(1, 100000),
                )
                self.session.transition_to(GameMode.COMBAT)

        # Update camera
        self.camera.update(
            self.player_x,
            self.player_y,
            self.current_map.pixel_width,
            self.current_map.pixel_height,
            dt,
        )
        self._sync_hud()

    def draw(self, surface: pygame.Surface) -> None:
        # Render HD-2D world onto the 640x360 canvas (HUD renders in HD pygame-gui overlay)
        self.renderer.render_map(
            dest_surf=surface,
            tilemap=self.current_map,
            cam_x=self.camera.x,
            cam_y=self.camera.y,
            player_x=self.player_x,
            player_y=self.player_y,
            player_moving=self.is_moving,
            player_facing=self.facing,
            time_sec=self.time_sec,
            player_animation_time=self.walk_animation_time,
        )
