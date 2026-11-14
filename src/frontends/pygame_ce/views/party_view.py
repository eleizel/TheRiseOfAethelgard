"""Dedicated Party Composition view for Inns and Rowan's cottage."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

import pygame
from pygame_gui.core import ObjectID, UIContainer
from pygame_gui.elements import UIButton, UIImage, UILabel, UIPanel, UITextBox

from src.core.events import AudioCue
from src.core.fsm import GameMode
from src.frontends.pygame_ce.combat_animator import EnemySpriteManager
from src.frontends.pygame_ce.ui_manager import GameUIManager, StatBar, attach_ornate_corners

if TYPE_CHECKING:
    from src.core.session import GameSession
    from src.entities.character import Character


class PartyView:
    """Two-panel Party Composition screen with keyboard Action Sub-Menu."""

    def __init__(
        self,
        session: GameSession,
        music_engine: Any = None,
        view_width: int = 640,
        view_height: int = 360,
        ui_manager: GameUIManager | None = None,
    ) -> None:
        self.session = session
        self.music_engine = music_engine
        self.view_width = view_width
        self.view_height = view_height
        self.ui_manager = ui_manager
        self.sprite_manager = EnemySpriteManager()

        self.cursor_idx = 0
        self.sub_menu_open = False
        self.sub_menu_options: list[tuple[str, str]] = []
        self.sub_menu_index = 0

        self.swap_mode: str | None = None
        self.swap_source_idx = -1
        self.swap_target_idx = 0

        self.status_message = "Manage your Active Squad (Slots 1-4) and Reserve Companions."
        self._root_panel: UIPanel | None = None
        self._left_panel: UIPanel | None = None
        self._right_panel: UIPanel | None = None
        self._status_label: UILabel | None = None
        self._list_container: UIContainer | None = None
        self._right_portrait: UIImage | None = None
        self._right_info_box: UITextBox | None = None
        self._right_gear_box: UITextBox | None = None
        self._sub_menu_panel: UIPanel | None = None
        self._sub_menu_buttons: list[UIButton] = []

        self._active_cards: list[tuple[UIPanel, UILabel, str]] = []
        self._reserve_cards: list[tuple[int, UIPanel, UILabel, str]] = []
        self._last_list_signature: tuple | None = None
        self._last_detail_char_id: str | None = None
        self._dirty_chrome = True
        self._dirty_list = True
        self._dirty_details = True
        self._dirty_submenu = True

    def on_enter(self) -> None:
        self.cursor_idx = 0
        self.sub_menu_open = False
        self.sub_menu_options = []
        self.sub_menu_index = 0
        self.swap_mode = None
        self.swap_source_idx = -1
        self.swap_target_idx = 0
        self.status_message = "Select a companion and press [ENTER] for options."
        self._dirty_chrome = True
        self._dirty_list = True
        self._dirty_details = True
        self._dirty_submenu = True

    def on_exit(self) -> None:
        self._teardown_ui()

    def _teardown_ui(self) -> None:
        if self._root_panel is not None:
            self._root_panel.kill()
            self._root_panel = None
        self._left_panel = None
        self._right_panel = None
        self._status_label = None
        self._list_container = None
        self._right_portrait = None
        self._right_info_box = None
        self._right_gear_box = None
        self._sub_menu_panel = None
        self._sub_menu_buttons.clear()
        self._active_cards.clear()
        self._reserve_cards.clear()
        self._last_list_signature = None
        self._last_detail_char_id = None

    def _selectable_rows(self) -> list[tuple[str, int]]:
        rows: list[tuple[str, int]] = [
            ("active", i) for i in range(len(self.session.party.active_members))
        ]
        rows.extend(
            ("reserve", j) for j in range(len(self.session.party.reserve_members))
        )
        return rows

    def _get_selected_character(self) -> tuple[str, int, Character | None]:
        rows = self._selectable_rows()
        if not rows:
            return ("active", 0, None)
        self.cursor_idx = max(0, min(self.cursor_idx, len(rows) - 1))
        kind, idx = rows[self.cursor_idx]
        if kind == "active":
            return (kind, idx, self.session.party.active_members[idx])
        return (kind, idx, self.session.party.reserve_members[idx])

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if self.swap_mode is not None:
            self._handle_swap_target_input(event)
            return

        if self.sub_menu_open:
            self._handle_sub_menu_input(event)
            return

        rows = self._selectable_rows()
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.session.event_bus.emit_audio(AudioCue.CANCEL)
            self.session.transition_to(GameMode.EXPLORATION)
            return

        if not rows:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.cursor_idx = (self.cursor_idx - 1) % len(rows)
            self.session.event_bus.emit_audio(AudioCue.CLICK)
            self._dirty_list = True
            self._dirty_details = True
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.cursor_idx = (self.cursor_idx + 1) % len(rows)
            self.session.event_bus.emit_audio(AudioCue.CLICK)
            self._dirty_list = True
            self._dirty_details = True
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._open_sub_menu()

    def _open_sub_menu(self) -> None:
        kind, idx, char = self._get_selected_character()
        if char is None:
            return

        if kind == "active" and idx == 0:
            self.status_message = f"{char.name} is permanently locked to Active Slot 1."
            self.session.event_bus.emit_audio(AudioCue.CANCEL)
            self._refresh_status_label()
            return

        options: list[tuple[str, str]] = []
        party = self.session.party
        if kind == "active":
            if idx > 1:
                options.append(("move_up", "Move Up"))
            if idx < len(party.active_members) - 1:
                options.append(("move_down", "Move Down"))
            if party.reserve_members:
                options.append(("swap_reserve", "Swap with Reserve"))
            if len(party.active_members) > 1:
                options.append(("bench", "Bench to Reserve"))
        else:
            if len(party.active_members) < 4:
                options.append(("deploy", "Deploy to Active"))
            if len(party.active_members) > 1:
                options.append(("swap_active", "Swap with Active"))

        options.append(("cancel", "Cancel"))
        self.sub_menu_options = options
        self.sub_menu_index = 0
        self.sub_menu_open = True
        self.session.event_bus.emit_audio(AudioCue.CLICK)
        self._dirty_submenu = True

    def _handle_sub_menu_input(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.sub_menu_open = False
            self.session.event_bus.emit_audio(AudioCue.CANCEL)
            self._dirty_submenu = True
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.sub_menu_index = (self.sub_menu_index - 1) % len(self.sub_menu_options)
            self.session.event_bus.emit_audio(AudioCue.CLICK)
            self._update_submenu_selection()
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.sub_menu_index = (self.sub_menu_index + 1) % len(self.sub_menu_options)
            self.session.event_bus.emit_audio(AudioCue.CLICK)
            self._update_submenu_selection()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            action_id, _ = self.sub_menu_options[self.sub_menu_index]
            self._execute_sub_menu_action(action_id)

    def _execute_sub_menu_action(self, action_id: str) -> None:
        kind, idx, char = self._get_selected_character()
        party = self.session.party
        self.sub_menu_open = False
        self._dirty_submenu = True

        if action_id == "cancel" or char is None:
            self.session.event_bus.emit_audio(AudioCue.CANCEL)
            return

        if action_id == "move_up" and kind == "active":
            if party.reorder_active(idx, idx - 1):
                self.cursor_idx -= 1
                self.status_message = f"Moved {char.name} up to Slot {idx}."
                self.session.event_bus.emit_audio(AudioCue.SELECT)
        elif action_id == "move_down" and kind == "active":
            if party.reorder_active(idx, idx + 1):
                self.cursor_idx += 1
                self.status_message = f"Moved {char.name} down to Slot {idx + 2}."
                self.session.event_bus.emit_audio(AudioCue.SELECT)
        elif action_id == "bench" and kind == "active":
            if party.bench_active(idx):
                self.cursor_idx = max(0, len(party.active_members) - 1)
                self.status_message = f"{char.name} moved to Reserve Bench."
                self.session.event_bus.emit_audio(AudioCue.SELECT)
        elif action_id == "deploy" and kind == "reserve":
            if party.deploy_reserve(idx):
                self.cursor_idx = len(party.active_members) - 1
                self.status_message = f"{char.name} deployed to Active Slot {len(party.active_members)}!"
                self.session.event_bus.emit_audio(AudioCue.SELECT)
        elif action_id == "swap_reserve" and kind == "active":
            self.swap_mode = "active_to_reserve"
            self.swap_source_idx = idx
            self.swap_target_idx = 0
            self.status_message = f"Select Reserve companion to swap with {char.name}."
            self.session.event_bus.emit_audio(AudioCue.CLICK)
        elif action_id == "swap_active" and kind == "reserve":
            self.swap_mode = "reserve_to_active"
            self.swap_source_idx = idx
            self.swap_target_idx = 1
            self.status_message = f"Select Active companion (Slots 2-4) to swap with {char.name}."
            self.session.event_bus.emit_audio(AudioCue.CLICK)

        self._dirty_list = True
        self._dirty_details = True

    def _handle_swap_target_input(self, event: pygame.event.Event) -> None:
        party = self.session.party
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.swap_mode = None
            self.status_message = "Swap cancelled."
            self.session.event_bus.emit_audio(AudioCue.CANCEL)
            self._dirty_list = True
            self._dirty_details = True
            return

        if self.swap_mode == "active_to_reserve":
            count = len(party.reserve_members)
            if count == 0:
                self.swap_mode = None
                self._dirty_list = True
                return
            if event.key in (pygame.K_UP, pygame.K_w):
                self.swap_target_idx = (self.swap_target_idx - 1) % count
                self.session.event_bus.emit_audio(AudioCue.CLICK)
                self._dirty_list = True
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.swap_target_idx = (self.swap_target_idx + 1) % count
                self.session.event_bus.emit_audio(AudioCue.CLICK)
                self._dirty_list = True
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if party.swap_active_with_reserve(self.swap_source_idx, self.swap_target_idx):
                    new_char = party.active_members[self.swap_source_idx]
                    self.status_message = f"{new_char.name} joined Active Slot {self.swap_source_idx + 1}!"
                    self.session.event_bus.emit_audio(AudioCue.SELECT)
                self.swap_mode = None
                self._dirty_list = True
                self._dirty_details = True
        elif self.swap_mode == "reserve_to_active":
            max_idx = len(party.active_members) - 1
            if max_idx < 1:
                self.swap_mode = None
                self._dirty_list = True
                return
            if event.key in (pygame.K_UP, pygame.K_w):
                self.swap_target_idx = max_idx if self.swap_target_idx <= 1 else self.swap_target_idx - 1
                self.session.event_bus.emit_audio(AudioCue.CLICK)
                self._dirty_list = True
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.swap_target_idx = 1 if self.swap_target_idx >= max_idx else self.swap_target_idx + 1
                self.session.event_bus.emit_audio(AudioCue.CLICK)
                self._dirty_list = True
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if party.swap_active_with_reserve(self.swap_target_idx, self.swap_source_idx):
                    new_char = party.active_members[self.swap_target_idx]
                    self.status_message = f"{new_char.name} joined Active Slot {self.swap_target_idx + 1}!"
                    self.session.event_bus.emit_audio(AudioCue.SELECT)
                self.swap_mode = None
                self._dirty_list = True
                self._dirty_details = True

    def update(self, dt: float) -> None:
        if self.ui_manager is None:
            return
        if self._dirty_chrome:
            self._build_chrome()
            self._dirty_chrome = False
        if self._dirty_list:
            self._refresh_list()
            self._refresh_status_label()
            self._dirty_list = False
        if self._dirty_details:
            self._refresh_details()
            self._dirty_details = False
        if self._dirty_submenu:
            self._rebuild_submenu()
            self._dirty_submenu = False

    def _refresh_status_label(self) -> None:
        if self._status_label is not None:
            self._status_label.set_text(self.status_message)

    def _build_chrome(self) -> None:
        if self.ui_manager is None:
            return
        self._teardown_ui()
        mgr = self.ui_manager.manager
        r = self.ui_manager.rect

        self._root_panel = UIPanel(
            relative_rect=r(0, 0, 1280, 720),
            starting_height=1,
            manager=mgr,
            object_id=ObjectID(object_id="#transparent_root"),
        )

        # Header banner
        header = UIPanel(
            relative_rect=r(28, 20, 1224, 76),
            starting_height=2,
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        UILabel(
            relative_rect=r(24, 10, 420, 30),
            text="Party Composition",
            manager=mgr,
            container=header,
            object_id=ObjectID(class_id="@header_label"),
        )
        self._status_label = UILabel(
            relative_rect=r(24, 42, 1170, 24),
            text=self.status_message,
            manager=mgr,
            container=header,
            object_id=ObjectID(class_id="@muted_label"),
        )

        # Left & Right persistent panels
        self._left_panel = UIPanel(
            relative_rect=r(28, 108, 600, 536),
            starting_height=2,
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(self._left_panel, self.ui_manager)

        self._right_panel = UIPanel(
            relative_rect=r(648, 108, 604, 536),
            starting_height=2,
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(self._right_panel, self.ui_manager)

        # Persistent right-panel widgets
        self._right_portrait = UIImage(
            relative_rect=r(32, 28, 128, 128),
            image_surface=pygame.Surface((128, 128), pygame.SRCALPHA),
            manager=mgr,
            container=self._right_panel,
        )
        self._right_info_box = UITextBox(
            html_text="",
            relative_rect=r(176, 24, 400, 172),
            manager=mgr,
            container=self._right_panel,
            object_id=ObjectID(class_id="@rpg_textbox_clean"),
        )
        self._right_gear_box = UITextBox(
            html_text="",
            relative_rect=r(32, 198, 540, 160),
            manager=mgr,
            container=self._right_panel,
            object_id=ObjectID(class_id="@rpg_textbox_clean"),
        )

        # Footer
        footer = UIPanel(
            relative_rect=r(28, 656, 1224, 44),
            starting_height=2,
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@rpg_panel"),
        )
        UILabel(
            relative_rect=r(24, 10, 1170, 24),
            text="[W/S or Arrows] Navigate   [ENTER / Space] Actions   [ESC] Return to World",
            manager=mgr,
            container=footer,
            object_id=ObjectID(class_id="@muted_label"),
        )

    def _refresh_list(self) -> None:
        if self.ui_manager is None or self._left_panel is None:
            return
        mgr = self.ui_manager.manager
        r = self.ui_manager.rect
        party = self.session.party

        sel_kind, sel_idx, _ = self._get_selected_character()

        focus_r = 0
        if self.swap_mode == "active_to_reserve":
            focus_r = self.swap_target_idx
        elif sel_kind == "reserve":
            focus_r = sel_idx
        start_r = max(0, min(focus_r - 1, max(0, len(party.reserve_members) - 3)))

        sig = (
            tuple(m.id for m in party.active_members),
            tuple(m.id for m in party.reserve_members),
            start_r,
        )

        # Fast path: only update card selection highlights and labels without recreating cards
        if sig == self._last_list_signature and self._list_container is not None:
            for slot, (card, name_lbl, base_name) in enumerate(self._active_cards):
                is_sel = (
                    (sel_kind == "active" and sel_idx == slot and self.swap_mode is None)
                    or (self.swap_mode == "reserve_to_active" and self.swap_target_idx == slot)
                )
                is_src = self.swap_mode == "active_to_reserve" and self.swap_source_idx == slot
                want_cls = "@rpg_card_selected" if (is_sel or is_src) else "@rpg_card"
                if (card.class_ids or [None])[-1] != want_cls:
                    card.change_object_id(ObjectID(class_id=want_cls))
                prefix = "> " if is_sel else ""
                name_lbl.set_text(f"{prefix}{base_name}")

            for r_idx, card, name_lbl, base_name in self._reserve_cards:
                is_sel = (
                    (sel_kind == "reserve" and sel_idx == r_idx and self.swap_mode is None)
                    or (self.swap_mode == "active_to_reserve" and self.swap_target_idx == r_idx)
                )
                is_src = self.swap_mode == "reserve_to_active" and self.swap_source_idx == r_idx
                want_cls = "@rpg_card_selected" if (is_sel or is_src) else "@rpg_card"
                if (card.class_ids or [None])[-1] != want_cls:
                    card.change_object_id(ObjectID(class_id=want_cls))
                prefix = "> " if is_sel else ""
                name_lbl.set_text(f"{prefix}{base_name}")
            return

        # Full list rebuild (only on party composition change or reserve scroll)
        self._last_list_signature = sig
        if self._list_container is not None:
            self._list_container.kill()
        self._active_cards.clear()
        self._reserve_cards.clear()

        self._list_container = UIContainer(
            relative_rect=r(0, 0, 600, 536),
            manager=mgr,
            container=self._left_panel,
        )

        UILabel(
            relative_rect=r(28, 14, 540, 26),
            text="Active Squad (Slots 1-4)",
            manager=mgr,
            container=self._list_container,
            object_id=ObjectID(class_id="@sub_header_label"),
        )

        for slot in range(4):
            y = 44 + slot * 66
            if slot < len(party.active_members):
                char = party.active_members[slot]
                is_sel = (
                    (sel_kind == "active" and sel_idx == slot and self.swap_mode is None)
                    or (self.swap_mode == "reserve_to_active" and self.swap_target_idx == slot)
                )
                is_src = self.swap_mode == "active_to_reserve" and self.swap_source_idx == slot
                card = UIPanel(
                    relative_rect=r(26, y, 548, 60),
                    starting_height=3,
                    manager=mgr,
                    container=self._list_container,
                    object_id=ObjectID(class_id="@rpg_card_selected" if (is_sel or is_src) else "@rpg_card"),
                )
                prt = self.sprite_manager.get_portrait(char.id, size=48)
                if prt is not None:
                    UIImage(
                        relative_rect=r(8, 6, 48, 48),
                        image_surface=prt,
                        manager=mgr,
                        container=card,
                    )
                lock_tag = " [Locked]" if slot == 0 else ""
                base_name = f"{slot + 1}. {char.name}{lock_tag}"
                prefix = "> " if is_sel else ""
                name_lbl = UILabel(
                    relative_rect=r(66, 4, 260, 28),
                    text=f"{prefix}{base_name}",
                    manager=mgr,
                    container=card,
                    object_id=ObjectID(class_id="@sub_header_label" if is_sel else "label"),
                )
                UILabel(
                    relative_rect=r(66, 30, 260, 26),
                    text=f"{char.class_id.replace('_', ' ').title()} • Lv.{char.level}",
                    manager=mgr,
                    container=card,
                    object_id=ObjectID(class_id="@muted_label"),
                )
                StatBar(
                    relative_rect=r(332, 6, 204, 22),
                    manager=mgr,
                    prefix="HP",
                    current_value=char.current_hp,
                    max_value=char.base_stats.max_hp,
                    container=card,
                    object_id=ObjectID(object_id="#hp_bar"),
                )
                StatBar(
                    relative_rect=r(332, 32, 204, 22),
                    manager=mgr,
                    prefix="MP",
                    current_value=char.current_mp,
                    max_value=char.base_stats.max_mp,
                    container=card,
                    object_id=ObjectID(object_id="#mp_bar"),
                )
                self._active_cards.append((card, name_lbl, base_name))
            else:
                card = UIPanel(
                    relative_rect=r(26, y, 548, 60),
                    starting_height=3,
                    manager=mgr,
                    container=self._list_container,
                    object_id=ObjectID(class_id="@rpg_card"),
                )
                UILabel(
                    relative_rect=r(20, 18, 500, 24),
                    text=f"{slot + 1}. [Empty Active Slot]",
                    manager=mgr,
                    container=card,
                    object_id=ObjectID(class_id="@muted_label"),
                )

        UILabel(
            relative_rect=r(28, 316, 540, 26),
            text=f"Reserve Bench ({len(party.reserve_members)})",
            manager=mgr,
            container=self._list_container,
            object_id=ObjectID(class_id="@sub_header_label"),
        )

        if not party.reserve_members:
            UILabel(
                relative_rect=r(36, 352, 520, 28),
                text="(No companions currently in reserve)",
                manager=mgr,
                container=self._list_container,
                object_id=ObjectID(class_id="@muted_label"),
            )
        else:
            visible_reserves = party.reserve_members[start_r : start_r + 3]
            for offset, r_char in enumerate(visible_reserves):
                r_idx = start_r + offset
                y = 348 + offset * 58
                is_sel = (
                    (sel_kind == "reserve" and sel_idx == r_idx and self.swap_mode is None)
                    or (self.swap_mode == "active_to_reserve" and self.swap_target_idx == r_idx)
                )
                is_src = self.swap_mode == "reserve_to_active" and self.swap_source_idx == r_idx
                card = UIPanel(
                    relative_rect=r(26, y, 548, 52),
                    starting_height=3,
                    manager=mgr,
                    container=self._list_container,
                    object_id=ObjectID(class_id="@rpg_card_selected" if (is_sel or is_src) else "@rpg_card"),
                )
                prt = self.sprite_manager.get_portrait(r_char.id, size=40)
                if prt is not None:
                    UIImage(
                        relative_rect=r(8, 6, 40, 40),
                        image_surface=prt,
                        manager=mgr,
                        container=card,
                    )
                prefix = "> " if is_sel else ""
                name_lbl = UILabel(
                    relative_rect=r(58, 2, 260, 26),
                    text=f"{prefix}{r_char.name}",
                    manager=mgr,
                    container=card,
                    object_id=ObjectID(class_id="@sub_header_label" if is_sel else "label"),
                )
                UILabel(
                    relative_rect=r(58, 25, 260, 24),
                    text=f"{r_char.class_id.replace('_', ' ').title()} • Lv.{r_char.level}",
                    manager=mgr,
                    container=card,
                    object_id=ObjectID(class_id="@muted_label"),
                )
                StatBar(
                    relative_rect=r(326, 4, 210, 20),
                    manager=mgr,
                    prefix="HP",
                    current_value=r_char.current_hp,
                    max_value=r_char.base_stats.max_hp,
                    container=card,
                    object_id=ObjectID(object_id="#hp_bar"),
                )
                StatBar(
                    relative_rect=r(326, 28, 210, 20),
                    manager=mgr,
                    prefix="MP",
                    current_value=r_char.current_mp,
                    max_value=r_char.base_stats.max_mp,
                    container=card,
                    object_id=ObjectID(object_id="#mp_bar"),
                )
                self._reserve_cards.append((r_idx, card, name_lbl, r_char.name))

    def _refresh_details(self) -> None:
        sel_kind, _, sel_char = self._get_selected_character()
        if sel_char is None:
            return

        if self._right_portrait is not None and sel_char.id != self._last_detail_char_id:
            prt = self.sprite_manager.get_portrait(sel_char.id, size=128)
            if prt is not None:
                self._right_portrait.set_image(prt)
            self._last_detail_char_id = sel_char.id

        stats = sel_char.base_stats
        role_txt = "Active Squad" if sel_kind == "active" else "Reserve Bench"
        weapon_txt = (sel_char.equipment.weapon or "None").replace("_", " ").title()
        armor_txt = (sel_char.equipment.armor or "None").replace("_", " ").title()
        abilities_txt = ", ".join(
            ab.replace("_", " ").title() for ab in sel_char.learned_abilities
        ) or "None"

        if self._right_info_box is not None:
            info_html = (
                f"<b><font color='#FFE078' size=5>{html.escape(sel_char.name)}</font></b><br>"
                f"{html.escape(sel_char.class_id.replace('_', ' ').title())} • Lv.{sel_char.level} ({role_txt})<br>"
                f"<b>HP:</b> {sel_char.current_hp}/{stats.max_hp} &nbsp;&nbsp; "
                f"<b>MP:</b> {sel_char.current_mp}/{stats.max_mp}<br>"
                f"<b>ATK:</b> {stats.attack} &nbsp; <b>DEF:</b> {stats.defense} &nbsp; "
                f"<b>MAG:</b> {stats.magic_attack}<br>"
                f"<b>RES:</b> {stats.magic_defense} &nbsp; <b>SPD:</b> {stats.speed} &nbsp; "
                f"<b>CRIT:</b> {int(stats.crit_chance * 100)}%"
            )
            self._right_info_box.set_text(info_html)

        if self._right_gear_box is not None:
            gear_html = (
                f"<b>Equipment</b><br>"
                f"Weapon: {html.escape(weapon_txt)} &nbsp;|&nbsp; Armor: {html.escape(armor_txt)}<br>"
                f"<b>Abilities</b><br>{html.escape(abilities_txt)}"
            )
            self._right_gear_box.set_text(gear_html)

    def _rebuild_submenu(self) -> None:
        if self._sub_menu_panel is not None:
            self._sub_menu_panel.kill()
            self._sub_menu_panel = None
        self._sub_menu_buttons.clear()

        if not self.sub_menu_open or not self.sub_menu_options or self.ui_manager is None or self._right_panel is None:
            return

        mgr = self.ui_manager.manager
        r = self.ui_manager.rect
        sub_h = 28 + len(self.sub_menu_options) * 38
        self._sub_menu_panel = UIPanel(
            relative_rect=r(172, 504 - sub_h, 260, sub_h),
            starting_height=5,
            manager=mgr,
            container=self._right_panel,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        for opt_idx, (_, label) in enumerate(self.sub_menu_options):
            btn = UIButton(
                relative_rect=r(16, 14 + opt_idx * 38, 228, 32),
                text=label,
                manager=mgr,
                container=self._sub_menu_panel,
                object_id=ObjectID(class_id="@action_button"),
            )
            if opt_idx == self.sub_menu_index:
                btn.select()
            self._sub_menu_buttons.append(btn)

    def _update_submenu_selection(self) -> None:
        for opt_idx, btn in enumerate(self._sub_menu_buttons):
            if opt_idx == self.sub_menu_index:
                btn.select()
            else:
                btn.unselect()

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((14, 16, 26))
