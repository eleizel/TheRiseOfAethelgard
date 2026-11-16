from src.tools.map_editor_utils import next_unique_id, validate_map_data


def test_next_unique_id_uses_highest_suffix_not_collection_length():
    map_data = {
        "collisions": [
            {"id": "col_1"},
            {"id": "col_4"},
            {"id": "col_12"},
        ],
        "triggers": [{"id": "dlg_trigger_1"}, {"id": "col_13"}],
        "props": [{"id": "light_lamp_2"}],
    }

    assert next_unique_id(map_data, "col") == "col_14"
    assert next_unique_id(map_data, "dlg_trigger") == "dlg_trigger_2"
    assert next_unique_id(map_data, "light_lamp") == "light_lamp_3"
    assert next_unique_id(map_data, "trans_exit") == "trans_exit_1"


def test_next_unique_id_does_not_reuse_an_existing_id_after_middle_deletion():
    # The old len(collection) + 1 strategy would choose col_3 here and collide.
    map_data = {
        "collisions": [
            {"id": "col_1"},
            {"id": "col_3"},
            {"id": "col_4"},
        ],
        "triggers": [],
        "props": [],
    }

    assert next_unique_id(map_data, "col") == "col_5"


def test_validation_blocks_duplicate_ids_and_invalid_rectangles():
    map_data = {
        "dimensions": {"width": 1280, "height": 720},
        "collisions": [
            {"id": "col_1", "x": 0, "y": 0, "w": 32, "h": 32},
            {"id": "col_1", "x": 40, "y": 0, "w": 0, "h": 32},
        ],
        "triggers": [],
        "props": [],
    }

    errors, warnings = validate_map_data(map_data)

    assert any("Duplicate ID 'col_1'" in error for error in errors)
    assert any("positive width and height" in error for error in errors)
    assert warnings == []


def test_out_of_bounds_collision_is_warning_not_blocking_error():
    map_data = {
        "dimensions": {"width": 1280, "height": 720},
        "collisions": [
            {"id": "col_edge", "x": -1, "y": 10, "w": 20, "h": 20},
        ],
        "triggers": [],
        "props": [],
    }

    errors, warnings = validate_map_data(map_data)

    assert errors == []
    assert len(warnings) == 1
    assert "col_edge" in warnings[0]


def test_validation_checks_required_trigger_references():
    map_data = {
        "dimensions": {"width": 640, "height": 360},
        "collisions": [],
        "triggers": [
            {
                "id": "dialogue_1",
                "trigger_type": "dialogue",
                "x": 10,
                "y": 10,
                "width": 20,
                "height": 20,
            },
            {
                "id": "transition_1",
                "trigger_type": "transition",
                "x": 30,
                "y": 10,
                "width": 20,
                "height": 20,
            },
        ],
        "props": [],
    }

    errors, _ = validate_map_data(map_data)

    assert any("dialogue_id" in error for error in errors)
    assert any("target_map_id" in error for error in errors)
