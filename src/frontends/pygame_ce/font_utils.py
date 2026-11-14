"""Font utilities providing clean typography and word-wrapped text rendering.

Prevents character dropouts (e.g. broken Freesansbold glyphs or missing Unicode symbols)
by prioritizing system fonts like Segoe UI / Arial with fallback to default, and offers
word-wrapping for text boxes throughout the game UI.
"""

from __future__ import annotations

from pathlib import Path

import pygame

_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Retrieve or create a cached font using Segoe UI/Arial or fallback."""
    if not pygame.font.get_init():
        pygame.font.init()

    key = (size, bold)
    if key in _FONT_CACHE:
        cached = _FONT_CACHE[key]
        try:
            cached.get_linesize()
            return cached
        except (pygame.error, Exception):
            _FONT_CACHE.clear()

    # 1. On Windows, try loading standard Regular / Bold Segoe UI directly (prevents SysFont picking Segoe UI Light)
    font_obj: pygame.font.Font | None = None
    win_font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
    win_path = Path("C:/Windows/Fonts") / win_font_name
    if win_path.exists():
        try:
            font_obj = pygame.font.Font(str(win_path), size)
        except Exception:
            font_obj = None

    # 2. Try clean legible modern system fonts (Verdana and Tahoma have excellent retro readability)
    if font_obj is None:
        preferred_fonts = ["verdana", "tahoma", "segoeui", "arial", "sans-serif"]
        try:
            font_obj = pygame.font.SysFont(preferred_fonts, size, bold=bold)
        except Exception:
            font_obj = None

    # 3. Fallback to default
    if font_obj is None:
        font_obj = pygame.font.Font(None, size)
        if bold:
            font_obj.set_bold(True)

    _FONT_CACHE[key] = font_obj
    return font_obj


def get_alagard_font(size: int) -> pygame.font.Font:
    """Retrieve or create a cached font using Alagard (Gothic retro RPG font)."""
    if not pygame.font.get_init():
        pygame.font.init()

    key = ("alagard", size)
    if key in _FONT_CACHE:
        cached = _FONT_CACHE[key]
        try:
            cached.get_linesize()
            return cached
        except (pygame.error, Exception):
            _FONT_CACHE.clear()

    assets_root = Path(__file__).resolve().parent.parent.parent.parent / "assets"
    alagard_path = assets_root / "fonts" / "alagard.ttf"
    if alagard_path.exists():
        try:
            f = pygame.font.Font(str(alagard_path), size)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            pass

    return get_font(size, bold=True)


def get_custom_font(font_name: str, size: int, fallback_bold: bool = False) -> pygame.font.Font:
    """Retrieve or create a cached font from assets/fonts by name (e.g. CinzelDecorative, MedievalSharp)."""
    if not pygame.font.get_init():
        pygame.font.init()

    clean_name = font_name if font_name.endswith(".ttf") else f"{font_name}.ttf"
    key = (clean_name.lower(), size)
    if key in _FONT_CACHE:
        cached = _FONT_CACHE[key]
        try:
            cached.get_linesize()
            return cached
        except (pygame.error, Exception):
            _FONT_CACHE.clear()

    assets_root = Path(__file__).resolve().parent.parent.parent.parent / "assets"
    candidate = assets_root / "fonts" / clean_name
    if candidate.exists():
        try:
            f = pygame.font.Font(str(candidate), size)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            pass

    return get_font(size, bold=fallback_bold)


def render_outlined_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    outline_color: tuple[int, int, int] = (10, 12, 22),
    x: int = 0,
    y: int = 0,
    outline_width: int = 1,
) -> pygame.Rect:
    """Renders text with a sharp, high-contrast dark outline to maximize retro readability."""
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                shadow = font.render(text, True, outline_color)
                surface.blit(shadow, (x + dx, y + dy))

    main_surf = font.render(text, True, color)
    surface.blit(main_surf, (x, y))
    return pygame.Rect(x - outline_width, y - outline_width, main_surf.get_width() + 2 * outline_width, main_surf.get_height() + 2 * outline_width)



def render_wrapped_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    x: int,
    y: int,
    max_width: int,
    line_spacing: int = 4,
) -> int:
    """Renders multi-line text with automatic word wrapping within max_width.

    Returns the total vertical height rendered.
    """
    paragraphs = text.split("\n")
    current_y = y
    line_height = font.get_linesize() + line_spacing

    for para in paragraphs:
        if not para.strip():
            current_y += line_height // 2
            continue

        words = para.split(" ")
        current_line: list[str] = []

        for word in words:
            test_line = " ".join(current_line + [word])
            line_w, _ = font.size(test_line)
            if line_w <= max_width or not current_line:
                current_line.append(word)
            else:
                line_surf = font.render(" ".join(current_line), True, color)
                surface.blit(line_surf, (x, current_y))
                current_y += line_height
                current_line = [word]

        if current_line:
            line_surf = font.render(" ".join(current_line), True, color)
            surface.blit(line_surf, (x, current_y))
            current_y += line_height

    return current_y - y
