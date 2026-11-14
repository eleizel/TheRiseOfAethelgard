"""Combat background manager for loading and scaling map-specific battle backgrounds."""

from __future__ import annotations

import random
from pathlib import Path

import pygame


class CombatBackgroundManager:
    """Discovers, caches, and provides random combat background art per map.

    Supports extensible directory structures like:
    assets/backgrounds/combat/<map_name>/combat_background_XX.jpg (or .jpeg / .png)
    """

    def __init__(
        self,
        assets_dir: Path | str | None = None,
        view_width: int = 640,
        view_height: int = 360,
    ) -> None:
        if assets_dir is None:
            self.assets_root = Path(__file__).resolve().parent.parent.parent.parent / "assets"
        else:
            self.assets_root = Path(assets_dir)

        self.combat_bg_dir = self.assets_root / "backgrounds" / "combat"
        self.view_width = view_width
        self.view_height = view_height

        self._file_cache: dict[str, list[Path]] = {}
        self._scaled_cache: dict[Path, pygame.Surface] = {}

    def get_random_background(self, map_id: str, map_name: str = "") -> pygame.Surface | None:
        """Pick and return a random scaled combat background for the given map."""
        if not self.combat_bg_dir.exists():
            return None

        # Build candidate folder names
        candidates = []
        if map_name:
            candidates.append(map_name.lower().replace(" ", "_"))
            candidates.append(map_name.lower())
        if map_id:
            candidates.append(map_id.lower().replace(" ", "_"))
            candidates.append(map_id.lower())

        # Also check alias mappings
        aliases = {
            "briarwood_edge": "briarwood_verge",
        }
        if map_id in aliases:
            candidates.append(aliases[map_id])

        matched_dir: Path | None = None
        for cand in candidates:
            p = self.combat_bg_dir / cand
            if p.is_dir():
                matched_dir = p
                break

        if matched_dir is None:
            return None

        # Discover background files
        dir_key = str(matched_dir)
        if dir_key not in self._file_cache:
            exts = {".jpg", ".jpeg", ".png"}
            files = [
                f for f in matched_dir.iterdir()
                if f.is_file() and f.suffix.lower() in exts and "combat_background" in f.name.lower()
            ]
            self._file_cache[dir_key] = sorted(files)

        files = self._file_cache[dir_key]
        if not files:
            return None

        chosen_file = random.choice(files)
        if chosen_file in self._scaled_cache:
            return self._scaled_cache[chosen_file]

        try:
            raw_surf = pygame.image.load(str(chosen_file))
            if pygame.display.get_surface() is not None:
                raw_surf = raw_surf.convert()

            scaled = pygame.transform.smoothscale(raw_surf, (self.view_width, self.view_height))
            self._scaled_cache[chosen_file] = scaled
            return scaled
        except Exception:
            return None
