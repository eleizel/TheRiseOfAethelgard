from PIL import Image

from src.frontends.pygame_ce.combat_animator import CombatantAnimState, EnemySpriteManager


def test_spell_animation_advances_eight_frames_and_returns_to_idle():
    state = CombatantAnimState(is_player=True)

    state.trigger_spell(duration=0.8, frame_count=8)
    assert state.anim_type == "spell"
    assert state.spell_frame_index == 0

    state.update(0.11)
    assert state.anim_type == "spell"
    assert state.spell_frame_index == 1

    state.update(0.3)
    assert state.anim_type == "spell"
    assert state.spell_frame_index in (4, 5)

    state.update(0.5)
    assert state.anim_type == "idle"
    assert state.offset_x == 0.0


def test_character_action_and_projectile_frames_load_and_cache(tmp_path):
    assets_root = tmp_path / "assets"
    enemy_dir = assets_root / "sprites" / "enemies"
    attack_dir = assets_root / "sprites" / "characters" / "rachel" / "attack"
    projectile_dir = assets_root / "sprites" / "effects" / "violet_ember"
    enemy_dir.mkdir(parents=True)
    attack_dir.mkdir(parents=True)
    projectile_dir.mkdir(parents=True)

    attack_path = attack_dir / "violet_ember_03.png"
    projectile_path = projectile_dir / "projectile_05.png"
    Image.new("RGBA", (64, 80), (130, 35, 190, 255)).save(attack_path)
    Image.new("RGBA", (32, 32), (190, 80, 255, 255)).save(projectile_path)

    manager = EnemySpriteManager(assets_dir=enemy_dir)

    attack_frame = manager.get_character_action_frame("rachel", "violet_ember", 3)
    projectile_frame = manager.get_projectile_frame("violet_ember", 5)

    assert attack_frame is not None
    assert attack_frame.get_size() == (64, 80)
    assert projectile_frame is not None
    assert projectile_frame.get_size() == (32, 32)
    assert manager.get_character_action_frame("rachel", "violet_ember", 3) is attack_frame
    assert manager.get_projectile_frame("violet_ember", 5) is projectile_frame


def test_missing_character_action_and_projectile_assets_fall_back_cleanly(tmp_path):
    assets_root = tmp_path / "assets"
    enemy_dir = assets_root / "sprites" / "enemies"
    enemy_dir.mkdir(parents=True)

    manager = EnemySpriteManager(assets_dir=enemy_dir)

    assert manager.get_character_action_frame("rachel", "violet_ember", 0) is None
    assert manager.get_projectile_frame("violet_ember", 0) is None



def test_violet_ember_result_exposes_ability_and_target_for_presentation():
    from src.data.characters import create_character
    from src.data.enemies import create_enemy
    from src.entities.party import Party
    from src.systems.combat.action import ActionType, CombatAction
    from src.systems.combat.round_combat import RoundCombat

    party = Party()
    rachel = create_character("rachel")
    party.add_character(rachel)
    enemy = create_enemy("thornvein_creeper", "violet_target")
    combat = RoundCombat(party=party, enemies=[enemy], seed=42)

    queued = combat.queue_player_action(
        CombatAction(
            actor_id="rachel",
            is_player=True,
            action_type=ActionType.ABILITY,
            ability_id="violet_ember",
            target_id="violet_target",
        )
    )
    assert queued is True

    result = combat.step_next_action()

    assert result is not None
    assert result.ability_id == "violet_ember"
    assert result.target_ids == ["violet_target"]


def test_violet_ember_two_phase_charge_and_projectile_frames_load():
    import pygame

    pygame.init()
    try:
        manager = EnemySpriteManager()
        for idx in range(8):
            charge = manager.get_projectile_frame("violet_ember", idx, prefix="charge")
            proj = manager.get_projectile_frame("violet_ember", idx, prefix="projectile")
            assert charge is not None
            assert charge.get_size() == (64, 80)
            assert proj is not None
            assert proj.get_size() == (64, 80)
    finally:
        pygame.quit()
