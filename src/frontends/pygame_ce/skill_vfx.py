"""Declarative data-driven VFX configuration for combat skills and abilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

PlacementMode = Literal[
    "caster",
    "projectile_to_target",
    "target_each",
    "target_group_center",
]
CasterAnimMode = Literal["lunge", "spell", "none"]


@dataclass(frozen=True)
class VFXPhase:
    """Single visual effect phase within a skill's presentation timeline."""

    prefix: str
    placement: PlacementMode
    start_time: float = 0.0
    duration: float = 0.60
    frame_count: int | None = None
    offset: tuple[float, float] = (0.0, 0.0)
    arc_height: float = 0.0
    scale: float = 1.0
    flip_for_enemy: bool = True


@dataclass(frozen=True)
class SkillVFXConfig:
    """Complete VFX and timing blueprint for a combat ability."""

    effect_id: str
    caster_anim: CasterAnimMode = "lunge"
    total_duration: float = 1.50
    impact_time: float = 0.75
    spell_duration: float = 0.80
    phases: tuple[VFXPhase, ...] = ()


SKILL_VFX_REGISTRY: Final[dict[str, SkillVFXConfig]] = {
    "violet_ember": SkillVFXConfig(
        effect_id="violet_ember",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=1.15,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="charge",
                placement="caster",
                start_time=0.0,
                duration=0.65,
                frame_count=8,
                offset=(-54.0, -102.0),
            ),
            VFXPhase(
                prefix="projectile",
                placement="projectile_to_target",
                start_time=0.65,
                duration=0.50,
                frame_count=8,
                offset=(-54.0, -102.0),
                arc_height=26.0,
            ),
        ),
    ),
}


def get_skill_vfx_config(ability_id: str | None) -> SkillVFXConfig | None:
    """Return the declarative VFX configuration for an ability, if registered."""
    if not ability_id:
        return None
    return SKILL_VFX_REGISTRY.get(ability_id)
