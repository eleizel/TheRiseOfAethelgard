import pygame

from src.frontends.pygame_ce.hd2d_renderer import (
    slice_walk_animation_sheet,
    walk_frame_index,
)


def test_four_frame_walk_preserves_legacy_timing():
    assert walk_frame_index(0.0, 4) == 0
    assert walk_frame_index(0.154, 4) == 1
    assert walk_frame_index(0.616, 4) == 0


def test_eight_frame_walk_matches_80ms_preview_timing():
    assert walk_frame_index(0.0, 8) == 0
    assert walk_frame_index(0.08, 8) == 1
    assert walk_frame_index(0.64, 8) == 0


def test_frame_index_is_non_negative_and_wraps():
    assert walk_frame_index(-1.0, 8) == 0
    assert walk_frame_index(100.0, 8) in range(8)
    assert walk_frame_index(0.5, 0) == 0

def test_animation_sheet_loader_supports_four_and_eight_frames():
    for columns in (4, 8):
        sheet = pygame.Surface((columns * 64, 4 * 80), pygame.SRCALPHA)
        for row in range(4):
            for column in range(columns):
                color = (row * 50, column * 25, 100, 255)
                sheet.fill(color, pygame.Rect(column * 64, row * 80, 64, 80))

        animations = slice_walk_animation_sheet(sheet)

        assert animations is not None
        assert set(animations) == {"down", "up", "right", "left"}
        assert all(len(frames) == columns for frames in animations.values())
        assert animations["left"][-1].get_at((0, 0)) == (150, (columns - 1) * 25, 100, 255)


def test_animation_sheet_loader_rejects_invalid_cell_geometry():
    assert slice_walk_animation_sheet(pygame.Surface((500, 320), pygame.SRCALPHA)) is None
    assert slice_walk_animation_sheet(pygame.Surface((512, 300), pygame.SRCALPHA)) is None
