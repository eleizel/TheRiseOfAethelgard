"""Background slice loading and destination-size behavior."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from PIL import Image

from src.frontends.pygame_ce.hd2d_renderer import HD2DRenderer


def test_background_loader_supports_native_and_declared_slice_sizes(tmp_path):
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))

    source_path = tmp_path / "slice.png"
    source_image = Image.new("RGBA", (640, 320), (30, 90, 40, 255))
    source_image.putpixel((0, 0), (30, 90, 40, 0))
    source_image.save(source_path)

    renderer = HD2DRenderer.__new__(HD2DRenderer)
    renderer._bg_cache = {}

    native = renderer._get_background_surface(str(source_path))
    scaled = renderer._get_background_surface(str(source_path), (640, 360))

    assert native is not None
    assert native.get_size() == (640, 320)
    assert native.get_at((0, 0)).a == 0
    assert scaled is not None
    assert scaled.get_size() == (640, 360)
    assert native is not scaled
    assert len(renderer._bg_cache) == 2

    pygame.quit()
