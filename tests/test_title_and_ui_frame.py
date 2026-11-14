"""Unit tests for the pygame-gui HD overlay system and title screen presentation."""

from __future__ import annotations

import os

import pygame
import pytest

from src.core.session import GameSession
from src.frontends.pygame_ce.ui_manager import GameUIManager
from src.frontends.pygame_ce.views.title_view import TitleView


@pytest.fixture(autouse=True)
def init_pygame():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1280, 720))
    yield


def test_game_ui_manager_theme_and_mouse_suppression():
    """Verify GameUIManager loads theme.json, scales rects, and suppresses mouse events."""
    ui_mgr = GameUIManager((1280, 720))
    assert ui_mgr.rect(100, 50, 200, 100) == pygame.Rect(100, 50, 200, 100)

    ui_mgr.set_window_size(1920, 1080)
    assert ui_mgr.rect(100, 50, 200, 100) == pygame.Rect(150, 75, 300, 150)

    mouse_ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    assert ui_mgr.process_event(mouse_ev) is False


def test_title_view_presentation_and_keyboard_navigation():
    """Verify TitleView renders background on canvas, HD pygame-gui menu, and handles keyboard nav."""
    session = GameSession(seed=42)
    ui_mgr = GameUIManager((1280, 720))
    view = TitleView(session=session, view_width=640, view_height=360, ui_manager=ui_mgr)
    view.on_enter()

    assert view.background_image is not None

    canvas = pygame.Surface((640, 360))
    screen = pygame.Surface((1280, 720))
    view.selected_index = 1  # "Continue"
    view.update(dt=0.1)
    ui_mgr.update(0.1)
    view.draw(canvas)
    ui_mgr.draw(screen)

    assert canvas.get_at((320, 180)).a == 255

    # Keyboard navigation
    view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    assert view.selected_index == 2  # "Toggle Mute"

    view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    assert view.selected_index == 1  # back to "Continue"


def test_all_game_views_render_with_pygame_gui_overlay():
    """Verify DialogueView, CombatView, ExplorationView, and MenuView render with GameUIManager."""
    from src.data.dialogues import DialogueNode
    from src.data.enemies import create_enemy
    from src.frontends.pygame_ce.views.combat_view import CombatView
    from src.frontends.pygame_ce.views.dialogue_view import DialogueView
    from src.frontends.pygame_ce.views.exploration_view import ExplorationView
    from src.frontends.pygame_ce.views.menu_view import MenuView
    from src.systems.combat.round_combat import RoundCombat

    session = GameSession(seed=42)
    session.initialize_new_game()
    ui_mgr = GameUIManager((1280, 720))
    canvas = pygame.Surface((640, 360))
    screen = pygame.Surface((1280, 720))

    # 1. DialogueView
    dlg_view = DialogueView(session=session, ui_manager=ui_mgr)
    dlg_view.current_node = DialogueNode(
        id="test_node",
        speaker_id="rowan",
        speaker_name="Rowan",
        text="The new HD interface now frames all dialogue across the realm.",
    )
    dlg_view.displayed_chars = 999
    dlg_view._rebuild_node_ui()
    dlg_view.update(0.016)
    ui_mgr.update(0.016)
    dlg_view.draw(canvas)
    ui_mgr.draw(screen)
    assert len(ui_mgr.manager.get_root_container().elements) > 0
    dlg_view.on_exit()

    # 2. CombatView
    enemy = create_enemy("thornvein_creeper", "e_1")
    combat = RoundCombat(party=session.party, enemies=[enemy], seed=42)
    session.combat = combat
    combat_view = CombatView(session=session, ui_manager=ui_mgr)
    combat_view.on_enter()
    combat_view.update(0.016)
    ui_mgr.update(0.016)
    combat_view.draw(canvas)
    ui_mgr.draw(screen)
    assert len(ui_mgr.manager.get_root_container().elements) > 0
    combat_view.on_exit()

    # 3. ExplorationView
    exp_view = ExplorationView(session=session, ui_manager=ui_mgr)
    exp_view.on_enter()
    exp_view.update(0.016)
    ui_mgr.update(0.016)
    exp_view.draw(canvas)
    ui_mgr.draw(screen)
    assert len(ui_mgr.manager.get_root_container().elements) > 0
    exp_view.on_exit()

    # 4. MenuView across all tabs
    menu_view = MenuView(session=session, ui_manager=ui_mgr)
    menu_view.on_enter()
    for tab_idx in range(len(menu_view.tabs)):
        menu_view.active_tab_idx = tab_idx
        menu_view._rebuild_ui()
        menu_view.update(0.016)
        ui_mgr.update(0.016)
        menu_view.draw(canvas)
        ui_mgr.draw(screen)
        assert len(ui_mgr.manager.get_root_container().elements) > 0
    menu_view.on_exit()

