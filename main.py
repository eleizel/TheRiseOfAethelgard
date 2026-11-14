"""The Rise of Aethelgard - Main Entry Point."""

from __future__ import annotations

import sys
from src.core.session import GameSession
from src.frontends.pygame_ce.app import PygameApp
from src.frontends.pygame_ce.music_engine import DynamicMusicEngine


def main() -> None:
    session = GameSession()
    music_engine = DynamicMusicEngine()
    app = PygameApp(session=session, music_engine=music_engine)
    app.run()


if __name__ == "__main__":
    main()
