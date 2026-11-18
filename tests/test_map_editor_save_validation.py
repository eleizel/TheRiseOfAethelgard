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


def test_map_editor_npc_prop_creation_and_rendering(tmp_path):
    import json
    from pathlib import Path

    import pygame

    from src.frontends.pygame_ce.hd2d_renderer import HD2DRenderer
    from src.systems.exploration.map_data import load_zone_map_from_json
    from src.tools.map_editor import MODE_PROP

    project_root = Path(__file__).resolve().parent.parent
    editor = VisualMapEditor.__new__(VisualMapEditor)
    editor.project_root = project_root
    editor._prop_sprite_cache = {}
    editor.available_prop_sprites = editor._discover_prop_sprites()
    editor.selected_prop_sprite_idx = 0
    editor.current_mode = MODE_PROP
    editor.map_data = {"collisions": [], "triggers": [], "props": []}
    editor.selected_item = None
    editor.selected_category = None
    editor.set_status = lambda message: setattr(editor, "status_message", message)

    assert len(editor.available_prop_sprites) >= 1
    editor._create_new_element(120, 160, 64, 80)

    assert len(editor.map_data["props"]) == 1
    prop_dict = editor.map_data["props"][0]
    assert prop_dict["prop_type"] == "npc"
    assert prop_dict["sprite"].startswith("assets/sprites/npcs/")
    assert prop_dict["solid_rect"] == [16, 58, 32, 20]
    field_names = [name for name, _ in editor._get_editable_fields()]
    assert {"prop_type", "sprite", "solid"}.issubset(set(field_names))

    # Verify round-trip through map_data + HD2DRenderer
    map_path = tmp_path / "map.json"
    map_path.write_text(
        json.dumps(
            {
                "id": "npc_test",
                "name": "NPC Test",
                "dimensions": {"width": 320, "height": 240},
                "props": [prop_dict],
            }
        ),
        encoding="utf-8",
    )
    tilemap = load_zone_map_from_json(map_path)
    assert len(tilemap.props) == 1
    assert tilemap.props[0].sprite == prop_dict["sprite"]

    # Verify native size helper uses actual image dimensions (e.g., 128x144 for root_goliath)
    goliath_rel = "assets/sprites/npcs/root_goliath.png"
    if (project_root / goliath_rel).exists():
        assert editor._get_prop_sprite_native_size(goliath_rel) == (128, 144)

    renderer = HD2DRenderer(view_width=320, view_height=240)
    surf = pygame.Surface((320, 240))
    renderer.draw_prop(surf, tilemap.props[0], 120, 160, 0.0)
