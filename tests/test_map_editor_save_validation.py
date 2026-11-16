import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.tools.map_editor import VisualMapEditor


def test_duplicate_ids_block_save_without_touching_map_json(tmp_path):
    map_dir = tmp_path / "test_map"
    map_dir.mkdir()
    map_json_path = map_dir / "map.json"
    original_content = '{ "original": true }'
    map_json_path.write_text(original_content, encoding="utf-8")

    editor = VisualMapEditor.__new__(VisualMapEditor)
    editor.maps_dir = tmp_path
    editor.map_id = "test_map"
    editor.map_data = {
        "dimensions": {"width": 128, "height": 96},
        "collisions": [
            {"id": "col_1", "x": 0, "y": 0, "w": 16, "h": 16},
            {"id": "col_1", "x": 32, "y": 0, "w": 16, "h": 16},
        ],
        "triggers": [],
        "props": [],
    }
    editor.set_status = lambda message: setattr(editor, "status_message", message)

    result = editor.save_map()

    assert result is False
    assert map_json_path.read_text(encoding="utf-8") == original_content
    assert not (map_dir / "map.json.bak").exists()
    assert editor.status_message.startswith("Save blocked:")
    assert "Duplicate ID 'col_1'" in editor.status_message
