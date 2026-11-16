"""Turn-based 4-member party combat view with classic SNES layout and HD-2D aesthetics."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import pygame
import pygame_gui
from pygame_gui.core import ObjectID

from src.core.fsm import GameMode
from src.data.abilities import ABILITY_REGISTRY, TargetScope
from src.entities.character import Character
from src.entities.enemy import Enemy, EnemyTier
from src.frontends.pygame_ce.combat_animator import CombatantAnimState, EnemySpriteManager
from src.frontends.pygame_ce.combat_background import CombatBackgroundManager
from src.frontends.pygame_ce.font_utils import get_font
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine, resolve_music_context
from src.frontends.pygame_ce.ui_manager import (
    GameUIManager,
    StatBar,
    attach_ornate_corners,
    get_status_icon,
    set_button_selected,
)
from src.systems.combat.action import ActionType, CombatAction
from src.systems.combat.round_combat import CombatPhase, RoundCombat

if TYPE_CHECKING:
    from src.core.session import GameSession


class CombatView:
    """SNES-style 4-member party combat presentation screen with HD pygame-gui overlay."""

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

        # Kept for world-canvas floating damage popups & enemy nameplates
        self.font = get_font(11)
        self.font_large = get_font(12, bold=True)

        # UI Navigation States
        self.menu_mode = "MAIN"  # "MAIN", "SKILLS", "ITEMS", "TARGET"
        self.main_options = ["Attack", "Skills", "Item", "Defend", "Flee"]
        self.main_index = 0
        self.skill_index = 0
        self.item_index = 0
        self.target_index = 0
        self.selected_action_type: ActionType | None = None
        self.selected_ability_id: str | None = None
        self.selected_item_id: str | None = None

        self.time_sec = 0.0
        self.execution_timer = 0.0
        self.execution_delay = 0.8  # Seconds between each combat action in round
        self.floating_texts: list[dict] = []
        self.rachel_projectiles: list[dict[str, float | str]] = []

        # Sprite Manager & Procedural Animation States
        self.sprite_manager = EnemySpriteManager()
        self.enemy_anim_states: dict[str, CombatantAnimState] = {}
        self.party_anim_states: dict[str, CombatantAnimState] = {}

        # Combat Background Art Manager
        self.bg_manager = CombatBackgroundManager(view_width=view_width, view_height=view_height)
        self.current_background: pygame.Surface | None = None

        # pygame-gui overlay widgets
        self._ui_widgets: list = []
        self._last_ui_signature: tuple | None = None

    @property
    def combat(self) -> RoundCombat | None:
        return self.session.combat

    def on_enter(self) -> None:
        self.menu_mode = "MAIN"
        self.main_index = 0
        self.skill_index = 0
        self.target_index = 0
        self.floating_texts.clear()

        # Initialize animation states
        self.enemy_anim_states.clear()
        self.party_anim_states.clear()
        if self.combat:
            for idx, enemy in enumerate(self.combat.enemies):
                self.enemy_anim_states[self._enemy_anim_key(enemy)] = CombatantAnimState(
                    phase_offset=idx * 0.9, is_player=False
                )
        for idx, char in enumerate(self.session.party.active_members):
            self.party_anim_states[char.id] = CombatantAnimState(
                phase_offset=idx * 0.7, is_player=True
            )

        # Music context resolution (regular combat vs boss)
        if self.music_engine and self.combat and self.combat.enemies:
            highest_tier = max((e.tier for e in self.combat.enemies), key=lambda t: t.value)
            ctx = resolve_music_context(GameMode.COMBAT, enemy_tier=highest_tier)
            self.music_engine.set_context(ctx)

        # Select random combat background for current map
        map_name = ""
        map_id = getattr(self.session, "map_id", "")
        try:
            from src.systems.exploration.map_data import MAP_REGISTRY
            if map_id in MAP_REGISTRY:
                map_name = MAP_REGISTRY[map_id]().name
        except Exception:
            pass
        self.current_background = self.bg_manager.get_random_background(map_id=map_id, map_name=map_name)
        self._victory_quests_notified = False
        self._sync_ui(force=True)

    def on_exit(self) -> None:
        self._clear_ui()

    def on_resize(self, width: int, height: int) -> None:
        self._sync_ui(force=True)

    @staticmethod
    def _enemy_anim_key(enemy: Enemy) -> str:
        return f"{enemy.id}#{id(enemy)}"

    def _is_enemy_targeted(self, enemy: Enemy) -> bool:
        """Check if this specific enemy is the currently selected target."""
        if self.menu_mode != "TARGET" or not self.combat or not self.combat.living_enemies:
            return False

        # If action targets allies, enemy is not targeted
        ab = ABILITY_REGISTRY.get(self.selected_ability_id or "basic_attack")
        if self.selected_action_type == ActionType.ITEM:
            return False
        if ab and ab.scope in (TargetScope.SINGLE_ALLY, TargetScope.ALL_ALLIES, TargetScope.SELF):
            return False
        if ab and ab.scope == TargetScope.ALL_ENEMIES:
            return enemy.is_alive

        living = self.combat.living_enemies
        target_idx = self.target_index % len(living)
        return living[target_idx] is enemy

    def _is_party_member_targeted(self, char: Character) -> bool:
        """Check if this specific party member is the currently selected target."""
        if self.menu_mode != "TARGET" or not self.combat or not self.combat.living_party:
            return False

        ab = ABILITY_REGISTRY.get(self.selected_ability_id or "basic_attack")
        is_ally_action = (
            self.selected_action_type == ActionType.ITEM
            or (ab and ab.scope in (TargetScope.SINGLE_ALLY, TargetScope.ALL_ALLIES, TargetScope.SELF))
        )
        if not is_ally_action:
            return False

        if self.selected_action_type != ActionType.ITEM and ab:
            if ab.scope == TargetScope.ALL_ALLIES:
                return char.is_alive
            if ab.scope == TargetScope.SELF:
                return char is self.combat.active_input_character

        living = self.combat.living_party
        target_idx = self.target_index % len(living)
        return living[target_idx] is char

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.combat or event.type != pygame.KEYDOWN:
            return

        # Battle End confirmation
        if self.combat.phase in (CombatPhase.VICTORY, CombatPhase.ESCAPED):
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.session.transition_to(GameMode.EXPLORATION)
            return

        if self.combat.phase == CombatPhase.DEFEAT:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.session.transition_to(GameMode.TITLE)
            return

        if self.combat.phase != CombatPhase.COMMAND_INPUT:
            return

        # Menu Navigation
        if self.menu_mode == "MAIN":
            self._handle_main_menu_input(event)
        elif self.menu_mode == "SKILLS":
            self._handle_skills_menu_input(event)
        elif self.menu_mode == "ITEMS":
            self._handle_items_menu_input(event)
        elif self.menu_mode == "TARGET":
            self._handle_target_input(event)

    def _handle_main_menu_input(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_UP, pygame.K_w):
            self.main_index = (self.main_index - 1) % len(self.main_options)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.main_index = (self.main_index + 1) % len(self.main_options)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            choice = self.main_options[self.main_index]
            char = self.combat.active_input_character
            if not char:
                return

            if choice == "Attack":
                self.selected_action_type = ActionType.ATTACK
                self.selected_ability_id = "basic_attack"
                self.menu_mode = "TARGET"
                self.target_index = 0
            elif choice == "Skills":
                if char.learned_abilities:
                    self.menu_mode = "SKILLS"
                    self.skill_index = 0
            elif choice == "Item":
                usable_items = [i for i, q in self.session.party.inventory.items() if q > 0]
                if usable_items:
                    self.menu_mode = "ITEMS"
                    self.item_index = 0
            elif choice == "Defend":
                self.combat.queue_player_action(
                    CombatAction(
                        actor_id=char.id,
                        is_player=True,
                        action_type=ActionType.DEFEND,
                    )
                )
                self.main_index = 0
            elif choice == "Flee":
                self.combat.queue_player_action(
                    CombatAction(
                        actor_id=char.id,
                        is_player=True,
                        action_type=ActionType.FLEE,
                    )
                )
                self.main_index = 0

        elif event.key == pygame.K_BACKSPACE or event.key == pygame.K_ESCAPE:
            # Step back to previous party member
            if self.combat.cancel_last_player_action():
                self.main_index = 0

    def _handle_skills_menu_input(self, event: pygame.event.Event) -> None:
        char = self.combat.active_input_character
        if not char:
            return

        abilities = char.learned_abilities
        if event.key in (pygame.K_UP, pygame.K_w):
            self.skill_index = (self.skill_index - 1) % len(abilities)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.skill_index = (self.skill_index + 1) % len(abilities)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            ab_id = abilities[self.skill_index]
            ab_def = ABILITY_REGISTRY.get(ab_id)
            if ab_def and char.current_mp >= ab_def.mp_cost:
                self.selected_action_type = ActionType.ABILITY
                self.selected_ability_id = ab_id
                self.menu_mode = "TARGET"
                self.target_index = 0
        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.menu_mode = "MAIN"

    def _handle_items_menu_input(self, event: pygame.event.Event) -> None:
        usable = [i for i, q in self.session.party.inventory.items() if q > 0]
        if not usable:
            self.menu_mode = "MAIN"
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.item_index = (self.item_index - 1) % len(usable)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.item_index = (self.item_index + 1) % len(usable)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.selected_action_type = ActionType.ITEM
            self.selected_item_id = usable[self.item_index]
            self.menu_mode = "TARGET"
            self.target_index = 0
        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.menu_mode = "MAIN"

    def _handle_target_input(self, event: pygame.event.Event) -> None:
        char = self.combat.active_input_character
        if not char:
            return

        ab = ABILITY_REGISTRY.get(self.selected_ability_id or "basic_attack")
        targets: list[Enemy | Character] = (
            self.combat.living_party
            if (ab and ab.scope in (TargetScope.SINGLE_ALLY, TargetScope.ALL_ALLIES, TargetScope.SELF))
            or self.selected_action_type == ActionType.ITEM
            else self.combat.living_enemies
        )

        if not targets:
            self.menu_mode = "MAIN"
            return

        is_fixed_scope = (
            self.selected_action_type != ActionType.ITEM
            and ab is not None
            and ab.scope in (TargetScope.ALL_ENEMIES, TargetScope.ALL_ALLIES, TargetScope.SELF)
        )
        if not is_fixed_scope and event.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
            self.target_index = (self.target_index - 1) % len(targets)
        elif not is_fixed_scope and event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
            self.target_index = (self.target_index + 1) % len(targets)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            chosen_target = targets[self.target_index]
            self.combat.queue_player_action(
                CombatAction(
                    actor_id=char.id,
                    is_player=True,
                    action_type=self.selected_action_type or ActionType.ATTACK,
                    target_id=chosen_target.id,
                    ability_id=self.selected_ability_id,
                    item_id=self.selected_item_id,
                )
            )
            # Reset menu for next character
            self.menu_mode = "MAIN"
            self.main_index = 0
        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.menu_mode = "MAIN"

    def update(self, dt: float) -> None:
        self.time_sec += dt
        if not self.combat:
            return

        if self.combat.phase == CombatPhase.VICTORY and not getattr(self, "_victory_quests_notified", False):
            self._victory_quests_notified = True
            for enemy in self.combat.enemies:
                self.session.quest_manager.on_enemy_defeated(enemy.sprite_id or enemy.id)
            self.session.quest_manager.on_inventory_changed(self.session.party)

        # Update animation states for all participants
        for enemy in self.combat.enemies:
            st = self.enemy_anim_states.setdefault(
                self._enemy_anim_key(enemy),
                CombatantAnimState(phase_offset=len(self.enemy_anim_states) * 0.9, is_player=False),
            )
            st.update(dt, is_alive=enemy.is_alive)

        for char in self.session.party.active_members:
            st = self.party_anim_states.setdefault(
                char.id, CombatantAnimState(phase_offset=len(self.party_anim_states) * 0.7, is_player=True)
            )
            st.update(dt, is_alive=char.is_alive)

        # Update active spell projectiles in world-space reference coordinates.
        for projectile in list(self.rachel_projectiles):
            projectile["elapsed"] = float(projectile["elapsed"]) + max(0.0, dt)
            if float(projectile["elapsed"]) >= (
                float(projectile["launch_delay"]) + float(projectile["duration"])
            ):
                self.rachel_projectiles.remove(projectile)

        # Automatic step pacing during Action Execution
        if self.combat.phase == CombatPhase.ACTION_EXECUTION:
            self.execution_timer += dt
            if self.execution_timer >= self.execution_delay:
                self.execution_timer = 0.0
                res = self.combat.step_next_action()
                if res:
                    # 1. Trigger the actor animation. Violet Ember uses Rachel's
                    # dedicated casting sequence; other actions keep the normal lunge.
                    attacker_char = next((c for c in self.session.party.active_members if c.name == res.source_name), None)
                    if attacker_char and attacker_char.id in self.party_anim_states:
                        actor_state = self.party_anim_states[attacker_char.id]
                        if attacker_char.id.lower() == "rachel" and res.ability_id == "violet_ember":
                            actor_state.trigger_spell(duration=0.8, frame_count=8)
                            target_ids = res.target_ids or []
                            target_enemy = next(
                                (e for e in self.combat.enemies if e.id in target_ids and e.is_alive),
                                None,
                            )
                            if target_enemy is not None:
                                self._spawn_rachel_violet_projectile(attacker_char, target_enemy)
                        else:
                            actor_state.trigger_attack(distance=34.0)
                    else:
                        attacker_enemy = next((e for e in self.combat.enemies if e.name == res.source_name), None)
                        if attacker_enemy:
                            ekey = self._enemy_anim_key(attacker_enemy)
                            if ekey in self.enemy_anim_states:
                                self.enemy_anim_states[ekey].trigger_attack(distance=34.0)

                    # 2. Trigger hurt recoil, white hit-flash, and floating damage numbers
                    if res.damage_dealt:
                        for idx, val in enumerate(res.damage_dealt):
                            tname = res.target_names[idx] if idx < len(res.target_names) else (res.target_names[0] if res.target_names else "")
                            pop_x = 160.0
                            pop_y = 120.0

                            target_enemy = next((e for e in self.combat.enemies if e.name == tname), None)
                            if target_enemy:
                                ekey = self._enemy_anim_key(target_enemy)
                                if ekey in self.enemy_anim_states:
                                    self.enemy_anim_states[ekey].trigger_hurt(recoil=14.0)
                                e_idx = self.combat.enemies.index(target_enemy)
                                pop_x = 90.0 + (e_idx % 2) * 24.0 + 30.0
                                pop_y = (125 - (len(self.combat.enemies) * 55) // 2) + e_idx * 55.0

                            target_char = next((c for c in self.session.party.active_members if c.name == tname), None)
                            if target_char:
                                if target_char.id in self.party_anim_states:
                                    self.party_anim_states[target_char.id].trigger_hurt(recoil=12.0)
                                c_idx = self.session.party.active_members.index(target_char)
                                pop_x = 450.0 + (c_idx % 2) * 24.0
                                pop_y = 65.0 + c_idx * 42.0

                            self.floating_texts.append(
                                {
                                    "text": f"{val}!" if res.is_crit else str(val),
                                    "color": (255, 230, 80) if res.is_crit else (255, 255, 255),
                                    "x": pop_x,
                                    "y": pop_y,
                                    "vy": -30.0,
                                    "alpha": 255,
                                }
                            )

                    elif res.healing_dealt:
                        for idx, val in enumerate(res.healing_dealt):
                            tname = res.target_names[idx] if idx < len(res.target_names) else (res.target_names[0] if res.target_names else "")
                            pop_x = 460.0
                            pop_y = 120.0
                            target_char = next((c for c in self.session.party.active_members if c.name == tname), None)
                            if target_char:
                                c_idx = self.session.party.active_members.index(target_char)
                                pop_x = 450.0 + (c_idx % 2) * 24.0
                                pop_y = 65.0 + c_idx * 42.0

                            self.floating_texts.append(
                                {
                                    "text": f"+{val}",
                                    "color": (80, 255, 120),
                                    "x": pop_x,
                                    "y": pop_y,
                                    "vy": -25.0,
                                    "alpha": 255,
                                }
                            )

        # Update floating texts
        for ft in list(self.floating_texts):
            ft["y"] += ft["vy"] * dt
            ft["alpha"] = max(0, ft["alpha"] - int(200 * dt))
            if ft["alpha"] <= 0:
                self.floating_texts.remove(ft)

        self._sync_ui()

    def draw(self, surface: pygame.Surface) -> None:
        if not self.combat:
            return

        # 0. Background solid clear
        surface.fill((14, 16, 26))

        # 1. Background Battle Arena (Twilight Forest Arena)
        self._draw_battle_arena(surface)

    def draw_screen_overlay(self, surface: pygame.Surface) -> None:
        """Render crisp HD combat sprites, reticles, and floating popups onto screen."""
        if not self.combat:
            return

        self._draw_enemies(surface)
        self._draw_party(surface)
        self._draw_rachel_projectiles(surface)

        sw_s, sh_s = surface.get_size()
        sx = sw_s / 1280.0
        sy = sh_s / 720.0
        pop_font = get_font(max(14, int(26 * min(sx, sy))), bold=True)
        for ft in self.floating_texts:
            txt_surf = pop_font.render(ft["text"], True, ft["color"])
            txt_surf.set_alpha(ft["alpha"])
            surface.blit(txt_surf, (int(ft["x"] * 2.0 * sx), int(ft["y"] * 2.0 * sy)))

    def _spawn_rachel_violet_projectile(
        self, caster: Character, target: Enemy
    ) -> None:
        """Queue the violet flame to leave Rachel's hand and travel to its target."""
        party_index = next(
            (i for i, member in enumerate(self.session.party.active_members) if member.id == caster.id),
            0,
        )
        party_row, party_col = divmod(party_index, 2)
        caster_x = 915.0 + party_col * 175.0
        caster_foot_y = 340.0 + party_row * 124.0

        enemy_count = len(self.combat.enemies) if self.combat else 1
        enemy_index = self.combat.enemies.index(target) if self.combat else 0
        is_elite = target.tier in (EnemyTier.ELITE, EnemyTier.BOSS)
        if enemy_count == 1:
            target_x = 280.0
            target_foot_y = 472.0 if is_elite else 432.0
        elif enemy_count == 2:
            target_x = 200.0 if enemy_index == 0 else 370.0
            target_foot_y = 362.0 if enemy_index == 0 else 464.0
        else:
            target_x = 170.0 + (enemy_index % 2) * 195.0
            target_foot_y = min(472.0, 336.0 + enemy_index * 64.0)

        self.rachel_projectiles.append(
            {
                "elapsed": 0.0,
                "launch_delay": 0.34,
                "duration": 0.32,
                "start_x": caster_x - 54.0,
                "start_y": caster_foot_y - 102.0,
                "end_x": target_x + 24.0,
                "end_y": target_foot_y - 54.0,
            }
        )

    def _draw_rachel_projectiles(self, surface: pygame.Surface) -> None:
        if not self.rachel_projectiles:
            return
        screen_w, screen_h = surface.get_size()
        sx = screen_w / 1280.0
        sy = screen_h / 720.0
        pixel_scale = 2.0 * min(sx, sy)

        for projectile in self.rachel_projectiles:
            flight_elapsed = float(projectile["elapsed"]) - float(projectile["launch_delay"])
            if flight_elapsed < 0.0:
                continue
            duration = max(0.01, float(projectile["duration"]))
            progress = min(1.0, max(0.0, flight_elapsed / duration))
            x = float(projectile["start_x"]) + (
                float(projectile["end_x"]) - float(projectile["start_x"])
            ) * progress
            y = float(projectile["start_y"]) + (
                float(projectile["end_y"]) - float(projectile["start_y"])
            ) * progress - math.sin(progress * math.pi) * 26.0

            frame_index = min(7, int(progress * 8.0))
            frame = self.sprite_manager.get_projectile_frame("violet_ember", frame_index)
            if frame is None:
                continue

            fw, fh = frame.get_size()
            dw = max(8, int(round(fw * pixel_scale)))
            dh = max(8, int(round(fh * pixel_scale)))
            scaled = frame if (dw, dh) == (fw, fh) else pygame.transform.scale(frame, (dw, dh))
            dest = (int(x * sx - dw / 2), int(y * sy - dh / 2))
            surface.blit(scaled, dest)

    def _draw_battle_arena(self, surface: pygame.Surface) -> None:
        if self.current_background is not None:
            surface.blit(self.current_background, (0, 0))
            return

        # Fallback Sky gradient
        for y in range(180):
            ratio = y / 180.0
            r = int(14 * (1.0 - ratio) + 25 * ratio)
            g = int(18 * (1.0 - ratio) + 38 * ratio)
            b = int(36 * (1.0 - ratio) + 48 * ratio)
            pygame.draw.line(surface, (r, g, b), (0, y), (self.view_width, y))

        # Ground battle plane (y: 170 to 226)
        pygame.draw.rect(surface, (38, 55, 36), (0, 170, self.view_width, 56))
        # Ground shadow / grid accent
        for gy in range(170, 226, 10):
            pygame.draw.line(surface, (28, 42, 28), (0, gy), (self.view_width, gy), 1)

    def _draw_enemies(self, surface: pygame.Surface) -> None:
        sw_s, sh_s = surface.get_size()
        sx = sw_s / 1280.0
        sy = sh_s / 720.0
        pixel_scale = 2.0 * min(sx, sy)
        ui_font = get_font(max(12, int(18 * min(sx, sy))), bold=True)

        enemies = self.combat.enemies
        num_enemies = len(enemies)

        for idx, enemy in enumerate(enemies):
            is_elite = enemy.tier in (EnemyTier.ELITE, EnemyTier.BOSS)
            if num_enemies == 1:
                cx = 280.0
                foot_y = 472.0 if is_elite else 432.0
            elif num_enemies == 2:
                cx = 200.0 if idx == 0 else 370.0
                foot_y = 362.0 if idx == 0 else 464.0
            else:
                cx = 170.0 + (idx % 2) * 195.0
                foot_y = min(472.0, 336.0 + idx * 64.0)

            anim_state = self.enemy_anim_states.setdefault(
                self._enemy_anim_key(enemy),
                CombatantAnimState(phase_offset=idx * 0.9, is_player=False),
            )

            rx, ry, sw, sh = self.sprite_manager.draw_enemy(
                surface=surface,
                enemy=enemy,
                base_x=cx * sx,
                base_y=foot_y * sy,
                anim_state=anim_state,
                is_elite_or_boss=is_elite,
                pixel_scale=pixel_scale,
                anchor_bottom_center=True,
            )

            if enemy.is_alive:
                is_targeted = self._is_enemy_targeted(enemy)

                # Name and HP bar above sprite (clamped below top banner y=62)
                bar_w = max(int(96 * sx), min(int(180 * sx), sw))
                bar_h = max(4, int(8 * sy))
                bar_x = rx + (sw - bar_w) // 2
                bar_y = max(int(86 * sy), ry - int(12 * sy))
                name_col = (255, 235, 90) if is_targeted else (240, 230, 210)
                name_txt = ui_font.render(enemy.name, True, name_col)
                name_x = rx + (sw - name_txt.get_width()) // 2
                name_y = bar_y - int(22 * sy)
                surface.blit(name_txt, (name_x, name_y))

                hp_ratio = enemy.current_hp / max(1, enemy.stats.max_hp)
                pygame.draw.rect(surface, (50, 15, 15), (bar_x, bar_y, bar_w, bar_h))
                pygame.draw.rect(surface, (220, 50, 50), (bar_x, bar_y, int(bar_w * hp_ratio), bar_h))
                pygame.draw.rect(surface, (80, 30, 30), (bar_x, bar_y, bar_w, bar_h), 1)

                if enemy.statuses:
                    icon_sz = max(16, int(20 * min(sx, sy)))
                    gap = max(2, int(4 * sx))
                    shown = enemy.statuses[:6]
                    total_w = len(shown) * icon_sz + (len(shown) - 1) * gap
                    ix = rx + (sw - total_w) // 2
                    iy = bar_y + bar_h + max(2, int(4 * sy))
                    for st in shown:
                        icon = get_status_icon(st.status, size=icon_sz)
                        if icon is not None:
                            surface.blit(icon, (ix, iy))
                        ix += icon_sz + gap

                # Target Selection Pointer & Targeting Reticle
                if is_targeted:
                    # 1. Bouncing golden arrowhead hovering above enemy name
                    bounce = int(math.sin(self.time_sec * 9.0) * 6 * sy)
                    cx = rx + sw // 2
                    tip_y = name_y - int(8 * sy) + bounce
                    pts = [
                        (cx, tip_y),
                        (cx - 10, tip_y - 14),
                        (cx - 4, tip_y - 14),
                        (cx - 4, tip_y - 24),
                        (cx + 4, tip_y - 24),
                        (cx + 4, tip_y - 14),
                        (cx + 10, tip_y - 14),
                    ]
                    pygame.draw.polygon(surface, (255, 235, 80), pts)
                    pygame.draw.polygon(surface, (80, 50, 10), pts, 1)

                    # 2. Gold corner reticle brackets around enemy sprite
                    box = pygame.Rect(rx - 6, ry - 6, sw + 12, sh + 12)
                    c_len = 12
                    g_col = (255, 220, 80)
                    # Top-Left
                    pygame.draw.line(surface, g_col, box.topleft, (box.left + c_len, box.top), 3)
                    pygame.draw.line(surface, g_col, box.topleft, (box.left, box.top + c_len), 3)
                    # Top-Right
                    pygame.draw.line(surface, g_col, box.topright, (box.right - c_len, box.top), 3)
                    pygame.draw.line(surface, g_col, box.topright, (box.right, box.top + c_len), 3)
                    # Bottom-Left
                    pygame.draw.line(surface, g_col, box.bottomleft, (box.left + c_len, box.bottom), 3)
                    pygame.draw.line(surface, g_col, box.bottomleft, (box.left, box.bottom - c_len), 3)
                    # Bottom-Right
                    pygame.draw.line(surface, g_col, box.bottomright, (box.right - c_len, box.bottom), 3)
                    pygame.draw.line(surface, g_col, box.bottomright, (box.right, box.bottom - c_len), 3)
            else:
                if anim_state.ko_alpha > 0.0:
                    ko_txt = ui_font.render(f"{enemy.name} [KO]", True, (140, 120, 120))
                    surface.blit(ko_txt, (rx, ry + sh // 2))

    def _draw_party(self, surface: pygame.Surface) -> None:
        sw_s, sh_s = surface.get_size()
        sx = sw_s / 1280.0
        sy = sh_s / 720.0
        pixel_scale = 2.0 * min(sx, sy)
        ui_font = get_font(max(12, int(18 * min(sx, sy))), bold=True)

        party_members = self.session.party.active_members
        active_char = self.combat.active_input_character

        # Arrange characters (64x80 -> 128x160, 72x96 -> 144x192) foot-anchored in 2x2 grid
        for idx, char in enumerate(party_members):
            row = idx // 2
            col = idx % 2

            cx = (915.0 + col * 175.0) * sx
            foot_y = (340.0 + row * 124.0) * sy

            anim_state = self.party_anim_states.setdefault(
                char.id, CombatantAnimState(phase_offset=idx * 0.7, is_player=True)
            )

            # Draw authentic 16-bit party member sprite facing left at exact 2x integer pixel scale
            rx, ry, sw, sh = self.sprite_manager.draw_party_member(
                surface=surface,
                char=char,
                base_x=cx,
                base_y=foot_y,
                anim_state=anim_state,
                pixel_scale=pixel_scale,
                anchor_bottom_center=True,
            )

            if char.is_alive:
                # Active Input Turn Indicator (bouncing gold pointer above character)
                if self.combat.phase == CombatPhase.COMMAND_INPUT and active_char and active_char.id == char.id:
                    bounce = int(math.sin(self.time_sec * 8.0) * 5 * sy)
                    cx = rx + sw // 2
                    pointer_pts = [
                        (cx, ry - 8 + bounce),
                        (cx - 8, ry - 20 + bounce),
                        (cx + 8, ry - 20 + bounce),
                    ]
                    pygame.draw.polygon(surface, (255, 225, 90), pointer_pts)
                    pygame.draw.polygon(surface, (70, 50, 10), pointer_pts, 1)

                # Ally Target Pointer (for healing skills or items)
                if self._is_party_member_targeted(char):
                    bounce = int(math.sin(self.time_sec * 9.0) * 6 * sy)
                    cx = rx + sw // 2
                    tip_y = ry - 10 + bounce
                    pts = [
                        (cx, tip_y),
                        (cx - 10, tip_y - 14),
                        (cx - 4, tip_y - 14),
                        (cx - 4, tip_y - 24),
                        (cx + 4, tip_y - 24),
                        (cx + 4, tip_y - 14),
                        (cx + 10, tip_y - 14),
                    ]
                    pygame.draw.polygon(surface, (80, 240, 140), pts)
                    pygame.draw.polygon(surface, (15, 70, 35), pts, 1)

                    # Green corner reticle brackets around party member
                    pbox = pygame.Rect(rx - 6, ry - 6, sw + 12, sh + 12)
                    c_len = 10
                    e_col = (80, 240, 140)
                    pygame.draw.line(surface, e_col, pbox.topleft, (pbox.left + c_len, pbox.top), 3)
                    pygame.draw.line(surface, e_col, pbox.topleft, (pbox.left, pbox.top + c_len), 3)
                    pygame.draw.line(surface, e_col, pbox.topright, (pbox.right - c_len, pbox.top), 3)
                    pygame.draw.line(surface, e_col, pbox.topright, (pbox.right, pbox.top + c_len), 3)
                    pygame.draw.line(surface, e_col, pbox.bottomleft, (pbox.left + c_len, pbox.bottom), 3)
                    pygame.draw.line(surface, e_col, pbox.bottomleft, (pbox.left, pbox.bottom - c_len), 3)
                    pygame.draw.line(surface, e_col, pbox.bottomright, (pbox.right - c_len, pbox.bottom), 3)
                    pygame.draw.line(surface, e_col, pbox.bottomright, (pbox.right, pbox.bottom - c_len), 3)
            else:
                ko_txt = ui_font.render(f"{char.name} [Fallen]", True, (160, 80, 80))
                surface.blit(ko_txt, (rx, ry + sh // 2))

    def _clear_ui(self) -> None:
        for w in self._ui_widgets:
            w.kill()
        self._ui_widgets.clear()
        self._last_ui_signature = None

    def _ui_signature(self) -> tuple[Any, ...]:
        if not self.combat:
            return ()
        active_char = self.combat.active_input_character
        last_log = self.combat.combat_log[-1] if self.combat.combat_log else ""
        party_sig = tuple(
            (
                c.id,
                c.current_hp,
                c.base_stats.max_hp,
                c.current_mp,
                c.base_stats.max_mp,
                c.level,
                c.is_alive,
                tuple((s.status.name, s.duration) for s in c.statuses),
            )
            for c in self.session.party.active_members
        )
        inv_sig = tuple(sorted((k, v) for k, v in self.session.party.inventory.items() if v > 0))
        return (
            self.combat.phase,
            self.menu_mode,
            self.main_index,
            self.skill_index,
            self.item_index,
            self.target_index,
            last_log,
            active_char.id if active_char else None,
            party_sig,
            inv_sig,
        )

    def _sync_ui(self, force: bool = False) -> None:
        if not self.ui_manager or not self.combat:
            return
        sig = self._ui_signature()
        if not force and sig == self._last_ui_signature:
            return
        self._last_ui_signature = sig
        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        for w in self._ui_widgets:
            w.kill()
        self._ui_widgets.clear()

        if not self.ui_manager or not self.combat:
            return

        mgr = self.ui_manager.manager
        r = self.ui_manager.rect

        # 1. Top Announcement Banner
        last_log = self.combat.combat_log[-1] if self.combat.combat_log else "Round Begin"
        banner = pygame_gui.elements.UIPanel(
            relative_rect=r(40, 14, 1200, 48),
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        pygame_gui.elements.UILabel(
            relative_rect=r(18, 6, 1164, 34),
            text=last_log,
            manager=mgr,
            container=banner,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        self._ui_widgets.append(banner)

        # 2. Bottom-Left Action Panel (compact 2 columns x 3 rows)
        action_panel = pygame_gui.elements.UIPanel(
            relative_rect=r(30, 486, 420, 166),
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(action_panel, self.ui_manager)
        self._ui_widgets.append(action_panel)

        active_char = self.combat.active_input_character
        if self.menu_mode == "MAIN":
            header = f"{active_char.name}'s Turn" if active_char else "Actions"
            pygame_gui.elements.UILabel(
                relative_rect=r(48, 8, 324, 26),
                text=header,
                manager=mgr,
                container=action_panel,
                object_id=ObjectID(class_id="@sub_header_label"),
            )
            for idx, opt in enumerate(self.main_options):
                col = idx // 3
                row = idx % 3
                btn = pygame_gui.elements.UIButton(
                    relative_rect=r(40 + col * 172, 40 + row * 38, 164, 34),
                    text=opt,
                    manager=mgr,
                    container=action_panel,
                    object_id=ObjectID(class_id="@rpg_button"),
                )
                set_button_selected(btn, idx == self.main_index)

        elif self.menu_mode == "SKILLS":
            pygame_gui.elements.UILabel(
                relative_rect=r(48, 8, 324, 26),
                text="Select Ability  [ESC Back]",
                manager=mgr,
                container=action_panel,
                object_id=ObjectID(class_id="@sub_header_label"),
            )
            if active_char:
                for idx, ab_id in enumerate(active_char.learned_abilities[:6]):
                    ab = ABILITY_REGISTRY.get(ab_id)
                    if not ab:
                        continue
                    col = idx // 3
                    row = idx % 3
                    btn = pygame_gui.elements.UIButton(
                        relative_rect=r(40 + col * 172, 40 + row * 38, 164, 34),
                        text=f"{ab.name} ({ab.mp_cost})",
                        manager=mgr,
                        container=action_panel,
                        object_id=ObjectID(class_id="@rpg_button"),
                    )
                    set_button_selected(btn, idx == self.skill_index)

        elif self.menu_mode == "ITEMS":
            pygame_gui.elements.UILabel(
                relative_rect=r(48, 8, 324, 26),
                text="Select Item  [ESC Back]",
                manager=mgr,
                container=action_panel,
                object_id=ObjectID(class_id="@sub_header_label"),
            )
            items = [(i, q) for i, q in self.session.party.inventory.items() if q > 0]
            if not items:
                pygame_gui.elements.UILabel(
                    relative_rect=r(40, 56, 340, 30),
                    text="No usable items.",
                    manager=mgr,
                    container=action_panel,
                    object_id=ObjectID(class_id="@muted_label"),
                )
            else:
                for idx, (it_id, qty) in enumerate(items[:6]):
                    col = idx // 3
                    row = idx % 3
                    btn = pygame_gui.elements.UIButton(
                        relative_rect=r(40 + col * 172, 40 + row * 38, 164, 34),
                        text=f"{it_id.replace('_', ' ').title()} x{qty}",
                        manager=mgr,
                        container=action_panel,
                        object_id=ObjectID(class_id="@rpg_button"),
                    )
                    set_button_selected(btn, idx == self.item_index)

        elif self.menu_mode == "TARGET":
            ab = ABILITY_REGISTRY.get(self.selected_ability_id or "basic_attack")
            if self.selected_action_type != ActionType.ITEM and ab and ab.scope == TargetScope.ALL_ENEMIES:
                hint = "Target: All Enemies  [ENTER Confirm]"
            elif self.selected_action_type != ActionType.ITEM and ab and ab.scope == TargetScope.ALL_ALLIES:
                hint = "Target: All Allies  [ENTER Confirm]"
            elif self.selected_action_type != ActionType.ITEM and ab and ab.scope == TargetScope.SELF:
                hint = "Target: Self  [ENTER Confirm]"
            else:
                hint = "Use Arrow Keys to select target"
            pygame_gui.elements.UILabel(
                relative_rect=r(48, 8, 324, 26),
                text="Choose Target  [ESC Back]",
                manager=mgr,
                container=action_panel,
                object_id=ObjectID(class_id="@sub_header_label"),
            )
            pygame_gui.elements.UILabel(
                relative_rect=r(40, 56, 340, 30),
                text=hint,
                manager=mgr,
                container=action_panel,
                object_id=ObjectID(class_id="@muted_label"),
            )

        # 3. Bottom-Right Party Status Table (compact 2x2 grid)
        status_panel = pygame_gui.elements.UIPanel(
            relative_rect=r(464, 486, 786, 166),
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(status_panel, self.ui_manager)
        self._ui_widgets.append(status_panel)

        any_ally_targeted = self.menu_mode == "TARGET" and any(
            self._is_party_member_targeted(c) for c in self.session.party.active_members
        )
        for idx, char in enumerate(self.session.party.active_members):
            row = idx // 2
            col = idx % 2
            cell_x = 32 + col * 366
            cell_y = 14 + row * 70
            is_active = active_char is not None and active_char.id == char.id
            is_card_highlighted = self._is_party_member_targeted(char) if any_ally_targeted else is_active

            card = pygame_gui.elements.UIPanel(
                relative_rect=r(cell_x, cell_y, 354, 64),
                manager=mgr,
                container=status_panel,
                object_id=ObjectID(class_id="@rpg_card_selected" if is_card_highlighted else "@rpg_card"),
            )

            name_suffix = "" if char.is_alive else " [Fallen]"
            pygame_gui.elements.UILabel(
                relative_rect=r(12, 6, 184, 26),
                text=f"{char.name} (Lv.{char.level}){name_suffix}",
                manager=mgr,
                container=card,
                object_id=ObjectID(class_id="@sub_header_label" if char.is_alive else "@muted_label"),
            )
            if char.statuses:
                icon_rect_sz = r(0, 0, 20, 20).width
                for st_idx, st in enumerate(char.statuses[:6]):
                    icon_surf = get_status_icon(st.status, size=icon_rect_sz)
                    if icon_surf is not None:
                        pygame_gui.elements.UIImage(
                            relative_rect=r(322 - st_idx * 24, 9, 20, 20),
                            image_surface=icon_surf,
                            manager=mgr,
                            container=card,
                        )
            StatBar(
                relative_rect=r(12, 35, 160, 22),
                manager=mgr,
                prefix="HP",
                current_value=char.current_hp,
                max_value=char.base_stats.max_hp,
                container=card,
                object_id=ObjectID(object_id="#hp_bar"),
            )
            StatBar(
                relative_rect=r(182, 35, 160, 22),
                manager=mgr,
                prefix="MP",
                current_value=char.current_mp,
                max_value=char.base_stats.max_mp,
                container=card,
                object_id=ObjectID(object_id="#mp_bar"),
            )

        # 4. Bottom Navigation Bar
        bottom_bar = pygame_gui.elements.UIPanel(
            relative_rect=r(30, 662, 1220, 44),
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel"),
        )
        pygame_gui.elements.UILabel(
            relative_rect=r(18, 6, 1184, 30),
            text="[WASD / Arrows] Move / Select    [ENTER / Space] Confirm    [ESC] Back / Cancel",
            manager=mgr,
            container=bottom_bar,
            object_id=ObjectID(class_id="@footer_label"),
        )
        self._ui_widgets.append(bottom_bar)

        # 5. Victory / Defeat Modal Overlays
        if self.combat.phase in (CombatPhase.VICTORY, CombatPhase.ESCAPED):
            modal = pygame_gui.elements.UIPanel(
                relative_rect=r(340, 170, 600, 320),
                starting_height=100,
                manager=mgr,
                object_id=ObjectID(class_id="@rpg_panel_gold"),
            )
            attach_ornate_corners(modal, self.ui_manager, starting_height=5)
            title = "VICTORY!" if self.combat.phase == CombatPhase.VICTORY else "ESCAPED!"
            pygame_gui.elements.UILabel(
                relative_rect=r(56, 22, 488, 48),
                text=title,
                manager=mgr,
                container=modal,
                object_id=ObjectID(class_id="@victory_header"),
            )
            rewards = self.combat.victory_rewards
            if rewards:
                pygame_gui.elements.UILabel(
                    relative_rect=r(40, 84, 520, 32),
                    text=f"Experience: +{rewards.get('total_exp', 0)} EXP ({rewards.get('exp_per_member', 0)} each)",
                    manager=mgr,
                    container=modal,
                    object_id=ObjectID(class_id="@centered_label"),
                )
                pygame_gui.elements.UILabel(
                    relative_rect=r(40, 124, 520, 32),
                    text=f"Gold Earned: +{rewards.get('total_gold', 0)} G",
                    manager=mgr,
                    container=modal,
                    object_id=ObjectID(class_id="@centered_sub_header_label"),
                )
                drops = rewards.get("dropped_items", [])
                drop_str = ", ".join(d.replace("_", " ").title() for d in drops) if drops else "None"
                pygame_gui.elements.UILabel(
                    relative_rect=r(40, 164, 520, 32),
                    text=f"Loot: {drop_str}",
                    manager=mgr,
                    container=modal,
                    object_id=ObjectID(class_id="@centered_muted_label"),
                )
            pygame_gui.elements.UILabel(
                relative_rect=r(56, 252, 488, 36),
                text="Press [ENTER] to return to world",
                manager=mgr,
                container=modal,
                object_id=ObjectID(class_id="@centered_sub_header_label"),
            )
            self._ui_widgets.append(modal)

        elif self.combat.phase == CombatPhase.DEFEAT:
            modal = pygame_gui.elements.UIPanel(
                relative_rect=r(340, 210, 600, 240),
                starting_height=100,
                manager=mgr,
                object_id=ObjectID(class_id="@rpg_panel_gold"),
            )
            attach_ornate_corners(modal, self.ui_manager, starting_height=5)
            pygame_gui.elements.UILabel(
                relative_rect=r(56, 24, 488, 48),
                text="DEFEAT",
                manager=mgr,
                container=modal,
                object_id=ObjectID(class_id="@victory_header"),
            )
            pygame_gui.elements.UILabel(
                relative_rect=r(40, 92, 520, 36),
                text="The party has succumbed to the corruption...",
                manager=mgr,
                container=modal,
                object_id=ObjectID(class_id="@centered_muted_label"),
            )
            pygame_gui.elements.UILabel(
                relative_rect=r(56, 174, 488, 36),
                text="Press [ENTER] to return to Title",
                manager=mgr,
                container=modal,
                object_id=ObjectID(class_id="@centered_sub_header_label"),
            )
            self._ui_widgets.append(modal)
