"""Tests for the declarative Main/Side Quest system and persistence."""

from __future__ import annotations

from pathlib import Path

from src.core.events import QuestCompletedEvent, QuestUpdatedEvent
from src.core.persistence import FileStorageBackend
from src.core.save_manager import SaveManager
from src.core.session import GameSession
from src.data.quests import QUEST_REGISTRY
from src.frontends.pygame_ce.views.dialogue_view import DialogueView
from src.systems.quests import (
    ObjectiveType,
    QuestCategory,
    QuestDefinition,
    QuestManager,
    QuestReward,
    QuestStep,
)


def test_shadow_in_briarwood_full_flow():
    session = GameSession(seed=101)
    session.initialize_new_game()
    qm = session.quest_manager

    # Quest auto-starts on new game
    assert qm.is_quest_active("shadow_in_briarwood")
    step = qm.get_current_step("shadow_in_briarwood")
    assert step is not None and step.id == "speak_tomas_accept"

    # Picking options 0 or 1 does NOT advance step 1
    qm.on_dialogue_choice("elder_tomas", "elder_choices", 0)
    qm.on_dialogue_choice("elder_tomas", "elder_choices", 1)
    assert qm.get_current_step("shadow_in_briarwood").id == "speak_tomas_accept"

    # Picking option 3 (index 2) advances to explore_briarwood_verge
    qm.on_dialogue_choice("elder_tomas", "elder_choices", 2)
    assert qm.get_current_step("shadow_in_briarwood").id == "explore_briarwood_verge"

    # Far away (> 90px) does not complete proximity step
    qm.on_player_moved("briarwood_verge", 100.0, 100.0)
    assert qm.get_current_step("shadow_in_briarwood").id == "explore_briarwood_verge"

    # Within <= 90px of Corrupted Treant (418, 918) completes step 2
    qm.on_player_moved("briarwood_verge", 418.0, 840.0)
    assert qm.get_current_step("shadow_in_briarwood").id == "kill_corrupted_treant"

    # Defeating Corrupted Treant advances to report_to_tomas
    qm.on_enemy_defeated("corrupted_treant")
    assert qm.get_current_step("shadow_in_briarwood").id == "report_to_tomas"

    # DialogueView switches Elder Tomas to turn-in tree during report_to_tomas
    dv = DialogueView(session)
    dv.start_dialogue("elder_tomas")
    assert dv.current_tree is not None and dv.current_tree.id == "elder_tomas_complete"

    start_gold = session.party.gold
    start_poultices = session.party.inventory.get("healing_poultice", 0)

    # Finishing turn-in dialogue completes quest & auto-claims rewards
    qm.on_dialogue_finished("elder_tomas")
    assert not qm.is_quest_active("shadow_in_briarwood")
    assert qm.is_quest_completed("shadow_in_briarwood")
    assert session.party.gold == start_gold + 150
    assert session.party.inventory.get("healing_poultice", 0) == start_poultices + 2
    assert session.party.quest_flags.get("prologue_complete") is True


def test_all_objective_types_and_events():
    session = GameSession(seed=7)
    session.initialize_new_game()

    custom_registry = {
        "side_test": QuestDefinition(
            id="side_test",
            title="Test All Objectives",
            category=QuestCategory.SIDE,
            description="Covers map, kill count, collect, flag, and talk.",
            steps=(
                QuestStep("s_map", "Enter Moor", ObjectiveType.ENTER_MAP, target_id="ashen_moor"),
                QuestStep("s_kill", "Kill 2 Hounds", ObjectiveType.KILL_ENEMY, target_id="bramble_hound", required_count=2),
                QuestStep("s_item", "Collect 3 Herbs", ObjectiveType.COLLECT_ITEM, target_id="panacea_herbs", required_count=3),
                QuestStep("s_flag", "Set Flag", ObjectiveType.FLAG_SET, target_id="bridge_repaired"),
                QuestStep("s_talk", "Talk NPC", ObjectiveType.TALK_TO_NPC, target_id="innkeeper_party"),
            ),
            reward=QuestReward(gold=50),
        )
    }

    qm = QuestManager(registry=custom_registry, event_bus=session.event_bus, party=session.party)
    assert qm.start_quest("side_test")

    qm.on_player_moved("ashen_moor", 50.0, 50.0)
    assert qm.get_current_step("side_test").id == "s_kill"

    qm.on_enemy_defeated("bramble_hound")
    assert qm.active_quests["side_test"].current_count == 1
    qm.on_enemy_defeated("bramble_hound")
    assert qm.get_current_step("side_test").id == "s_item"

    session.party.add_item("panacea_herbs", 2)  # already had 2 -> 4 >= 3
    qm.on_inventory_changed()
    assert qm.get_current_step("side_test").id == "s_flag"

    qm.on_flag_set("bridge_repaired")
    assert qm.get_current_step("side_test").id == "s_talk"

    qm.on_dialogue_finished("innkeeper_party")
    assert qm.is_quest_completed("side_test")

    events = session.event_bus.drain()
    assert any(isinstance(e, QuestUpdatedEvent) for e in events)
    assert any(isinstance(e, QuestCompletedEvent) and e.quest_id == "side_test" for e in events)


def test_quest_save_load_roundtrip(tmp_path: Path):
    save_mgr = SaveManager(FileStorageBackend(base_dir=tmp_path))
    session = GameSession(save_manager=save_mgr, seed=42)
    session.initialize_new_game()
    session.quest_manager.on_dialogue_choice("elder_tomas", "elder_choices", 2)
    assert session.quest_manager.get_current_step("shadow_in_briarwood").id == "explore_briarwood_verge"

    assert session.save_game(slot_id=1) is True

    loaded = GameSession(save_manager=save_mgr, seed=1)
    assert loaded.load_game(slot_id=1) is True
    assert loaded.quest_manager.is_quest_active("shadow_in_briarwood")
    assert loaded.quest_manager.get_current_step("shadow_in_briarwood").id == "explore_briarwood_verge"
    assert set(QUEST_REGISTRY.keys()) >= {"shadow_in_briarwood", "briarwood_monolith"}


def test_briarwood_monolith_sidequest_flow():
    from src.data.items import ITEM_REGISTRY

    session = GameSession(seed=42)
    session.initialize_new_game()
    qm = session.quest_manager
    targets = {"special_encounter_trigger": (304.5, 630.5)}

    assert not qm.is_quest_active("briarwood_monolith")

    # > 120 px away: should not unlock
    triggered_far = qm.on_player_moved("briarwood_verge", 304.5, 630.5 - 125.0, target_positions=targets)
    assert triggered_far == []
    assert not qm.is_quest_active("briarwood_monolith")

    # <= 120 px away: unlocks sidequest and triggers discovery dialogue
    triggered_near = qm.on_player_moved("briarwood_verge", 304.5, 630.5 - 115.0, target_positions=targets)
    assert triggered_near == ["monolith_discovery"]
    assert qm.is_quest_active("briarwood_monolith")
    assert qm.get_current_step("briarwood_monolith").id == "interact_monolith"

    # Re-entering proximity does not re-trigger
    assert qm.on_player_moved("briarwood_verge", 304.5, 630.5 - 50.0, target_positions=targets) == []

    # Step 1: interact with the monolith
    qm.on_dialogue_started("special_encounter")
    assert qm.get_current_step("briarwood_monolith").id == "touch_spiral"

    # Step 2: option 1 does not advance; option 2 (choice_index=1) advances
    qm.on_dialogue_choice("special_encounter", "special_2", 0)
    assert qm.get_current_step("briarwood_monolith").id == "touch_spiral"
    qm.on_dialogue_choice("special_encounter", "special_2", 1)
    assert qm.get_current_step("briarwood_monolith").id == "kill_mandragora_matron"

    # Last step: kill Mandragora Matron and claim Bloomweave Vestments
    gold_before = session.party.gold
    qm.on_enemy_defeated("mandragora_matron")
    assert qm.is_quest_completed("briarwood_monolith")
    assert session.party.gold == gold_before + 90
    assert session.party.inventory.get("bloomweave_vestments") == 1

    vestments = ITEM_REGISTRY["bloomweave_vestments"]
    assert vestments.stat_bonus.max_hp > 0
    assert vestments.stat_bonus.magic_attack > 0


def test_scripted_combat_blocked_after_quest_step_completed():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame

    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))

    from src.core.fsm import GameMode
    from src.frontends.pygame_ce.views.dialogue_view import DialogueView

    session = GameSession(seed=42)
    session.initialize_new_game()
    session.transition_to(GameMode.EXPLORATION)
    qm = session.quest_manager
    dv = DialogueView(session)

    # Advance main quest past kill_corrupted_treant (still active on report_to_tomas)
    qm.on_dialogue_choice("elder_tomas", "elder_choices", 2)
    qm.on_player_moved("briarwood_verge", 418.0, 918.0)
    assert not qm.is_step_completed("shadow_in_briarwood", "kill_corrupted_treant")
    qm.on_enemy_defeated("corrupted_treant")
    assert qm.is_step_completed("shadow_in_briarwood", "kill_corrupted_treant")
    assert qm.get_current_step("shadow_in_briarwood").id == "report_to_tomas"

    # Re-interacting with treant_boss shows defeated flavor text and cannot trigger combat
    dv.start_dialogue("treant_boss")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "treant_boss_defeated"
    assert dv.current_node is not None and dv.current_node.next_node_id is None

    session.combat = None
    dv._execute_action_trigger("START_BOSS_COMBAT")
    assert session.combat is None
    assert session.current_mode == GameMode.EXPLORATION

    # Complete monolith sidequest and verify special_encounter / START_SPECIAL_COMBAT is blocked
    qm.on_player_moved(
        "briarwood_verge", 304.5, 630.5, target_positions={"special_encounter_trigger": (304.5, 630.5)}
    )
    qm.on_dialogue_started("special_encounter")
    qm.on_dialogue_choice("special_encounter", "special_2", 1)
    qm.on_enemy_defeated("mandragora_matron")
    assert qm.is_step_completed("briarwood_monolith", "kill_mandragora_matron")

    dv.start_dialogue("special_encounter")
    assert dv.current_tree is not None
    assert dv.current_tree.id == "special_encounter_defeated"
    dv._execute_action_trigger("START_SPECIAL_COMBAT")
    assert session.combat is None
    assert session.current_mode == GameMode.EXPLORATION
