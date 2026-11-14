"""Unit tests for the 4-member round-based combat engine."""

from src.data.characters import create_character
from src.data.enemies import create_enemy
from src.entities.party import Party
from src.systems.combat.action import ActionType, CombatAction
from src.systems.combat.round_combat import CombatPhase, RoundCombat


def test_combat_initialization_and_turn_queuing():
    party = Party()
    for name in ["rowan", "lyra", "caelen", "melissa"]:
        party.add_character(create_character(name))

    enemies = [create_enemy("thornvein_creeper", "enemy_1"), create_enemy("bramble_hound", "enemy_2")]
    combat = RoundCombat(party=party, enemies=enemies, seed=42)

    assert combat.phase == CombatPhase.COMMAND_INPUT
    assert len(combat.living_party) == 4
    assert len(combat.living_enemies) == 2
    assert combat.active_input_character.id == "rowan"

    # Queue action for Rowan
    assert combat.queue_player_action(
        CombatAction(actor_id="rowan", is_player=True, action_type=ActionType.ATTACK, target_id="enemy_1")
    ) is True
    assert combat.active_input_character.id == "lyra"

    # Queue action for Lyra
    combat.queue_player_action(
        CombatAction(actor_id="lyra", is_player=True, action_type=ActionType.DEFEND)
    )
    assert combat.active_input_character.id == "caelen"

    # Queue action for Caelen
    combat.queue_player_action(
        CombatAction(actor_id="caelen", is_player=True, action_type=ActionType.ATTACK, target_id="enemy_1")
    )
    assert combat.active_input_character.id == "melissa"

    # Queue action for Melissa -> triggers round execution automatically!
    combat.queue_player_action(
        CombatAction(actor_id="melissa", is_player=True, action_type=ActionType.ABILITY, ability_id="flame_lance", target_id="enemy_1")
    )

    assert combat.phase == CombatPhase.ACTION_EXECUTION
    assert len(combat.action_queue) > 0


def test_combat_step_action_resolution():
    party = Party()
    party.add_character(create_character("rowan"))
    enemies = [create_enemy("thornvein_creeper", "enemy_1")]

    combat = RoundCombat(party=party, enemies=enemies, seed=123)

    combat.queue_player_action(
        CombatAction(actor_id="rowan", is_player=True, action_type=ActionType.ATTACK, target_id="enemy_1")
    )

    # Step through all actions
    while combat.phase == CombatPhase.ACTION_EXECUTION:
        res = combat.step_next_action()
        if res:
            assert res.source_name != ""
            assert len(res.message) > 0


def test_combat_victory_and_rewards():
    party = Party(gold=50)
    rowan = create_character("rowan")
    party.add_character(rowan)

    # Low HP enemy to guarantee defeat in one hit
    weak_enemy = create_enemy("thornvein_creeper", "weak_target")
    weak_enemy.current_hp = 5
    combat = RoundCombat(party=party, enemies=[weak_enemy], seed=42)

    combat.queue_player_action(
        CombatAction(actor_id="rowan", is_player=True, action_type=ActionType.ATTACK, target_id="weak_target")
    )

    # Step until victory
    while combat.phase == CombatPhase.ACTION_EXECUTION:
        combat.step_next_action()

    assert combat.phase == CombatPhase.VICTORY
    assert combat.victory_rewards["total_gold"] > 0
    assert party.gold > 50
    assert rowan.current_exp > 0


def test_combat_defeat_condition():
    party = Party()
    rowan = create_character("rowan")
    rowan.current_hp = 1
    party.add_character(rowan)

    strong_treant = create_enemy("corrupted_treant", "boss")
    strong_treant.stats.attack = 200  # Will one-shot Rowan
    combat = RoundCombat(party=party, enemies=[strong_treant], seed=42)

    combat.queue_player_action(
        CombatAction(actor_id="rowan", is_player=True, action_type=ActionType.ATTACK, target_id="boss")
    )

    while combat.phase == CombatPhase.ACTION_EXECUTION:
        combat.step_next_action()

    assert combat.phase == CombatPhase.DEFEAT
    assert rowan.is_alive is False
    assert party.is_party_defeated is True


def test_status_resolution_ally_buff_and_regen_tick():
    from src.entities.actor import StatusType, resolve_status_type

    assert resolve_status_type("armor_break") == StatusType.VULNERABLE
    assert resolve_status_type("attack_up") == StatusType.ATTACK_UP
    assert resolve_status_type("stun") == StatusType.STUN

    party = Party()
    lyra = create_character("lyra")
    lyra.current_hp = 50
    party.add_character(lyra)

    enemy = create_enemy("thornvein_creeper", "e1")
    enemy.stats.attack = 1
    combat = RoundCombat(party=party, enemies=[enemy], seed=1)

    combat.queue_player_action(
        CombatAction(
            actor_id="lyra",
            is_player=True,
            action_type=ActionType.ABILITY,
            target_id="lyra",
            ability_id="regrowth",
        )
    )
    while combat.phase == CombatPhase.ACTION_EXECUTION:
        combat.step_next_action()

    # Regrowth should have applied REGEN, which ticked once (+1 duration consumed)
    regen_statuses = [s for s in lyra.statuses if s.status == StatusType.REGEN]
    assert len(regen_statuses) == 1
    assert regen_statuses[0].duration == 2
    assert lyra.current_hp > 50


def test_stun_skips_turn_and_panacea_cleanses_negative_statuses():
    from src.entities.actor import ActiveStatus, StatusType

    party = Party()
    rowan = create_character("rowan")
    rowan.statuses.append(ActiveStatus(status=StatusType.DEFENSE_UP, duration=3))
    rowan.statuses.append(ActiveStatus(status=StatusType.POISON, duration=3, magnitude=5))
    party.add_character(rowan)
    party.add_item("panacea_herbs", 1)

    enemy = create_enemy("thornvein_creeper", "e1")
    enemy.statuses.append(ActiveStatus(status=StatusType.STUN, duration=2))
    combat = RoundCombat(party=party, enemies=[enemy], seed=1)

    combat.queue_player_action(
        CombatAction(
            actor_id="rowan",
            is_player=True,
            action_type=ActionType.ITEM,
            target_id="rowan",
            item_id="panacea_herbs",
        )
    )

    messages: list[str] = []
    while combat.phase == CombatPhase.ACTION_EXECUTION:
        res = combat.step_next_action()
        if res:
            messages.append(res.message)

    assert any("stunned and cannot move" in m for m in messages)
    # Poison cleansed, Defense Up preserved
    assert all(s.status != StatusType.POISON for s in rowan.statuses)
    assert any(s.status == StatusType.DEFENSE_UP for s in rowan.statuses)


def test_all_statuses_covered_by_starting_abilities_and_self_target():
    from src.data.abilities import ABILITY_REGISTRY
    from src.data.classes import CLASS_REGISTRY
    from src.entities.actor import StatusType, resolve_status_type

    covered: set[StatusType] = set()
    for cid in ("vanguard", "botanist", "scout", "weave_mage", "hunter"):
        for aid in CLASS_REGISTRY[cid].starting_abilities:
            ab = ABILITY_REGISTRY[aid]
            st = resolve_status_type(ab.status_inflict)
            if st is not None:
                covered.add(st)

    assert covered == set(StatusType)

    # Verify TargetScope.SELF (hunters_mark) applies ATTACK_UP to Jack
    party = Party()
    jack = create_character("jack")
    party.add_character(jack)
    enemy = create_enemy("thornvein_creeper", "e1")
    combat = RoundCombat(party=party, enemies=[enemy], seed=1)
    combat.queue_player_action(
        CombatAction(
            actor_id="jack",
            is_player=True,
            action_type=ActionType.ABILITY,
            target_id="e1",
            ability_id="hunters_mark",
        )
    )
    while combat.phase == CombatPhase.ACTION_EXECUTION:
        combat.step_next_action()
    assert any(s.status == StatusType.ATTACK_UP for s in jack.statuses)
