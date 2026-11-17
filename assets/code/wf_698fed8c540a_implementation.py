"""Quest Manager for tracking active and completed quests in The Rise of Aethelgard."""

from typing import Dict, List, Optional, Any


class QuestManager:
    """Manages quest lifecycles, objectives, and stage progressions."""

    def __init__(self) -> None:
        self.quests: Dict[str, Dict[str, Any]] = {
            "shadows_over_the_verge": {
                "id": "shadows_over_the_verge",
                "name": "Shadows over the Verge",
                "status": "NOT_STARTED",  # NOT_STARTED, ACTIVE, COMPLETED
                "current_stage": 0,
                "stages": [
                    {
                        "stage_id": 0,
                        "name": "The Elder's Debrief",
                        "description": "Return to Oakhaven Village and speak with Elder Tomas at the inn.",
                        "completed": False,
                    },
                    {
                        "stage_id": 1,
                        "name": "Verge Incursion",
                        "description": "Travel to the northern boundary and enter the Verge Outpost Ruins.",
                        "completed": False,
                    },
                    {
                        "stage_id": 2,
                        "name": "Intercept the Patrol",
                        "description": "Locate Scout Vane and defeat the Root Blight ambush patrol.",
                        "completed": False,
                    },
                    {
                        "stage_id": 3,
                        "name": "Mission Complete",
                        "description": "Secure the Blighted Core and report the findings.",
                        "completed": False,
                    },
                ],
            }
        }

    def start_quest(self, quest_id: str) -> bool:
        if quest_id in self.quests and self.quests[quest_id]["status"] == "NOT_STARTED":
            self.quests[quest_id]["status"] = "ACTIVE"
            self.quests[quest_id]["current_stage"] = 0
            return True
        return False

    def advance_stage(self, quest_id: str) -> int:
        if quest_id not in self.quests or self.quests[quest_id]["status"] != "ACTIVE":
            return -1

        quest = self.quests[quest_id]
        current = quest["current_stage"]
        if current < len(quest["stages"]) - 1:
            quest["stages"][current]["completed"] = True
            quest["current_stage"] += 1
            return quest["current_stage"]
        else:
            quest["stages"][current]["completed"] = True
            quest["status"] = "COMPLETED"
            return -1

    def get_quest_status(self, quest_id: str) -> Optional[str]:
        if quest_id in self.quests:
            return self.quests[quest_id]["status"]
        return None
