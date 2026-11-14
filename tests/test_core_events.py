"""Unit tests for EventBus and domain events."""

from src.core.events import (
    AudioCue,
    AudioCueEvent,
    DamageDealtEvent,
    EventBus,
    HealthRestoredEvent,
)


def test_event_bus_drain():
    bus = EventBus()
    bus.emit(AudioCueEvent(cue=AudioCue.HIT))
    bus.emit(DamageDealtEvent(source_id="rowan", target_id="goblin", amount=25))

    events = bus.drain()
    assert len(events) == 2
    assert isinstance(events[0], AudioCueEvent)
    assert events[0].cue == AudioCue.HIT
    assert isinstance(events[1], DamageDealtEvent)
    assert events[1].amount == 25

    # Second drain is empty
    assert len(bus.drain()) == 0


def test_event_bus_subscription():
    bus = EventBus()
    received: list[HealthRestoredEvent] = []

    def on_heal(event: HealthRestoredEvent):
        received.append(event)

    bus.subscribe(HealthRestoredEvent, on_heal)
    bus.emit(HealthRestoredEvent(target_id="rowan", amount=40))

    assert len(received) == 1
    assert received[0].amount == 40

    bus.unsubscribe(HealthRestoredEvent, on_heal)
    bus.emit(HealthRestoredEvent(target_id="lyra", amount=20))
    assert len(received) == 1
