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


def test_spritesheet_slicing_and_character_cast_pose(tmp_path):
    assets_root = tmp_path / "assets"
    enemy_dir = assets_root / "sprites" / "enemies"
    attack_dir = assets_root / "sprites" / "characters" / "rowan" / "attack"
    effect_dir = assets_root / "sprites" / "effects" / "iron_bastion"
    enemy_dir.mkdir(parents=True)
    attack_dir.mkdir(parents=True)
    effect_dir.mkdir(parents=True)

    # 4x1 cast strip for Rowan (256x80 -> 4 frames of 64x80)
    Image.new("RGBA", (256, 80), (200, 180, 90, 255)).save(attack_dir / "cast_4x1.png")
    # 4x2 buff sheet (128x64 -> 8 frames of 32x32)
    Image.new("RGBA", (128, 64), (100, 210, 255, 255)).save(effect_dir / "buff_4x2.png")

    manager = EnemySpriteManager(assets_dir=enemy_dir)
    assert manager.get_character_action_frame_count("rowan", "cast") == 4
    cast_frame = manager.get_character_action_frame("rowan", "cast", 3)
    assert cast_frame is not None
    assert cast_frame.get_size() == (64, 80)

    assert manager.get_effect_frame_count("iron_bastion", "buff") == 8
    buff_frame = manager.get_projectile_frame("iron_bastion", 7, prefix="buff")
    assert buff_frame is not None
    assert buff_frame.get_size() == (32, 32)


def test_generic_skill_vfx_placements_and_violet_ember():
    import pygame

    from src.core.session import GameSession
    from src.data.enemies import create_enemy
    from src.frontends.pygame_ce.skill_vfx import SkillVFXConfig, VFXPhase
    from src.frontends.pygame_ce.views.combat_view import CombatView
    from src.systems.combat.round_combat import ActionResult, RoundCombat

    pygame.init()
    try:
        session = GameSession(seed=42)
        session.initialize_new_game()
        enemies = [
            create_enemy("bramble_hound", "e1"),
            create_enemy("spore_pod", "e2"),
        ]
        session.combat = RoundCombat(party=session.party, enemies=enemies, seed=42)
        view = CombatView(session=session)
        view.on_enter()

        # 1. Violet Ember spawns charge (caster) + projectile (projectile_to_target)
        rachel = next(c for c in session.party.active_members if c.id == "rachel")
        ve_res = ActionResult(
            source_name=rachel.name,
            action_name="Violet Ember",
            target_names=[enemies[0].name],
            damage_dealt=[42],
            healing_dealt=[],
            is_crit=False,
            status_applied=None,
            message="Rachel used Violet Ember!",
            ability_id="violet_ember",
            target_ids=[enemies[0].id],
        )
        view._trigger_attacker_animation(ve_res)
        assert len(view.active_vfx_instances) == 2
        assert {inst["prefix"] for inst in view.active_vfx_instances} == {"charge", "projectile"}

        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        view._draw_active_vfx(surf)

        # 2. Party-wide target_each + target_group_center spawning
        view.active_vfx_instances.clear()
        party_ids = [m.id for m in session.party.active_members]
        party_names = [m.name for m in session.party.active_members]
        buff_res = ActionResult(
            source_name="Rowan",
            action_name="Aegis Rally",
            target_names=party_names,
            damage_dealt=[],
            healing_dealt=[],
            is_crit=False,
            status_applied="DEFENSE_UP",
            message="Rowan bolstered the party!",
            ability_id="aegis_rally",
            target_ids=party_ids,
        )
        buff_cfg = SkillVFXConfig(
            effect_id="violet_ember",
            caster_anim="lunge",
            phases=(
                VFXPhase(prefix="charge", placement="target_each", start_time=0.0, duration=0.8, frame_count=8),
                VFXPhase(prefix="projectile", placement="target_group_center", start_time=0.1, duration=0.5, frame_count=8),
            ),
        )
        view._spawn_skill_vfx(buff_res, buff_cfg)
        assert len(view.active_vfx_instances) == len(party_ids) + 1
    finally:
        pygame.quit()


def test_wisteria_blaze_burn_strip_loads_and_targets_each_enemy():
    import pygame

    from src.core.session import GameSession
    from src.data.enemies import create_enemy
    from src.frontends.pygame_ce.views.combat_view import CombatView
    from src.systems.combat.round_combat import ActionResult, RoundCombat

    pygame.init()
    try:
        manager = EnemySpriteManager()
        assert manager.get_effect_frame_count("wisteria_blaze", "burn") == 8
        frame = manager.get_projectile_frame("wisteria_blaze", 4, prefix="burn")
        assert frame is not None
        assert frame.get_size() == (80, 80)

        session = GameSession(seed=42)
        session.initialize_new_game()
        enemies = [
            create_enemy("bramble_hound", "e1"),
            create_enemy("spore_pod", "e2"),
        ]
        session.combat = RoundCombat(party=session.party, enemies=enemies, seed=42)
        view = CombatView(session=session)
        view.on_enter()

        rachel = next(c for c in session.party.active_members if c.id == "rachel")
        wb_res = ActionResult(
            source_name=rachel.name,
            action_name="Wisteria Blaze",
            target_names=[e.name for e in enemies],
            damage_dealt=[32, 30],
            healing_dealt=[],
            is_crit=False,
            status_applied="BURN",
            message="Rachel cast Wisteria Blaze!",
            ability_id="wisteria_blaze",
            target_ids=[e.id for e in enemies],
        )
        view._trigger_attacker_animation(wb_res)
        assert len(view.active_vfx_instances) == 2
        assert all(inst["prefix"] == "burn" for inst in view.active_vfx_instances)

        view.update(0.45)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        view._draw_active_vfx(surf)
    finally:
        pygame.quit()


def test_orchid_inferno_sheet_loads_and_centers_on_enemy_group():
    import pygame

    from src.core.session import GameSession
    from src.data.enemies import create_enemy
    from src.frontends.pygame_ce.views.combat_view import CombatView
    from src.systems.combat.round_combat import ActionResult, RoundCombat

    pygame.init()
    try:
        manager = EnemySpriteManager()
        assert manager.get_effect_frame_count("orchid_inferno", "inferno") == 8
        frame = manager.get_projectile_frame("orchid_inferno", 3, prefix="inferno")
        assert frame is not None
        assert frame.get_size() == (160, 160)

        session = GameSession(seed=42)
        session.initialize_new_game()
        enemies = [
            create_enemy("bramble_hound", "e1"),
            create_enemy("spore_pod", "e2"),
        ]
        session.combat = RoundCombat(party=session.party, enemies=enemies, seed=42)
        view = CombatView(session=session)
        view.on_enter()

        rachel = next(c for c in session.party.active_members if c.id == "rachel")
        oi_res = ActionResult(
            source_name=rachel.name,
            action_name="Orchid Inferno",
            target_names=[e.name for e in enemies],
            damage_dealt=[55, 52],
            healing_dealt=[],
            is_crit=False,
            status_applied="BURN",
            message="Rachel cast Orchid Inferno!",
            ability_id="orchid_inferno",
            target_ids=[e.id for e in enemies],
        )
        view._trigger_attacker_animation(oi_res)
        assert len(view.active_vfx_instances) == 1
        assert view.active_vfx_instances[0]["prefix"] == "inferno"

        view.update(0.50)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        view._draw_active_vfx(surf)
    finally:
        pygame.quit()


def test_petal_hex_sheet_loads_and_renders_for_player_and_enemy():
    import pygame

    from src.core.session import GameSession
    from src.data.enemies import create_enemy
    from src.frontends.pygame_ce.views.combat_view import CombatView
    from src.systems.combat.round_combat import ActionResult, RoundCombat

    pygame.init()
    try:
        manager = EnemySpriteManager()
        assert manager.get_effect_frame_count("petal_hex", "hex") == 8
        frame = manager.get_projectile_frame("petal_hex", 4, prefix="hex")
        assert frame is not None
        assert frame.get_size() == (80, 80)

        session = GameSession(seed=42)
        session.initialize_new_game()
        enemy = create_enemy("root_wraith", "wraith_1")
        session.combat = RoundCombat(party=session.party, enemies=[enemy], seed=42)
        view = CombatView(session=session)
        view.on_enter()

        rachel = next(c for c in session.party.active_members if c.id == "rachel")
        ph_res = ActionResult(
            source_name=rachel.name,
            action_name="Petal Hex",
            target_names=[enemy.name],
            damage_dealt=[26],
            healing_dealt=[],
            is_crit=False,
            status_applied="VULNERABLE",
            message="Rachel cast Petal Hex!",
            ability_id="petal_hex",
            target_ids=[enemy.id],
        )
        view._trigger_attacker_animation(ph_res)
        assert len(view.active_vfx_instances) == 1
        assert view.active_vfx_instances[0]["prefix"] == "hex"

        view.update(0.50)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        view._draw_active_vfx(surf)
    finally:
        pygame.quit()


def test_orchid_mist_sheet_loads_and_renders_for_all_enemies():
    import pygame

    from src.core.session import GameSession
    from src.data.enemies import create_enemy
    from src.frontends.pygame_ce.views.combat_view import CombatView
    from src.systems.combat.round_combat import ActionResult, RoundCombat

    pygame.init()
    try:
        manager = EnemySpriteManager()
        assert manager.get_effect_frame_count("orchid_mist", "mist") == 8
        frame = manager.get_projectile_frame("orchid_mist", 4, prefix="mist")
        assert frame is not None
        assert frame.get_size() == (80, 80)

        session = GameSession(seed=42)
        session.initialize_new_game()
        enemies = [
            create_enemy("bramble_hound", "hound_1"),
            create_enemy("spore_pod", "pod_1"),
        ]
        session.combat = RoundCombat(party=session.party, enemies=enemies, seed=42)
        view = CombatView(session=session)
        view.on_enter()

        rachel = next(c for c in session.party.active_members if c.id == "rachel")
        om_res = ActionResult(
            source_name=rachel.name,
            action_name="Orchid Mist",
            target_names=[e.name for e in enemies],
            damage_dealt=[18, 16],
            healing_dealt=[],
            is_crit=False,
            status_applied="POISON",
            message="Rachel cast Orchid Mist!",
            ability_id="orchid_mist",
            target_ids=[e.id for e in enemies],
        )
        view._trigger_attacker_animation(om_res)
        # target_each on 2 enemies spawns 2 instances
        assert len(view.active_vfx_instances) == 2
        assert all(inst["prefix"] == "mist" for inst in view.active_vfx_instances)

        view.update(0.50)
        surf = pygame.Surface((1280, 720), pygame.SRCALPHA)
        view._draw_active_vfx(surf)
    finally:
        pygame.quit()

