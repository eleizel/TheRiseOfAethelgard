from PIL import Image

from src.tools.animation_extractor import fit_frame_to_canvas


def test_fit_frame_to_canvas_preserves_aspect_and_bottom_alignment():
    source = Image.new("RGBA", (250, 390), (0, 0, 0, 0))
    source.paste((240, 40, 30, 255), (30, 30, 220, 390))

    result = fit_frame_to_canvas(source, (64, 80))

    assert result.size == (64, 80)
    bbox = result.getchannel("A").getbbox()
    assert bbox is not None
    assert bbox[3] == 80
    assert result.getpixel((0, 40))[3] == 0
