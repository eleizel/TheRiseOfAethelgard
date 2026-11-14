"""Wrapper around pygame_gui.UIManager providing keyboard-only RPG theming and HD overlay scaling."""

from __future__ import annotations

import os
from pathlib import Path

import pygame
import pygame_gui
from pygame_gui.core import ObjectID

from src.entities.actor import StatusType

MOUSE_EVENT_TYPES = {
    pygame.MOUSEMOTION,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
    pygame.MOUSEWHEEL,
}


class GameUIManager:
    """Manages the HD-2D pygame_gui overlay at native window resolution."""

    REF_WIDTH = 1280
    REF_HEIGHT = 720

    def __init__(self, window_size: tuple[int, int] = (1280, 720)) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        if pygame.display.get_surface() is None:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            pygame.display.set_mode(window_size)

        self.window_width, self.window_height = window_size
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        theme_path = project_root / "assets" / "ui" / "theme.json"

        self.manager = pygame_gui.UIManager(
            window_size,
            theme_path=str(theme_path) if theme_path.exists() else None,
        )

    def set_window_size(self, width: int, height: int) -> None:
        """Update UIManager resolution when the game window resizes or toggles fullscreen."""
        self.window_width = max(320, width)
        self.window_height = max(180, height)
        self.manager.set_window_resolution((self.window_width, self.window_height))

    def process_event(self, event: pygame.event.Event) -> bool:
        """Forward non-mouse events to pygame_gui (enforcing keyboard-only RPG controls)."""
        if event.type in MOUSE_EVENT_TYPES:
            return False
        return self.manager.process_events(event)

    def update(self, dt: float) -> None:
        self.manager.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        self.manager.draw_ui(screen)

    def clear(self) -> None:
        """Clear all active UI elements from the root container."""
        self.manager.clear_and_reset()

    def rect(self, x: float, y: float, w: float, h: float) -> pygame.Rect:
        """Scale a 1280x720 reference rectangle to the current window dimensions."""
        sx = self.window_width / self.REF_WIDTH
        sy = self.window_height / self.REF_HEIGHT
        return pygame.Rect(
            int(round(x * sx)),
            int(round(y * sy)),
            max(1, int(round(w * sx))),
            max(1, int(round(h * sy))),
        )


def set_button_selected(
    button: pygame_gui.elements.UIButton,
    selected: bool,
    base_class: str = "@rpg_button",
    selected_class: str = "@rpg_button_selected",
) -> None:
    """Apply selected/unselected visual class ID to a UIButton without mouse hover."""
    target_class = selected_class if selected else base_class
    current_ids = button.object_ids
    if current_ids and current_ids[-1] == target_class:
        return
    button.change_object_id(ObjectID(class_id=target_class))


_CORNER_BASE_CACHE: dict[str, pygame.Surface] = {}
_CORNER_SCALED_CACHE: dict[tuple[str, int, int], pygame.Surface] = {}
_CORNER_NAMES = ("top_left", "top_right", "bottom_left", "bottom_right")


def _get_corner_surface(corner_name: str, width: int, height: int) -> pygame.Surface | None:
    if corner_name not in _CORNER_BASE_CACHE:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        corner_path = project_root / "assets" / "ui" / f"corner_{corner_name}_48.png"
        if not corner_path.exists():
            return None
        _CORNER_BASE_CACHE[corner_name] = pygame.image.load(str(corner_path)).convert_alpha()

    base = _CORNER_BASE_CACHE[corner_name]
    if base.get_size() == (width, height):
        return base
    key = (corner_name, width, height)
    if key not in _CORNER_SCALED_CACHE:
        _CORNER_SCALED_CACHE[key] = pygame.transform.smoothscale(base, (width, height))
    return _CORNER_SCALED_CACHE[key]


def attach_ornate_corners(
    panel: pygame_gui.elements.UIPanel,
    ui_manager: GameUIManager,
    starting_height: int = 5,
) -> list[pygame_gui.elements.UIImage]:
    """Attach the 48x48 ornate golden corners onto the four corners of a UIPanel."""
    scaled_rect = ui_manager.rect(0, 0, 48, 48)
    pw, ph = panel.get_container().get_size()
    cw = max(1, min(scaled_rect.width, pw // 2))
    ch = max(1, min(scaled_rect.height, ph // 2))

    positions = {
        "top_left": (0, 0),
        "top_right": (pw - cw, 0),
        "bottom_left": (0, ph - ch),
        "bottom_right": (pw - cw, ph - ch),
    }

    images: list[pygame_gui.elements.UIImage] = []
    for name in _CORNER_NAMES:
        surf = _get_corner_surface(name, cw, ch)
        if surf is None:
            continue
        x, y = positions[name]
        img = pygame_gui.elements.UIImage(
            relative_rect=pygame.Rect(x, y, cw, ch),
            image_surface=surf,
            manager=ui_manager.manager,
            container=panel,
            starting_height=starting_height,
        )
        images.append(img)
    return images


class StatBar(pygame_gui.elements.UIProgressBar):
    """Progress bar displaying ``<prefix> <current>/<max>`` instead of a percentage."""

    def __init__(
        self,
        relative_rect: pygame.Rect,
        manager: pygame_gui.UIManager,
        prefix: str = "",
        current_value: int = 0,
        max_value: int = 1,
        container: pygame_gui.core.interfaces.IContainerLikeInterface | None = None,
        object_id: ObjectID | str | None = None,
    ) -> None:
        self._prefix = prefix
        self._current_value = max(0, int(current_value))
        self._max_value = max(1, int(max_value))
        super().__init__(
            relative_rect=relative_rect,
            manager=manager,
            container=container,
            object_id=object_id,
        )
        self.set_values(self._current_value, self._max_value)

    def status_text(self) -> str:
        """Return ``<prefix> <current>/<max>`` (or ``<current>/<max>`` when prefix is empty)."""
        if self._prefix:
            return f"{self._prefix} {self._current_value}/{self._max_value}"
        return f"{self._current_value}/{self._max_value}"

    def set_values(self, current_value: int, max_value: int) -> None:
        """Update current/max values and force pygame_gui to redraw the bar text."""
        self._current_value = max(0, int(current_value))
        self._max_value = max(1, int(max_value))
        pct = min(100.0, max(0.0, (self._current_value / self._max_value) * 100.0))
        # Force UIProgressBar to rebuild status text even when pct matches previous value.
        self.current_progress = -1.0
        self.set_current_progress(pct)


_STATUS_ICON_FILENAMES: dict[StatusType, str] = {
    StatusType.POISON: "status_poison.png",
    StatusType.BLEED: "status_bleed.png",
    StatusType.BURN: "status_burn.png",
    StatusType.STUN: "status_stun.png",
    StatusType.BLIND: "status_blind.png",
    StatusType.VULNERABLE: "status_vulnerable.png",
    StatusType.WEAKEN: "status_weaken.png",
    StatusType.REGEN: "status_regeneration.png",
    StatusType.ATTACK_UP: "status_attack_up.png",
    StatusType.DEFENSE_UP: "status_fortify.png",
    StatusType.SPEED_UP: "status_haste.png",
}
_STATUS_ICON_BASE_CACHE: dict[StatusType, pygame.Surface | None] = {}
_STATUS_ICON_SCALED_CACHE: dict[tuple[StatusType, int], pygame.Surface] = {}


def get_status_icon(status: StatusType, size: int = 20) -> pygame.Surface | None:
    """Load and cache a status icon surface scaled to ``size x size`` pixels."""
    if status not in _STATUS_ICON_BASE_CACHE:
        filename = _STATUS_ICON_FILENAMES.get(status)
        if not filename:
            _STATUS_ICON_BASE_CACHE[status] = None
        else:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            icon_path = project_root / "assets" / "sprites" / "status" / filename
            if icon_path.exists():
                _STATUS_ICON_BASE_CACHE[status] = pygame.image.load(str(icon_path)).convert_alpha()
            else:
                _STATUS_ICON_BASE_CACHE[status] = None

    base = _STATUS_ICON_BASE_CACHE[status]
    if base is None:
        return None
    target_size = max(8, int(size))
    if base.get_size() == (target_size, target_size):
        return base
    key = (status, target_size)
    if key not in _STATUS_ICON_SCALED_CACHE:
        _STATUS_ICON_SCALED_CACHE[key] = pygame.transform.smoothscale(base, (target_size, target_size))
    return _STATUS_ICON_SCALED_CACHE[key]
