"""SaveManager orchestrating save slots and payload recovery."""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.core.persistence import (
    FileStorageBackend,
    SaveMemento,
    SaveValidationError,
    StorageBackend,
)


@dataclass
class SaveSlotSummary:
    slot_id: int
    exists: bool
    timestamp: str | None = None
    play_time_seconds: float = 0.0
    map_id: str | None = None
    party_leader_name: str | None = None
    party_leader_level: int = 1
    party_count: int = 0


class SaveManager:
    """Manages multi-slot save files, autosave, and corrupt save detection."""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self.backend = backend or FileStorageBackend()
        self.last_load_error: str | None = None

    def _slot_key(self, slot_id: int) -> str:
        if slot_id == 0:
            return "autosave"
        return f"save_slot_{slot_id}"

    def save_game(self, memento: SaveMemento, slot_id: int = 1) -> bool:
        """Persist a SaveMemento to the given slot."""
        try:
            memento.slot_id = slot_id
            payload = json.dumps(memento.to_dict(), indent=2)
            self.backend.save(self._slot_key(slot_id), payload)
            return True
        except Exception as exc:
            self.last_load_error = str(exc)
            return False

    def load_game(self, slot_id: int = 1) -> SaveMemento | None:
        """Load and validate a SaveMemento from the given slot."""
        key = self._slot_key(slot_id)
        raw = self.backend.load(key)
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            return SaveMemento.from_dict(data)
        except (json.JSONDecodeError, SaveValidationError) as exc:
            self.last_load_error = f"Corrupt save in slot {slot_id}: {exc}"
            # Preserve corrupt save as .corrupt.json if backed by file storage
            if isinstance(self.backend, FileStorageBackend):
                path = self.backend._get_path(key)
                corrupt_path = path.with_suffix(".corrupt.json")
                path.replace(corrupt_path)
            return None

    def get_slot_summary(self, slot_id: int) -> SaveSlotSummary:
        """Inspect slot metadata without loading full game state."""
        key = self._slot_key(slot_id)
        raw = self.backend.load(key)
        if raw is None:
            return SaveSlotSummary(slot_id=slot_id, exists=False)

        try:
            data = json.loads(raw)
            party = data.get("party", {})
            active = party.get("active_members", [])
            leader = active[0] if active else {}
            return SaveSlotSummary(
                slot_id=slot_id,
                exists=True,
                timestamp=data.get("timestamp"),
                play_time_seconds=float(data.get("play_time_seconds", 0.0)),
                map_id=data.get("map_id"),
                party_leader_name=leader.get("name"),
                party_leader_level=int(leader.get("level", 1)),
                party_count=len(active),
            )
        except Exception:
            return SaveSlotSummary(slot_id=slot_id, exists=False)

    def delete_slot(self, slot_id: int) -> bool:
        return self.backend.delete(self._slot_key(slot_id))
