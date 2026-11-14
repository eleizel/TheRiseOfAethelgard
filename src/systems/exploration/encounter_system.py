"""Encounter manager handling hybrid random step encounters and visible elite entities."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class WanderingElite:
    """A visible monster patrolling the map."""
    id: str
    name: str
    x: float
    y: float
    radius: float = 16.0
    patrol_direction: int = 1
    speed: float = 20.0
    aggro_range: float = 64.0

    def update(self, dt: float, min_x: float, max_x: float) -> None:
        self.x += self.patrol_direction * self.speed * dt
        if self.x <= min_x:
            self.x = min_x
            self.patrol_direction = 1
        elif self.x >= max_x:
            self.x = max_x
            self.patrol_direction = -1

    def is_touching_player(self, px: float, py: float, touch_radius: float = 24.0) -> bool:
        dist_sq = (self.x - px) ** 2 + (self.y - py) ** 2
        return dist_sq <= touch_radius ** 2


class EncounterSystem:
    """Manages wild encounter step thresholds and elite encounters."""

    SAFE_ZONES = {"oakhaven_village", "oakhaven_village_main"}

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.step_counter: float = 0.0
        self.min_steps_between_encounters: float = 180.0  # ~3 seconds of continuous movement
        self.encounter_rate: float = 0.006

    def record_movement(self, distance_pixels: float, map_id: str) -> bool:
        """Accumulate movement. Returns True if a wild combat encounter is triggered."""
        if map_id in self.SAFE_ZONES or distance_pixels <= 0.0:
            return False

        self.step_counter += distance_pixels
        if self.step_counter < self.min_steps_between_encounters:
            return False

        # Dice roll for encounter
        roll = self.rng.random()
        threshold = self.encounter_rate * (self.step_counter - self.min_steps_between_encounters) / 100.0
        if roll < threshold:
            self.step_counter = 0.0
            return True

        return False

    def reset_steps(self) -> None:
        self.step_counter = 0.0
