from pathlib import Path

from PIL import Image, ImageChops

ROWAN_ASSETS = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "sprites"
    / "characters"
    / "rowan"
)


def test_rowan_walk_matrix_uses_64x80_cells():
    matrix = Image.open(ROWAN_ASSETS / "rowan_walk_matrix.png").convert("RGBA")
    assert matrix.height == 320
    assert matrix.width % 64 == 0
    frame_count = matrix.width // 64
    assert frame_count in (4, 8)
    assert matrix.getchannel("A").getextrema()[0] == 0

    for row in range(4):
        for column in range(frame_count):
            frame = matrix.crop(
                (column * 64, row * 80, (column + 1) * 64, (row + 1) * 80)
            )
            assert frame.size == (64, 80)
            bbox = frame.getchannel("A").getbbox()
            assert bbox is not None
            # All frames preserve the shared ground line.
            assert bbox[3] == 73


def test_rowan_directional_strips_match_matrix_rows_exactly():
    matrix = Image.open(ROWAN_ASSETS / "rowan_walk_matrix.png").convert("RGBA")
    directions = ("down", "up", "right", "left")
    frame_count = matrix.width // 64

    for row, direction in enumerate(directions):
        strip = Image.open(
            ROWAN_ASSETS / f"rowan_walk_{direction}.png"
        ).convert("RGBA")
        assert strip.size == (frame_count * 64, 80)
        expected = matrix.crop((0, row * 80, matrix.width, (row + 1) * 80))
        assert ImageChops.difference(strip, expected).getbbox() is None
