"""PygameApp window manager, display scaling pipeline, and main loop."""

from __future__ import annotations

import sys
from typing import Any

import pygame

from src.core.fsm import GameMode
from src.core.session import GameSession
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine
from src.frontends.pygame_ce.ui_manager import GameUIManager
from src.frontends.pygame_ce.views.combat_view import CombatView
from src.frontends.pygame_ce.views.dialogue_view import DialogueView
from src.frontends.pygame_ce.views.exploration_view import ExplorationView
from src.frontends.pygame_ce.views.menu_view import MenuView
from src.frontends.pygame_ce.views.party_view import PartyView
from src.frontends.pygame_ce.views.title_view import TitleView

CANVAS_WIDTH = 640
CANVAS_HEIGHT = 360
DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 720


class PygameApp:
    """Main application manager for The Rise of Aethelgard."""

    def __init__(
        self,
        session: GameSession | None = None,
        music_engine: DynamicMusicEngine | None = None,
        headless: bool = False,
    ) -> None:
        self.headless = headless
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        self.session = session or GameSession()
        self.music_engine = music_engine or DynamicMusicEngine()

        self.canvas = pygame.Surface((CANVAS_WIDTH, CANVAS_HEIGHT))
        self.window_width = DEFAULT_WINDOW_WIDTH
        self.window_height = DEFAULT_WINDOW_HEIGHT
        self.is_fullscreen = False

        if not self.headless:
            pygame.display.set_caption("The Rise of Aethelgard")
            self.screen = pygame.display.set_mode(
                (self.window_width, self.window_height),
                pygame.RESIZABLE,
            )
        else:
            self.screen = pygame.Surface((self.window_width, self.window_height))

        self.clock = pygame.time.Clock()
        self.is_running = True
        self.ui_manager = GameUIManager((self.window_width, self.window_height))

        # Views
        self.views: dict[GameMode, Any] = {
            GameMode.TITLE: TitleView(self.session, self.music_engine, CANVAS_WIDTH, CANVAS_HEIGHT, ui_manager=self.ui_manager),
            GameMode.EXPLORATION: ExplorationView(self.session, self.music_engine, CANVAS_WIDTH, CANVAS_HEIGHT, ui_manager=self.ui_manager),
            GameMode.COMBAT: CombatView(self.session, self.music_engine, CANVAS_WIDTH, CANVAS_HEIGHT, ui_manager=self.ui_manager),
            GameMode.MENU: MenuView(self.session, self.music_engine, CANVAS_WIDTH, CANVAS_HEIGHT, ui_manager=self.ui_manager),
            GameMode.PARTY: PartyView(self.session, self.music_engine, CANVAS_WIDTH, CANVAS_HEIGHT, ui_manager=self.ui_manager),
            GameMode.DIALOGUE: DialogueView(self.session, self.music_engine, CANVAS_WIDTH, CANVAS_HEIGHT, ui_manager=self.ui_manager),
        }
        self.active_mode = self.session.current_mode
        self._get_active_view().on_enter()

    def _get_active_view(self) -> Any:
        return self.views.get(self.session.current_mode, self.views[GameMode.TITLE])

    def toggle_fullscreen(self) -> None:
        if self.headless:
            return
        self.is_fullscreen = not self.is_fullscreen
        flags = pygame.FULLSCREEN if self.is_fullscreen else pygame.RESIZABLE
        size = (0, 0) if self.is_fullscreen else (self.window_width, self.window_height)
        self.screen = pygame.display.set_mode(size, flags)
        w, h = self.screen.get_size()
        self.ui_manager.set_window_size(w, h)
        active = self._get_active_view()
        if hasattr(active, "on_resize"):
            active.on_resize(w, h)

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                    continue

            if event.type == pygame.VIDEORESIZE and not self.is_fullscreen:
                self.window_width, self.window_height = event.w, event.h
                self.screen = pygame.display.set_mode(
                    (self.window_width, self.window_height), pygame.RESIZABLE
                )
                self.ui_manager.set_window_size(self.window_width, self.window_height)
                active = self._get_active_view()
                if hasattr(active, "on_resize"):
                    active.on_resize(self.window_width, self.window_height)

            self.ui_manager.process_event(event)
            # Delegate to active view
            self._get_active_view().handle_event(event)

    def update(self, dt: float) -> None:
        # Check if mode switched
        if self.session.current_mode != self.active_mode:
            prev_view = self.views.get(self.active_mode)
            if prev_view and hasattr(prev_view, "on_exit"):
                prev_view.on_exit()

            self.active_mode = self.session.current_mode
            if self.active_mode == GameMode.DIALOGUE:
                tree_id = getattr(self.session, "pending_dialogue_id", None) or "prologue_intro"
                self.views[GameMode.DIALOGUE].start_dialogue(tree_id)
                self.session.pending_dialogue_id = None
            elif self.active_mode in self.views:
                self.views[self.active_mode].on_enter()

        self._get_active_view().update(dt)
        self.ui_manager.update(dt)

    def draw(self) -> None:
        self.canvas.fill((12, 14, 24))
        # If in dialogue mode, render exploration backdrop beneath dialogue window
        if self.session.current_mode == GameMode.DIALOGUE:
            self.views[GameMode.EXPLORATION].draw(self.canvas)
            self.views[GameMode.DIALOGUE].draw(self.canvas)
        else:
            self._get_active_view().draw(self.canvas)

        # Scale canvas to screen preserving aspect ratio with letterboxing if needed
        screen_w, screen_h = self.screen.get_size()
        scale = min(screen_w / CANVAS_WIDTH, screen_h / CANVAS_HEIGHT)
        scaled_w = int(CANVAS_WIDTH * scale)
        scaled_h = int(CANVAS_HEIGHT * scale)

        scaled_canvas = pygame.transform.scale(self.canvas, (scaled_w, scaled_h))
        dest_x = (screen_w - scaled_w) // 2
        dest_y = (screen_h - scaled_h) // 2

        self.screen.fill((0, 0, 0))
        self.screen.blit(scaled_canvas, (dest_x, dest_y))

        active_view = self._get_active_view()
        if hasattr(active_view, "draw_screen_overlay"):
            active_view.draw_screen_overlay(self.screen)

        self.ui_manager.draw(self.screen)

        if not self.headless:
            pygame.display.flip()

    def run(self) -> None:
        """Run application game loop at 60 FPS."""
        while self.is_running:
            dt = self.clock.tick(60) / 1000.0
            dt = min(0.05, dt)  # Cap large delta time spikes
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()
