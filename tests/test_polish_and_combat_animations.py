"""Unit tests for polish fixes and combat animations:
- NPC dialogue trigger from all 4 directions
- South map transition corridor coverage
- Target cursor logic for enemies and party members
- Combatant animation states (idle bob, attack lunge, hurt recoil, hit-flash, KO fade)
- Enemy sprite manager loading and fallbacks
"""

import os

import pygame
import pytest

from src.core.fsm import GameMode
from src.core.session import GameSession
from src.data.enemies import create_enemy
from src.frontends.pygame_ce.combat_animator import CombatantAnimState, EnemySpriteManager
from src.frontends.pygame_ce.views.combat_view import CombatView
from src.frontends.pygame_ce.views.exploration_view import ExplorationView
from src.systems.combat.action import ActionType
from src.systems.combat.round_combat import RoundCombat


@pytest.fixture(autouse=True)
def setup_headless_pygame():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))
    yield


def test_npc_dialogue_trigger_all_directions():
    """Verify player can trigger NPC conversation from all 4 directions (above, below, left, right)."""
    session = GameSession(seed=42)
    view = ExplorationView(session=session)
    view.switch_map("oakhaven_village", 0, 0)

    # Locate elder tomas trigger
    tomas_trig = next(
        (t for t in view.current_map.triggers if "elder" in (t.dialogue_id or "").lower() or "tomas" in (t.dialogue_id or "").lower() or "tomas" in t.id.lower()),
        None,
    )
    assert tomas_trig is not None

    cx = tomas_trig.x + tomas_trig.width / 2.0
    cy = tomas_trig.y + tomas_trig.height / 2.0

    # 1. From South facing UP
    view.player_x = cx
    view.player_y = tomas_trig.y + tomas_trig.height + 16.0
    view.facing = "up"
    event_space = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
    view.handle_event(event_space)
    assert session.pending_dialogue_id in ("elder_tomas", "elder_thomas")
    assert session.fsm.current_mode == GameMode.DIALOGUE

    # Reset state to exploration
    session.transition_to(GameMode.EXPLORATION)
    session.pending_dialogue_id = None

    # 2. From West facing RIGHT (step close to Tomas, outside house door radius)
    view.player_x = tomas_trig.x - 4.0
    view.player_y = tomas_trig.y + tomas_trig.height - 12.0
    view.facing = "right"
    view.handle_event(event_space)
    assert session.pending_dialogue_id in ("elder_tomas", "elder_thomas")
    assert session.fsm.current_mode == GameMode.DIALOGUE

    session.transition_to(GameMode.EXPLORATION)
    session.pending_dialogue_id = None

    # 3. From East facing LEFT
    view.player_x = tomas_trig.x + tomas_trig.width + 16.0
    view.player_y = cy
    view.facing = "left"
    view.handle_event(event_space)
    assert session.pending_dialogue_id in ("elder_tomas", "elder_thomas")
    assert session.fsm.current_mode == GameMode.DIALOGUE

    session.transition_to(GameMode.EXPLORATION)
    session.pending_dialogue_id = None

    # 4. From North facing DOWN
    view.player_x = cx
    view.player_y = tomas_trig.y - 16.0
    view.facing = "down"
    view.handle_event(event_space)
    assert session.pending_dialogue_id in ("elder_tomas", "elder_thomas")
    assert session.fsm.current_mode == GameMode.DIALOGUE


def test_south_map_transition_corridor():
    """Verify player walking south across the road triggers map transition to Briarwood, and can return to Oakhaven without being yoinked back."""
    session = GameSession(seed=42)
    view = ExplorationView(session=session)
    view.switch_map("oakhaven_village", 0, 0)

    exit_trig = next((t for t in view.current_map.triggers if t.trigger_type == "transition" and t.target_map_id in ("briarwood_edge", "briarwood_verge")), None)
    assert exit_trig is not None

    # Step directly inside exit transition trigger zone in Oakhaven
    view.player_x = exit_trig.x + exit_trig.width / 2.0
    view.player_y = exit_trig.y + exit_trig.height / 2.0
    view.update(dt=0.016)

    # Must transition to briarwood_edge / briarwood_verge
    assert view.current_map.id in ("briarwood_edge", "briarwood_verge")
    assert session.map_id in ("briarwood_edge", "briarwood_verge")

    # Clear transition cooldown as player navigates through Briarwood
    view.update(dt=1.0)

    # Now step on exit_to_oakhaven in Briarwood
    return_trig = next((t for t in view.current_map.triggers if t.trigger_type == "transition" and t.target_map_id == "oakhaven_village"), None)
    assert return_trig is not None
    view.player_x = return_trig.x + return_trig.width / 2.0
    view.player_y = return_trig.y + return_trig.height / 2.0
    view.update(dt=0.016)

    # Must transition back to Oakhaven Village safely
    assert view.current_map.id == "oakhaven_village"
    assert session.map_id == "oakhaven_village"
    assert view.player_y == 620.0  # Spawns safely north of the southern exit trigger

    # Verify no ping-pong bouncing (yoinking) over subsequent frames
    for _ in range(30):
        view.update(dt=0.016)
    assert view.current_map.id == "oakhaven_village"


def test_combat_target_cursor_enemy_and_ally():
    """Verify target cursor highlights only the intended entity using entity IDs."""
    session = GameSession(seed=42)
    session.initialize_new_game()
    e1 = create_enemy("thornvein_creeper", "e_1")
    e2 = create_enemy("bramble_hound", "e_2")
    combat = RoundCombat(party=session.party, enemies=[e1, e2], seed=42)
    session.combat = combat

    view = CombatView(session=session)
    view.on_enter()

    # When in TARGET mode targeting enemies with basic attack
    view.menu_mode = "TARGET"
    view.selected_action_type = ActionType.ATTACK
    view.selected_ability_id = "basic_attack"
    view.target_index = 0

    assert view._is_enemy_targeted(e1) is True
    assert view._is_enemy_targeted(e2) is False
    assert view._is_party_member_targeted(session.party.active_members[0]) is False

    # Shift target index to 1
    view.target_index = 1
    assert view._is_enemy_targeted(e1) is False
    assert view._is_enemy_targeted(e2) is True

    # When first enemy is defeated
    e1.take_damage(999)
    assert e1.is_alive is False
    # Now living_enemies is only [e2]. target_index % len(living) = 0 -> e2!
    view.target_index = 0
    assert view._is_enemy_targeted(e2) is True
    assert view._is_enemy_targeted(e1) is False

    # When using Item or healing skill targeting ally
    view.selected_action_type = ActionType.ITEM
    view.selected_item_id = "healing_poultice"
    view.target_index = 0
    assert view._is_enemy_targeted(e2) is False
    assert view._is_party_member_targeted(session.party.active_members[0]) is True
    assert view._is_party_member_targeted(session.party.active_members[1]) is False


def test_combat_multi_and_self_target_highlighting():
    """Verify ALL_ENEMIES, ALL_ALLIES, and SELF highlight the full target group."""
    session = GameSession(seed=42)
    session.initialize_new_game()
    e1 = create_enemy("thornvein_creeper", "e_1")
    e2 = create_enemy("bramble_hound", "e_2")
    combat = RoundCombat(party=session.party, enemies=[e1, e2], seed=42)
    session.combat = combat

    view = CombatView(session=session)
    view.on_enter()
    view.menu_mode = "TARGET"
    view.selected_action_type = ActionType.ABILITY

    # ALL_ENEMIES highlights every living enemy
    view.selected_ability_id = "smoke_screen"
    assert view._is_enemy_targeted(e1) is True
    assert view._is_enemy_targeted(e2) is True
    e1.take_damage(999)
    assert view._is_enemy_targeted(e1) is False
    assert view._is_enemy_targeted(e2) is True

    # ALL_ALLIES highlights every living party member
    view.selected_ability_id = "soothing_bloom"
    for member in session.party.active_members:
        assert view._is_party_member_targeted(member) is True

    # SELF highlights only the active caster
    view.selected_ability_id = "hunters_mark"
    assert view._is_party_member_targeted(session.party.active_members[0]) is True
    assert view._is_party_member_targeted(session.party.active_members[1]) is False


def test_combatant_animation_states():
    """Verify idle bobbing, attack lunge displacement, and hurt recoil & hit-flash."""
    anim = CombatantAnimState(phase_offset=0.0, is_player=False)

    # 1. Idle update creates vertical bob
    anim.update(dt=0.2, is_alive=True)
    assert anim.anim_type == "idle"
    assert anim.offset_x == 0.0
    assert anim.offset_y != 0.0  # Bobbing

    # 2. Attack lunge moves forward (+X for enemy)
    anim.trigger_attack(duration=0.4, distance=30.0)
    assert anim.anim_type == "attack"
    anim.update(dt=0.2, is_alive=True)
    assert anim.offset_x > 15.0  # Lunging forward towards right

    # Finish attack anim
    anim.update(dt=0.3, is_alive=True)
    assert anim.anim_type == "idle"

    # 3. Hurt recoil moves backward (-X for enemy) and activates hit flash
    anim.trigger_hurt(duration=0.4, recoil=12.0)
    assert anim.anim_type == "hurt"
    assert anim.flash_timer > 0.0
    anim.update(dt=0.1, is_alive=True)
    assert anim.flash_timer > 0.0

    # 4. Defeated / KO fade
    anim.update(dt=0.5, is_alive=False)
    assert anim.ko_alpha < 255.0


def test_enemy_sprite_manager_loading_and_render():
    """Verify EnemySpriteManager loads enemy assets and renders cleanly without errors."""
    mgr = EnemySpriteManager()
    surf = pygame.Surface((320, 240), pygame.SRCALPHA)

    enemy = create_enemy("bramble_hound", "hound_test")
    anim = CombatantAnimState()

    rx, ry, sw, sh = mgr.draw_enemy(
        surface=surf,
        enemy=enemy,
        base_x=100.0,
        base_y=80.0,
        anim_state=anim,
    )

    assert sw > 0
    assert sh > 0
    assert rx == 100
    assert ry == int(80 + anim.offset_y)


def test_party_character_sprites_and_portraits_loading():
    """Verify party member sprites and portraits exist and load correctly for all 4 companions."""
    mgr = EnemySpriteManager()
    party_ids = ["rowan", "lyra", "caelen", "melissa"]

    for cid in party_ids:
        base_sprite, flash_sprite = mgr.get_character_sprite(char_id=cid, max_w=56, max_h=56)
        assert base_sprite.get_width() > 0
        assert base_sprite.get_height() > 0
        assert flash_sprite.get_width() > 0

        portrait = mgr.get_portrait(speaker_id=cid, size=64)
        assert portrait is not None
        assert portrait.get_width() == 64
        assert portrait.get_height() == 64


def test_menu_inventory_equip_modal():
    """Verify selecting an equippable item in inventory triggers target picker modal and equips the item."""
    from src.frontends.pygame_ce.views.menu_view import MenuView

    session = GameSession(seed=42)
    session.initialize_new_game()
    view = MenuView(session=session)
    view.active_tab_idx = 1  # Inventory tab

    # Add sunwarden_blade to inventory
    session.party.add_item("sunwarden_blade", 1)

    # Select the sword in inventory
    inv_items = list(session.party.inventory.items())
    sword_idx = next(i for i, (iid, _) in enumerate(inv_items) if iid == "sunwarden_blade")
    view.item_index = sword_idx

    # Press Enter to open target picker modal
    event_enter = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
    view.handle_event(event_enter)

    assert view.inventory_target_picker is True
    assert view.target_char_index == 0

    # Rowan is char 0. Confirm equipping on Rowan
    old_weapon = session.party.active_members[0].equipment.weapon
    view.handle_event(event_enter)

    # Modal should close and Rowan's weapon should now be sunwarden_blade
    assert view.inventory_target_picker is False
    assert session.party.active_members[0].equipment.weapon == "sunwarden_blade"
    # Old weapon should be placed back into inventory
    if old_weapon:
        assert session.party.inventory.get(old_weapon, 0) > 0


def test_menu_equipment_slot_picker():
    """Verify Equipment tab slot navigation and equipment picker modal functionality."""
    from src.frontends.pygame_ce.views.menu_view import MenuView

    session = GameSession(seed=42)
    session.initialize_new_game()
    view = MenuView(session=session)
    view.active_tab_idx = 2  # Equipment tab

    # Add guard_brigandine to inventory
    session.party.add_item("guard_brigandine", 1)

    # Slot 1 is Armor (0=Weapon, 1=Armor, 2=Accessory)
    view.slot_index = 1

    # Press Enter to open equipment picker modal
    event_enter = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
    view.handle_event(event_enter)

    assert view.equipment_picking is True
    options = view._get_compatible_equipment_options(1)
    assert len(options) >= 2  # [None (unequip), "guard_brigandine", ...]

    # Select guard_brigandine in the modal
    brig_idx = next(i for i, opt in enumerate(options) if opt == "guard_brigandine")
    view.equip_picker_index = brig_idx

    view.handle_event(event_enter)

    assert view.equipment_picking is False
    assert session.party.active_members[0].equipment.armor == "guard_brigandine"


def test_word_wrapped_text_rendering():
    """Verify render_wrapped_text word-wraps cleanly without overflow or exceptions."""
    from src.frontends.pygame_ce.font_utils import get_font, render_wrapped_text

    font = get_font(18)
    surf = pygame.Surface((300, 200), pygame.SRCALPHA)
    long_desc = "Channel ancient roots to form a hardened barrier, granting +15 Defense and reflecting 20% thorns damage."

    lines_rendered = render_wrapped_text(
        surface=surf,
        text=long_desc,
        font=font,
        color=(255, 255, 255),
        x=10,
        y=10,
        max_width=150,
        line_spacing=4,
    )

    # Should wrap into multiple lines given 150px max width
    assert lines_rendered >= 3


def test_combat_background_manager():
    """Verify CombatBackgroundManager dynamically loads and scales map backgrounds."""
    from src.frontends.pygame_ce.combat_background import CombatBackgroundManager

    bg_mgr = CombatBackgroundManager(view_width=640, view_height=360)

    # Briarwood Verge background resolution via map_id and map_name
    bg1 = bg_mgr.get_random_background(map_id="briarwood_edge", map_name="Briarwood Verge")
    assert bg1 is not None
    assert bg1.get_size() == (640, 360)

    bg2 = bg_mgr.get_random_background(map_id="briarwood_edge")
    assert bg2 is not None
    assert bg2.get_size() == (640, 360)

    # Unknown map fallback to None
    bg_unknown = bg_mgr.get_random_background(map_id="nonexistent_dungeon")
    assert bg_unknown is None


def test_sprite_and_portrait_transparency_and_normalized_height():
    """Verify restored transparency for Lyra & Melissa and identical combat sprite heights."""
    from PIL import Image

    # 1. Portraits transparency check
    for p_name in ["lyra.png", "melissa.png", "rowan.png", "caelen.png"]:
        im = Image.open(f"assets/portraits/{p_name}")
        alpha = im.split()[-1]
        min_a, max_a = alpha.getextrema()
        assert min_a == 0, f"Portrait {p_name} must have transparent background (min alpha == 0)"
        assert max_a == 255, f"Portrait {p_name} must have opaque content"

    # 2. Combat sprites transparency and height check
    for s_name in ["lyra.png", "melissa.png", "rowan.png", "caelen.png"]:
        im = Image.open(f"assets/sprites/{s_name}")
        alpha = im.split()[-1]
        min_a, max_a = alpha.getextrema()
        assert min_a == 0, f"Sprite {s_name} must have transparent background"
        assert im.size == (64, 80), f"Sprite {s_name} must be normalized to 64x80 (got {im.size})"


def test_welcome_screen_background_and_alagard_font():
    """Verify TitleView loads welcome background art and theme.json configures Alagard for the title."""
    import json
    from pathlib import Path

    from src.frontends.pygame_ce.views.title_view import TitleView

    session = GameSession(seed=42)
    view = TitleView(session=session)

    assert view.background_image is not None
    assert view.background_image.get_size() == (640, 360)
    assert view.ui_manager is not None
    theme = json.loads(Path("assets/ui/theme.json").read_text(encoding="utf-8"))
    assert "alagard.ttf" in theme["@title_hero"]["font"]["regular_path"]


def test_rowan_walk_cycle_sprites_and_matrix():
    """Verify Rowan's walk cycle spritesheets, transparency, matrix layout, and HD2D renderer slicing."""
    from pathlib import Path

    from PIL import Image

    from src.frontends.pygame_ce.hd2d_renderer import HD2DRenderer

    rowan_dir = Path("assets/sprites/characters/rowan")

    # 1. Matrix contract: four direction rows, 64x80 cells, 4 or 8 frames per row.
    matrix_path = rowan_dir / "rowan_walk_matrix.png"
    assert matrix_path.exists(), f"Missing {matrix_path}"
    m_im = Image.open(matrix_path).convert("RGBA")
    assert m_im.height == 320, f"Matrix must be 320px high (got {m_im.size})"
    assert m_im.width % 64 == 0, f"Matrix width must be divisible by 64 (got {m_im.size})"
    frame_count = m_im.width // 64
    assert frame_count in (4, 8), f"Expected 4 or 8 frames per direction (got {frame_count})"
    assert m_im.getchannel("A").getextrema() == (0, 255)

    # 2. Directional strips must match the matrix's frame count.
    for direction in ["down", "up", "right", "left"]:
        strip_path = rowan_dir / f"rowan_walk_{direction}.png"
        assert strip_path.exists(), f"Missing {strip_path}"
        im = Image.open(strip_path).convert("RGBA")
        assert im.size == (frame_count * 64, 80), (
            f"{strip_path.name} must be {frame_count * 64}x80 (got {im.size})"
        )
        assert im.getchannel("A").getextrema() == (0, 255)

    # 3. HD2D Renderer animation slicing verification
    renderer = HD2DRenderer()
    assert "rowan" in renderer._character_animations
    rowan_anims = renderer._character_animations["rowan"]
    assert set(rowan_anims.keys()) == {"down", "up", "right", "left"}
    for d, frames in rowan_anims.items():
        assert len(frames) == frame_count, (
            f"Direction {d} must have {frame_count} frames (got {len(frames)})"
        )
        for idx, f in enumerate(frames):
            assert f.get_size() == (64, 80), f"Frame {idx} of {d} must be 64x80"

    # 4. Verification of draw_player_sprite call
    test_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
    renderer.draw_player_sprite(test_surf, 50, 70, is_moving=True, facing="down", time_sec=0.5)

    # 5. Directional facing verification (ensure no moonwalking!)
    import numpy as np

    def check_facing(frame_surf):
        arr = pygame.surfarray.array3d(frame_surf)
        # Face/skin (high red/green, lower blue) vs Cape (predominantly red)
        skin = (arr[:, :, 0] > 180) & (arr[:, :, 1] > 140) & (arr[:, :, 1] < 220) & (arr[:, :, 2] > 100) & (arr[:, :, 2] < 180)
        cape = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 90) & (arr[:, :, 2] < 90)
        skin_xs = np.where(skin)[0]
        cape_xs = np.where(cape)[0]
        return "LEFT" if np.mean(skin_xs) < np.mean(cape_xs) else "RIGHT"

    assert check_facing(rowan_anims["left"][0]) == "LEFT", "Left animation must face left"
    assert check_facing(rowan_anims["right"][0]) == "RIGHT", "Right animation must face right"


def test_combat_duplicate_enemy_targeting_and_ko_fade():
    """Enemies sharing a template/ID must target and KO-fade independently."""
    session = GameSession(seed=42)
    session.initialize_new_game()
    h1 = create_enemy("bramble_hound", "bramble_hound")
    matron = create_enemy("mandragora_matron", "mandragora_matron")
    h2 = create_enemy("bramble_hound", "bramble_hound")
    combat = RoundCombat(party=session.party, enemies=[h1, matron, h2], seed=42)
    session.combat = combat

    view = CombatView(session=session)
    view.on_enter()
    view.menu_mode = "TARGET"
    view.selected_action_type = ActionType.ATTACK
    view.selected_ability_id = "basic_attack"

    view.target_index = 0
    assert view._is_enemy_targeted(h1) is True
    assert view._is_enemy_targeted(h2) is False

    view.target_index = 2
    assert view._is_enemy_targeted(h1) is False
    assert view._is_enemy_targeted(h2) is True

    # Kill index 0 (h1); h1's anim state must fade to 0 while h2 remains at 255
    h1.take_damage(9999)
    for _ in range(30):
        view.update(0.05)

    st_h1 = view.enemy_anim_states[view._enemy_anim_key(h1)]
    st_h2 = view.enemy_anim_states[view._enemy_anim_key(h2)]
    assert st_h1.ko_alpha == 0.0
    assert st_h2.ko_alpha == 255.0





