"""Memento and Repository patterns for decoupled game persistence.

Provides pluggable storage backends (File, Memory) and schema validation/migrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

SAVE_STORAGE_KEY = "the_rise_of_aethelgard_save"
CURRENT_SAVE_VERSION = 1


class SaveValidationError(ValueError):
    """Raised when a save payload cannot safely be restored."""


@dataclass
class SaveMemento:
    """Snapshot of active game state for persistence."""
    save_version: int = CURRENT_SAVE_VERSION
    slot_id: int = 1
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    play_time_seconds: float = 0.0
    current_mode: str = "EXPLORATION"
    map_id: str = "oakhaven_village"
    player_x: int = 10
    player_y: int = 10
    party: dict[str, Any] = field(default_factory=dict)
    run_seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "save_version": self.save_version,
            "slot_id": self.slot_id,
            "timestamp": self.timestamp,
            "play_time_seconds": self.play_time_seconds,
            "current_mode": self.current_mode,
            "map_id": self.map_id,
            "player_x": self.player_x,
            "player_y": self.player_y,
            "party": dict(self.party),
            "run_seed": self.run_seed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SaveMemento:
        validated = validate_and_migrate_save_payload(data)
        return cls(
            save_version=validated["save_version"],
            slot_id=validated["slot_id"],
            timestamp=validated.get("timestamp", datetime.now().isoformat()),
            play_time_seconds=float(validated.get("play_time_seconds", 0.0)),
            current_mode=validated.get("current_mode", "EXPLORATION"),
            map_id=validated.get("map_id", "oakhaven_village"),
            player_x=int(validated.get("player_x", 10)),
            player_y=int(validated.get("player_y", 10)),
            party=dict(validated.get("party", {})),
            run_seed=validated.get("run_seed"),
        )


def validate_and_migrate_save_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and migrate save payload to current schema."""
    if not isinstance(data, dict):
        raise SaveValidationError("Save payload must be a JSON object")

    migrated = dict(data)
    raw_version = migrated.get("save_version", CURRENT_SAVE_VERSION)
    try:
        version = int(raw_version)
    except (TypeError, ValueError) as exc:
        raise SaveValidationError("Save version must be an integer") from exc

    if version < 1:
        raise SaveValidationError(f"Unsupported save version: {version}")
    if version > CURRENT_SAVE_VERSION:
        raise SaveValidationError(
            f"Save version {version} is newer than supported version {CURRENT_SAVE_VERSION}"
        )

    # Validate mandatory party object
    party = migrated.get("party")
    if not isinstance(party, dict):
        raise SaveValidationError("Save payload requires a party object")

    if not isinstance(party.get("active_members"), list):
        raise SaveValidationError("Party requires an active_members list")

    migrated["save_version"] = version
    migrated["slot_id"] = int(migrated.get("slot_id", 1))
    return migrated


class StorageBackend(Protocol):
    """Protocol for abstract save/load operations."""
    def save(self, key: str, payload: str) -> None: ...
    def load(self, key: str) -> str | None: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> bool: ...


class FileStorageBackend:
    """Atomic file-based storage backend."""

    def __init__(self, base_dir: Path | str = "saves") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        safe_key = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in key)
        return self.base_dir / f"{safe_key}.json"

    def save(self, key: str, payload: str) -> None:
        target = self._get_path(key)
        temp_file = target.with_suffix(".tmp")
        temp_file.write_text(payload, encoding="utf-8")
        temp_file.replace(target)

    def load(self, key: str) -> str | None:
        target = self._get_path(key)
        if not target.exists():
            return None
        return target.read_text(encoding="utf-8")

    def exists(self, key: str) -> bool:
        return self._get_path(key).exists()

    def delete(self, key: str) -> bool:
        target = self._get_path(key)
        if target.exists():
            target.unlink()
            return True
        return False


class MemoryStorageBackend:
    """In-memory backend for fast, isolated unit testing."""

    def __init__(self) -> None:
        self._storage: dict[str, str] = {}

    def save(self, key: str, payload: str) -> None:
        self._storage[key] = payload

    def load(self, key: str) -> str | None:
        return self._storage.get(key)

    def exists(self, key: str) -> bool:
        return key in self._storage

    def delete(self, key: str) -> bool:
        if key in self._storage:
            del self._storage[key]
            return True
        return False
