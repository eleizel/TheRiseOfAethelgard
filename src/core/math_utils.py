"""Mathematical utilities for combat formulas, stat calculations, and progression."""

from __future__ import annotations

import random


def calculate_damage(
    raw_dmg: int,
    defense: int,
    defense_penetration: float = 0.0,
    elemental_multiplier: float = 1.0,
    is_crit: bool = False,
    crit_multiplier: float = 1.5,
    variance: float = 0.10,
    rng: random.Random | None = None,
) -> int:
    """Calculate damage incorporating defense mitigation, penetration, elements, and variance.

    Formulas:
    - Defense reduces incoming damage through flat threshold and percentage mitigation.
    - Elemental affinities (Weakness = 1.5x / 2.0x, Resistance = 0.5x, Immune = 0.0x).
    - Critical hits apply crit_multiplier.
    - Final damage applies slight +- variance (default +-10%).
    """
    penetration = max(0.0, min(1.0, defense_penetration))
    effective_defense = max(0, int(defense * (1 - penetration)))

    flat_reduction = effective_defense // 5
    remaining_damage = max(0, raw_dmg - flat_reduction)

    # Diminishing returns asymptotic armor curve capped at 65% mitigation
    mitigation = min(0.65, effective_defense / (effective_defense + 100))
    base_damage = remaining_damage * (1.0 - mitigation)

    # Elemental affinity
    damage_with_element = base_damage * max(0.0, elemental_multiplier)

    # Critical hit
    if is_crit:
        damage_with_element *= crit_multiplier

    # Damage variance
    if variance > 0.0:
        generator = rng or random
        spread = generator.uniform(1.0 - variance, 1.0 + variance)
        final_damage = damage_with_element * spread
    else:
        final_damage = damage_with_element

    return max(1, int(round(final_damage))) if elemental_multiplier > 0 else 0


def calculate_exp_threshold(level: int) -> int:
    """Calculate the total EXP required to reach the next level."""
    return int(50 + 20 * (level - 1) + 10 * ((level - 1) ** 2))
