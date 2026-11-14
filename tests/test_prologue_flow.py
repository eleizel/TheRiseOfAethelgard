"""End-to-end integration test simulating the entire Prologue narrative flow."""

from src.core.fsm import GameMode
from src.core.session import GameSession
from src.frontends.pygame_ce.views.dialogue_view import DialogueView
from src.systems.combat.action import ActionType, CombatAction
from src.systems.combat.round_combat import CombatPhase


def test_complete_prologue_narrative_flow():
    # 1. Initialize Game in Oakhaven
    session = GameSession(seed=777)
    session.initialize_new_game()
    assert session.map_id == "oakhaven_village"
    assert len(session.party.active_members) == 4
    dialogue_view = DialogueView(session)

    # 2. Rowan talks to Elder Tomas
    dialogue_view.start_dialogue("elder_tomas")
    session.transition_to(GameMode.DIALOGUE)

    # Fast-forward through conversation
    dialogue_view._advance_node()  # to choices
    dialogue_view._advance_to_node("elder_ready")  # pick ready choice
    dialogue_view._advance_node()  # to elder_end
    dialogue_view._advance_node()  # executes FLAG_MET_ELDER and closes

    assert session.party.quest_flags.get("met_elder") is True
    assert session.current_mode == GameMode.EXPLORATION

    # 3. Rowan enters Briarwood Verge
    session.map_id = "briarwood_edge"
    session.player_x = 13
    session.player_y = 17

    # 4. Confront the Corrupted Treant Boss
    dialogue_view.start_dialogue("treant_boss")
    session.transition_to(GameMode.DIALOGUE)
    dialogue_view._advance_node()  # to boss_2
    dialogue_view._advance_node()  # triggers START_BOSS_COMBAT

    assert session.current_mode == GameMode.COMBAT
    assert session.combat is not None
    assert session.combat.enemies[0].name == "Corrupted Treant"

    # 5. Battle resolution: Party unleashes all abilities
    combat = session.combat
    # Rowan smites
    combat.queue_player_action(CombatAction(actor_id="rowan", is_player=True, action_type=ActionType.ATTACK, target_id="treant_boss"))
    # Lyra heals/wards
    combat.queue_player_action(CombatAction(actor_id="lyra", is_player=True, action_type=ActionType.DEFEND))
    # Caelen strikes
    combat.queue_player_action(CombatAction(actor_id="caelen", is_player=True, action_type=ActionType.ATTACK, target_id="treant_boss"))
    # Melissa casts Pyroclasm/Fire
    combat.queue_player_action(CombatAction(actor_id="melissa", is_player=True, action_type=ActionType.ABILITY, ability_id="flame_lance", target_id="treant_boss"))

    # Force defeat treant to advance story
    combat.enemies[0].current_hp = 0
    combat._check_battle_end()
    assert combat.phase == CombatPhase.VICTORY

    # 6. Prologue Victory Dialogue
    dialogue_view.start_dialogue("prologue_victory")
    dialogue_view._advance_node()  # to vic_2
    dialogue_view._advance_node()  # to vic_3
    dialogue_view._advance_node()  # to vic_4
    dialogue_view._advance_node()  # triggers COMPLETE_PROLOGUE

    assert session.party.quest_flags.get("prologue_complete") is True
    # Gold and SP rewarded
    assert session.party.gold >= 400
    assert session.party.active_members[0].skill_points >= 4
