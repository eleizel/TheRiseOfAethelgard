from __future__ import annotations

from src.core.session import GameSession


def test_whispers_in_the_roots_lifecycle():
    session = GameSession()
    session.initialize_new_game()
    
    # Simulate prerequisite completion
    session.quest_manager.completed_quests.append("shadow_in_briarwood")
    
    # Start quest via manager
    assert session.quest_manager.start_quest("whispers_in_the_roots") is True
    
    # Step 1: Talk to Elder Tomas
    q = session.quest_manager.active_quests["whispers_in_the_roots"]
    assert q.step_index == 0
    session.quest_manager.on_dialogue_finished("elder_tomas_whispers")
    
    # Step 2: Reach Rooted Hollows
    assert q.step_index == 1
    session.quest_manager.on_player_moved("rooted_hollows", 320.0, 100.0, target_positions={"rooted_hollows": (320.0, 100.0)})
    
    # Step 3: Defeat Root Goliath
    assert q.step_index == 2
    session.quest_manager.on_enemy_defeated("root_goliath", 1)
    
    # Step 4: Seal Blight Font
    assert q.step_index == 3
    session.quest_manager.on_flag_set("root_font_sealed")
    
    # Quest completion & rewards
    assert "whispers_in_the_roots" in session.quest_manager.completed_quests
    assert session.party.gold >= 300
    assert session.party.inventory.get("sunfire_blade", 0) >= 1
    assert session.party.quest_flags.get("whispers_in_the_roots_completed") is True
