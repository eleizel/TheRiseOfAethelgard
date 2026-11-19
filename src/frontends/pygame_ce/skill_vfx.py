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
    "wisteria_blaze": SkillVFXConfig(
        effect_id="wisteria_blaze",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.75,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="burn",
                placement="target_each",
                start_time=0.20,
                duration=1.10,
                frame_count=8,
                offset=(0.0, -76.0),
                scale=1.15,
            ),
        ),
    ),
    "orchid_inferno": SkillVFXConfig(
        effect_id="orchid_inferno",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.75,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="inferno",
                placement="target_group_center",
                start_time=0.15,
                duration=1.20,
                frame_count=8,
                offset=(0.0, -80.0),
                scale=1.15,
            ),
        ),
    ),
    "orchid_mist": SkillVFXConfig(
        effect_id="orchid_mist",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.75,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="mist",
                placement="target_each",
                start_time=0.15,
                duration=1.15,
                frame_count=8,
                offset=(0.0, -56.0),
                scale=1.15,
            ),
        ),
    ),
    "petal_hex": SkillVFXConfig(
        effect_id="petal_hex",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.75,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="hex",
                placement="target_each",
                start_time=0.15,
                duration=1.15,
                frame_count=8,
                offset=(0.0, -64.0),
                scale=1.10,
            ),
        ),
    ),
    # Melissa (Weave Scholar)
    "flame_lance": SkillVFXConfig(
        effect_id="flame_lance",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.95,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="charge",
                placement="caster",
                start_time=0.0,
                duration=0.50,
                frame_count=8,
                offset=(-54.0, -102.0),
            ),
            VFXPhase(
                prefix="projectile",
                placement="projectile_to_target",
                start_time=0.50,
                duration=0.45,
                frame_count=8,
                offset=(-54.0, -102.0),
                arc_height=8.0,
            ),
            VFXPhase(
                prefix="impact",
                placement="target_each",
                start_time=0.95,
                duration=0.55,
                frame_count=8,
                offset=(0.0, -54.0),
                scale=1.10,
            ),
        ),
    ),
    "frost_shard": SkillVFXConfig(
        effect_id="frost_shard",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.95,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="charge",
                placement="caster",
                start_time=0.0,
                duration=0.50,
                frame_count=8,
                offset=(-54.0, -102.0),
            ),
            VFXPhase(
                prefix="projectile",
                placement="projectile_to_target",
                start_time=0.50,
                duration=0.45,
                frame_count=8,
                offset=(-54.0, -102.0),
                arc_height=18.0,
            ),
            VFXPhase(
                prefix="impact",
                placement="target_each",
                start_time=0.95,
                duration=0.55,
                frame_count=8,
                offset=(0.0, -54.0),
                scale=1.10,
            ),
        ),
    ),
    "arcane_ward": SkillVFXConfig(
        effect_id="arcane_ward",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.65,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="buff",
                placement="target_each",
                start_time=0.20,
                duration=1.15,
                frame_count=8,
                offset=(0.0, -64.0),
                scale=1.10,
            ),
        ),
    ),
    "blizzard_surge": SkillVFXConfig(
        effect_id="blizzard_surge",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.70,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="charge",
                placement="caster",
                start_time=0.0,
                duration=0.45,
                frame_count=8,
                offset=(-54.0, -102.0),
            ),
            VFXPhase(
                prefix="impact",
                placement="target_group_center",
                start_time=0.35,
                duration=1.10,
                frame_count=8,
                offset=(0.0, -72.0),
                scale=1.15,
            ),
        ),
    ),
    "pyroclasm": SkillVFXConfig(
        effect_id="pyroclasm",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.70,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="charge",
                placement="caster",
                start_time=0.0,
                duration=0.50,
                frame_count=8,
                offset=(-54.0, -102.0),
            ),
            VFXPhase(
                prefix="impact",
                placement="target_each",
                start_time=0.40,
                duration=1.05,
                frame_count=8,
                offset=(0.0, -64.0),
                scale=1.15,
            ),
        ),
    ),
    "supernova": SkillVFXConfig(
        effect_id="supernova",
        caster_anim="spell",
        total_duration=1.50,
        impact_time=0.75,
        spell_duration=0.80,
        phases=(
            VFXPhase(
                prefix="charge",
                placement="caster",
                start_time=0.0,
                duration=0.50,
                frame_count=8,
                offset=(-54.0, -102.0),
            ),
            VFXPhase(
                prefix="impact",
                placement="target_group_center",
                start_time=0.40,
                duration=1.10,
                frame_count=8,
                offset=(0.0, -80.0),
                scale=1.20,
            ),
        ),
    ),
}


def get_skill_vfx_config(ability_id: str | None) -> SkillVFXConfig | None:
    """Return the declarative VFX configuration for an ability, if registered."""
    if not ability_id:
        return None
    return SKILL_VFX_REGISTRY.get(ability_id)
