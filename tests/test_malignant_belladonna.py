"""Unit and integration tests for Elite Enemy: Malignant Belladonna."""

from __future__ import annotations

import os
import random
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.core.fsm import GameMode
from src.core.session import GameSession
from src.data.abilities import ABILITY_REGISTRY, AbilityElement, TargetScope
from src.data.characters import create_character
from src.data.enemies import (
    ENEMY_TEMPLATES,
    MAP_LEVEL_BANDS,
    create_enemy,
    generate_encounter_for_map,
)
from src.data.items import ITEM_REGISTRY
from src.entities.actor import StatusType, resolve_status_type
from src.entities.enemy import Enemy, EnemyTier
from src.entities.party import Party
from src.frontends.pygame_ce.combat_animator import EnemySpriteManager
from src.frontends.pygame_ce.music_engine import MusicContext, resolve_music_context
from src.frontends.pygame_ce.views.combat_view import CombatView
from src.systems.combat.action import ActionType, CombatAction
from src.systems.combat.round_combat import CombatPhase, RoundCombat


def test_malignant_belladonna_template_and_lore_identity():
    assert "malignant_belladonna" in ENEMY_TEMPLATES
    tmpl = ENEMY_TEMPLATES["malignant_belladonna"]

    assert tmpl["name"] == "Malignant Belladonna"
    assert tmpl["tier"] == EnemyTier.ELITE
    assert tmpl["level"] == 3
    assert isinstance(tmpl["description"], str) and len(tmpl["description"]) >= 40
    assert "FIRE" in tmpl["weaknesses"]
    assert "HOLY" in tmpl["weaknesses"]
    assert "EARTH" in tmpl["resistances"]
    assert "DARK" in tmpl["resistances"]

    for ability_id in tmpl["abilities"]:
        assert ability_id in ABILITY_REGISTRY, f"Unknown ability {ability_id}"

    for item_id, chance in tmpl["loot_drops"]:
        assert item_id in ITEM_REGISTRY, f"Unknown loot item {item_id}"
        assert 0.0 < chance <= 1.0

    # Stats should reflect ELITE caster threat (higher HP/MATK than Briarwood minions)
    creeper = ENEMY_TEMPLATES["thornvein_creeper"]
    assert tmpl["stats"].max_hp > creeper["stats"].max_hp * 2
    assert tmpl["stats"].magic_attack > creeper["stats"].magic_attack
    assert tmpl["exp_reward"] > creeper["exp_reward"]
    assert tmpl["gold_reward"] > creeper["gold_reward"]


def test_malignant_belladonna_creation_scaling_and_serialization():
    base = create_enemy("malignant_belladonna", "belladonna_1")
    assert base.name == "Malignant Belladonna"
    assert base.tier == EnemyTier.ELITE
    assert base.sprite_id == "malignant_belladonna"
    assert base.level == 3
    assert base.current_hp == base.stats.max_hp
    assert "nightshade" in base.description.lower()

    lvl1 = create_enemy("malignant_belladonna", "belladonna_lvl1", level=1)
    lvl4 = create_enemy("malignant_belladonna", "belladonna_lvl4", level=4)
    assert lvl1.level == 1
    assert lvl4.level == 4
    assert lvl1.stats.max_hp < base.stats.max_hp < lvl4.stats.max_hp
    assert lvl1.stats.magic_attack < base.stats.magic_attack < lvl4.stats.magic_attack
    assert lvl1.exp_reward < base.exp_reward < lvl4.exp_reward

    restored = Enemy.from_dict(base.to_dict())
    assert restored.id == base.id
    assert restored.name == base.name
    assert restored.tier == EnemyTier.ELITE
    assert restored.sprite_id == "malignant_belladonna"
    assert restored.description == base.description
    assert restored.weaknesses == base.weaknesses
    assert restored.resistances == base.resistances
    assert restored.abilities == base.abilities


def test_malignant_belladonna_briarwood_encounter_pool_spawning():
    rng = random.Random(2026)
    min_bw, max_bw = MAP_LEVEL_BANDS["briarwood_verge"]

    seen_templates: set[str] = set()
    belladonna_encounters = 0
    for _ in range(150):
        troop = generate_encounter_for_map("briarwood_verge", party_avg_level=3.0, rng=rng)
        assert 1 <= len(troop) <= 3
        elite_count = sum(1 for e in troop if e.tier == EnemyTier.ELITE)
        assert elite_count <= 1, "Random Briarwood encounter should have at most 1 ELITE"
        for enemy in troop:
            assert min_bw <= enemy.level <= max_bw
            seen_templates.add(enemy.sprite_id)
            if enemy.sprite_id == "malignant_belladonna":
                belladonna_encounters += 1

    assert "malignant_belladonna" in seen_templates
    assert belladonna_encounters > 0
    assert {"thornvein_creeper", "bramble_hound", "spore_pod"}.issubset(seen_templates)

    # Explicit elite encounter generation scales within [base_level, base_level + 2]
    elite_troop = generate_encounter_for_map(
        "briarwood_verge",
        is_elite=True,
        party_avg_level=4.0,
        elite_template_id="malignant_belladonna",
    )
    assert len(elite_troop) == 1
    assert elite_troop[0].sprite_id == "malignant_belladonna"
    assert elite_troop[0].tier == EnemyTier.ELITE
    assert elite_troop[0].level == 4


def test_malignant_belladonna_sprite_and_music_integration():
    import pygame

    sprite_path = (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "sprites"
        / "enemies"
        / "malignant_belladonna.png"
    )
    assert sprite_path.is_file()

    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))
    try:
        mgr = EnemySpriteManager()
        assert mgr._resolve_filename("malignant_belladonna", "Malignant Belladonna") == "malignant_belladonna.png"
        base_surf, flash_surf = mgr.get_enemy_sprite("malignant_belladonna", "Malignant Belladonna")
        assert base_surf.get_size() == flash_surf.get_size()
        raw_surf = mgr._raw_cache["malignant_belladonna.png"]
        assert raw_surf.get_size() == (112, 112)

        belladonna = create_enemy("malignant_belladonna", "belladonna_1")
        assert resolve_music_context(GameMode.COMBAT, belladonna.tier) == MusicContext.BOSS

        session = GameSession(seed=42)
        session.initialize_new_game()
        session.combat = RoundCombat(party=session.party, enemies=[belladonna], seed=42)
        view = CombatView(session)
        view.on_enter()
        canvas = pygame.Surface((1280, 720))
        view.draw(canvas)
    finally:
        pygame.quit()


def test_malignant_belladonna_signature_abilities_and_aoe_resolution():
    for ab_id, expected_elem, expected_scope, expected_status in (
        ("nightshade_miasma", AbilityElement.DARK, TargetScope.ALL_ENEMIES, StatusType.POISON),
        ("venomous_lash", AbilityElement.PHYSICAL, TargetScope.SINGLE_ENEMY, StatusType.BLEED),
        ("withering_pollen", AbilityElement.DARK, TargetScope.SINGLE_ENEMY, StatusType.WEAKEN),
    ):
        ab = ABILITY_REGISTRY[ab_id]
        assert ab.element == expected_elem
        assert ab.scope == expected_scope
        assert resolve_status_type(ab.status_inflict) == expected_status

    # Verify Nightshade Miasma hits ALL living party members and applies Poison
    party = Party()
    rowan = create_character("rowan", level=3)
    rachel = create_character("rachel", level=3)
    lyra = create_character("lyra", level=3)
    for member in (rowan, rachel, lyra):
        party.add_character(member)

    belladonna = create_enemy("malignant_belladonna", "belladonna_1", level=3)
    combat = RoundCombat(party=party, enemies=[belladonna], seed=7)

    res = combat._execute_action(
        CombatAction(
            actor_id="belladonna_1",
            is_player=False,
            action_type=ActionType.ABILITY,
            target_id="rowan",
            ability_id="nightshade_miasma",
            speed_initiative=20.0,
        )
    )
    assert res is not None
    assert res.ability_id == "nightshade_miasma"
    assert res.target_names == ["Rowan", "Rachel", "Lyra"]
    assert len(res.damage_dealt) == 3
    assert all(dmg > 0 for dmg in res.damage_dealt)
    assert all(m.current_hp < m.base_stats.max_hp for m in (rowan, rachel, lyra))
    assert any(
        any(st.status == StatusType.POISON for st in m.statuses)
        for m in (rowan, rachel, lyra)
    )

    # Verify Venomous Lash deals physical damage and can inflict BLEED
    lash_res = None
    for seed in range(20):
        p = Party()
        r = create_character("rowan", level=3)
        p.add_character(r)
        b = create_enemy("malignant_belladonna", "belladonna_1", level=3)
        c = RoundCombat(party=p, enemies=[b], seed=seed)
        out = c._execute_action(
            CombatAction(
                actor_id="belladonna_1",
                is_player=False,
                action_type=ActionType.ABILITY,
                target_id="rowan",
                ability_id="venomous_lash",
            )
        )
        if out and out.status_applied == "BLEED":
            lash_res = out
            assert any(st.status == StatusType.BLEED for st in r.statuses)
            break
    assert lash_res is not None

    # Verify Withering Pollen deals dark damage and can inflict WEAKEN
    pollen_res = None
    for seed in range(20):
        p = Party()
        r = create_character("rowan", level=3)
        p.add_character(r)
        b = create_enemy("malignant_belladonna", "belladonna_1", level=3)
        c = RoundCombat(party=p, enemies=[b], seed=seed)
        out = c._execute_action(
            CombatAction(
                actor_id="belladonna_1",
                is_player=False,
                action_type=ActionType.ABILITY,
                target_id="rowan",
                ability_id="withering_pollen",
            )
        )
        if out and out.status_applied == "WEAKEN":
            pollen_res = out
            assert any(st.status == StatusType.WEAKEN for st in r.statuses)
            break
    assert pollen_res is not None


def test_malignant_belladonna_combat_affinities_flee_block_and_victory_resolution():
    party = Party(gold=20)
    rowan = create_character("rowan", level=3)
    rachel = create_character("rachel", level=3)
    melissa = create_character("melissa", level=3)
    lyra = create_character("lyra", level=3)
    for member in (rowan, rachel, melissa, lyra):
        party.add_character(member)

    belladonna = create_enemy("malignant_belladonna", "belladonna_1", level=3)
    combat = RoundCombat(party=party, enemies=[belladonna], seed=99)

    assert combat._get_element_multiplier("FIRE", belladonna) == 1.6
    assert combat._get_element_multiplier("HOLY", belladonna) == 1.6
    assert combat._get_element_multiplier("EARTH", belladonna) == 0.5
    assert combat._get_element_multiplier("DARK", belladonna) == 0.5

    # Fleeing is blocked against EnemyTier.ELITE
    combat.queue_player_action(CombatAction(actor_id="rowan", is_player=True, action_type=ActionType.FLEE))
    combat.queue_player_action(
        CombatAction(actor_id="rachel", is_player=True, action_type=ActionType.ABILITY, target_id="belladonna_1", ability_id="violet_ember")
    )
    combat.queue_player_action(
        CombatAction(actor_id="melissa", is_player=True, action_type=ActionType.ABILITY, target_id="belladonna_1", ability_id="flame_lance")
    )
    combat.queue_player_action(
        CombatAction(actor_id="lyra", is_player=True, action_type=ActionType.ABILITY, target_id="rowan", ability_id="soothing_bloom")
    )

    messages: list[str] = []
    while combat.phase == CombatPhase.ACTION_EXECUTION:
        res = combat.step_next_action()
        if res:
            messages.append(res.message)

    assert any("Cannot flee from an elite or boss encounter!" in m for m in messages)
    assert combat.phase != CombatPhase.ESCAPED

    # Continue rounds until party defeats Malignant Belladonna
    rounds = 0
    while combat.phase == CombatPhase.COMMAND_INPUT and rounds < 15:
        rounds += 1
        for member in combat.living_party:
            if member.id == "rowan":
                act = CombatAction(
                    actor_id="rowan",
                    is_player=True,
                    action_type=ActionType.ABILITY,
                    target_id="belladonna_1",
                    ability_id="radiant_slash",
                )
            elif member.id == "rachel":
                act = CombatAction(
                    actor_id="rachel",
                    is_player=True,
                    action_type=ActionType.ABILITY,
                    target_id="belladonna_1",
                    ability_id="violet_ember",
                )
            elif member.id == "melissa":
                act = CombatAction(
                    actor_id="melissa",
                    is_player=True,
                    action_type=ActionType.ABILITY,
                    target_id="belladonna_1",
                    ability_id="flame_lance",
                )
            else:
                act = CombatAction(
                    actor_id="lyra",
                    is_player=True,
                    action_type=ActionType.ABILITY,
                    target_id=combat.living_party[0].id,
                    ability_id="herbal_salve",
                )
            combat.queue_player_action(act)

        while combat.phase == CombatPhase.ACTION_EXECUTION:
            combat.step_next_action()

    assert combat.phase == CombatPhase.VICTORY
    assert not belladonna.is_alive
    assert combat.victory_rewards["total_exp"] == belladonna.exp_reward
    assert combat.victory_rewards["total_gold"] == belladonna.gold_reward
    assert party.gold == 20 + belladonna.gold_reward
    for dropped in combat.victory_rewards["dropped_items"]:
        assert dropped in {"panacea_herbs", "mana_draught"}
        assert party.inventory.get(dropped, 0) >= 1
