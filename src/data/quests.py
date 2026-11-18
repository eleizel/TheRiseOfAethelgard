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
    "whispers_in_the_roots": QuestDefinition(
        id="whispers_in_the_roots",
        title="Whispers in the Roots",
        category=QuestCategory.MAIN,
        description=(
            "Descend into the Rooted Hollows beneath Briarwood and "
            "neutralize the pulsing Blight font."
        ),
        auto_start=False,
        prereq_quests=("shadow_in_briarwood",),
        steps=(
            QuestStep(
                id="talk_elder_tomas",
                description="Speak with Elder Tomas in Oakhaven about the seismic tremors.",
                objective_type=ObjectiveType.DIALOGUE_CHOICE,
                target_id="elder_tomas_whispers",
                node_id="elder_whispers_choices",
                choice_index=0,
            ),
            QuestStep(
                id="reach_rooted_hollows",
                description="Locate the hidden cavern entrance in Briarwood Verge.",
                objective_type=ObjectiveType.ENTER_MAP,
                target_id="rooted_hollows",
            ),
            QuestStep(
                id="defeat_root_guardian",
                description="Defeat the Root Goliath guarding the subterranean font.",
                objective_type=ObjectiveType.KILL_ENEMY,
                target_id="root_goliath",
                required_count=1,
            ),
            QuestStep(
                id="seal_root_font",
                description="Interact with the Blight Font to seal it permanently.",
                objective_type=ObjectiveType.FLAG_SET,
                target_id="root_font_sealed",
            ),
        ),
        reward=QuestReward(
            exp=250,
            gold=300,
            items={"elixir_of_dawn": 2, "sunfire_blade": 1},
            flags=("whispers_in_the_roots_completed",),
        ),
        unlock_proximity=("briarwood_verge", "root_cave_entrance", 96.0),
        unlock_dialogue_id="elder_tomas_whispers_start",
    ),
}
