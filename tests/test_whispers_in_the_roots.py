from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.core.fsm import GameMode
from src.core.session import GameSession
from src.frontends.pygame_ce.views.dialogue_view import DialogueView


def test_whispers_in_the_roots_lifecycle():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))

    session = GameSession(seed=42)
    session.initialize_new_game()
    session.transition_to(GameMode.EXPLORATION)

    # Complete prologue quest first
    qm = session.quest_manager
    qm.completed_quests.append("shadow_in_briarwood")
    qm.active_quests.pop("shadow_in_briarwood", None)

    dv = DialogueView(session)

    # Talking to Elder Tomas after Corrupted Treant routes to elder_tomas_whispers with 'elder' portrait
    dv.start_dialogue("elder_tomas")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "elder_tomas_whispers"
    assert dv.current_node is not None
    assert dv.current_node.speaker_id == "elder"

    # Accepting via START_QUEST_WHISPERS_IN_THE_ROOTS starts quest and advances to reach_rooted_hollows
    dv._execute_action_trigger("START_QUEST_WHISPERS_IN_THE_ROOTS")
    assert qm.is_quest_active("whispers_in_the_roots")
    assert qm.get_current_step("whispers_in_the_roots").id == "reach_rooted_hollows"

    # Talking to Elder Tomas while active routes to elder_tomas_whispers_active
    dv.start_dialogue("elder_tomas")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "elder_tomas_whispers_active"

    # Step 2: Enter Rooted Hollows
    qm.on_player_moved("rooted_hollows", 320.0, 100.0)
    assert qm.get_current_step("whispers_in_the_roots").id == "defeat_root_guardian"

    # Blight Font cannot be sealed before defeating Root Goliath
    dv.start_dialogue("seal_blight_font_dialogue")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "seal_blight_font_locked"
    dv._execute_action_trigger("SEAL_ROOT_FONT")
    assert not session.party.quest_flags.get("root_font_sealed")

    # Step 3: Defeat Root Goliath (and verify combat cannot be re-triggered)
    qm.on_enemy_defeated("root_goliath", 1)
    assert qm.get_current_step("whispers_in_the_roots").id == "seal_root_font"
    dv.start_dialogue("root_goliath_boss")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "root_goliath_boss_defeated"

    # Step 4: Seal Blight Font -> completes quest & grants rewards
    dv.start_dialogue("seal_blight_font_dialogue")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "seal_blight_font_dialogue"
    dv._execute_action_trigger("SEAL_ROOT_FONT")

    assert qm.is_quest_completed("whispers_in_the_roots")
    assert session.party.gold >= 300
    assert session.party.inventory.get("sunfire_blade", 0) >= 1
    assert session.party.quest_flags.get("whispers_in_the_roots_completed") is True

    # Elder Tomas now reflects quest completion
    dv.start_dialogue("elder_tomas")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "elder_tomas_whispers_done"
