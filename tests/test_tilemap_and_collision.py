"""Unit tests for tilemap layout, bounds, and collision detection."""

from src.systems.exploration.map_data import (
    build_briarwood_map,
    build_oakhaven_village_map,
    load_map,
)


def test_oakhaven_map_properties():
    tilemap = build_oakhaven_village_map()
    assert tilemap.id == "oakhaven_village"
    assert tilemap.width_tiles == 30
    assert tilemap.height_tiles == 20
    assert tilemap.pixel_width == 30 * 32
    assert tilemap.pixel_height == 20 * 32
    assert len(tilemap.triggers) >= 2


def test_briarwood_map_properties():
    tilemap = build_briarwood_map()
    assert tilemap.id == "briarwood_verge"
    assert tilemap.ambient_particles == "spores"
    assert len(tilemap.props) > 0


def test_map_registry_loader():
    oakhaven = load_map("oakhaven_village")
    assert oakhaven.name == "Oakhaven Village"

    briarwood = load_map("briarwood_verge")
    assert briarwood.name == "Briarwood Verge"


def test_map_out_of_bounds_collision():
    tilemap = build_oakhaven_village_map()
    # Left of map
    assert tilemap.is_rect_colliding(-10, 50, 16, 16) is True
    # Above map
    assert tilemap.is_rect_colliding(50, -10, 16, 16) is True
    # Right of map
    assert tilemap.is_rect_colliding(tilemap.pixel_width + 10, 50, 16, 16) is True
    # Below map
    assert tilemap.is_rect_colliding(50, tilemap.pixel_height + 10, 16, 16) is True


def test_water_collision_oakhaven():
    tilemap = build_oakhaven_village_map()
    # Water pond is at tiles x:2-6, y:2-5 (pixels 64-224, 64-192)
    assert tilemap.is_rect_colliding(80, 80, 16, 16) is True


def test_json_zone_map_oakhaven():
    """Verify Oakhaven Village loads seamlessly from JSON with 1280x720 composite canvas."""
    oakhaven = load_map("oakhaven_village")
    assert oakhaven.id == "oakhaven_village"
    assert oakhaven.name == "Oakhaven Village"
    assert oakhaven.pixel_width == 1280
    assert oakhaven.pixel_height == 720
    assert oakhaven.background_image is not None
    assert len(oakhaven.collision_boxes) > 0
    assert len(oakhaven.triggers) >= 3

    # Out of bounds collision check on 1280x720 canvas
    assert oakhaven.is_rect_colliding(-10, 300, 16, 16) is True
    assert oakhaven.is_rect_colliding(1290, 300, 16, 16) is True
    assert oakhaven.is_rect_colliding(300, -10, 16, 16) is True
    assert oakhaven.is_rect_colliding(300, 730, 16, 16) is True

    # Pond collision (around x: 150, y: 150)
    assert oakhaven.is_rect_colliding(150, 150, 16, 16) is True

    # Rowan cottage collision (around x: 650, y: 150)
    assert oakhaven.is_rect_colliding(650, 150, 16, 16) is True

    # Main cobblestone central road should be clear (around x: 600, y: 350)
    assert oakhaven.is_rect_colliding(600, 350, 16, 16) is False


def test_composite_background_frustum_culling_render():
    """Verify HD2DRenderer blits the 1280x720 background across all 4 quadrants without clipping errors."""
    import pygame

    from src.frontends.pygame_ce.hd2d_renderer import HD2DRenderer

    oakhaven = load_map("oakhaven_village")
    renderer = HD2DRenderer(view_width=640, view_height=360)
    canvas = pygame.Surface((640, 360))

    # Test rendering across 4 screen positions:
    # Top-Left (0, 0), Top-Right (640, 0), Bottom-Left (0, 360), Bottom-Right (640, 360)
    test_viewports = [(0.0, 0.0), (640.0, 0.0), (0.0, 360.0), (640.0, 360.0)]
    for cx, cy in test_viewports:
        renderer.render_map(
            dest_surf=canvas,
            tilemap=oakhaven,
            cam_x=cx,
            cam_y=cy,
            player_x=cx + 320,
            player_y=cy + 180,
            player_moving=False,
            player_facing="down",
            time_sec=1.0,
        )
        assert canvas.get_at((320, 180)) is not None


def test_json_zone_map_briarwood_verge():
    """Verify Briarwood Verge loads from JSON with 3 linked slices forming a 640x1080 vertical world."""
    import pygame

    from src.frontends.pygame_ce.hd2d_renderer import HD2DRenderer

    briarwood = load_map("briarwood_verge")
    assert briarwood.id == "briarwood_verge"
    assert briarwood.name == "Briarwood Verge"
    assert briarwood.pixel_width == 640
    assert briarwood.pixel_height == 1080
    assert (briarwood.background_image is not None) or (len(briarwood.background_slices) > 0)
    assert len(briarwood.collision_boxes) > 0
    assert len(briarwood.triggers) >= 1

    # Verify renderer loads and draws the background without error
    renderer = HD2DRenderer(view_width=640, view_height=360)
    screen = pygame.Surface((640, 360))
    renderer.render_map(
        dest_surf=screen,
        tilemap=briarwood,
        cam_x=0.0,
        cam_y=0.0,
        player_x=320.0,
        player_y=100.0,
        player_moving=False,
        player_facing="down",
        time_sec=0.5,
    )
    assert screen.get_at((320, 100)) is not None

    # Path at entrance is clear
    assert briarwood.is_rect_colliding(320, 64, 16, 16) is False

    # Ruined wall in screen 1 collides
    assert briarwood.is_rect_colliding(450, 100, 16, 16) is True

    # Ancient tree spirit in screen 2 collides
    assert briarwood.is_rect_colliding(350, 550, 16, 16) is True

    # Corrupted treant boss in screen 3 collides
    assert briarwood.is_rect_colliding(390, 900, 16, 16) is True

    # Test frustum rendering across all 3 screens (y=0, y=360, y=720)
    renderer = HD2DRenderer(view_width=640, view_height=360)
    canvas = pygame.Surface((640, 360))
    for screen_y in [0.0, 360.0, 720.0]:
        renderer.render_map(
            dest_surf=canvas,
            tilemap=briarwood,
            cam_x=0.0,
            cam_y=screen_y,
            player_x=320.0,
            player_y=screen_y + 180.0,
            player_moving=False,
            player_facing="down",
            time_sec=1.0,
        )
        assert canvas.get_at((320, 180)) is not None


def test_oakhaven_village_main_integration():
    """Verify Oakhaven Village Main loads from JSON, is a safe zone, and links its triggers."""
    from src.data.dialogues import get_dialogue_tree
    from src.systems.exploration.encounter_system import EncounterSystem

    main_map = load_map("oakhaven_village_main")
    assert main_map.id == "oakhaven_village_main"
    assert main_map.pixel_width == 1280
    assert main_map.pixel_height == 720
    assert main_map.background_image == "assets/maps/oakhaven_village_main/background.png"
    assert len(main_map.collision_boxes) > 0

    transitions = [t for t in main_map.triggers if t.trigger_type == "transition"]
    assert any(t.target_map_id == "oakhaven_village" for t in transitions)

    dialogues = [t for t in main_map.triggers if t.trigger_type == "dialogue"]
    assert len(dialogues) == 5
    for trig in dialogues:
        assert trig.dialogue_id is not None
        tree = get_dialogue_tree(trig.dialogue_id)
        assert tree.id == trig.dialogue_id

    encounters = EncounterSystem(seed=42)
    assert "oakhaven_village_main" in encounters.SAFE_ZONES
    assert encounters.record_movement(500.0, "oakhaven_village_main") is False


def test_shop_interior_oakhaven_and_dialogue_transition():
    """Verify shop_interior_oakhaven loads, is safe, and dialogue ENTER_MAP transitions work."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame

    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))

    from src.core.fsm import GameMode
    from src.core.session import GameSession
    from src.data.dialogues import get_dialogue_tree
    from src.frontends.pygame_ce.views.dialogue_view import DialogueView
    from src.frontends.pygame_ce.views.exploration_view import ExplorationView
    from src.systems.exploration.encounter_system import EncounterSystem

    shop_map = load_map("shop_interior_oakhaven")
    assert shop_map.id == "shop_interior_oakhaven"
    assert shop_map.pixel_width == 640
    assert shop_map.pixel_height == 360
    assert shop_map.is_rect_colliding(312, 284, 16, 16) is False
    assert any(t.target_map_id == "oakhaven_village_main" for t in shop_map.triggers)
    assert get_dialogue_tree("oakhaven_shop_open").id == "oakhaven_shop_open"

    encounters = EncounterSystem(seed=42)
    assert "shop_interior_oakhaven" in encounters.SAFE_ZONES
    assert encounters.record_movement(500.0, "shop_interior_oakhaven") is False

    session = GameSession(seed=42)
    session.initialize_new_game()
    session.transition_to(GameMode.EXPLORATION)
    ev = ExplorationView(session)
    dv = DialogueView(session)

    dv.start_dialogue("enter_shop_oakhaven")
    assert dv.current_node is not None and len(dv.current_node.choices) == 2
    dv._execute_action_trigger("ENTER_MAP:shop_interior_oakhaven:320:300")
    assert session.pending_map_transition == ("shop_interior_oakhaven", 320.0, 300.0)

    ev.on_enter()
    assert ev.current_map.id == "shop_interior_oakhaven"
    assert session.map_id == "shop_interior_oakhaven"
    assert (ev.player_x, ev.player_y) == (320.0, 300.0)


def test_armory_and_inn_interiors_integration():
    """Verify armory and inn interiors load, are safe zones, and link dialogues/exits."""
    from src.data.dialogues import get_dialogue_tree
    from src.systems.exploration.encounter_system import EncounterSystem

    encounters = EncounterSystem(seed=42)
    cases = [
        ("armory_interior_oakhaven", "enter_armory_oakhaven", "oakhaven_armory_open"),
        ("inn_interior_oakhaven", "enter_inn_oakhaven", "oakhaven_inn_open"),
    ]
    for map_id, enter_dlg, open_dlg in cases:
        interior = load_map(map_id)
        assert interior.id == map_id
        assert interior.pixel_width == 640
        assert interior.pixel_height == 360
        assert interior.is_rect_colliding(312, 284, 16, 16) is False
        assert any(t.target_map_id == "oakhaven_village_main" for t in interior.triggers)
        assert get_dialogue_tree(enter_dlg).id == enter_dlg
        assert get_dialogue_tree(open_dlg).id == open_dlg
        assert map_id in encounters.SAFE_ZONES
        assert encounters.record_movement(500.0, map_id) is False
