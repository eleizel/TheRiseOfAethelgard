"""GameSession orchestrating domain state, event bus, FSM, and persistence."""

from __future__ import annotations

import random
from typing import Any

from src.core.events import EventBus, StateChangedEvent
from src.core.fsm import GameMode, StateMachine
from src.core.persistence import SaveMemento
from src.core.save_manager import SaveManager
from src.data.characters import create_character
from src.data.skill_trees import CHARACTER_TREES, create_character_skill_tree
from src.entities.party import Party
from src.systems.progression.skill_tree import CharacterSkillTree
from src.systems.quests import QuestManager


class GameSession:
    """Central domain session maintaining runtime state, party, and progression."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        save_manager: SaveManager | None = None,
        seed: int | None = None,
    ) -> None:
        self.seed = seed if seed is not None else random.randint(1, 1_000_000)
        self.rng = random.Random(self.seed)
        self.event_bus = event_bus or EventBus()
        self.save_manager = save_manager or SaveManager()
        self.fsm = StateMachine(initial_mode=GameMode.TITLE)

        self.party = Party()
        self.skill_trees: dict[str, CharacterSkillTree] = {}
        self.quest_manager = QuestManager(event_bus=self.event_bus, party=self.party)
        self.map_id = "oakhaven_village"
        self.player_x = 10
        self.player_y = 10
        self.player_pixel_x: float | None = None
        self.player_pixel_y: float | None = None
        self._needs_exploration_sync: bool = False
        self.play_time_seconds = 0.0
        self.combat: Any = None  # Populated when entering COMBAT mode

    @property
    def current_mode(self) -> GameMode:
        return self.fsm.current_mode

    def transition_to(self, target_mode: GameMode) -> bool:
        """Attempt to transition modes and emit domain event if successful."""
        old_mode = self.fsm.current_mode
        if self.fsm.transition_to(target_mode, self):
            self.event_bus.emit(
                StateChangedEvent(
                    previous_mode=old_mode.name,
                    new_mode=target_mode.name,
                )
            )
            return True
        return False

    def rest_at_inn(self, cost: int = 50) -> bool:
        """Attempt to rest at an inn, deducting cost and fully restoring party HP/MP and cleansing status."""
        if self.party.gold < cost:
            return False
        self.party.gold -= cost
        for member in self.party.active_members + self.party.reserve_members:
            eff = member.effective_stats
            member.current_hp = eff.max_hp
            member.current_mp = eff.max_mp
            member.clear_negative_statuses()
        return True

    def has_character(self, char_id: str) -> bool:
        """Return True if char_id is already unlocked in active or reserve party."""
        return any(m.id == char_id for m in self.party.active_members + self.party.reserve_members)

    def unlock_character(self, char_id: str, skill_points_bonus: int = 0) -> Any | None:
        """Unlock a new companion at Rowan's current level with class stat growth applied."""
        if self.has_character(char_id):
            return None
        rowan = next((m for m in self.party.active_members + self.party.reserve_members if m.id == "rowan"), None)
        target_level = rowan.level if rowan is not None else 1
        char = create_character(char_id, level=target_level)
        if skill_points_bonus > 0:
            char.skill_points += skill_points_bonus
        self.party.add_character(char)
        self.skill_trees[char_id] = create_character_skill_tree(char_id)
        return char

    def initialize_new_game(self) -> None:
        """Create new game state starting in Oakhaven with Rowan and Rachel."""
        self.party = Party(gold=250)
        for char_id in ["rowan", "rachel"]:
            char = create_character(char_id, level=1)
            char.skill_points = 2  # Starting talent points to test skill trees immediately
            self.party.add_character(char)
            self.skill_trees[char_id] = create_character_skill_tree(char_id)

        # Starter supplies & equipment in party inventory
        self.party.add_item("healing_poultice", 4)
        self.party.add_item("mana_draught", 3)
        self.party.add_item("panacea_herbs", 2)
        self.party.add_item("sunwarden_blade", 1)
        self.party.add_item("shadow_fang", 1)
        self.party.add_item("silver_ring", 2)

        self.map_id = "oakhaven_village"
        self.player_x = 10
        self.player_y = 10
        self.player_pixel_x = None
        self.player_pixel_y = None
        self._needs_exploration_sync = True
        self.play_time_seconds = 0.0
        self.quest_manager = QuestManager(event_bus=self.event_bus, party=self.party)
        self.quest_manager.initialize_auto_quests()
        self.transition_to(GameMode.EXPLORATION)

    def create_memento(self, slot_id: int = 1) -> SaveMemento:
        """Create a serializable snapshot of current session state."""
        party_dict = self.party.to_dict()
        party_dict["skill_trees"] = {
            cid: tree.to_dict() for cid, tree in self.skill_trees.items()
        }
        party_dict["quests"] = self.quest_manager.to_dict()
        return SaveMemento(
            slot_id=slot_id,
            play_time_seconds=self.play_time_seconds,
            current_mode=self.current_mode.name,
            map_id=self.map_id,
            player_x=self.player_x,
            player_y=self.player_y,
            player_pixel_x=self.player_pixel_x,
            player_pixel_y=self.player_pixel_y,
            party=party_dict,
            run_seed=self.seed,
        )

    def restore_from_memento(self, memento: SaveMemento) -> None:
        """Restore session state from a verified memento."""
        self.party = Party.from_dict(memento.party)
        raw_trees = memento.party.get("skill_trees", {})
        self.skill_trees = {}
        for cid, t_data in raw_trees.items():
            nodes = CHARACTER_TREES.get(cid, {})
            self.skill_trees[cid] = CharacterSkillTree.from_dict(t_data, nodes)

        # Ensure all party members have a skill tree
        for m in self.party.active_members + self.party.reserve_members:
            if m.id not in self.skill_trees:
                self.skill_trees[m.id] = create_character_skill_tree(m.id)

        self.quest_manager = QuestManager(event_bus=self.event_bus, party=self.party)
        self.quest_manager.load_dict(memento.party.get("quests"))

        self.map_id = memento.map_id
        self.player_x = memento.player_x
        self.player_y = memento.player_y
        self.player_pixel_x = memento.player_pixel_x
        self.player_pixel_y = memento.player_pixel_y
        self._needs_exploration_sync = True
        self.play_time_seconds = memento.play_time_seconds
        self.seed = memento.run_seed or self.seed
        self.rng = random.Random(self.seed)

        target_mode = (
            GameMode[memento.current_mode]
            if memento.current_mode in GameMode.__members__
            else GameMode.EXPLORATION
        )
        self.fsm = StateMachine(initial_mode=target_mode)

    def save_game(self, slot_id: int = 1) -> bool:
        """Persist current session to designated slot."""
        memento = self.create_memento(slot_id=slot_id)
        return self.save_manager.save_game(memento, slot_id=slot_id)

    def load_game(self, slot_id: int = 1) -> bool:
        """Load session from designated slot."""
        memento = self.save_manager.load_game(slot_id=slot_id)
        if memento is None:
            return False
        self.restore_from_memento(memento)
        return True
