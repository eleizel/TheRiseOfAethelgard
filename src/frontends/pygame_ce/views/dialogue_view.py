"""Interactive dialogue presentation view using pygame-gui HD overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pygame_gui
from pygame_gui.core import ObjectID
from pygame_gui.elements import UIButton, UIImage, UILabel, UIPanel, UITextBox

from src.core.events import AudioCue
from src.core.fsm import GameMode
from src.data.dialogues import get_dialogue_tree
from src.data.enemies import create_enemy
from src.frontends.pygame_ce.combat_animator import EnemySpriteManager
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine
from src.frontends.pygame_ce.ui_manager import (
    GameUIManager,
    attach_ornate_corners,
    set_button_selected,
)
from src.systems.combat.round_combat import RoundCombat
from src.systems.dialogue.dialogue_models import DialogueNode, DialogueTree

if TYPE_CHECKING:
    from src.core.session import GameSession


class DialogueView:
    """Dialogue and narrative choice interface rendered in the HD-2D pygame-gui overlay."""

    _SCRIPTED_COMBAT_GUARDS: dict[str, tuple[str, str]] = {
        "START_BOSS_COMBAT": ("shadow_in_briarwood", "kill_corrupted_treant"),
        "START_SPECIAL_COMBAT": ("briarwood_monolith", "kill_mandragora_matron"),
    }
    _DEFEATED_ENCOUNTER_DIALOGUES: dict[str, tuple[str, str, str]] = {
        "treant_boss": (
            "shadow_in_briarwood",
            "kill_corrupted_treant",
            "The corrupted treant has already been felled. Only quiet, blackened roots remain.",
        ),
        "special_encounter": (
            "briarwood_monolith",
            "kill_mandragora_matron",
            "The ancient monolith stands silent now, its foul energy completely dissipated.",
        ),
    }

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

        self.sprite_manager = EnemySpriteManager()

        self.current_tree: DialogueTree | None = None
        self.current_node: DialogueNode | None = None
        self.choice_index = 0
        self.displayed_chars = 0
        self.typewriter_speed = 45.0
        self.time_sec = 0.0

        # pygame-gui widgets
        self._box_panel: UIPanel | None = None
        self._portrait_img: UIImage | None = None
        self._speaker_label: UILabel | None = None
        self._text_box: UITextBox | None = None
        self._hint_label: UILabel | None = None
        self._choices_panel: UIPanel | None = None
        self._choice_buttons: list[UIButton] = []
        self._choices_shown = False

    def start_dialogue(self, tree_id: str) -> None:
        """Begin a dialogue sequence from tree_id."""
        if tree_id == "elder_tomas" and self.session.quest_manager.is_step_active(
            "shadow_in_briarwood", "report_to_tomas"
        ):
            tree_id = "elder_tomas_complete"
        defeated_info = self._DEFEATED_ENCOUNTER_DIALOGUES.get(tree_id)
        if defeated_info is not None:
            quest_id, step_id, defeated_text = defeated_info
            if self.session.quest_manager.is_step_completed(quest_id, step_id):
                self.current_tree = DialogueTree(
                    id=f"{tree_id}_defeated",
                    nodes={
                        "defeated_1": DialogueNode(
                            id="defeated_1",
                            speaker_name="Rowan",
                            speaker_id="rowan",
                            text=defeated_text,
                            next_node_id=None,
                        )
                    },
                    start_node_id="defeated_1",
                )
                self.current_node = self.current_tree.get_node("defeated_1")
                self.choice_index = 0
                self.displayed_chars = 0
                self.time_sec = 0.0
                self._choices_shown = False
                self._rebuild_node_ui()
                return
        try:
            self.current_tree = get_dialogue_tree(tree_id)
        except ValueError:
            self.current_tree = DialogueTree(
                id=tree_id,
                nodes={
                    "fallback_1": DialogueNode(
                        id="fallback_1",
                        speaker_name="Rowan",
                        speaker_id="rowan",
                        text="There is nothing of note here right now.",
                        next_node_id=None,
                    )
                },
                start_node_id="fallback_1",
            )
        self.current_node = self.current_tree.get_node(self.current_tree.start_node_id)
        self.session.quest_manager.on_dialogue_started(self.current_tree.id)
        self.choice_index = 0
        self.displayed_chars = 0
        self.time_sec = 0.0
        self._choices_shown = False
        self._rebuild_node_ui()

    def on_enter(self) -> None:
        self.choice_index = 0
        self.displayed_chars = 0
        if self.current_node is not None:
            self._rebuild_node_ui()

    def on_exit(self) -> None:
        for attr in ("_box_panel", "_choices_panel"):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.kill()
                setattr(self, attr, None)
        self._portrait_img = None
        self._speaker_label = None
        self._text_box = None
        self._hint_label = None
        self._choice_buttons.clear()
        self._choices_shown = False

    def on_resize(self, width: int, height: int) -> None:
        if self.current_node is not None:
            self._rebuild_node_ui()

    def _rebuild_node_ui(self) -> None:
        self.on_exit()
        if not self.current_node:
            return

        mgr = self.ui_manager.manager
        r = self.ui_manager.rect

        self._box_panel = UIPanel(
            relative_rect=r(40, 492, 1200, 200),
            starting_height=2,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(self._box_panel, self.ui_manager)

        # Portrait on left
        p_surf = self._build_portrait_surface(self.current_node.speaker_id, size=144)
        self._portrait_img = UIImage(
            relative_rect=r(24, 28, 144, 144),
            image_surface=p_surf,
            manager=mgr,
            container=self._box_panel,
        )

        # Speaker badge
        self._speaker_label = UILabel(
            relative_rect=r(190, 20, 700, 34),
            text=self.current_node.speaker_name,
            manager=mgr,
            container=self._box_panel,
            object_id=ObjectID(class_id="@header_label"),
        )

        # Rich text box with native typewriter effect
        self._text_box = UITextBox(
            html_text=self.current_node.text,
            relative_rect=r(186, 56, 980, 108),
            manager=mgr,
            container=self._box_panel,
            object_id=ObjectID(class_id="@dialogue_textbox"),
        )
        self._text_box.set_active_effect(
            pygame_gui.TEXT_EFFECT_TYPING_APPEAR,
            params={"time_per_letter": 1.0 / self.typewriter_speed},
        )

        hint = "[SPACE / ENTER] Continue" if not self.current_node.choices else "[ARROWS] Choose   [ENTER] Confirm"
        self._hint_label = UILabel(
            relative_rect=r(750, 162, 390, 28),
            text=hint,
            manager=mgr,
            container=self._box_panel,
            object_id=ObjectID(class_id="@footer_label"),
        )

    def _build_choices_ui(self) -> None:
        if self._choices_panel is not None:
            self._choices_panel.kill()
            self._choices_panel = None
        self._choice_buttons.clear()

        if not self.current_node or not self.current_node.choices:
            return

        mgr = self.ui_manager.manager
        r = self.ui_manager.rect
        choices = self.current_node.choices
        row_h = 46
        panel_h = len(choices) * row_h + 24
        panel_w = 560
        panel_x = 230
        panel_y = 482 - panel_h

        self._choices_panel = UIPanel(
            relative_rect=r(panel_x, panel_y, panel_w, panel_h),
            starting_height=3,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(self._choices_panel, self.ui_manager)

        for idx, choice in enumerate(choices):
            is_sel = idx == self.choice_index
            btn = UIButton(
                relative_rect=r(38, 12 + idx * row_h, panel_w - 76, 40),
                text=f"> {choice.text}" if is_sel else f"  {choice.text}",
                manager=mgr,
                container=self._choices_panel,
                object_id=ObjectID(
                    class_id="@rpg_button_selected" if is_sel else "@rpg_button"
                ),
            )
            self._choice_buttons.append(btn)
        self._choices_shown = True

    def _refresh_choice_selection(self) -> None:
        if not self.current_node:
            return
        for idx, btn in enumerate(self._choice_buttons):
            is_sel = idx == self.choice_index
            text = self.current_node.choices[idx].text
            btn.set_text(f"> {text}" if is_sel else f"  {text}")
            set_button_selected(btn, is_sel)

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.current_node or event.type != pygame.KEYDOWN:
            return

        has_choices = len(self.current_node.choices) > 0
        full_text_shown = self.displayed_chars >= len(self.current_node.text)

        if has_choices and full_text_shown:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.choice_index = (self.choice_index - 1) % len(self.current_node.choices)
                self._refresh_choice_selection()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.choice_index = (self.choice_index + 1) % len(self.current_node.choices)
                self._refresh_choice_selection()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                choice = self.current_node.choices[self.choice_index]
                if self.current_tree:
                    self.session.quest_manager.on_dialogue_choice(
                        self.current_tree.id, self.current_node.id, self.choice_index
                    )
                self._advance_to_node(choice.target_node_id)
        else:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if not full_text_shown:
                    self.displayed_chars = len(self.current_node.text)
                    if self._text_box is not None:
                        self._text_box.set_active_effect(None)
                    if has_choices and not self._choices_shown:
                        self._build_choices_ui()
                else:
                    self._advance_node()

    def _advance_node(self) -> None:
        if not self.current_node or not self.current_tree:
            self._close_dialogue()
            return

        if self.current_node.action_trigger:
            self._execute_action_trigger(self.current_node.action_trigger)

        next_id = self.current_node.next_node_id
        if next_id:
            self._advance_to_node(next_id)
        else:
            self._close_dialogue()

    def _advance_to_node(self, node_id: str) -> None:
        if not self.current_tree:
            return
        next_node = self.current_tree.get_node(node_id)
        if next_node:
            self.current_node = next_node
            self.displayed_chars = 0
            self.choice_index = 0
            self._choices_shown = False
            self.session.event_bus.emit_audio(AudioCue.CLICK)
            self._rebuild_node_ui()
        else:
            self._close_dialogue()

    def _execute_action_trigger(self, trigger: str) -> None:
        guard = self._SCRIPTED_COMBAT_GUARDS.get(trigger)
        if guard is not None:
            quest_id, step_id = guard
            if self.session.quest_manager.is_step_completed(quest_id, step_id):
                return
        if trigger == "FLAG_MET_ELDER":
            self.session.party.quest_flags["met_elder"] = True
            self.session.quest_manager.on_flag_set("met_elder")
        elif trigger == "START_BOSS_COMBAT":
            treant = create_enemy("corrupted_treant", "treant_boss")
            self.session.combat = RoundCombat(
                party=self.session.party,
                enemies=[treant],
                event_bus=self.session.event_bus,
                seed=self.session.rng.randint(1, 100000),
            )
            self.session.transition_to(GameMode.COMBAT)
        elif trigger == "START_SPECIAL_COMBAT":
            abomination = create_enemy("mandragora_matron", "mandragora_matron")
            hound1 = create_enemy("bramble_hound", "bramble_hound_1")
            hound2 = create_enemy("bramble_hound", "bramble_hound_2")
            self.session.combat = RoundCombat(
                party=self.session.party,
                enemies=[hound1, abomination, hound2],
                event_bus=self.session.event_bus,
                seed=self.session.rng.randint(1, 100000),
            )
            self.session.transition_to(GameMode.COMBAT)
        elif trigger == "COMPLETE_PROLOGUE":
            self.session.party.quest_flags["prologue_complete"] = True
            self.session.party.gold += 150
            for char in self.session.party.active_members:
                char.skill_points += 2
        elif trigger == "OPEN_PARTY_COMPOSITION":
            self.session.transition_to(GameMode.PARTY)

    def _close_dialogue(self) -> None:
        finished_tree_id = self.current_tree.id if self.current_tree else None
        self.current_tree = None
        self.current_node = None
        self.on_exit()
        if finished_tree_id:
            quest_tree_id = "elder_tomas" if finished_tree_id == "elder_tomas_complete" else finished_tree_id
            self.session.quest_manager.on_dialogue_finished(quest_tree_id)
        if self.session.current_mode == GameMode.DIALOGUE:
            self.session.transition_to(GameMode.EXPLORATION)

    def update(self, dt: float) -> None:
        self.time_sec += dt
        if self.current_node and self.displayed_chars < len(self.current_node.text):
            self.displayed_chars += int(self.typewriter_speed * dt) + 1
            self.displayed_chars = min(self.displayed_chars, len(self.current_node.text))
            if (
                self.displayed_chars >= len(self.current_node.text)
                and self.current_node.choices
                and not self._choices_shown
            ):
                self._build_choices_ui()

    def draw(self, surface: pygame.Surface) -> None:
        """World-canvas draw is a no-op; DialogueView renders via the HD pygame-gui overlay."""
        return

    def _build_portrait_surface(self, speaker_id: str, size: int = 144) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        prt = self.sprite_manager.get_portrait(speaker_id, size=size)
        if prt is not None:
            surf.blit(prt, (0, 0))
            return surf

        # Crisp fallback portrait badge
        cx, cy = size // 2, size // 2
        pygame.draw.circle(surf, (45, 55, 80), (cx, cy), size // 2 - 4)
        pygame.draw.circle(surf, (212, 175, 55), (cx, cy), size // 2 - 4, 2)
        if speaker_id == "rowan":
            pygame.draw.circle(surf, (170, 175, 185), (cx, cy - 8), size // 4)
        elif speaker_id == "lyra":
            pygame.draw.circle(surf, (50, 130, 70), (cx, cy - 8), size // 4)
        else:
            pygame.draw.circle(surf, (200, 185, 165), (cx, cy - 8), size // 4)
        return surf
