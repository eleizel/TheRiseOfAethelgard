"""Unit tests for combat formulas and math utilities."""

from src.core.math_utils import calculate_damage, calculate_exp_threshold


def test_calculate_damage_basic():
    dmg = calculate_damage(raw_dmg=30, defense=10, variance=0.0)
    assert dmg > 0
    assert dmg < 30


def test_calculate_damage_critical_hit():
    normal = calculate_damage(raw_dmg=40, defense=10, is_crit=False, variance=0.0)
    crit = calculate_damage(raw_dmg=40, defense=10, is_crit=True, crit_multiplier=2.0, variance=0.0)
    assert abs(crit - normal * 2) <= 1


def test_calculate_damage_elemental_immunity():
    dmg = calculate_damage(raw_dmg=50, defense=10, elemental_multiplier=0.0, variance=0.0)
    assert dmg == 0


def test_calculate_exp_threshold_scaling():
    exp1 = calculate_exp_threshold(1)
    exp2 = calculate_exp_threshold(2)
    exp3 = calculate_exp_threshold(3)
    assert exp1 < exp2 < exp3
