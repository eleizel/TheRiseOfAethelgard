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
from src.frontends.pygame_ce.skill_vfx import SkillVFXConfig, get_skill_vfx_config
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
        self.execution_delay = 0.15  # Brief pause between queued combat actions
        self.floating_texts: list[dict] = []
        self.active_vfx_instances: list[dict[str, Any]] = []
        self._active_action_anim: dict[str, Any] | None = None
        self._pending_prev_log: str = ""

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

    @property
    def _effective_ui_phase(self) -> CombatPhase | None:
        """Keep execution UI visible until the final action presentation finishes."""
        if not self.combat:
            return None
        if self._active_action_anim is not None and self.combat.phase in (
            CombatPhase.VICTORY,
            CombatPhase.DEFEAT,
            CombatPhase.ESCAPED,
        ):
            return CombatPhase.ACTION_EXECUTION
        return self.combat.phase

    def on_enter(self) -> None:
        self.menu_mode = "MAIN"
        self.main_index = 0
        self.skill_index = 0
        self.target_index = 0
        self.floating_texts.clear()
        self.active_vfx_instances.clear()
        self._active_action_anim = None
        self._pending_prev_log = ""
        self.execution_timer = 0.0

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

        # Battle End confirmation (wait until final action presentation finishes)
        ui_phase = self._effective_ui_phase
        if ui_phase in (CombatPhase.VICTORY, CombatPhase.ESCAPED):
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if (
                    ui_phase == CombatPhase.VICTORY
                    and any(e.sprite_id == "mandragora_matron" for e in self.combat.enemies)
                    and not self.session.has_character("lyra")
                ):
                    self.session.pending_dialogue_id = "lyra_rescue_dialogue"
                self.session.transition_to(GameMode.EXPLORATION)
            return

        if ui_phase == CombatPhase.DEFEAT:
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

        # Update active skill VFX instances in world-space reference coordinates.
        for inst in list(self.active_vfx_instances):
            inst["elapsed"] = float(inst["elapsed"]) + max(0.0, dt)
            if float(inst["elapsed"]) >= float(inst["start_time"]) + float(inst["duration"]):
                self.active_vfx_instances.remove(inst)

        # Progress active action banner + animation timing
        if self._active_action_anim is not None:
            self._update_action_presentation(dt)
        elif self.combat.phase == CombatPhase.ACTION_EXECUTION:
            self.execution_timer += dt
            if self.execution_timer >= self.execution_delay:
                self.execution_timer = 0.0
                prev_log = self.combat.combat_log[-1] if self.combat.combat_log else "Round Begin"
                res = self.combat.step_next_action()
                if res:
                    self._pending_prev_log = prev_log
                    self._start_action_presentation(res)

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
        self._draw_active_vfx(surface)
        self._draw_action_banner(surface)

        sw_s, sh_s = surface.get_size()
        sx = sw_s / 1280.0
        sy = sh_s / 720.0
        pop_font = get_font(max(14, int(26 * min(sx, sy))), bold=True)
        for ft in self.floating_texts:
            txt_surf = pop_font.render(ft["text"], True, ft["color"])
            txt_surf.set_alpha(ft["alpha"])
            surface.blit(txt_surf, (int(ft["x"] * 2.0 * sx), int(ft["y"] * 2.0 * sy)))

    def _start_action_presentation(self, res: Any) -> None:
        """Initialize the fade-in action banner, 1.5s skill animation window, and delayed impact."""
        is_basic = res.ability_id == "basic_attack" or res.action_name in (
            "Attack",
            "Defend",
            "Flee",
            "Stunned",
        )
        vfx_cfg = get_skill_vfx_config(res.ability_id)
        if is_basic:
            fade_in = 0.14
            anim_duration = 0.75
            fade_out = 0.22
            impact_offset = 0.30
        else:
            fade_in = 0.20
            anim_duration = vfx_cfg.total_duration if vfx_cfg else 1.50
            fade_out = 0.30
            impact_offset = vfx_cfg.impact_time if vfx_cfg else 0.75

        self._active_action_anim = {
            "res": res,
            "label": res.action_name,
            "elapsed": 0.0,
            "fade_in": fade_in,
            "anim_duration": anim_duration,
            "fade_out": fade_out,
            "total_duration": fade_in + anim_duration,
            "impact_time": fade_in + impact_offset,
            "anim_started": False,
            "impact_triggered": False,
        }

    def _update_action_presentation(self, dt: float) -> None:
        """Advance the current action's fade-in, animation, impact, and synchronized fade-out."""
        state = self._active_action_anim
        if not state:
            return
        state["elapsed"] += dt
        elapsed = float(state["elapsed"])
        res = state["res"]

        if not state["anim_started"] and elapsed >= float(state["fade_in"]):
            state["anim_started"] = True
            self._trigger_attacker_animation(res)

        if not state["impact_triggered"] and elapsed >= float(state["impact_time"]):
            state["impact_triggered"] = True
            self._trigger_action_impact(res)

        if elapsed >= float(state["total_duration"]):
            if not state["anim_started"]:
                self._trigger_attacker_animation(res)
            if not state["impact_triggered"]:
                self._trigger_action_impact(res)
            self._active_action_anim = None

    def _trigger_attacker_animation(self, res: Any) -> None:
        """Start the caster/attacker sprite animation and any registered skill VFX phases."""
        if not self.combat:
            return
        vfx_cfg = get_skill_vfx_config(res.ability_id)
        attacker_char = next(
            (c for c in self.session.party.active_members if c.name == res.source_name),
            None,
        )
        if attacker_char and attacker_char.id in self.party_anim_states:
            actor_state = self.party_anim_states[attacker_char.id]
            caster_mode = vfx_cfg.caster_anim if vfx_cfg else "lunge"
            is_skill = res.ability_id not in (None, "basic_attack")
            has_cast_pose = (
                is_skill
                and self.sprite_manager.get_character_action_frame_count(attacker_char.id, "cast") > 0
            )
            if caster_mode == "spell" or (caster_mode == "lunge" and has_cast_pose):
                pose_id = res.ability_id or "cast"
                pose_count = self.sprite_manager.get_character_action_frame_count(
                    attacker_char.id, pose_id
                )
                if pose_count <= 0:
                    pose_id = "cast"
                    pose_count = max(
                        1, self.sprite_manager.get_character_action_frame_count(attacker_char.id, "cast")
                    )
                spell_dur = vfx_cfg.spell_duration if vfx_cfg else 0.80
                actor_state.trigger_spell(duration=spell_dur, frame_count=pose_count, action_id=pose_id)
            elif caster_mode == "lunge":
                actor_state.trigger_attack(distance=34.0, action_id=res.ability_id or "attack")

            if vfx_cfg is not None:
                self._spawn_skill_vfx(res, vfx_cfg, is_enemy_caster=False)
            return

        attacker_enemy = next(
            (e for e in self.combat.enemies if e.name == res.source_name),
            None,
        )
        if attacker_enemy:
            ekey = self._enemy_anim_key(attacker_enemy)
            if ekey in self.enemy_anim_states:
                caster_mode = vfx_cfg.caster_anim if vfx_cfg else "lunge"
                if caster_mode != "none":
                    self.enemy_anim_states[ekey].trigger_attack(distance=34.0)
            if vfx_cfg is not None:
                self._spawn_skill_vfx(res, vfx_cfg, is_enemy_caster=True)

    def _trigger_action_impact(self, res: Any) -> None:
        """Apply hurt recoil, hit-flash, and floating damage/healing numbers at impact."""
        if not self.combat:
            return
        if res.damage_dealt:
            for idx, val in enumerate(res.damage_dealt):
                tname = (
                    res.target_names[idx]
                    if idx < len(res.target_names)
                    else (res.target_names[0] if res.target_names else "")
                )
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

                target_char = next(
                    (c for c in self.session.party.active_members if c.name == tname),
                    None,
                )
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
                tname = (
                    res.target_names[idx]
                    if idx < len(res.target_names)
                    else (res.target_names[0] if res.target_names else "")
                )
                pop_x = 460.0
                pop_y = 120.0
                target_char = next(
                    (c for c in self.session.party.active_members if c.name == tname),
                    None,
                )
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

    def _get_action_banner_alpha(self) -> int:
        """Compute current alpha [0, 255] for the floating action-name banner."""
        state = self._active_action_anim
        if not state:
            return 0
        elapsed = float(state["elapsed"])
        fade_in = float(state["fade_in"])
        fade_out = float(state["fade_out"])
        total = float(state["total_duration"])

        if elapsed < fade_in:
            return max(0, min(255, int(255.0 * (elapsed / max(0.01, fade_in)))))
        if elapsed >= total - fade_out:
            remaining = max(0.0, total - elapsed)
            return max(0, min(255, int(255.0 * (remaining / max(0.01, fade_out)))))
        return 255

    def _draw_action_banner(self, surface: pygame.Surface) -> None:
        """Render the centered skill/action box 20px below the top announcement banner."""
        alpha = self._get_action_banner_alpha()
        if alpha <= 0 or not self._active_action_anim:
            return

        sw_s, sh_s = surface.get_size()
        sx = sw_s / 1280.0
        sy = sh_s / 720.0

        label = str(self._active_action_anim["label"])
        font = get_font(max(14, int(20 * min(sx, sy))), bold=True)
        txt_surf = font.render(label, True, (250, 242, 220))

        box_w = max(int(320 * sx), txt_surf.get_width() + int(64 * sx))
        box_w = min(box_w, int(640 * sx))
        box_h = max(28, int(38 * sy))
        box_x = (sw_s - box_w) // 2
        # Top banner is y=14, h=48 (bottom y=62); 20px below => y=82
        box_y = int(82 * sy)

        panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (18, 22, 34, 228), (0, 0, box_w, box_h), border_radius=max(4, int(6 * min(sx, sy))))
        pygame.draw.rect(
            panel,
            (212, 178, 92, 245),
            (0, 0, box_w, box_h),
            width=max(1, int(2 * min(sx, sy))),
            border_radius=max(4, int(6 * min(sx, sy))),
        )

        txt_x = (box_w - txt_surf.get_width()) // 2
        txt_y = (box_h - txt_surf.get_height()) // 2
        panel.blit(txt_surf, (txt_x, txt_y))
        panel.set_alpha(alpha)
        surface.blit(panel, (box_x, box_y))

    def _get_party_anchor(self, char: Character) -> tuple[float, float]:
        party_index = next(
            (i for i, member in enumerate(self.session.party.active_members) if member.id == char.id),
            0,
        )
        party_row, party_col = divmod(party_index, 2)
        return 915.0 + party_col * 175.0, 340.0 + party_row * 124.0

    def _get_enemy_anchor(self, enemy: Enemy) -> tuple[float, float]:
        enemy_count = len(self.combat.enemies) if self.combat else 1
        enemy_index = self.combat.enemies.index(enemy) if (self.combat and enemy in self.combat.enemies) else 0
        is_elite = enemy.tier in (EnemyTier.ELITE, EnemyTier.BOSS)
        if enemy_count == 1:
            return 280.0, 472.0 if is_elite else 432.0
        if enemy_count == 2:
            return (200.0 if enemy_index == 0 else 370.0), (362.0 if enemy_index == 0 else 464.0)
        return 170.0 + (enemy_index % 2) * 195.0, min(472.0, 336.0 + enemy_index * 64.0)

    def _resolve_vfx_targets(self, res: Any) -> list[tuple[float, float]]:
        """Resolve world-space anchor coordinates for all targets of an action."""
        if not self.combat:
            return []
        anchors: list[tuple[float, float]] = []
        target_ids = res.target_ids or []
        for tid in target_ids:
            enemy = next((e for e in self.combat.enemies if e.id == tid), None)
            if enemy is not None:
                anchors.append(self._get_enemy_anchor(enemy))
                continue
            char = next((c for c in self.session.party.active_members if c.id == tid), None)
            if char is not None:
                anchors.append(self._get_party_anchor(char))
        if anchors:
            return anchors

        for tname in res.target_names or []:
            enemy = next((e for e in self.combat.enemies if e.name == tname), None)
            if enemy is not None:
                anchors.append(self._get_enemy_anchor(enemy))
                continue
            char = next((c for c in self.session.party.active_members if c.name == tname), None)
            if char is not None:
                anchors.append(self._get_party_anchor(char))
        return anchors

    def _spawn_skill_vfx(
        self, res: Any, vfx_cfg: SkillVFXConfig, is_enemy_caster: bool = False
    ) -> None:
        """Instantiate all declarative VFXPhase entries for a skill action."""
        if not self.combat:
            return
        if is_enemy_caster:
            caster_enemy = next((e for e in self.combat.enemies if e.name == res.source_name), None)
            caster_anchor = self._get_enemy_anchor(caster_enemy) if caster_enemy else (280.0, 432.0)
        else:
            caster_char = next(
                (c for c in self.session.party.active_members if c.name == res.source_name),
                None,
            )
            caster_anchor = self._get_party_anchor(caster_char) if caster_char else (915.0, 340.0)

        target_anchors = self._resolve_vfx_targets(res)
        if not target_anchors:
            target_anchors = [caster_anchor]

        for phase in vfx_cfg.phases:
            frame_count = phase.frame_count or self.sprite_manager.get_effect_frame_count(
                vfx_cfg.effect_id, phase.prefix
            )
            if frame_count <= 0:
                continue

            flip_x = is_enemy_caster and phase.flip_for_enemy
            dx = -phase.offset[0] if flip_x else phase.offset[0]
            dy = phase.offset[1]

            if phase.placement == "caster":
                self.active_vfx_instances.append(
                    {
                        "effect_id": vfx_cfg.effect_id,
                        "prefix": phase.prefix,
                        "frame_count": frame_count,
                        "elapsed": 0.0,
                        "start_time": phase.start_time,
                        "duration": max(0.01, phase.duration),
                        "start_x": caster_anchor[0] + dx,
                        "start_y": caster_anchor[1] + dy,
                        "end_x": caster_anchor[0] + dx,
                        "end_y": caster_anchor[1] + dy,
                        "arc_height": 0.0,
                        "scale": phase.scale,
                        "flip_x": flip_x,
                    }
                )
            elif phase.placement == "projectile_to_target":
                sx_pt = caster_anchor[0] + dx
                sy_pt = caster_anchor[1] + dy
                for tx, ty in target_anchors:
                    self.active_vfx_instances.append(
                        {
                            "effect_id": vfx_cfg.effect_id,
                            "prefix": phase.prefix,
                            "frame_count": frame_count,
                            "elapsed": 0.0,
                            "start_time": phase.start_time,
                            "duration": max(0.01, phase.duration),
                            "start_x": sx_pt,
                            "start_y": sy_pt,
                            "end_x": tx + (-24.0 if flip_x else 24.0),
                            "end_y": ty - 54.0,
                            "arc_height": phase.arc_height,
                            "scale": phase.scale,
                            "flip_x": flip_x,
                        }
                    )
            elif phase.placement == "target_each":
                for tx, ty in target_anchors:
                    self.active_vfx_instances.append(
                        {
                            "effect_id": vfx_cfg.effect_id,
                            "prefix": phase.prefix,
                            "frame_count": frame_count,
                            "elapsed": 0.0,
                            "start_time": phase.start_time,
                            "duration": max(0.01, phase.duration),
                            "start_x": tx + dx,
                            "start_y": ty + dy,
                            "end_x": tx + dx,
                            "end_y": ty + dy,
                            "arc_height": 0.0,
                            "scale": phase.scale,
                            "flip_x": flip_x,
                        }
                    )
            elif phase.placement == "target_group_center":
                avg_x = sum(pt[0] for pt in target_anchors) / len(target_anchors)
                avg_y = sum(pt[1] for pt in target_anchors) / len(target_anchors)
                self.active_vfx_instances.append(
                    {
                        "effect_id": vfx_cfg.effect_id,
                        "prefix": phase.prefix,
                        "frame_count": frame_count,
                        "elapsed": 0.0,
                        "start_time": phase.start_time,
                        "duration": max(0.01, phase.duration),
                        "start_x": avg_x + dx,
                        "start_y": avg_y + dy,
                        "end_x": avg_x + dx,
                        "end_y": avg_y + dy,
                        "arc_height": 0.0,
                        "scale": phase.scale,
                        "flip_x": flip_x,
                    }
                )

    def _draw_active_vfx(self, surface: pygame.Surface) -> None:
        if not self.active_vfx_instances:
            return
        screen_w, screen_h = surface.get_size()
        sx = screen_w / 1280.0
        sy = screen_h / 720.0
        base_pixel_scale = 2.0 * min(sx, sy)

        for inst in self.active_vfx_instances:
            local_elapsed = float(inst["elapsed"]) - float(inst["start_time"])
            if local_elapsed < 0.0:
                continue
            duration = max(0.01, float(inst["duration"]))
            progress = min(1.0, max(0.0, local_elapsed / duration))
            x = float(inst["start_x"]) + (
                float(inst["end_x"]) - float(inst["start_x"])
            ) * progress
            y = float(inst["start_y"]) + (
                float(inst["end_y"]) - float(inst["start_y"])
            ) * progress - math.sin(progress * math.pi) * float(inst["arc_height"])

            frame_count = max(1, int(inst["frame_count"]))
            frame_index = min(frame_count - 1, int(progress * frame_count))
            frame = self.sprite_manager.get_projectile_frame(
                str(inst["effect_id"]), frame_index, prefix=str(inst["prefix"])
            )
            if frame is None:
                continue

            if inst["flip_x"]:
                frame = pygame.transform.flip(frame, True, False)

            fw, fh = frame.get_size()
            scale = base_pixel_scale * float(inst["scale"])
            dw = max(8, int(round(fw * scale)))
            dh = max(8, int(round(fh * scale)))
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
                name_txt = ui_font.render(f"({enemy.level}) {enemy.name}", True, name_col)
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
        if self._active_action_anim is not None and not self._active_action_anim["impact_triggered"]:
            last_log = self._pending_prev_log
        else:
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
            self._effective_ui_phase,
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
        if self._active_action_anim is not None and not self._active_action_anim["impact_triggered"]:
            last_log = self._pending_prev_log or "Round Begin"
        else:
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
        ui_phase = self._effective_ui_phase
        if ui_phase in (CombatPhase.VICTORY, CombatPhase.ESCAPED):
            modal = pygame_gui.elements.UIPanel(
                relative_rect=r(340, 170, 600, 320),
                starting_height=100,
                manager=mgr,
                object_id=ObjectID(class_id="@rpg_panel_gold"),
            )
            attach_ornate_corners(modal, self.ui_manager, starting_height=5)
            title = "VICTORY!" if ui_phase == CombatPhase.VICTORY else "ESCAPED!"
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

        elif ui_phase == CombatPhase.DEFEAT:
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
