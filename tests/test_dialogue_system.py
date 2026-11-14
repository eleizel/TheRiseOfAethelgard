"""Unit tests for the dialogue tree system, branching choices, and triggers."""

from src.core.session import GameSession
from src.data.dialogues import get_dialogue_tree
from src.frontends.pygame_ce.views.dialogue_view import DialogueView


def test_dialogue_tree_structure():
    tree = get_dialogue_tree("elder_tomas")
    assert tree.id == "elder_tomas"
    assert tree.start_node_id == "elder_1"

    node = tree.get_node("elder_1")
    assert node is not None
    assert node.speaker_name == "Elder Tomas"
    assert node.next_node_id == "elder_choices"

    choices_node = tree.get_node("elder_choices")
    assert choices_node is not None
    assert len(choices_node.choices) == 3


def test_dialogue_view_execution_and_triggers():
    session = GameSession(seed=42)
    session.initialize_new_game()
    view = DialogueView(session)

    view.start_dialogue("elder_tomas")
    assert view.current_node.id == "elder_1"

    # Advance past elder_1
    view._advance_node()
    assert view.current_node.id == "elder_choices"
    assert len(view.current_node.choices) == 3

    # Choose option 2: "I will investigate the woods myself." -> elder_ready
    view._advance_to_node(view.current_node.choices[2].target_node_id)
    assert view.current_node.id == "elder_ready"

    # Advance to elder_end
    view._advance_node()
    assert view.current_node.id == "elder_end"
    assert view.current_node.action_trigger == "FLAG_MET_ELDER"

    # Close dialogue, trigger should execute
    view._advance_node()
    assert session.party.quest_flags.get("met_elder") is True


def test_rowan_house_inspect_dialogue_registered():
    """Verify rowan_house_inspect dialogue tree exists and loads correctly."""
    tree = get_dialogue_tree("rowan_house_inspect")
    assert tree.id == "rowan_house_inspect"
    assert tree.start_node_id == "house_1"
    node = tree.get_node("house_1")
    assert node.speaker_id == "rowan"
    assert "cottage" in node.text.lower()


def test_dialogue_view_safe_fallback_for_unknown_trees():
    """Verify DialogueView gracefully falls back without crashing on unregistered dialogue IDs."""
    session = GameSession(seed=42)
    view = DialogueView(session)
    view.start_dialogue("unregistered_inspect_point_xyz")
    assert view.current_node is not None
    assert view.current_node.id == "fallback_1"
    assert "nothing of note" in view.current_node.text.lower()

