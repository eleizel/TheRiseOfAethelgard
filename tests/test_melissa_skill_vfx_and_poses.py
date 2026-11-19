"""Tests for Melissa (Weave Scholar) combat poses, 4x2 skill VFX sheets, and CombatView wiring."""

from __future__ import annotations

import os
from pathlib import Path

import pygame
import pytest
from PIL import Image

from src.core.session import GameSession
from src.data.abilities import ABILITY_REGISTRY
from src.data.enemies import create_enemy
from src.frontends.pygame_ce.combat_animator import CombatantAnimState, EnemySpriteManager
from src.frontends.pygame_ce.skill_vfx import SKILL_VFX_REGISTRY, get_skill_vfx_config
from src.frontends.pygame_ce.views.combat_view import CombatView
from src.systems.combat.round_combat import ActionResult, RoundCombat


@pytest.fixture(autouse=True)
def setup_headless_pygame():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))
    yield
    pygame.quit()


MELISSA_EFFECT_SHEETS: list[tuple[str, str, tuple[int, int], tuple[int, int]]] = [
    ("flame_lance", "charge", (320, 160), (80, 80)),
    ("flame_lance", "projectile", (320, 160), (80, 80)),
    ("flame_lance", "impact", (320, 160), (80, 80)),
    ("frost_shard", "charge", (320, 160), (80, 80)),
    ("frost_shard", "projectile", (320, 160), (80, 80)),
    ("frost_shard", "impact", (320, 160), (80, 80)),
    ("arcane_ward", "buff", (320, 160), (80, 80)),
    ("blizzard_surge", "charge", (320, 160), (80, 80)),
    ("blizzard_surge", "impact", (384, 192), (96, 96)),
    ("pyroclasm", "charge", (320, 160), (80, 80)),
    ("pyroclasm", "impact", (320, 160), (80, 80)),
    ("supernova", "charge", (320, 160), (80, 80)),
    ("supernova", "impact", (640, 320), (160, 160)),
]


def test_melissa_pose_and_vfx_assets_exist_with_valid_rgba_and_dimensions():
    """Verify Melissa's base sprite, cast/attack poses, and all 4x2 VFX sheets have valid RGBA and exact sizes."""
    base_sprite = Path("assets/sprites/melissa.png")
    assert base_sprite.is_file()
    with Image.open(base_sprite) as im:
        assert im.mode == "RGBA"
        assert im.size == (64, 80)
        min_a, max_a = im.getchannel("A").getextrema()
        assert min_a == 0
        assert max_a > 0

    for pose_name in ("cast", "attack"):
        pose_path = Path(f"assets/sprites/characters/melissa/attack/{pose_name}.png")
        assert pose_path.is_file(), f"Missing Melissa pose {pose_path}"
        with Image.open(pose_path) as im:
            assert im.mode == "RGBA"
            assert im.size == (64, 80)
            min_a, max_a = im.getchannel("A").getextrema()
            assert min_a < 255
            assert max_a > 0

    for ability_id, prefix, sheet_size, _frame_size in MELISSA_EFFECT_SHEETS:
        sheet_path = Path(f"assets/sprites/effects/{ability_id}/{prefix}_4x2.png")
        assert sheet_path.is_file(), f"Missing VFX sheet {sheet_path}"
        with Image.open(sheet_path) as im:
            assert im.mode == "RGBA"
            assert im.size == sheet_size, (
                f"{sheet_path} expected {sheet_size}, got {im.size}"
            )
            min_a, max_a = im.getchannel("A").getextrema()
            assert min_a < 255
            assert max_a > 0


def test_melissa_skill_vfx_registry_and_frame_slicing():
    """Verify all 6 Melissa abilities are registered in SKILL_VFX_REGISTRY and load 8 non-empty frames per phase."""
    melissa_abilities = (
        "flame_lance",
        "frost_shard",
        "arcane_ward",
        "blizzard_surge",
        "pyroclasm",
        "supernova",
    )
    for ability_id in melissa_abilities:
        assert ability_id in ABILITY_REGISTRY
        cfg = get_skill_vfx_config(ability_id)
        assert cfg is not None, f"{ability_id} missing from SKILL_VFX_REGISTRY"
        assert cfg.effect_id == ability_id
        assert cfg.caster_anim == "spell"
        assert len(cfg.phases) >= 1

    # Existing Rachel skills must stay registered
    for rachel_ability in ("violet_ember", "wisteria_blaze", "orchid_inferno", "petal_hex"):
        assert rachel_ability in SKILL_VFX_REGISTRY

    mgr = EnemySpriteManager()
    assert mgr.get_character_action_frame_count("melissa", "cast") == 1
    assert mgr.get_character_action_frame_count("melissa", "attack") == 1

    cast_frame = mgr.get_character_action_frame("melissa", "cast", 0)
    attack_frame = mgr.get_character_action_frame("melissa", "attack", 0)
    assert cast_frame is not None and cast_frame.get_size() == (64, 80)
    assert attack_frame is not None and attack_frame.get_size() == (64, 80)

    for ability_id, prefix, _sheet_size, frame_size in MELISSA_EFFECT_SHEETS:
        assert mgr.get_effect_frame_count(ability_id, prefix) == 8
        for idx in range(8):
            frame = mgr.get_projectile_frame(ability_id, idx, prefix=prefix)
            assert frame is not None, f"Failed loading {ability_id}/{prefix} frame {idx}"
            assert frame.get_size() == frame_size
            # Verify frame contains non-empty visible pixels
            bbox = frame.get_bounding_rect()
            assert bbox.width > 0 and bbox.height > 0


def test_melissa_combat_animator_draw_and_all_six_vfx_render():
    """End-to-end CombatView test for Melissa's cast/attack poses and all 6 skill VFX pipelines."""
    session = GameSession(seed=42)
    session.initialize_new_game()
    melissa = session.unlock_character("melissa")
    assert melissa is not None
    assert melissa in session.party.active_members

    enemies = [
        create_enemy("bramble_hound", "e1"),
        create_enemy("spore_pod", "e2"),
    ]
    session.combat = RoundCombat(party=session.party, enemies=enemies, seed=42)
    view = CombatView(session=session)
    view.on_enter()

    surf = pygame.Surface((1280, 720), pygame.SRCALPHA)

    # 1. Verify draw_party_member resolves idle, cast, and attack poses for Melissa
    anim = CombatantAnimState(is_player=True)
    _, _, sw, sh = view.sprite_manager.draw_party_member(
        surf, melissa, 915.0, 464.0, anim, pixel_scale=2.0, anchor_bottom_center=True
    )
    assert (sw, sh) == (128, 160)

    anim.trigger_spell(duration=0.80, frame_count=1, action_id="cast")
    _, _, sw_cast, sh_cast = view.sprite_manager.draw_party_member(
        surf, melissa, 915.0, 464.0, anim, pixel_scale=2.0, anchor_bottom_center=True
    )
    assert (sw_cast, sh_cast) == (128, 160)

    anim.trigger_attack(distance=34.0, action_id="basic_attack")
    _, _, sw_atk, sh_atk = view.sprite_manager.draw_party_member(
        surf, melissa, 915.0, 464.0, anim, pixel_scale=2.0, anchor_bottom_center=True
    )
    assert (sw_atk, sh_atk) == (128, 160)

    # 2. Verify basic_attack uses attack lunge
    basic_res = ActionResult(
        source_name=melissa.name,
        action_name="Strike",
        target_names=[enemies[0].name],
        damage_dealt=[8],
        healing_dealt=[],
        is_crit=False,
        status_applied=None,
        message="Melissa attacks!",
        ability_id="basic_attack",
        target_ids=[enemies[0].id],
    )
    view._trigger_attacker_animation(basic_res)
    assert view.party_anim_states["melissa"].anim_type == "attack"
    assert len(view.active_vfx_instances) == 0

    # 3. Verify all 6 active abilities trigger spell pose and spawn & render all VFX phases
    party_ids = [m.id for m in session.party.active_members]
    party_names = [m.name for m in session.party.active_members]
    scenarios = [
        (
            "flame_lance",
            "Flame Lance",
            [enemies[0].id],
            [enemies[0].name],
            {"charge", "projectile", "impact"},
            3,
        ),
        (
            "frost_shard",
            "Frost Shard",
            [enemies[0].id],
            [enemies[0].name],
            {"charge", "projectile", "impact"},
            3,
        ),
        (
            "arcane_ward",
            "Arcane Ward",
            party_ids,
            party_names,
            {"buff"},
            len(party_ids),
        ),
        (
            "blizzard_surge",
            "Blizzard Surge",
            [e.id for e in enemies],
            [e.name for e in enemies],
            {"charge", "impact"},
            2,
        ),
        (
            "pyroclasm",
            "Pyroclasm",
            [enemies[0].id],
            [enemies[0].name],
            {"charge", "impact"},
            2,
        ),
        (
            "supernova",
            "Supernova",
            [e.id for e in enemies],
            [e.name for e in enemies],
            {"charge", "impact"},
            2,
        ),
    ]

    for ability_id, action_name, target_ids, target_names, expected_prefixes, expected_count in scenarios:
        view.active_vfx_instances.clear()
        res = ActionResult(
            source_name=melissa.name,
            action_name=action_name,
            target_names=target_names,
            damage_dealt=[30] * len(target_ids) if ability_id != "arcane_ward" else [],
            healing_dealt=[],
            is_crit=False,
            status_applied="DEFENSE_UP" if ability_id == "arcane_ward" else None,
            message=f"Melissa cast {action_name}!",
            ability_id=ability_id,
            target_ids=target_ids,
        )
        view._start_action_presentation(res)
        # Advance past fade_in (0.20s) to spawn VFX and spell pose
        view.update(0.25)
        assert view.party_anim_states["melissa"].anim_type == "spell"
        assert len(view.active_vfx_instances) == expected_count
        assert {inst["prefix"] for inst in view.active_vfx_instances} == expected_prefixes

        # Sample rendering across multiple timestamps within the 1.50s window
        for step_dt in (0.30, 0.45, 0.40):
            view.update(step_dt)
            view.draw(surf)
            view.draw_screen_overlay(surf)
