"""Declarative registry of Main and Side quests."""

from __future__ import annotations

from typing import Final

from src.systems.quests.quest_models import (
    ObjectiveType,
    QuestCategory,
    QuestDefinition,
    QuestReward,
    QuestStep,
)

QUEST_REGISTRY: Final[dict[str, QuestDefinition]] = {
    "shadow_in_briarwood": QuestDefinition(
        id="shadow_in_briarwood",
        title="Shadows in Briarwood",
        category=QuestCategory.MAIN,
        description=(
            "Oakhaven's frontier is rotting with black sap. Speak with Elder Tomas, "
            "investigate the Briarwood Verge, and defeat the Corrupted Treant."
        ),
        auto_start=True,
        steps=(
            QuestStep(
                id="speak_tomas_accept",
                description="Talk to Elder Tomas in Oakhaven and volunteer to investigate",
                objective_type=ObjectiveType.DIALOGUE_CHOICE,
                target_id="elder_tomas",
                node_id="elder_choices",
                choice_index=2,
            ),
            QuestStep(
                id="explore_briarwood_verge",
                description="Explore deep into Briarwood Verge to locate the corruption",
                objective_type=ObjectiveType.REACH_PROXIMITY,
                target_id="talk_treant_boss",
                map_id="briarwood_verge",
                proximity_radius=90.0,
                target_pos=(418.0, 918.0),
            ),
            QuestStep(
                id="kill_corrupted_treant",
                description="Defeat the Corrupted Treant in Briarwood Verge",
                objective_type=ObjectiveType.KILL_ENEMY,
                target_id="corrupted_treant",
                required_count=1,
            ),
            QuestStep(
                id="report_to_tomas",
                description="Return to Oakhaven and report to Elder Tomas",
                objective_type=ObjectiveType.TALK_TO_NPC,
                target_id="elder_tomas",
            ),
        ),
        reward=QuestReward(
            exp=120,
            gold=150,
            items={"healing_poultice": 2},
            flags=("prologue_complete",),
        ),
    ),
    "briarwood_monolith": QuestDefinition(
        id="briarwood_monolith",
        title="The Foul Monolith",
        category=QuestCategory.SIDE,
        description=(
            "A strange monolith in Briarwood Verge radiates foul energy. "
            "Investigate the monolith and quell whatever lurks within."
        ),
        unlock_proximity=("briarwood_verge", "special_encounter_trigger", 120.0),
        unlock_dialogue_id="monolith_discovery",
        steps=(
            QuestStep(
                id="interact_monolith",
                description="Inspect the glowing monolith in Briarwood Verge",
                objective_type=ObjectiveType.DIALOGUE_STARTED,
                target_id="special_encounter",
            ),
            QuestStep(
                id="touch_spiral",
                description="Reach for the glowing spiral on the monolith",
                objective_type=ObjectiveType.DIALOGUE_CHOICE,
                target_id="special_encounter",
                node_id="special_2",
                choice_index=1,
            ),
            QuestStep(
                id="kill_mandragora_matron",
                description="Defeat the Mandragora Matron",
                objective_type=ObjectiveType.KILL_ENEMY,
                target_id="mandragora_matron",
                required_count=1,
            ),
        ),
        reward=QuestReward(
            exp=100,
            gold=90,
            items={"bloomweave_vestments": 1},
        ),
    ),
}
