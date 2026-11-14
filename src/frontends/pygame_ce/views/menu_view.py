"""Comprehensive party management, inventory, equipment, and skill tree menu view using pygame-gui."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

import pygame
from pygame_gui.core import ObjectID, UIContainer
from pygame_gui.elements import (
    UIButton,
    UIImage,
    UILabel,
    UIPanel,
    UIScrollingContainer,
    UITextBox,
)

from src.core.fsm import GameMode
from src.data.items import ITEM_REGISTRY, ItemType
from src.frontends.pygame_ce.combat_animator import EnemySpriteManager
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine
from src.frontends.pygame_ce.ui_manager import GameUIManager, StatBar, attach_ornate_corners

if TYPE_CHECKING:
    from src.core.session import GameSession


class MenuView:
    """Camp and party management menu rendered in the HD-2D pygame-gui overlay."""

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

        self.tabs = ["Roster", "Inventory", "Equipment", "Skill Trees", "Quests", "Save Game", "Return"]
        self.active_tab_idx = 0

        # Sub-navigation state
        self.char_index = 0
        self.quest_index = 0
        self.item_index = 0
        self.node_index = 0
        self.save_slot_index = 0
        self.slot_index = 0  # 0: Weapon, 1: Armor, 2: Accessory

        # Equipment picker mode (from Equipment tab)
        self.equipment_picking = False
        self.equip_picker_index = 0

        # Target picker mode (from Inventory tab)
        self.inventory_target_picker = False
        self.target_char_index = 0
        self.roster_reordering = False

        self.status_message = ""
        self.time_sec = 0.0
        self.sprite_manager = EnemySpriteManager()

        # Root UI container
        self._root_panel: UIPanel | None = None
        self._tab_container: UIContainer | None = None
        self._modal_panel: UIPanel | None = None
        self._time_label: UILabel | None = None
        self._gold_label: UILabel | None = None
        self._status_label: UILabel | None = None
        self._tab_buttons: list[UIButton] = []
        self._built_tab_name: str | None = None
        self._roster_cards: list[tuple[UIPanel, UILabel, str]] = []
        self._roster_portrait: UIImage | None = None
        self._roster_details_box: UITextBox | None = None
        self._roster_detail_char_id: str | None = None
        self._roster_sig: tuple | None = None
        self._skill_node_buttons: list[UIButton] = []
        self._skill_desc_box: UITextBox | None = None
        self._skill_sig: tuple | None = None
        self._inv_buttons: list[tuple[UIButton, str]] = []
        self._inv_desc_box: UITextBox | None = None
        self._inv_sig: tuple | None = None
        self._equip_cards: list[tuple[UIPanel, UILabel, str]] = []
        self._equip_sig: tuple | None = None
        self._save_buttons: list[tuple[UIButton, str]] = []
        self._save_sig: tuple | None = None
        self._dirty_ui = False

    def on_enter(self) -> None:
        self.active_tab_idx = 0
        self.char_index = 0
        self.quest_index = 0
        self.item_index = 0
        self.node_index = 0
        self.slot_index = 0
        self.equipment_picking = False
        self.inventory_target_picker = False
        self.roster_reordering = False
        self.status_message = "Viewing Roster"
        self._rebuild_ui()

    def on_exit(self) -> None:
        if self._modal_panel is not None:
            self._modal_panel.kill()
            self._modal_panel = None
        if self._root_panel is not None:
            self._root_panel.kill()
            self._root_panel = None
        self._tab_container = None
        self._time_label = None
        self._gold_label = None
        self._status_label = None
        self._tab_buttons.clear()
        self._built_tab_name = None
        self._roster_cards.clear()
        self._roster_portrait = None
        self._roster_details_box = None
        self._roster_detail_char_id = None
        self._roster_sig = None
        self._skill_node_buttons.clear()
        self._skill_desc_box = None
        self._skill_sig = None
        self._inv_buttons.clear()
        self._inv_desc_box = None
        self._inv_sig = None
        self._equip_cards.clear()
        self._equip_sig = None
        self._save_buttons.clear()
        self._save_sig = None

    def on_resize(self, width: int, height: int) -> None:
        self._rebuild_ui()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return

        if self.inventory_target_picker:
            self._handle_inventory_picker_input(event)
            self._rebuild_ui()
            return

        if self.equipment_picking:
            self._handle_equipment_picker_input(event)
            self._rebuild_ui()
            return

        if event.key == pygame.K_ESCAPE:
            self.session.transition_to(GameMode.EXPLORATION)
            return

        if event.key == pygame.K_q:
            self.active_tab_idx = (self.active_tab_idx - 1) % len(self.tabs)
            self._on_tab_switched()
            self._rebuild_ui()
            return
        if event.key == pygame.K_e:
            self.active_tab_idx = (self.active_tab_idx + 1) % len(self.tabs)
            self._on_tab_switched()
            self._rebuild_ui()
            return

        tab = self.tabs[self.active_tab_idx]
        if tab == "Roster":
            self._handle_roster_input(event)
        elif tab == "Quests":
            self._handle_quests_input(event)
        elif tab == "Inventory":
            self._handle_inventory_input(event)
        elif tab == "Equipment":
            self._handle_equipment_input(event)
        elif tab == "Skill Trees":
            self._handle_skill_tree_input(event)
        elif tab == "Save Game":
            self._handle_save_input(event)
        elif tab == "Return":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.session.transition_to(GameMode.EXPLORATION)
                return

        self._rebuild_ui()

    def _on_tab_switched(self) -> None:
        self.quest_index = 0
        self.item_index = 0
        self.node_index = 0
        self.slot_index = 0
        self.equipment_picking = False
        self.inventory_target_picker = False
        self.roster_reordering = False
        self.status_message = f"Viewing {self.tabs[self.active_tab_idx]}"

    def _handle_roster_input(self, event: pygame.event.Event) -> None:
        members = self.session.party.active_members
        if not members:
            return
        if self.roster_reordering:
            if event.key in (pygame.K_UP, pygame.K_w):
                if self.char_index > 1 and self.session.party.reorder_active(self.char_index, self.char_index - 1):
                    self.char_index -= 1
                    self.status_message = f"Moved {members[self.char_index].name} to Slot {self.char_index + 1}."
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.char_index < len(members) - 1 and self.session.party.reorder_active(
                    self.char_index, self.char_index + 1
                ):
                    self.char_index += 1
                    self.status_message = f"Moved {members[self.char_index].name} to Slot {self.char_index + 1}."
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.roster_reordering = False
                self.status_message = "Formation updated."
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.char_index = (self.char_index - 1) % len(members)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.char_index = (self.char_index + 1) % len(members)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            if self.char_index == 0:
                self.status_message = "Rowan is locked to Slot 1. Swap active/reserve at Town Inns or Rowan's cottage."
            elif len(members) > 2:
                self.roster_reordering = True
                self.status_message = f"Reordering {members[self.char_index].name}: [W/S] Move, [ENTER] Done."
            else:
                self.status_message = "Active/Reserve swaps are available at Town Inns and Rowan's cottage."

    def _handle_inventory_input(self, event: pygame.event.Event) -> None:
        items = list(self.session.party.inventory.items())
        if not items:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.item_index = (self.item_index - 1) % len(items)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.item_index = (self.item_index + 1) % len(items)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            item_id, _qty = items[self.item_index]
            item_def = ITEM_REGISTRY.get(item_id)
            if item_def:
                self.inventory_target_picker = True
                self.target_char_index = self.char_index

    def _handle_inventory_picker_input(self, event: pygame.event.Event) -> None:
        members = self.session.party.active_members
        if not members:
            self.inventory_target_picker = False
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.target_char_index = (self.target_char_index - 1) % len(members)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.target_char_index = (self.target_char_index + 1) % len(members)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            items = list(self.session.party.inventory.items())
            if not items or self.item_index >= len(items):
                self.inventory_target_picker = False
                return

            item_id, _qty = items[self.item_index]
            item_def = ITEM_REGISTRY.get(item_id)
            target = members[self.target_char_index]

            if not item_def:
                self.inventory_target_picker = False
                return

            if item_def.item_type == ItemType.CONSUMABLE:
                if item_def.heal_hp > 0:
                    healed = target.heal(item_def.heal_hp)
                    self.session.party.remove_item(item_id, 1)
                    self.status_message = f"Used {item_def.name} on {target.name} (+{healed} HP)!"
                elif item_def.heal_mp > 0:
                    restored = target.restore_mp(item_def.heal_mp)
                    self.session.party.remove_item(item_id, 1)
                    self.status_message = f"Used {item_def.name} on {target.name} (+{restored} MP)!"
            elif item_def.item_type == ItemType.WEAPON:
                old = target.equipment.weapon
                if old:
                    self.session.party.add_item(old, 1)
                target.equipment.weapon = item_id
                self.session.party.remove_item(item_id, 1)
                self.status_message = f"Equipped {item_def.name} on {target.name}!"
            elif item_def.item_type == ItemType.ARMOR:
                old = target.equipment.armor
                if old:
                    self.session.party.add_item(old, 1)
                target.equipment.armor = item_id
                self.session.party.remove_item(item_id, 1)
                self.status_message = f"Equipped {item_def.name} on {target.name}!"
            elif item_def.item_type == ItemType.ACCESSORY:
                old = target.equipment.accessory
                if old:
                    self.session.party.add_item(old, 1)
                target.equipment.accessory = item_id
                self.session.party.remove_item(item_id, 1)
                self.status_message = f"Equipped {item_def.name} on {target.name}!"

            self.inventory_target_picker = False
        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.inventory_target_picker = False

    def _get_compatible_equipment_options(self, slot_idx: int) -> list[str | None]:
        """Returns list of item IDs matching slot_idx, with None representing [Unequip]."""
        slot_type = [ItemType.WEAPON, ItemType.ARMOR, ItemType.ACCESSORY][slot_idx]
        options: list[str | None] = [None]
        for item_id, qty in self.session.party.inventory.items():
            if qty > 0:
                item_def = ITEM_REGISTRY.get(item_id)
                if item_def and item_def.item_type == slot_type:
                    options.append(item_id)
        return options

    def _handle_equipment_input(self, event: pygame.event.Event) -> None:
        members = self.session.party.active_members
        if not members:
            return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.char_index = (self.char_index - 1) % len(members)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.char_index = (self.char_index + 1) % len(members)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.slot_index = (self.slot_index - 1) % 3
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.slot_index = (self.slot_index + 1) % 3
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.equipment_picking = True
            self.equip_picker_index = 0

    def _handle_equipment_picker_input(self, event: pygame.event.Event) -> None:
        options = self._get_compatible_equipment_options(self.slot_index)
        if not options:
            self.equipment_picking = False
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.equip_picker_index = (self.equip_picker_index - 1) % len(options)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.equip_picker_index = (self.equip_picker_index + 1) % len(options)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            char = self.session.party.active_members[self.char_index]
            chosen_id = options[self.equip_picker_index]

            if self.slot_index == 0:
                old = char.equipment.weapon
                if old:
                    self.session.party.add_item(old, 1)
                char.equipment.weapon = chosen_id
                if chosen_id:
                    self.session.party.remove_item(chosen_id, 1)
                    it = ITEM_REGISTRY.get(chosen_id)
                    self.status_message = f"Equipped {it.name if it else chosen_id} on {char.name}!"
                else:
                    self.status_message = f"Unequipped weapon on {char.name}."
            elif self.slot_index == 1:
                old = char.equipment.armor
                if old:
                    self.session.party.add_item(old, 1)
                char.equipment.armor = chosen_id
                if chosen_id:
                    self.session.party.remove_item(chosen_id, 1)
                    it = ITEM_REGISTRY.get(chosen_id)
                    self.status_message = f"Equipped {it.name if it else chosen_id} on {char.name}!"
                else:
                    self.status_message = f"Unequipped armor on {char.name}."
            elif self.slot_index == 2:
                old = char.equipment.accessory
                if old:
                    self.session.party.add_item(old, 1)
                char.equipment.accessory = chosen_id
                if chosen_id:
                    self.session.party.remove_item(chosen_id, 1)
                    it = ITEM_REGISTRY.get(chosen_id)
                    self.status_message = f"Equipped {it.name if it else chosen_id} on {char.name}!"
                else:
                    self.status_message = f"Unequipped accessory on {char.name}."

            self.equipment_picking = False
        elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            self.equipment_picking = False

    def _handle_skill_tree_input(self, event: pygame.event.Event) -> None:
        members = self.session.party.active_members
        if not members:
            return
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.char_index = (self.char_index - 1) % len(members)
            self.node_index = 0
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.char_index = (self.char_index + 1) % len(members)
            self.node_index = 0

        char = members[self.char_index]
        tree = self.session.skill_trees.get(char.id)
        if not tree:
            return
        node_ids = list(tree.nodes.keys())
        if not node_ids:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.node_index = (self.node_index - 1) % len(node_ids)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.node_index = (self.node_index + 1) % len(node_ids)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            node_id = node_ids[self.node_index]
            can, reason = tree.can_unlock(node_id, char.skill_points)
            if can:
                tree.unlock_node(char, node_id)
                self.status_message = f"Unlocked {tree.nodes[node_id].name}!"
            else:
                self.status_message = f"Cannot unlock: {reason}"

    def _handle_save_input(self, event: pygame.event.Event) -> None:
        slots = [1, 2, 3]
        if event.key in (pygame.K_UP, pygame.K_w):
            self.save_slot_index = (self.save_slot_index - 1) % len(slots)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.save_slot_index = (self.save_slot_index + 1) % len(slots)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            slot = slots[self.save_slot_index]
            if self.session.save_game(slot_id=slot):
                self.status_message = f"Game successfully saved to Slot {slot}!"
            else:
                self.status_message = "Failed to save game!"

    def update(self, dt: float) -> None:
        self.time_sec += dt
        if self._time_label is not None:
            mins = int(self.session.play_time_seconds // 60)
            secs = int(self.session.play_time_seconds % 60)
            self._time_label.set_text(f"Time: {mins:02d}:{secs:02d}")

    def draw(self, surface: pygame.Surface) -> None:
        """Draw dark backdrop onto 640x360 canvas; all Camp Journal widgets render in HD overlay."""
        surface.fill((12, 14, 24))

    def _build_chrome(self, mgr, r) -> None:
        self._root_panel = UIPanel(
            relative_rect=r(0, 0, 1280, 720),
            starting_height=1,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel"),
        )
        attach_ornate_corners(self._root_panel, self.ui_manager)

        # Header
        UILabel(
            relative_rect=r(54, 16, 360, 40),
            text="CAMP JOURNAL",
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@header_label"),
        )
        mins = int(self.session.play_time_seconds // 60)
        secs = int(self.session.play_time_seconds % 60)
        self._time_label = UILabel(
            relative_rect=r(820, 20, 180, 32),
            text=f"Time: {mins:02d}:{secs:02d}",
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@muted_label"),
        )
        self._gold_label = UILabel(
            relative_rect=r(1030, 18, 220, 36),
            text=f"Gold: {self.session.party.gold} G",
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@sub_header_label"),
        )

        # Tab Bar
        self._tab_buttons.clear()
        tab_w = 168
        gap = 8
        start_x = 28
        for idx, tab_name in enumerate(self.tabs):
            is_active = idx == self.active_tab_idx
            btn = UIButton(
                relative_rect=r(start_x + idx * (tab_w + gap), 66, tab_w, 42),
                text=tab_name,
                manager=mgr,
                container=self._root_panel,
                object_id=ObjectID(class_id="@rpg_tab_active" if is_active else "@rpg_tab"),
            )
            self._tab_buttons.append(btn)

        # Footer Status Bar
        footer = UIPanel(
            relative_rect=r(54, 654, 1172, 46),
            starting_height=2,
            manager=mgr,
            container=self._root_panel,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        self._status_label = UILabel(
            relative_rect=r(18, 8, 540, 28),
            text=self.status_message,
            manager=mgr,
            container=footer,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        UILabel(
            relative_rect=r(570, 8, 584, 28),
            text="[Q/E] Tabs   [Arrows] Navigate   [ENTER] Select   [ESC] Exit",
            manager=mgr,
            container=footer,
            object_id=ObjectID(class_id="@footer_label"),
        )

    def _rebuild_ui(self) -> None:
        mgr = self.ui_manager.manager
        r = self.ui_manager.rect

        if self._root_panel is None:
            self._build_chrome(mgr, r)
        else:
            if self._gold_label is not None:
                self._gold_label.set_text(f"Gold: {self.session.party.gold} G")
            if self._status_label is not None:
                self._status_label.set_text(self.status_message)
            for idx, btn in enumerate(self._tab_buttons):
                want_id = "@rpg_tab_active" if idx == self.active_tab_idx else "@rpg_tab"
                if (btn.class_ids or [None])[-1] != want_id:
                    btn.change_object_id(ObjectID(class_id=want_id))

        if self._modal_panel is not None:
            self._modal_panel.kill()
            self._modal_panel = None

        tab = self.tabs[self.active_tab_idx]

        # Fast path for Roster navigation / reordering without destroying panels
        members = self.session.party.active_members
        roster_sig = tuple(m.id for m in members)
        if (
            tab == "Roster"
            and self._built_tab_name == "Roster"
            and self._tab_container is not None
            and roster_sig == self._roster_sig
            and self._roster_cards
        ):
            self._update_roster_tab_in_place()
            return

        # Fast path for Skill Trees node navigation without destroying panels
        if (
            tab == "Skill Trees"
            and self._built_tab_name == "Skill Trees"
            and self._tab_container is not None
            and members
        ):
            c_idx = min(self.char_index, len(members) - 1)
            c = members[c_idx]
            tr = self.session.skill_trees.get(c.id)
            s_sig = (c.id, tuple(sorted(tr.unlocked_nodes)) if tr else (), c.skill_points)
            if s_sig == self._skill_sig and self._skill_node_buttons:
                self._update_skill_tree_in_place()
                return

        # Fast path for Inventory item navigation without destroying panels
        if (
            tab == "Inventory"
            and not self.inventory_target_picker
            and self._built_tab_name == "Inventory"
            and self._tab_container is not None
        ):
            inv_sig = tuple(self.session.party.inventory.items())
            if inv_sig == self._inv_sig and self._inv_buttons:
                self._update_inventory_tab_in_place()
                return

        # Fast path for Equipment slot navigation without destroying panels
        if (
            tab == "Equipment"
            and not self.equipment_picking
            and self._built_tab_name == "Equipment"
            and self._tab_container is not None
            and members
        ):
            c_idx = min(self.char_index, len(members) - 1)
            c = members[c_idx]
            eq_sig = (c.id, c.equipment.weapon, c.equipment.armor, c.equipment.accessory)
            if eq_sig == self._equip_sig and self._equip_cards:
                self._update_equipment_tab_in_place()
                return

        # Fast path for Save Game slot navigation without destroying panels
        if (
            tab == "Save Game"
            and self._built_tab_name == "Save Game"
            and self._tab_container is not None
            and self._save_buttons
        ):
            self._update_save_tab_in_place()
            return

        if self._tab_container is not None:
            self._tab_container.kill()
            self._tab_container = None
        self._roster_cards.clear()
        self._roster_portrait = None
        self._roster_details_box = None
        self._roster_detail_char_id = None
        self._roster_sig = None
        self._skill_node_buttons.clear()
        self._skill_desc_box = None
        self._skill_sig = None
        self._inv_buttons.clear()
        self._inv_desc_box = None
        self._inv_sig = None
        self._equip_cards.clear()
        self._equip_sig = None
        self._save_buttons.clear()
        self._save_sig = None

        self._tab_container = UIContainer(
            relative_rect=r(0, 0, 1280, 720),
            manager=mgr,
            container=self._root_panel,
        )
        self._built_tab_name = tab

        if tab == "Roster":
            self._build_roster_tab(mgr, r)
        elif tab == "Quests":
            self._build_quests_tab(mgr, r)
        elif tab == "Inventory":
            self._build_inventory_tab(mgr, r)
        elif tab == "Equipment":
            self._build_equipment_tab(mgr, r)
        elif tab == "Skill Trees":
            self._build_skill_tree_tab(mgr, r)
        elif tab == "Save Game":
            self._build_save_tab(mgr, r)
        elif tab == "Return":
            self._build_return_tab(mgr, r)

        # Modals
        if self.inventory_target_picker:
            self._build_inventory_picker_modal(mgr, r)
        elif self.equipment_picking:
            self._build_equipment_picker_modal(mgr, r)

    def _build_roster_tab(self, mgr, r) -> None:
        members = self.session.party.active_members
        self._roster_sig = tuple(m.id for m in members)
        self._roster_cards.clear()
        left_panel = UIPanel(
            relative_rect=r(28, 126, 600, 512),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(left_panel, self.ui_manager)
        right_panel = UIPanel(
            relative_rect=r(648, 126, 604, 512),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(right_panel, self.ui_manager)

        for idx, char in enumerate(members):
            is_sel = idx == self.char_index
            card = UIPanel(
                relative_rect=r(26, 26 + idx * 116, 548, 106),
                starting_height=3,
                manager=mgr,
                container=left_panel,
                object_id=ObjectID(class_id="@rpg_card_selected" if is_sel else "@rpg_card"),
            )
            prt = self.sprite_manager.get_portrait(char.id, size=84)
            if prt is not None:
                UIImage(
                    relative_rect=r(14, 12, 84, 84),
                    image_surface=prt,
                    manager=mgr,
                    container=card,
                )
            prefix = "> " if is_sel else ""
            slot_tag = " [Locked]" if idx == 0 else (" [Moving]" if (is_sel and self.roster_reordering) else "")
            name_lbl = UILabel(
                relative_rect=r(112, 10, 260, 28),
                text=f"{prefix}{char.name}{slot_tag}",
                manager=mgr,
                container=card,
                object_id=ObjectID(class_id="@sub_header_label" if is_sel else "label"),
            )
            self._roster_cards.append((card, name_lbl, char.name))
            UILabel(
                relative_rect=r(112, 40, 260, 24),
                text=f"{char.class_id.replace('_', ' ').title()} • Lv.{char.level}",
                manager=mgr,
                container=card,
                object_id=ObjectID(class_id="@muted_label"),
            )
            StatBar(
                relative_rect=r(364, 18, 166, 22),
                manager=mgr,
                prefix="HP",
                current_value=char.current_hp,
                max_value=char.base_stats.max_hp,
                container=card,
                object_id=ObjectID(object_id="#hp_bar"),
            )
            StatBar(
                relative_rect=r(364, 46, 166, 22),
                manager=mgr,
                prefix="MP",
                current_value=char.current_mp,
                max_value=char.base_stats.max_mp,
                container=card,
                object_id=ObjectID(object_id="#mp_bar"),
            )

        if members and self.char_index < len(members):
            char = members[self.char_index]
            prt = self.sprite_manager.get_portrait(char.id, size=140)
            self._roster_portrait = UIImage(
                relative_rect=r(32, 32, 140, 140),
                image_surface=prt if prt is not None else pygame.Surface((140, 140), pygame.SRCALPHA),
                manager=mgr,
                container=right_panel,
            )
            self._roster_detail_char_id = char.id
            abilities_html = "".join(
                f"• {html.escape(ab_id.replace('_', ' ').title())}<br>"
                for ab_id in char.learned_abilities
            ) or "<i>None learned</i>"
            details_html = (
                f"<b><font color='#FFE078' size=5>{html.escape(char.name)}</font></b><br>"
                f"Class: {html.escape(char.class_id.replace('_', ' ').title())} (Lv.{char.level})<br>"
                f"<font color='#78F08C'>Available SP: {char.skill_points}</font><br><br>"
                f"<b>Learned Abilities:</b><br>{abilities_html}"
            )
            self._roster_details_box = UITextBox(
                html_text=details_html,
                relative_rect=r(184, 28, 392, 412),
                manager=mgr,
                container=right_panel,
                object_id=ObjectID(class_id="@rpg_textbox_clean"),
            )
            UILabel(
                relative_rect=r(20, 466, 564, 26),
                text="[ENTER] Reorder Slots 2-4  •  Swap Reserve at Inns / Rowan's cottage",
                manager=mgr,
                container=right_panel,
                object_id=ObjectID(class_id="@muted_label"),
            )

    def _get_quest_entries(self) -> list[tuple[str, bool]]:
        qm = self.session.quest_manager
        entries: list[tuple[str, bool]] = [(qid, False) for qid in qm.active_quests]
        entries.extend((qid, True) for qid in qm.completed_quests)
        return entries

    def _handle_quests_input(self, event: pygame.event.Event) -> None:
        entries = self._get_quest_entries()
        if not entries:
            return
        if event.key in (pygame.K_UP, pygame.K_w):
            self.quest_index = (self.quest_index - 1) % len(entries)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.quest_index = (self.quest_index + 1) % len(entries)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            qid, is_done = entries[self.quest_index % len(entries)]
            qm = self.session.quest_manager
            if is_done:
                self.status_message = "Completed quests cannot be tracked."
            elif qm.set_tracked_quest(qid):
                defn = qm.registry.get(qid)
                self.status_message = f"Tracking quest: {defn.title if defn else qid}"

    def _build_quests_tab(self, mgr, r) -> None:
        left_panel = UIPanel(
            relative_rect=r(28, 122, 566, 514),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(left_panel, self.ui_manager)
        right_panel = UIPanel(
            relative_rect=r(610, 122, 642, 514),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(right_panel, self.ui_manager)

        qm = self.session.quest_manager
        entries = self._get_quest_entries()
        if not entries:
            UILabel(
                relative_rect=r(32, 32, 480, 32),
                text="No quests recorded yet.",
                manager=mgr,
                container=left_panel,
                object_id=ObjectID(class_id="@muted_label"),
            )
            return

        self.quest_index = min(self.quest_index, len(entries) - 1)
        scroll = UIScrollingContainer(
            relative_rect=r(18, 22, 530, 470),
            manager=mgr,
            container=left_panel,
        )

        for idx, (qid, is_done) in enumerate(entries):
            defn = qm.registry.get(qid)
            if defn is None:
                continue
            is_sel = idx == self.quest_index
            cat_tag = "MAIN" if defn.category.name == "MAIN" else "SIDE"
            if is_done:
                state_tag = " [Done]"
            elif qid == qm.tracked_quest_id:
                state_tag = " [Tracked]"
            else:
                state_tag = ""
            prefix = "> " if is_sel else "  "
            UIButton(
                relative_rect=r(8, 8 + idx * 54, 492, 46),
                text=f"{prefix}[{cat_tag}] {defn.title}{state_tag}",
                manager=mgr,
                container=scroll,
                object_id=ObjectID(class_id="@rpg_button_selected" if is_sel else "@rpg_button"),
            )

        sel_qid, sel_done = entries[self.quest_index]
        defn = qm.registry.get(sel_qid)
        if defn is None:
            return

        cat_label = "Main Quest" if defn.category.name == "MAIN" else "Side Quest"
        status_label = (
            "<font color='#78F08C'>Completed</font>"
            if sel_done
            else ("<font color='#FFE078'>Active (Tracked)</font>" if sel_qid == qm.tracked_quest_id else "<font color='#FFE078'>Active</font>")
        )
        prog = qm.active_quests.get(sel_qid)
        cur_step_idx = len(defn.steps) if sel_done else (prog.step_index if prog else 0)

        steps_html_parts: list[str] = []
        for s_idx, step in enumerate(defn.steps):
            if s_idx < cur_step_idx:
                steps_html_parts.append(f"<font color='#78F08C'>[x] {html.escape(step.description)}</font>")
            elif s_idx == cur_step_idx and not sel_done and prog is not None:
                step_txt = qm.format_step_label(prog, step)
                steps_html_parts.append(f"<font color='#FFE078'>[&gt;] {html.escape(step_txt)}</font>")

        reward_str = html.escape(defn.reward.summary_text() or "None")
        details_html = (
            f"<b><font color='#FFE078' size=5>{html.escape(defn.title)}</font></b><br>"
            f"{cat_label} • {status_label}<br><br>"
            f"{html.escape(defn.description)}<br><br>"
            f"<b>Objectives:</b><br>{'<br>'.join(steps_html_parts)}<br><br>"
            f"<b>Rewards:</b> <font color='#92C5F7'>{reward_str}</font>"
        )
        UITextBox(
            html_text=details_html,
            relative_rect=r(28, 28, 586, 424),
            manager=mgr,
            container=right_panel,
            object_id=ObjectID(class_id="@rpg_textbox_clean"),
        )
        UILabel(
            relative_rect=r(28, 466, 586, 26),
            text="[W/S] Select Quest  •  [ENTER] Track on HUD",
            manager=mgr,
            container=right_panel,
            object_id=ObjectID(class_id="@muted_label"),
        )

    def _update_roster_tab_in_place(self) -> None:
        members = self.session.party.active_members
        for idx, (card, name_lbl, base_name) in enumerate(self._roster_cards):
            is_sel = idx == self.char_index
            want_cls = "@rpg_card_selected" if is_sel else "@rpg_card"
            if (card.class_ids or [None])[-1] != want_cls:
                card.change_object_id(ObjectID(class_id=want_cls))
            prefix = "> " if is_sel else ""
            slot_tag = " [Locked]" if idx == 0 else (" [Moving]" if (is_sel and self.roster_reordering) else "")
            name_lbl.set_text(f"{prefix}{base_name}{slot_tag}")

        if members and self.char_index < len(members):
            char = members[self.char_index]
            if self._roster_portrait is not None and char.id != self._roster_detail_char_id:
                prt = self.sprite_manager.get_portrait(char.id, size=140)
                if prt is not None:
                    self._roster_portrait.set_image(prt)
                self._roster_detail_char_id = char.id
            if self._roster_details_box is not None:
                abilities_html = "".join(
                    f"• {html.escape(ab_id.replace('_', ' ').title())}<br>"
                    for ab_id in char.learned_abilities
                ) or "<i>None learned</i>"
                details_html = (
                    f"<b><font color='#FFE078' size=5>{html.escape(char.name)}</font></b><br>"
                    f"Class: {html.escape(char.class_id.replace('_', ' ').title())} (Lv.{char.level})<br>"
                    f"<font color='#78F08C'>Available SP: {char.skill_points}</font><br><br>"
                    f"<b>Learned Abilities:</b><br>{abilities_html}"
                )
                self._roster_details_box.set_text(details_html)

    def _build_inventory_tab(self, mgr, r) -> None:
        left_panel = UIPanel(
            relative_rect=r(28, 126, 600, 512),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(left_panel, self.ui_manager)
        right_panel = UIPanel(
            relative_rect=r(648, 126, 604, 512),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(right_panel, self.ui_manager)

        items = list(self.session.party.inventory.items())
        self._inv_sig = tuple(items)
        self._inv_buttons.clear()
        if not items:
            UILabel(
                relative_rect=r(36, 36, 400, 32),
                text="Inventory is empty.",
                manager=mgr,
                container=left_panel,
                object_id=ObjectID(class_id="@muted_label"),
            )
            return

        self.item_index = min(self.item_index, len(items) - 1)
        scroll = UIScrollingContainer(
            relative_rect=r(28, 28, 544, 456),
            manager=mgr,
            container=left_panel,
        )
        row_h = 46
        scroll.set_scrollable_area_dimensions((516, max(452, len(items) * row_h + 10)))

        for idx, (it_id, qty) in enumerate(items):
            is_sel = idx == self.item_index
            it_def = ITEM_REGISTRY.get(it_id)
            name = it_def.name if it_def else it_id.replace("_", " ").title()
            base_text = f"{name}   (x{qty})"
            prefix = "> " if is_sel else "  "
            btn = UIButton(
                relative_rect=r(4, 4 + idx * row_h, 508, 40),
                text=f"{prefix}{base_text}",
                manager=mgr,
                container=scroll,
                object_id=ObjectID(
                    class_id="@rpg_button_selected" if is_sel else "@rpg_button"
                ),
            )
            self._inv_buttons.append((btn, base_text))

        sel_id, _ = items[self.item_index]
        self._inv_desc_box = UITextBox(
            html_text=self._format_item_info_html(sel_id),
            relative_rect=r(32, 32, 540, 448),
            manager=mgr,
            container=right_panel,
            object_id=ObjectID(class_id="@rpg_textbox_clean"),
        )

    @staticmethod
    def _format_item_info_html(item_id: str) -> str:
        it_def = ITEM_REGISTRY.get(item_id)
        if not it_def:
            return ""
        action_hint = (
            "Press [ENTER] to Use on Companion"
            if it_def.item_type == ItemType.CONSUMABLE
            else "Press [ENTER] to Equip on Companion"
        )
        bonuses: list[str] = []
        sb = it_def.stat_bonus
        if sb:
            if sb.attack:
                bonuses.append(f"+{sb.attack} ATK")
            if sb.defense:
                bonuses.append(f"+{sb.defense} DEF")
            if sb.magic_attack:
                bonuses.append(f"+{sb.magic_attack} MAG")
            if sb.magic_defense:
                bonuses.append(f"+{sb.magic_defense} MDEF")
            if sb.speed:
                bonuses.append(f"+{sb.speed} SPD")
            if sb.max_hp:
                bonuses.append(f"+{sb.max_hp} HP")
            if sb.max_mp:
                bonuses.append(f"+{sb.max_mp} MP")
        bonus_line = f"<br><font color='#8CD8FF'>Bonuses: {', '.join(bonuses)}</font>" if bonuses else ""
        return (
            f"<b><font color='#FFE078' size=5>{html.escape(it_def.name)}</font></b><br>"
            f"Type: {html.escape(it_def.item_type.name.title())}  •  Value: {it_def.value} G"
            f"{bonus_line}<br><br>"
            f"{html.escape(it_def.description)}<br><br>"
            f"<font color='#8CF0A0'>{action_hint}</font>"
        )

    def _update_inventory_tab_in_place(self) -> None:
        items = list(self.session.party.inventory.items())
        if not items:
            return
        self.item_index = min(self.item_index, len(items) - 1)
        for idx, (btn, base_text) in enumerate(self._inv_buttons):
            is_sel = idx == self.item_index
            want_cls = "@rpg_button_selected" if is_sel else "@rpg_button"
            if (btn.class_ids or [None])[-1] != want_cls:
                btn.change_object_id(ObjectID(class_id=want_cls))
                prefix = "> " if is_sel else "  "
                btn.set_text(f"{prefix}{base_text}")
        if self._inv_desc_box is not None:
            sel_id, _ = items[self.item_index]
            self._inv_desc_box.set_text(self._format_item_info_html(sel_id))

    def _build_equipment_tab(self, mgr, r) -> None:
        members = self.session.party.active_members
        if not members:
            return
        self.char_index = min(self.char_index, len(members) - 1)
        char = members[self.char_index]

        UILabel(
            relative_rect=r(28, 120, 1224, 34),
            text=f"<  {char.name} ({char.class_id.replace('_', ' ').title()})  >   [Left/Right to Switch]",
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@sub_header_label"),
        )

        left_panel = UIPanel(
            relative_rect=r(28, 160, 600, 478),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(left_panel, self.ui_manager)
        right_panel = UIPanel(
            relative_rect=r(648, 160, 604, 478),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(right_panel, self.ui_manager)

        self._equip_sig = (char.id, char.equipment.weapon, char.equipment.armor, char.equipment.accessory)
        self._equip_cards.clear()
        slots = [
            ("Weapon", char.equipment.weapon),
            ("Armor", char.equipment.armor),
            ("Accessory", char.equipment.accessory),
        ]
        for idx, (slot_name, eq_id) in enumerate(slots):
            is_sel = idx == self.slot_index
            eq_name = (
                ITEM_REGISTRY[eq_id].name
                if eq_id and eq_id in ITEM_REGISTRY
                else "None (Empty)"
            )
            card = UIPanel(
                relative_rect=r(28, 28 + idx * 142, 544, 122),
                starting_height=3,
                manager=mgr,
                container=left_panel,
                object_id=ObjectID(class_id="@rpg_card_selected" if is_sel else "@rpg_card"),
            )
            prefix = "> " if is_sel else ""
            slot_lbl = UILabel(
                relative_rect=r(18, 14, 280, 32),
                text=f"{prefix}{slot_name}",
                manager=mgr,
                container=card,
                object_id=ObjectID(class_id="@sub_header_label" if is_sel else "label"),
            )
            self._equip_cards.append((card, slot_lbl, slot_name))
            UILabel(
                relative_rect=r(310, 16, 238, 28),
                text="[ENTER] Replace / Equip",
                manager=mgr,
                container=card,
                object_id=ObjectID(class_id="@footer_label"),
            )
            UILabel(
                relative_rect=r(24, 60, 520, 36),
                text=eq_name,
                manager=mgr,
                container=card,
                object_id=ObjectID(class_id="label" if eq_id else "@muted_label"),
            )

        prt = self.sprite_manager.get_portrait(char.id, size=128)
        if prt is not None:
            UIImage(
                relative_rect=r(32, 32, 128, 128),
                image_surface=prt,
                manager=mgr,
                container=right_panel,
            )
        eff = char.effective_stats
        stats_html = (
            f"<b><font color='#FFE078' size=5>Effective Stats</font></b><br><br>"
            f"<b>Max HP:</b> {eff.max_hp}<br>"
            f"<b>Max MP:</b> {eff.max_mp}<br>"
            f"<b>Attack:</b> {eff.attack}<br>"
            f"<b>Defense:</b> {eff.defense}<br>"
            f"<b>Magic Atk:</b> {eff.magic_attack}<br>"
            f"<b>Speed:</b> {eff.speed}"
        )
        UITextBox(
            html_text=stats_html,
            relative_rect=r(176, 28, 396, 422),
            manager=mgr,
            container=right_panel,
            object_id=ObjectID(class_id="@rpg_textbox_clean"),
        )

    def _update_equipment_tab_in_place(self) -> None:
        for idx, (card, slot_lbl, slot_name) in enumerate(self._equip_cards):
            is_sel = idx == self.slot_index
            want_cls = "@rpg_card_selected" if is_sel else "@rpg_card"
            if (card.class_ids or [None])[-1] != want_cls:
                card.change_object_id(ObjectID(class_id=want_cls))
                prefix = "> " if is_sel else ""
                slot_lbl.set_text(f"{prefix}{slot_name}")

    def _build_skill_tree_tab(self, mgr, r) -> None:
        members = self.session.party.active_members
        if not members:
            return
        self.char_index = min(self.char_index, len(members) - 1)
        char = members[self.char_index]
        tree = self.session.skill_trees.get(char.id)

        UILabel(
            relative_rect=r(28, 120, 1224, 34),
            text=f"<  {char.name}'s Talent Tree (Available SP: {char.skill_points})  >   [Left/Right to Switch]",
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@sub_header_label"),
        )

        left_panel = UIPanel(
            relative_rect=r(28, 160, 600, 478),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(left_panel, self.ui_manager)
        right_panel = UIPanel(
            relative_rect=r(648, 160, 604, 478),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(right_panel, self.ui_manager)

        if not tree or not tree.nodes:
            return

        node_ids = list(tree.nodes.keys())
        self.node_index = min(self.node_index, len(node_ids) - 1)

        # Build 2D tree graph layout grouped by tier (aligned by prereq x to avoid crossed lines)
        gx, gy, gw, gh = 24, 26, 544, 418
        tiers = sorted({tree.nodes[nid].tier for nid in node_ids})
        num_tiers = max(1, len(tiers))
        tier_rows: dict[int, list[str]] = {}
        centers: dict[str, tuple[int, int]] = {}
        for t_idx, t_val in enumerate(tiers):
            row_nodes = [nid for nid in node_ids if tree.nodes[nid].tier == t_val]
            if t_idx > 0:
                def _prereq_x(nid: str) -> float:
                    pres = [centers[p][0] for p in tree.nodes[nid].prerequisites if p in centers]
                    return sum(pres) / len(pres) if pres else float(gw / 2)

                row_nodes.sort(key=_prereq_x)
            tier_rows[t_val] = row_nodes
            cy = int(gh * (t_idx + 0.5) / num_tiers)
            for c_idx, nid in enumerate(row_nodes):
                cx = int(gw * (c_idx + 0.5) / max(1, len(row_nodes)))
                centers[nid] = (cx, cy)

        # Render branch connection lines behind node buttons
        graph_rect = r(gx, gy, gw, gh)
        line_surf = pygame.Surface((graph_rect.width, graph_rect.height), pygame.SRCALPHA)
        sx = graph_rect.width / gw
        sy = graph_rect.height / gh
        for nid in node_ids:
            node = tree.nodes[nid]
            x2, y2 = centers[nid]
            p2 = (int(x2 * sx), int(y2 * sy))
            for pre_id in node.prerequisites:
                if pre_id not in centers:
                    continue
                x1, y1 = centers[pre_id]
                p1 = (int(x1 * sx), int(y1 * sy))
                if nid in tree.unlocked_nodes and pre_id in tree.unlocked_nodes:
                    col, w = (230, 184, 76), 3
                elif pre_id in tree.unlocked_nodes:
                    col, w = (110, 175, 240), 3
                else:
                    col, w = (65, 78, 110), 2
                pygame.draw.line(line_surf, col, p1, p2, w)
                pygame.draw.circle(line_surf, col, p1, 4)
                pygame.draw.circle(line_surf, col, p2, 4)

        UIImage(
            relative_rect=graph_rect,
            image_surface=line_surf,
            manager=mgr,
            container=left_panel,
            starting_height=1,
        )

        # Render interactive node buttons at each tree coordinate
        self._skill_node_buttons.clear()
        self._skill_sig = (char.id, tuple(sorted(tree.unlocked_nodes)), char.skill_points)
        for idx, n_id in enumerate(node_ids):
            node = tree.nodes[n_id]
            cx, cy = centers[n_id]
            row_count = len(tier_rows[node.tier])
            btn_w = 248 if row_count >= 2 else 290
            btn_h = 54
            bx = gx + cx - btn_w // 2
            by = gy + cy - btn_h // 2

            is_sel = idx == self.node_index
            is_unlocked = n_id in tree.unlocked_nodes
            can_unlock, _ = tree.can_unlock(n_id, char.skill_points)
            badge = "[OK]" if is_unlocked else ("[*]" if can_unlock else "[ ]")
            btn = UIButton(
                relative_rect=r(bx, by, btn_w, btn_h),
                text=f"{badge} {node.name} ({node.cost_sp} SP)",
                manager=mgr,
                container=left_panel,
                starting_height=3,
                object_id=ObjectID(
                    class_id="@rpg_button_selected" if is_sel else "@rpg_button"
                ),
            )
            self._skill_node_buttons.append(btn)

        sel_id = node_ids[self.node_index]
        node = tree.nodes[sel_id]
        can_unlock, reason = tree.can_unlock(sel_id, char.skill_points)
        if sel_id in tree.unlocked_nodes:
            status_html = "<font color='#78E68C'><b>Status: UNLOCKED</b></font>"
        elif can_unlock:
            status_html = "<font color='#FFE078'><b>Status: READY TO UNLOCK (Press [ENTER])</b></font>"
        else:
            status_html = f"<font color='#EB7878'><b>Status: {html.escape(reason)}</b></font>"

        desc_html = (
            f"<b><font color='#FFE078' size=5>{html.escape(node.name)}</font></b><br>"
            f"<font color='#A6B0C8'>Type: {html.escape(node.node_type.name)} (Tier {node.tier})</font><br><br>"
            f"{html.escape(node.description)}<br><br>"
            f"{status_html}"
        )
        self._skill_desc_box = UITextBox(
            html_text=desc_html,
            relative_rect=r(32, 32, 540, 414),
            manager=mgr,
            container=right_panel,
            object_id=ObjectID(class_id="@rpg_textbox_clean"),
        )

    def _update_skill_tree_in_place(self) -> None:
        members = self.session.party.active_members
        if not members:
            return
        char = members[min(self.char_index, len(members) - 1)]
        tree = self.session.skill_trees.get(char.id)
        if not tree or not tree.nodes:
            return
        node_ids = list(tree.nodes.keys())
        self.node_index = min(self.node_index, len(node_ids) - 1)
        for idx, btn in enumerate(self._skill_node_buttons):
            want_cls = "@rpg_button_selected" if idx == self.node_index else "@rpg_button"
            if (btn.class_ids or [None])[-1] != want_cls:
                btn.change_object_id(ObjectID(class_id=want_cls))

        if self._skill_desc_box is not None:
            sel_id = node_ids[self.node_index]
            node = tree.nodes[sel_id]
            can_unlock, reason = tree.can_unlock(sel_id, char.skill_points)
            if sel_id in tree.unlocked_nodes:
                status_html = "<font color='#78E68C'><b>Status: UNLOCKED</b></font>"
            elif can_unlock:
                status_html = "<font color='#FFE078'><b>Status: READY TO UNLOCK (Press [ENTER])</b></font>"
            else:
                status_html = f"<font color='#EB7878'><b>Status: {html.escape(reason)}</b></font>"
            desc_html = (
                f"<b><font color='#FFE078' size=5>{html.escape(node.name)}</font></b><br>"
                f"<font color='#A6B0C8'>Type: {html.escape(node.node_type.name)} (Tier {node.tier})</font><br><br>"
                f"{html.escape(node.description)}<br><br>"
                f"{status_html}"
            )
            self._skill_desc_box.set_text(desc_html)

    def _build_save_tab(self, mgr, r) -> None:
        slots_box = UIPanel(
            relative_rect=r(240, 160, 800, 390),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(slots_box, self.ui_manager)
        self._save_buttons.clear()
        for idx, slot_num in enumerate([1, 2, 3]):
            summary = self.session.save_manager.get_slot_summary(slot_num)
            is_sel = idx == self.save_slot_index
            status_str = (
                f"Slot {slot_num}: {summary.party_leader_name} (Lv.{summary.party_leader_level}) - {summary.map_id}"
                if summary.exists
                else f"Slot {slot_num}: Empty"
            )
            prefix = "> " if is_sel else "  "
            btn = UIButton(
                relative_rect=r(52, 34 + idx * 112, 696, 88),
                text=prefix + status_str,
                manager=mgr,
                container=slots_box,
                object_id=ObjectID(
                    class_id="@rpg_button_selected" if is_sel else "@rpg_button"
                ),
            )
            self._save_buttons.append((btn, status_str))

    def _update_save_tab_in_place(self) -> None:
        for idx, (btn, status_str) in enumerate(self._save_buttons):
            is_sel = idx == self.save_slot_index
            want_cls = "@rpg_button_selected" if is_sel else "@rpg_button"
            if (btn.class_ids or [None])[-1] != want_cls:
                btn.change_object_id(ObjectID(class_id=want_cls))
                prefix = "> " if is_sel else "  "
                btn.set_text(prefix + status_str)

    def _build_return_tab(self, mgr, r) -> None:
        box = UIPanel(
            relative_rect=r(320, 240, 640, 200),
            starting_height=2,
            manager=mgr,
            container=self._tab_container,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(box, self.ui_manager)
        UILabel(
            relative_rect=r(54, 44, 532, 42),
            text="Ready to Return?",
            manager=mgr,
            container=box,
            object_id=ObjectID(class_id="@header_label"),
        )
        UILabel(
            relative_rect=r(40, 102, 560, 36),
            text="Press [ENTER] or [ESC] to resume exploration.",
            manager=mgr,
            container=box,
        )

    def _build_inventory_picker_modal(self, mgr, r) -> None:
        members = self.session.party.active_members
        items = list(self.session.party.inventory.items())
        if not members or not items or self.item_index >= len(items):
            return
        item_id, _ = items[self.item_index]
        it_def = ITEM_REGISTRY.get(item_id)
        item_name = it_def.name if it_def else item_id

        modal_h = 110 + len(members) * 56
        modal_y = (720 - modal_h) // 2
        self._modal_panel = UIPanel(
            relative_rect=r(340, modal_y, 600, modal_h),
            starting_height=10,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        verb = "Use" if (it_def and it_def.item_type == ItemType.CONSUMABLE) else "Equip"
        UILabel(
            relative_rect=r(24, 16, 552, 34),
            text=f"{verb} {item_name} on whom?",
            manager=mgr,
            container=self._modal_panel,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        for idx, char in enumerate(members):
            is_sel = idx == self.target_char_index
            prefix = "> " if is_sel else "  "
            UIButton(
                relative_rect=r(24, 62 + idx * 54, 552, 46),
                text=f"{prefix}{char.name}  (HP {char.current_hp}/{char.base_stats.max_hp} | MP {char.current_mp}/{char.base_stats.max_mp})",
                manager=mgr,
                container=self._modal_panel,
                object_id=ObjectID(
                    class_id="@rpg_button_selected" if is_sel else "@rpg_button"
                ),
            )
        UILabel(
            relative_rect=r(24, modal_h - 36, 552, 24),
            text="[ENTER] Confirm   [ESC] Cancel",
            manager=mgr,
            container=self._modal_panel,
            object_id=ObjectID(class_id="@muted_label"),
        )

    def _build_equipment_picker_modal(self, mgr, r) -> None:
        options = self._get_compatible_equipment_options(self.slot_index)
        slot_name = ["Weapon", "Armor", "Accessory"][self.slot_index]
        visible = min(len(options), 6)
        modal_h = 120 + visible * 52
        modal_y = (720 - modal_h) // 2

        self._modal_panel = UIPanel(
            relative_rect=r(320, modal_y, 640, modal_h),
            starting_height=10,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        UILabel(
            relative_rect=r(24, 16, 592, 34),
            text=f"Choose {slot_name}",
            manager=mgr,
            container=self._modal_panel,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        scroll = UIScrollingContainer(
            relative_rect=r(20, 60, 600, modal_h - 104),
            manager=mgr,
            container=self._modal_panel,
        )
        scroll.set_scrollable_area_dimensions((570, max(100, len(options) * 52)))

        for idx, opt_id in enumerate(options):
            is_sel = idx == self.equip_picker_index
            prefix = "> " if is_sel else "  "
            label = (
                "[Unequip / Empty]"
                if opt_id is None
                else (ITEM_REGISTRY[opt_id].name if opt_id in ITEM_REGISTRY else opt_id)
            )
            UIButton(
                relative_rect=r(4, idx * 52, 562, 44),
                text=f"{prefix}{label}",
                manager=mgr,
                container=scroll,
                object_id=ObjectID(
                    class_id="@rpg_button_selected" if is_sel else "@rpg_button"
                ),
            )
        UILabel(
            relative_rect=r(24, modal_h - 36, 592, 24),
            text="[ENTER] Equip / Replace   [ESC] Cancel",
            manager=mgr,
            container=self._modal_panel,
            object_id=ObjectID(class_id="@muted_label"),
        )
