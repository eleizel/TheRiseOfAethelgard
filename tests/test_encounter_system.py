"""Unit tests for hybrid encounters: random step counter and wandering elites."""

from src.systems.exploration.encounter_system import EncounterSystem, WanderingElite


def test_safe_zone_no_random_encounters():
    sys = EncounterSystem(seed=42)
    # Moving in oakhaven_village should never trigger wild encounter
    for _ in range(50):
        triggered = sys.record_movement(distance_pixels=100.0, map_id="oakhaven_village")
        assert triggered is False
    assert sys.step_counter == 0.0


def test_wild_zone_encounter_triggers_eventually():
    sys = EncounterSystem(seed=12345)
    triggered = False
    for _ in range(100):
        if sys.record_movement(distance_pixels=50.0, map_id="briarwood_verge"):
            triggered = True
            break
    assert triggered is True


def test_wandering_elite_patrol_and_touch():
    elite = WanderingElite(id="treant_01", name="Corrupted Treant", x=100.0, y=100.0, speed=50.0)

    # Player far away
    assert elite.is_touching_player(px=200.0, py=200.0) is False

    # Player close
    assert elite.is_touching_player(px=105.0, py=105.0) is True

    # Patrol update bounces within [80, 150]
    elite.update(dt=1.0, min_x=80.0, max_x=150.0)
    assert elite.x == 150.0
    assert elite.patrol_direction == -1
