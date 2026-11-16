"""Classic 4-member round-based combat engine with turn initiative and formulas."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from src.core.events import AudioCue, EventBus, StatusAppliedEvent
from src.core.math_utils import calculate_damage
from src.data.abilities import ABILITY_REGISTRY, AbilityElement, TargetScope
from src.data.items import ITEM_REGISTRY
from src.entities.actor import (
    NEGATIVE_STATUSES,
    ActiveStatus,
    StatusType,
    resolve_status_type,
)
from src.entities.character import Character
from src.entities.enemy import Enemy, EnemyTier
from src.entities.party import Party
from src.systems.combat.action import ActionType, CombatAction


class CombatPhase(Enum):
    COMMAND_INPUT = auto()
    ACTION_EXECUTION = auto()
    VICTORY = auto()
    DEFEAT = auto()
    ESCAPED = auto()


@dataclass
class ActionResult:
    source_name: str
    action_name: str
    target_names: list[str]
    damage_dealt: list[int]
    healing_dealt: list[int]
    is_crit: bool
    status_applied: str | None
    message: str
    ability_id: str | None = None
    target_ids: list[str] | None = None


class RoundCombat:
    """Manages full lifecycle of a 4-member party turn-based combat encounter."""

    def __init__(
        self,
        party: Party,
        enemies: list[Enemy],
        event_bus: EventBus | None = None,
        seed: int | None = None,
    ) -> None:
        self.party = party
        self.enemies = enemies
        self.event_bus = event_bus or EventBus()
        self.rng = random.Random(seed)

        self.phase = CombatPhase.COMMAND_INPUT
        self.round_number = 1
        self.current_party_idx = 0
        self.pending_player_actions: list[CombatAction] = []
        self.action_queue: list[CombatAction] = []
        self.defending_actors: set[str] = set()

        self.victory_rewards: dict[str, Any] = {}
        self.last_action_result: ActionResult | None = None
        self.combat_log: list[str] = [f"Battle began against {', '.join(e.name for e in self.enemies)}!"]

    @property
    def living_party(self) -> list[Character]:
        return [m for m in self.party.active_members if m.is_alive]

    @property
    def living_enemies(self) -> list[Enemy]:
        return [e for e in self.enemies if e.is_alive]

    @property
    def active_input_character(self) -> Character | None:
        living = self.living_party
        if 0 <= self.current_party_idx < len(living):
            return living[self.current_party_idx]
        return None

    def queue_player_action(self, action: CombatAction) -> bool:
        """Queue action for active input character and advance to next party member."""
        if self.phase != CombatPhase.COMMAND_INPUT:
            return False

        living = self.living_party
        if not living:
            self.phase = CombatPhase.DEFEAT
            return False

        self.pending_player_actions.append(action)
        self.current_party_idx += 1

        # If all living party members have inputted commands, begin execution!
        if self.current_party_idx >= len(living):
            self.start_round_execution()

        return True

    def cancel_last_player_action(self) -> bool:
        """Step back to previous party member to re-select actions."""
        if self.phase != CombatPhase.COMMAND_INPUT or self.current_party_idx <= 0:
            return False

        self.current_party_idx -= 1
        if self.pending_player_actions:
            self.pending_player_actions.pop()
        return True

    def start_round_execution(self) -> None:
        """Roll enemy AI and assemble speed-ordered round action queue."""
        self.phase = CombatPhase.ACTION_EXECUTION
        self.defending_actors.clear()
        all_actions: list[CombatAction] = list(self.pending_player_actions)

        # Roll Enemy Actions
        living_party = self.living_party
        for enemy in self.living_enemies:
            if not living_party:
                break

            target = self.rng.choice(living_party)
            # Pick enemy ability or basic attack
            usable_abilities = [ab for ab in enemy.abilities if ab in ABILITY_REGISTRY]
            chosen_ability = self.rng.choice(usable_abilities) if usable_abilities else "basic_attack"

            all_actions.append(
                CombatAction(
                    actor_id=enemy.id,
                    is_player=False,
                    action_type=ActionType.ABILITY if chosen_ability != "basic_attack" else ActionType.ATTACK,
                    target_id=target.id,
                    ability_id=chosen_ability,
                    speed_initiative=float(self._effective_speed(enemy) + self.rng.uniform(-1.0, 1.0)),
                )
            )

        # Calculate initiative for player actions
        for act in all_actions:
            if act.is_player:
                char = next((c for c in self.party.active_members if c.id == act.actor_id), None)
                speed = self._effective_speed(char) if char else 10.0
                act.speed_initiative = float(speed + self.rng.uniform(-1.0, 1.0))
                # Defend priority
                if act.action_type == ActionType.DEFEND:
                    act.speed_initiative += 100.0

        # Sort descending by initiative speed
        all_actions.sort(key=lambda a: a.speed_initiative, reverse=True)
        self.action_queue = all_actions

    def step_next_action(self) -> ActionResult | None:
        """Resolve the next pending action in the round queue."""
        if self.phase != CombatPhase.ACTION_EXECUTION:
            return None

        while self.action_queue:
            action = self.action_queue.pop(0)
            res = self._execute_action(action)
            if res:
                self.last_action_result = res
                self.combat_log.append(res.message)
                self._check_battle_end()
                return res

        # Round completed
        self._end_of_round_cleanup()
        return None

    def _execute_action(self, action: CombatAction) -> ActionResult | None:
        actor: Character | Enemy | None = None
        if action.is_player:
            actor = next((c for c in self.party.active_members if c.id == action.actor_id), None)
        else:
            actor = next((e for e in self.enemies if e.id == action.actor_id), None)

        if not actor or not actor.is_alive:
            return None  # Actor was KO'd before turn

        source_name = actor.name

        # 0. Stun Check
        if self._has_status(actor, StatusType.STUN):
            return ActionResult(
                source_name=source_name,
                action_name="Stunned",
                target_names=[],
                damage_dealt=[],
                healing_dealt=[],
                is_crit=False,
                status_applied=None,
                message=f"{source_name} is stunned and cannot move!",
            )

        # 1. Defend Action
        if action.action_type == ActionType.DEFEND:
            self.defending_actors.add(actor.id)
            self.event_bus.emit_audio(AudioCue.DEFEND)
            return ActionResult(
                source_name=source_name,
                action_name="Defend",
                target_names=[source_name],
                damage_dealt=[],
                healing_dealt=[],
                is_crit=False,
                status_applied=None,
                message=f"{source_name} takes a defensive stance!",
            )

        # 2. Flee Action
        if action.action_type == ActionType.FLEE:
            has_boss = any(e.tier in (EnemyTier.BOSS, EnemyTier.ELITE) for e in self.living_enemies)
            if has_boss:
                return ActionResult(
                    source_name=source_name,
                    action_name="Flee",
                    target_names=[],
                    damage_dealt=[],
                    healing_dealt=[],
                    is_crit=False,
                    status_applied=None,
                    message="Cannot flee from an elite or boss encounter!",
                )
            if self.rng.random() < 0.65:
                self.phase = CombatPhase.ESCAPED
                self._clear_party_statuses()
                self.event_bus.emit_audio(AudioCue.DOOR)
                return ActionResult(
                    source_name=source_name,
                    action_name="Flee",
                    target_names=[],
                    damage_dealt=[],
                    healing_dealt=[],
                    is_crit=False,
                    status_applied=None,
                    message="The party successfully escaped!",
                )
            else:
                return ActionResult(
                    source_name=source_name,
                    action_name="Flee",
                    target_names=[],
                    damage_dealt=[],
                    healing_dealt=[],
                    is_crit=False,
                    status_applied=None,
                    message="Failed to escape!",
                )

        # 3. Item Action
        if action.action_type == ActionType.ITEM and action.item_id:
            item_def = ITEM_REGISTRY.get(action.item_id)
            if item_def and item_def.revive:
                ko_allies = [c for c in self.party.active_members if not c.is_alive]
                target = next((c for c in ko_allies if c.id == action.target_id), ko_allies[0] if ko_allies else None)
            else:
                target = next(
                    (c for c in self.living_party if c.id == action.target_id),
                    self.living_party[0] if self.living_party else None,
                )
            if not target or not self.party.remove_item(action.item_id, 1):
                return None

            item_name = item_def.name if item_def else action.item_id.replace("_", " ").title()
            effects: list[str] = []
            actual_heal = 0

            if item_def and item_def.revive and not target.is_alive:
                revive_hp = max(1, int(target.base_stats.max_hp * 0.4))
                target.current_hp = revive_hp
                actual_heal = revive_hp
                effects.append(f"revived with {revive_hp} HP")
            elif item_def and item_def.heal_hp > 0:
                actual_heal = target.heal(item_def.heal_hp)
                effects.append(f"+{actual_heal} HP")
            elif not item_def:
                heal_val = 60 if action.item_id == "healing_poultice" else 30
                actual_heal = target.heal(heal_val)
                effects.append(f"+{actual_heal} HP")

            if item_def and item_def.heal_mp > 0:
                old_mp = target.current_mp
                target.current_mp = min(target.base_stats.max_mp, target.current_mp + item_def.heal_mp)
                actual_mp = target.current_mp - old_mp
                effects.append(f"+{actual_mp} MP")

            if item_def and item_def.cleanse_status:
                before = len(target.statuses)
                target.statuses = [s for s in target.statuses if s.status not in NEGATIVE_STATUSES]
                removed = before - len(target.statuses)
                effects.append("cleansed statuses" if removed > 0 else "no ailments to cleanse")

            self.event_bus.emit_audio(AudioCue.HEAL)
            effect_str = ", ".join(effects) if effects else "used"
            return ActionResult(
                source_name=source_name,
                action_name=item_name,
                target_names=[target.name],
                damage_dealt=[],
                healing_dealt=[actual_heal] if actual_heal > 0 else [],
                is_crit=False,
                status_applied=None,
                message=f"{source_name} used {item_name} on {target.name} ({effect_str})!",
            )

        # 4. Attack or Ability
        ability_id = action.ability_id or "basic_attack"
        ability = ABILITY_REGISTRY.get(ability_id, ABILITY_REGISTRY["basic_attack"])

        # Check MP for player
        if action.is_player and isinstance(actor, Character):
            if actor.current_mp < ability.mp_cost:
                ability = ABILITY_REGISTRY["basic_attack"]
            else:
                actor.current_mp -= ability.mp_cost

        # Determine Targets
        targets = self._resolve_targets(action, ability)
        if not targets:
            return None

        damages: list[int] = []
        heals: list[int] = []
        target_names: list[str] = [t.name for t in targets]
        has_crit = False
        applied_status: str | None = None
        missed_all = False

        raw_stat = float(actor.base_stats.attack if isinstance(actor, Character) else actor.stats.attack)
        raw_mag = float(actor.base_stats.magic_attack if isinstance(actor, Character) else actor.stats.magic_attack)
        crit_rate = actor.base_stats.crit_chance if isinstance(actor, Character) else actor.stats.crit_chance

        if self._has_status(actor, StatusType.ATTACK_UP):
            raw_stat *= 1.35
            raw_mag *= 1.35
        if self._has_status(actor, StatusType.WEAKEN):
            raw_stat *= 0.70
            raw_mag *= 0.70

        status_type = resolve_status_type(ability.status_inflict)
        is_blinded = self._has_status(actor, StatusType.BLIND)

        is_support = ability.element == AbilityElement.HEAL or ability.scope in (
            TargetScope.SINGLE_ALLY,
            TargetScope.ALL_ALLIES,
            TargetScope.SELF,
        )

        for target in targets:
            if is_support:
                actual = 0
                if ability.element == AbilityElement.HEAL and ability.power > 0 and isinstance(target, Character):
                    heal_amt = int(ability.power + raw_mag * 0.8)
                    actual = target.heal(heal_amt)
                heals.append(actual)

                if status_type and self.rng.random() < ability.status_chance:
                    mag = max(8, int(raw_mag * 0.4)) if status_type == StatusType.REGEN else 0
                    self._apply_status(target, status_type, duration=3, magnitude=mag)
                    applied_status = status_type.name
            else:
                if is_blinded and self.rng.random() < 0.45:
                    damages.append(0)
                    continue

                target_def = float(target.base_stats.defense if isinstance(target, Character) else target.stats.defense)
                if target.id in self.defending_actors:
                    target_def *= 1.6
                if self._has_status(target, StatusType.DEFENSE_UP):
                    target_def *= 1.4
                if self._has_status(target, StatusType.VULNERABLE):
                    target_def *= 0.65

                elem_mult = self._get_element_multiplier(ability.element.name, target)
                is_crit = self.rng.random() < crit_rate
                if is_crit:
                    has_crit = True

                raw_dmg = int(ability.power + (raw_stat if ability.element == AbilityElement.PHYSICAL else raw_mag) * 0.9)
                dmg = calculate_damage(
                    raw_dmg=raw_dmg,
                    defense=int(target_def),
                    elemental_multiplier=elem_mult,
                    is_crit=is_crit,
                    rng=self.rng,
                )
                actual_dmg = target.take_damage(dmg)
                damages.append(actual_dmg)

                # Check status application
                if status_type and self.rng.random() < ability.status_chance:
                    dur = 2 if status_type == StatusType.STUN else 3
                    self._apply_status(target, status_type, duration=dur, magnitude=max(4, dmg // 3))
                    applied_status = status_type.name

        if not is_support and damages and all(d == 0 for d in damages) and is_blinded:
            missed_all = True

        # Audio cue
        if any(h > 0 for h in heals):
            self.event_bus.emit_audio(AudioCue.HEAL)
        elif has_crit:
            self.event_bus.emit_audio(AudioCue.CRIT)
        else:
            self.event_bus.emit_audio(AudioCue.HIT)

        # Format message
        status_suffix = f" ({applied_status.replace('_', ' ').title()}!)" if applied_status else ""
        if is_support:
            total_heal = sum(heals)
            if total_heal > 0:
                msg = f"{source_name} casts {ability.name} healing {', '.join(target_names)} for {total_heal} HP!{status_suffix}"
            else:
                msg = f"{source_name} uses {ability.name} on {', '.join(target_names)}!{status_suffix}"
        elif missed_all:
            msg = f"{source_name} is blinded and {ability.name} missed {', '.join(target_names)}!"
        else:
            crit_str = " (Critical Hit!)" if has_crit else ""
            msg = f"{source_name} uses {ability.name} on {', '.join(target_names)} dealing {sum(damages)} damage{crit_str}!{status_suffix}"

        return ActionResult(
            source_name=source_name,
            action_name=ability.name,
            target_names=target_names,
            damage_dealt=damages,
            healing_dealt=heals,
            is_crit=has_crit,
            status_applied=applied_status,
            message=msg,
            ability_id=ability.id,
            target_ids=[target.id for target in targets],
        )

    def _resolve_targets(self, action: CombatAction, ability) -> list[Character | Enemy]:
        living_party = self.living_party
        living_enemies = self.living_enemies

        if action.is_player:
            if ability.scope == TargetScope.SELF:
                actor = next((c for c in living_party if c.id == action.actor_id), None)
                return [actor] if actor else []
            elif ability.scope == TargetScope.SINGLE_ENEMY:
                target = next((e for e in living_enemies if e.id == action.target_id), living_enemies[0] if living_enemies else None)
                return [target] if target else []
            elif ability.scope == TargetScope.ALL_ENEMIES:
                return list(living_enemies)
            elif ability.scope == TargetScope.SINGLE_ALLY:
                target = next((c for c in living_party if c.id == action.target_id), living_party[0] if living_party else None)
                return [target] if target else []
            elif ability.scope == TargetScope.ALL_ALLIES:
                return list(living_party)
        else:
            # Enemy targeting player or self
            if ability.scope == TargetScope.SELF:
                actor = next((e for e in living_enemies if e.id == action.actor_id), None)
                return [actor] if actor else []
            elif ability.scope in (TargetScope.SINGLE_ENEMY, TargetScope.ALL_ENEMIES):
                target = next((c for c in living_party if c.id == action.target_id), living_party[0] if living_party else None)
                return [target] if target else []

        return []

    def _get_element_multiplier(self, element_name: str, target: Character | Enemy) -> float:
        if isinstance(target, Enemy):
            if element_name in target.weaknesses:
                return 1.6
            if element_name in target.resistances:
                return 0.5
        return 1.0

    def _has_status(self, actor: Character | Enemy, status_type: StatusType) -> bool:
        return any(s.status == status_type for s in actor.statuses)

    def _effective_speed(self, actor: Character | Enemy) -> float:
        base_spd = float(actor.base_stats.speed if isinstance(actor, Character) else actor.stats.speed)
        if self._has_status(actor, StatusType.SPEED_UP):
            base_spd *= 1.40
        return base_spd

    def _apply_status(
        self,
        target: Character | Enemy,
        status_type: StatusType,
        duration: int,
        magnitude: int = 0,
    ) -> None:
        for existing in target.statuses:
            if existing.status == status_type:
                existing.duration = max(existing.duration, duration)
                existing.magnitude = max(existing.magnitude, magnitude)
                break
        else:
            target.statuses.append(ActiveStatus(status=status_type, duration=duration, magnitude=magnitude))
        self.event_bus.emit(
            StatusAppliedEvent(
                target_id=target.id,
                status_id=status_type.name.lower(),
                status_name=status_type.name.replace("_", " ").title(),
                duration=duration,
            )
        )

    def _clear_party_statuses(self) -> None:
        for member in self.party.active_members:
            member.statuses.clear()

    def _end_of_round_cleanup(self) -> None:
        """Apply DoT/HoT ticks, status duration countdowns, and reset for next round."""
        # Tick Party Statuses
        for char in self.living_party:
            for st in list(char.statuses):
                if st.status in (StatusType.POISON, StatusType.BLEED, StatusType.BURN):
                    default_dmg = 7 if st.status == StatusType.BURN else 6
                    dmg = max(1, st.magnitude or default_dmg)
                    char.take_damage(dmg)
                    self.combat_log.append(f"{char.name} suffers {dmg} {st.status.name.lower()} damage!")
                elif st.status == StatusType.REGEN:
                    heal_amt = max(1, st.magnitude or 12)
                    actual = char.heal(heal_amt)
                    if actual > 0:
                        self.combat_log.append(f"{char.name} regenerates {actual} HP!")
                st.duration -= 1
                if st.duration <= 0:
                    char.statuses.remove(st)

        # Tick Enemy Statuses
        for enemy in self.living_enemies:
            for st in list(enemy.statuses):
                if st.status in (StatusType.POISON, StatusType.BLEED, StatusType.BURN):
                    default_dmg = 9 if st.status == StatusType.BURN else 8
                    dmg = max(1, st.magnitude or default_dmg)
                    enemy.take_damage(dmg)
                    self.combat_log.append(f"{enemy.name} suffers {dmg} {st.status.name.lower()} damage!")
                elif st.status == StatusType.REGEN:
                    heal_amt = max(1, st.magnitude or 12)
                    old_hp = enemy.current_hp
                    enemy.current_hp = min(enemy.stats.max_hp, enemy.current_hp + heal_amt)
                    actual = enemy.current_hp - old_hp
                    if actual > 0:
                        self.combat_log.append(f"{enemy.name} regenerates {actual} HP!")
                st.duration -= 1
                if st.duration <= 0:
                    enemy.statuses.remove(st)

        self._check_battle_end()

        # If battle is still ongoing, prepare next round
        if self.phase == CombatPhase.ACTION_EXECUTION:
            self.round_number += 1
            self.current_party_idx = 0
            self.pending_player_actions.clear()
            self.phase = CombatPhase.COMMAND_INPUT

    def _check_battle_end(self) -> None:
        if not self.living_enemies:
            self.phase = CombatPhase.VICTORY
            self._clear_party_statuses()
            self.event_bus.emit_audio(AudioCue.VICTORY)
            self._award_victory_rewards()
        elif self.party.is_party_defeated:
            self.phase = CombatPhase.DEFEAT
            self.event_bus.emit_audio(AudioCue.DEFEAT)

    def _award_victory_rewards(self) -> None:
        total_exp = sum(e.exp_reward for e in self.enemies)
        total_gold = sum(e.gold_reward for e in self.enemies)
        self.party.gold += total_gold

        survivors = self.living_party
        exp_per_member = total_exp // max(1, len(survivors))
        level_ups: dict[str, list[int]] = {}

        for member in survivors:
            leveled = member.gain_exp(exp_per_member)
            if leveled:
                level_ups[member.name] = leveled

        # Loot drops
        dropped_items: list[str] = []
        for enemy in self.enemies:
            for item_id, chance in enemy.loot_drops:
                if self.rng.random() < chance:
                    self.party.add_item(item_id, 1)
                    dropped_items.append(item_id)

        self.victory_rewards = {
            "total_exp": total_exp,
            "exp_per_member": exp_per_member,
            "total_gold": total_gold,
            "level_ups": level_ups,
            "dropped_items": dropped_items,
        }
