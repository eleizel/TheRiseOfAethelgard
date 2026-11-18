"""Title view with HD-2D welcome art and Clean Modern Dark-Slate pygame-gui overlay."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pygame_gui
from pygame_gui.core import ObjectID
from pygame_gui.elements import UIButton, UIImage, UILabel, UIPanel

from src.core.fsm import GameMode
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine, MusicContext
from src.frontends.pygame_ce.ui_manager import (
    GameUIManager,
    attach_ornate_corners,
    set_button_selected,
)

if TYPE_CHECKING:
    from src.core.session import GameSession


class TitleView:
    """Atmospheric title screen with welcome background and keyboard-only pygame-gui menu."""

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

        self.options = ["New Game", "Continue", "Toggle Mute", "Quit"]
        self.selected_index = 0
        self.time_sec = 0.0
        self.load_slot_open = False
        self.load_slot_index = 0

        self.background_image: pygame.Surface | None = None
        self._load_welcome_background()

        self.title_logo: pygame.Surface | None = None
        self.sword_cursor: pygame.Surface | None = None
        self._load_ui_assets()

        # pygame-gui widgets
        self._root_panel: UIPanel | None = None
        self._menu_panel: UIPanel | None = None
        self._title_logo_img: UIImage | None = None
        self._cursor_img: UIImage | None = None
        self._buttons: list[UIButton] = []
        self._load_panel: UIPanel | None = None
        self._load_buttons: list[UIButton] = []
        self._load_status_label: UILabel | None = None

    def _load_welcome_background(self) -> None:
        """Load and smoothscale welcome background art from assets/backgrounds/welcome."""
        assets_dir = Path(__file__).resolve().parents[4] / "assets" / "backgrounds" / "welcome"
        if not assets_dir.exists():
            return

        candidates = (
            list(assets_dir.glob("*.jpeg"))
            + list(assets_dir.glob("*.jpg"))
            + list(assets_dir.glob("*.png"))
        )
        if not candidates:
            return

        try:
            raw = pygame.image.load(str(candidates[0]))
            if pygame.display.get_surface() is not None:
                raw = raw.convert()
            self.background_image = pygame.transform.smoothscale(
                raw, (self.view_width, self.view_height)
            )
        except Exception:
            self.background_image = None

    def _load_ui_assets(self) -> None:
        ui_dir = Path(__file__).resolve().parents[4] / "assets" / "ui"
        logo_path = ui_dir / "title_logo.png"
        if logo_path.exists():
            try:
                surf = pygame.image.load(str(logo_path))
                if pygame.display.get_surface() is not None:
                    surf = surf.convert_alpha()
                self.title_logo = surf
            except Exception:
                self.title_logo = None

        cursor_path = ui_dir / "sword_cursor.png"
        if cursor_path.exists():
            try:
                surf = pygame.image.load(str(cursor_path))
                if pygame.display.get_surface() is not None:
                    surf = surf.convert_alpha()
                self.sword_cursor = surf
            except Exception:
                self.sword_cursor = None

    def _build_ui(self) -> None:
        self.on_exit()
        mgr = self.ui_manager.manager
        r = self.ui_manager.rect

        if self.title_logo is not None:
            logo_rect = r(190, 0, 900, 300)
            scaled_logo = pygame.transform.smoothscale(self.title_logo, logo_rect.size)
            self._title_logo_img = UIImage(
                relative_rect=logo_rect,
                image_surface=scaled_logo,
                manager=mgr,
            )
            self._title_label = None
        else:
            self._title_logo_img = None
            self._title_label = UILabel(
                relative_rect=r(140, 58, 1000, 90),
                text="THE RISE OF AETHELGARD",
                manager=mgr,
                object_id=ObjectID(class_id="@title_hero"),
            )

        self._subtitle_label = UILabel(
            relative_rect=r(240, 290, 800, 36),
            text="A 16-BIT HD-2D CHRONICLE",
            manager=mgr,
            object_id=ObjectID(class_id="@title_subtitle"),
        )

        self._menu_panel = UIPanel(
            relative_rect=r(420, 350, 465, 280),
            starting_height=1,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(self._menu_panel, self.ui_manager)

        self._buttons = []
        btn_w, btn_h = 280, 44
        btn_x = 88
        start_y = 32
        step_y = 56
        for idx, opt in enumerate(self.options):
            is_sel = idx == self.selected_index
            btn = UIButton(
                relative_rect=r(btn_x, start_y + idx * step_y, btn_w, btn_h),
                text=opt,
                manager=mgr,
                container=self._menu_panel,
                object_id=ObjectID(
                    class_id="@title_button_selected" if is_sel else "@title_button"
                ),
            )
            self._buttons.append(btn)

        if self.sword_cursor is not None:
            cur_rect = r(44, start_y + self.selected_index * step_y + 6, 32, 32)
            scaled_cur = pygame.transform.smoothscale(self.sword_cursor, cur_rect.size)
            self._cursor_img = UIImage(
                relative_rect=cur_rect,
                image_surface=scaled_cur,
                manager=mgr,
                container=self._menu_panel,
                starting_height=4,
            )
        else:
            self._cursor_img = None

        self._version_label = UILabel(
            relative_rect=r(24, 674, 300, 32),
            text="v0.1.0 Pre-Alpha",
            manager=mgr,
            object_id=ObjectID(class_id="@muted_label"),
        )
        self._credits_label = UILabel(
            relative_rect=r(700, 674, 556, 32),
            text="© 2026  •  DEVELOPED BY: SERGIO ESPERALTA GATA",
            manager=mgr,
            object_id=ObjectID(class_id="@footer_label"),
        )
        self._root_panel = self._menu_panel

    def _refresh_button_selection(self) -> None:
        r = self.ui_manager.rect
        start_y = 32
        step_y = 56
        for idx, btn in enumerate(self._buttons):
            is_sel = idx == self.selected_index
            set_button_selected(
                btn,
                is_sel,
                base_class="@title_button",
                selected_class="@title_button_selected",
            )
        if self._cursor_img is not None:
            cur_rect = r(44, start_y + self.selected_index * step_y + 6, 32, 32)
            self._cursor_img.set_relative_position(cur_rect.topleft)

    def on_enter(self) -> None:
        if self.music_engine:
            self.music_engine.set_context(MusicContext.WELCOME)
        self._build_ui()

    def on_exit(self) -> None:
        self._close_load_modal()
        for attr in (
            "_title_logo_img",
            "_title_label",
            "_subtitle_label",
            "_cursor_img",
            "_menu_panel",
            "_version_label",
            "_credits_label",
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.kill()
                setattr(self, attr, None)
        self._buttons.clear()
        self._root_panel = None

    def _open_load_modal(self) -> None:
        self._close_load_modal()
        self.load_slot_open = True
        # Default selection to first occupied slot (or Slot 1 if all empty)
        self.load_slot_index = 0
        for idx, slot_num in enumerate((1, 2, 3)):
            if self.session.save_manager.get_slot_summary(slot_num).exists:
                self.load_slot_index = idx
                break

        mgr = self.ui_manager.manager
        r = self.ui_manager.rect
        self._load_panel = UIPanel(
            relative_rect=r(280, 210, 720, 380),
            starting_height=8,
            manager=mgr,
            object_id=ObjectID(class_id="@rpg_panel_gold"),
        )
        attach_ornate_corners(self._load_panel, self.ui_manager)
        UILabel(
            relative_rect=r(24, 18, 672, 34),
            text="Select Save Slot to Load",
            manager=mgr,
            container=self._load_panel,
            object_id=ObjectID(class_id="@sub_header_label"),
        )
        self._load_buttons.clear()
        for idx, slot_num in enumerate((1, 2, 3)):
            summary = self.session.save_manager.get_slot_summary(slot_num)
            label = (
                f"Slot {slot_num}: {summary.party_leader_name} (Lv.{summary.party_leader_level}) - {summary.map_id}"
                if summary.exists
                else f"Slot {slot_num}: Empty"
            )
            is_sel = idx == self.load_slot_index
            btn = UIButton(
                relative_rect=r(36, 68 + idx * 58, 648, 48),
                text=f"> {label}" if is_sel else f"  {label}",
                manager=mgr,
                container=self._load_panel,
                object_id=ObjectID(class_id="@rpg_button_selected" if is_sel else "@rpg_button"),
            )
            self._load_buttons.append(btn)

        back_sel = self.load_slot_index == 3
        back_btn = UIButton(
            relative_rect=r(36, 250, 648, 46),
            text="> Back" if back_sel else "  Back",
            manager=mgr,
            container=self._load_panel,
            object_id=ObjectID(class_id="@rpg_button_selected" if back_sel else "@rpg_button"),
        )
        self._load_buttons.append(back_btn)

        self._load_status_label = UILabel(
            relative_rect=r(36, 316, 648, 32),
            text="[W/S] Select Slot   [ENTER] Load   [ESC] Cancel",
            manager=mgr,
            container=self._load_panel,
            object_id=ObjectID(class_id="@muted_label"),
        )

    def _close_load_modal(self) -> None:
        self.load_slot_open = False
        if self._load_panel is not None:
            self._load_panel.kill()
            self._load_panel = None
        self._load_buttons.clear()
        self._load_status_label = None

    def _refresh_load_selection(self) -> None:
        for idx, btn in enumerate(self._load_buttons):
            is_sel = idx == self.load_slot_index
            raw = btn.text.lstrip("> ").strip()
            btn.set_text(f"> {raw}" if is_sel else f"  {raw}")
            set_button_selected(btn, is_sel)

    def _confirm_load_slot(self) -> None:
        if self.load_slot_index >= 3:
            self._close_load_modal()
            return
        slot_num = self.load_slot_index + 1
        if self.session.load_game(slot_id=slot_num):
            self._close_load_modal()
            self.session.transition_to(GameMode.EXPLORATION)
        elif self._load_status_label is not None:
            self._load_status_label.set_text(f"Slot {slot_num} is empty.")

    def on_resize(self, width: int, height: int) -> None:
        was_load_open = self.load_slot_open
        self._build_ui()
        if was_load_open:
            self._open_load_modal()

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.load_slot_open:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.load_slot_index = (self.load_slot_index - 1) % 4
                    self._refresh_load_selection()
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.load_slot_index = (self.load_slot_index + 1) % 4
                    self._refresh_load_selection()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._confirm_load_slot()
                elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    self._close_load_modal()
            elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                for idx, btn in enumerate(self._load_buttons):
                    if event.ui_element == btn:
                        self.load_slot_index = idx
                        self._confirm_load_slot()
                        return
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected_index = (self.selected_index - 1) % len(self.options)
                self._refresh_button_selection()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected_index = (self.selected_index + 1) % len(self.options)
                self._refresh_button_selection()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._choose_option()
            elif event.key == pygame.K_m and self.music_engine:
                self.music_engine.toggle_mute()
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            for idx, btn in enumerate(self._buttons):
                if event.ui_element == btn:
                    self.selected_index = idx
                    self._refresh_button_selection()
                    self._choose_option()
                    return

    def _choose_option(self) -> None:
        choice = self.options[self.selected_index]
        if choice == "New Game":
            self.session.initialize_new_game()
            self.session.pending_dialogue_id = "prologue_intro"
            self.session.transition_to(GameMode.DIALOGUE)
        elif choice == "Continue":
            self._open_load_modal()
        elif choice == "Toggle Mute":
            if self.music_engine:
                self.music_engine.toggle_mute()
        elif choice == "Quit":
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def update(self, dt: float) -> None:
        self.time_sec += dt

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the atmospheric welcome background onto the 640x360 world canvas."""
        if self.background_image is not None:
            surface.blit(self.background_image, (0, 0))
        else:
            for y in range(self.view_height):
                ratio = y / self.view_height
                r = int(12 * (1.0 - ratio) + 28 * ratio)
                g = int(14 * (1.0 - ratio) + 24 * ratio)
                b = int(32 * (1.0 - ratio) + 55 * ratio)
                pygame.draw.line(surface, (r, g, b), (0, y), (self.view_width, y))

            mountains = [
                (0, 240), (120, 180), (220, 210), (340, 160),
                (460, 200), (560, 175), (640, 220), (640, 360), (0, 360),
            ]
            pygame.draw.polygon(surface, (18, 16, 28), mountains)
            for tx in range(0, self.view_width + 40, 35):
                pts = [(tx, 360), (tx + 18, 260), (tx + 36, 360)]
                pygame.draw.polygon(surface, (10, 8, 18), pts)
