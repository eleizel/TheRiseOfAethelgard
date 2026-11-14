"""Headless integration test for PygameApp lifecycle, views, and rendering."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from src.core.fsm import GameMode
from src.core.session import GameSession
from src.data.enemies import create_enemy
from src.frontends.pygame_ce.app import PygameApp
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine
from src.systems.combat.round_combat import RoundCombat


def test_headless_app_lifecycle():
    session = GameSession(seed=999)
    music = DynamicMusicEngine()
    app = PygameApp(session=session, music_engine=music, headless=True)

    # 1. Starts in TITLE mode
    assert app.session.current_mode == GameMode.TITLE
    for _ in range(5):
        app.update(dt=0.016)
        app.draw()

    # 2. Transition to EXPLORATION
    session.initialize_new_game()
    app.update(dt=0.016)
    app.draw()

    assert app.session.current_mode == GameMode.EXPLORATION
    assert app.active_mode == GameMode.EXPLORATION
    for _ in range(10):
        app.update(dt=0.016)
        app.draw()

    assert session.play_time_seconds > 0.0

    # 3. Transition to MENU (Camp Journal)
    session.transition_to(GameMode.MENU)
    app.update(dt=0.016)
    app.draw()

    assert app.session.current_mode == GameMode.MENU
    assert app.active_mode == GameMode.MENU
    for _ in range(5):
        app.update(dt=0.016)
        app.draw()

    # 4. Return to EXPLORATION
    session.transition_to(GameMode.EXPLORATION)
    app.update(dt=0.016)
    app.draw()
    assert app.session.current_mode == GameMode.EXPLORATION

    # 5. Enter COMBAT
    session.combat = RoundCombat(
        party=session.party,
        enemies=[create_enemy("thornvein_creeper", "creeper_1")],
        seed=101,
    )
    session.transition_to(GameMode.COMBAT)
    app.update(dt=0.016)
    app.draw()

    assert app.session.current_mode == GameMode.COMBAT
    assert app.active_mode == GameMode.COMBAT
    for _ in range(10):
        app.update(dt=0.016)
        app.draw()
