"""Runtime quest tracker, objective evaluator, and reward distributor."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from src.core.events import AudioCue, EventBus, QuestCompletedEvent, QuestUpdatedEvent
from src.systems.quests.quest_models import (
    ObjectiveType,
    QuestDefinition,
    QuestProgress,
    QuestStep,
)

if TYPE_CHECKING:
    from src.entities.party import Party


class QuestManager:
    """Tracks active/completed quests and advances sequential objectives."""

    def __init__(
        self,
        registry: dict[str, QuestDefinition] | None = None,
        event_bus: EventBus | None = None,
        party: Party | None = None,
    ) -> None:
        if registry is None:
            from src.data.quests import QUEST_REGISTRY

            registry = QUEST_REGISTRY
        self.registry: dict[str, QuestDefinition] = registry
        self.event_bus = event_bus or EventBus()
        self.party = party

        self.active_quests: dict[str, QuestProgress] = {}
        self.completed_quests: list[str] = []
        self.tracked_quest_id: str | None = None

    def bind_party(self, party: Party) -> None:
        """Attach the current Party instance for reward claims and item checks."""
        self.party = party

    def initialize_auto_quests(self) -> None:
        """Start all quests marked with auto_start=True whose prerequisites are met."""
        for qid, defn in self.registry.items():
            if defn.auto_start and qid not in self.active_quests and qid not in self.completed_quests:
                self.start_quest(qid)

    def start_quest(self, quest_id: str) -> bool:
        """Activate a quest if defined, unstarted, and prerequisites are satisfied."""
        defn = self.registry.get(quest_id)
        if defn is None or not defn.steps:
            return False
        if quest_id in self.active_quests or quest_id in self.completed_quests:
            return False
        if any(req not in self.completed_quests for req in defn.prereq_quests):
            return False

        self.active_quests[quest_id] = QuestProgress(quest_id=quest_id, step_index=0, current_count=0)
        if self.tracked_quest_id is None:
            self.tracked_quest_id = quest_id

        first_step = defn.steps[0]
        self.event_bus.emit(
            QuestUpdatedEvent(
                quest_id=quest_id,
                quest_title=defn.title,
                step_description=first_step.description,
                is_new=True,
            )
        )
        return True

    def is_quest_active(self, quest_id: str) -> bool:
        return quest_id in self.active_quests

    def is_quest_completed(self, quest_id: str) -> bool:
        return quest_id in self.completed_quests

    def is_step_active(self, quest_id: str, step_id: str) -> bool:
        step = self.get_current_step(quest_id)
        return step is not None and step.id == step_id

    def is_step_completed(self, quest_id: str, step_id: str) -> bool:
        """Return True if quest_id is completed or has already advanced past step_id."""
        if quest_id in self.completed_quests:
            return True
        prog = self.active_quests.get(quest_id)
        defn = self.registry.get(quest_id)
        if prog is None or defn is None:
            return False
        for idx, step in enumerate(defn.steps):
            if step.id == step_id:
                return prog.step_index > idx
        return False

    def get_current_step(self, quest_id: str) -> QuestStep | None:
        prog = self.active_quests.get(quest_id)
        defn = self.registry.get(quest_id)
        if prog is None or defn is None:
            return None
        if 0 <= prog.step_index < len(defn.steps):
            return defn.steps[prog.step_index]
        return None

    def set_tracked_quest(self, quest_id: str) -> bool:
        if quest_id in self.active_quests:
            self.tracked_quest_id = quest_id
            return True
        return False

    def get_tracked_quest(self) -> tuple[QuestDefinition, QuestProgress, QuestStep] | None:
        if self.tracked_quest_id and self.tracked_quest_id in self.active_quests:
            qid = self.tracked_quest_id
        elif self.active_quests:
            qid = next(iter(self.active_quests))
            self.tracked_quest_id = qid
        else:
            return None
        defn = self.registry.get(qid)
        prog = self.active_quests.get(qid)
        step = self.get_current_step(qid)
        if defn is None or prog is None or step is None:
            return None
        return defn, prog, step

    def format_step_label(self, prog: QuestProgress, step: QuestStep) -> str:
        if step.required_count > 1:
            return f"{step.description} ({prog.current_count}/{step.required_count})"
        return step.description

    # ------------------------------------------------------------------
    # Event / Gameplay Hooks
    # ------------------------------------------------------------------
    def on_dialogue_choice(self, dialogue_id: str, node_id: str, choice_index: int) -> None:
        for qid in list(self.active_quests):
            step = self.get_current_step(qid)
            if step is None or step.objective_type != ObjectiveType.DIALOGUE_CHOICE:
                continue
            if step.target_id != dialogue_id:
                continue
            if step.node_id is not None and step.node_id != node_id:
                continue
            if step.choice_index is not None and step.choice_index != choice_index:
                continue
            self._advance_quest(qid)

    def on_dialogue_started(self, dialogue_id: str) -> None:
        for qid in list(self.active_quests):
            step = self.get_current_step(qid)
            if step is None or step.objective_type != ObjectiveType.DIALOGUE_STARTED:
                continue
            if step.target_id == dialogue_id:
                self._advance_quest(qid)

    def on_dialogue_finished(self, dialogue_id: str) -> None:
        for qid in list(self.active_quests):
            step = self.get_current_step(qid)
            if step is None or step.objective_type != ObjectiveType.TALK_TO_NPC:
                continue
            if step.target_id == dialogue_id:
                self._advance_quest(qid)

    def on_player_moved(
        self,
        map_id: str,
        px: float,
        py: float,
        target_positions: dict[str, tuple[float, float]] | None = None,
    ) -> list[str]:
        triggered_dialogues: list[str] = []

        for qid, defn in self.registry.items():
            if defn.unlock_proximity is None:
                continue
            if qid in self.active_quests or qid in self.completed_quests:
                continue
            u_map, u_target, u_radius = defn.unlock_proximity
            if u_map != map_id:
                continue
            pos = target_positions.get(u_target) if target_positions else None
            if pos is None:
                continue
            if math.hypot(px - pos[0], py - pos[1]) <= u_radius:
                if self.start_quest(qid) and defn.unlock_dialogue_id:
                    triggered_dialogues.append(defn.unlock_dialogue_id)

        for qid in list(self.active_quests):
            step = self.get_current_step(qid)
            if step is None:
                continue
            if step.objective_type == ObjectiveType.ENTER_MAP:
                expected_map = step.map_id or step.target_id
                if expected_map == map_id:
                    self._advance_quest(qid)
            elif step.objective_type == ObjectiveType.REACH_PROXIMITY:
                expected_map = step.map_id
                if expected_map is not None and expected_map != map_id:
                    continue
                pos = step.target_pos or (target_positions.get(step.target_id) if target_positions else None)
                if pos is None:
                    continue
                dist = math.hypot(px - pos[0], py - pos[1])
                if dist <= step.proximity_radius:
                    self._advance_quest(qid)

        return triggered_dialogues

    def on_enemy_defeated(self, enemy_template_id: str, count: int = 1) -> None:
        for qid in list(self.active_quests):
            step = self.get_current_step(qid)
            prog = self.active_quests.get(qid)
            if step is None or prog is None or step.objective_type != ObjectiveType.KILL_ENEMY:
                continue
            if step.target_id != enemy_template_id:
                continue
            prog.current_count = min(step.required_count, prog.current_count + max(1, count))
            if prog.current_count >= step.required_count:
                self._advance_quest(qid)

    def on_inventory_changed(self, party: Party | None = None) -> None:
        p = party or self.party
        if p is None:
            return
        for qid in list(self.active_quests):
            step = self.get_current_step(qid)
            prog = self.active_quests.get(qid)
            if step is None or prog is None or step.objective_type != ObjectiveType.COLLECT_ITEM:
                continue
            owned = p.inventory.get(step.target_id, 0)
            prog.current_count = min(step.required_count, owned)
            if owned >= step.required_count:
                self._advance_quest(qid)

    def on_flag_set(self, flag_name: str) -> None:
        for qid in list(self.active_quests):
            step = self.get_current_step(qid)
            if step is None or step.objective_type != ObjectiveType.FLAG_SET:
                continue
            if step.target_id == flag_name:
                self._advance_quest(qid)

    # ------------------------------------------------------------------
    # Progression & Rewards
    # ------------------------------------------------------------------
    def _advance_quest(self, quest_id: str) -> None:
        prog = self.active_quests.get(quest_id)
        defn = self.registry.get(quest_id)
        if prog is None or defn is None:
            return

        next_idx = prog.step_index + 1
        if next_idx < len(defn.steps):
            prog.step_index = next_idx
            prog.current_count = 0
            next_step = defn.steps[next_idx]
            self.event_bus.emit(
                QuestUpdatedEvent(
                    quest_id=quest_id,
                    quest_title=defn.title,
                    step_description=next_step.description,
                    is_new=False,
                )
            )
            # Re-evaluate inventory in case next step is COLLECT_ITEM already in bag
            if next_step.objective_type == ObjectiveType.COLLECT_ITEM:
                self.on_inventory_changed()
            return

        # Final step completed -> auto-claim rewards!
        del self.active_quests[quest_id]
        if quest_id not in self.completed_quests:
            self.completed_quests.append(quest_id)

        self._grant_rewards(defn)
        if self.tracked_quest_id == quest_id:
            self.tracked_quest_id = next(iter(self.active_quests), None)

        self.event_bus.emit_audio(AudioCue.VICTORY)
        self.event_bus.emit(
            QuestCompletedEvent(
                quest_id=quest_id,
                quest_title=defn.title,
                reward_summary=defn.reward.summary_text(),
            )
        )
        # Unlock any follow-up auto-start quests whose prerequisites are now met
        self.initialize_auto_quests()

    def _grant_rewards(self, defn: QuestDefinition) -> None:
        if self.party is None:
            return
        reward = defn.reward
        if reward.gold > 0:
            self.party.gold += reward.gold
        if reward.exp > 0:
            for member in self.party.active_members:
                member.gain_exp(reward.exp)
        for item_id, qty in reward.items.items():
            if qty > 0:
                self.party.add_item(item_id, qty)
        for flag in reward.flags:
            self.party.quest_flags[flag] = True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "active_quests": {qid: prog.to_dict() for qid, prog in self.active_quests.items()},
            "completed_quests": list(self.completed_quests),
            "tracked_quest_id": self.tracked_quest_id,
        }

    def load_dict(self, data: dict[str, Any] | None) -> None:
        self.active_quests.clear()
        self.completed_quests.clear()
        self.tracked_quest_id = None
        if not data:
            return

        raw_active = data.get("active_quests", {})
        if isinstance(raw_active, dict):
            for qid, p_data in raw_active.items():
                if qid in self.registry and isinstance(p_data, dict):
                    prog = QuestProgress.from_dict(p_data)
                    prog.quest_id = qid
                    self.active_quests[qid] = prog

        raw_completed = data.get("completed_quests", [])
        if isinstance(raw_completed, list):
            for qid in raw_completed:
                if qid in self.registry and qid not in self.completed_quests:
                    self.completed_quests.append(qid)

        tracked = data.get("tracked_quest_id")
        if isinstance(tracked, str) and tracked in self.active_quests:
            self.tracked_quest_id = tracked
        elif self.active_quests:
            self.tracked_quest_id = next(iter(self.active_quests))
