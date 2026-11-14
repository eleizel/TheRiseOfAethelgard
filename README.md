# The Rise of Aethelgard

A 16-Bit Classic JRPG with HD-2D aesthetics, powered by **pygame-ce**.

*The Rise of Aethelgard* is an origins prequel to *Quest for Aethelgard*, chronicling the golden zenith of the High Kingdom before its ruin, the awakening of the primeval Root Blight, and Captain Rowan's quest of vindication, royal lineage, and vengeance.

---

## Features

- **16-Bit HD-2D Visuals**:
  - Rendered at **640x360** internal canvas and scaled smoothly with aspect-ratio preservation to 1280x720 window (or `F11` fullscreen).
  - Procedural retro SNES pixel art (tiles, props, cottages, lanterns, crystals).
  - Dynamic 2D lighting pipeline with flickering torches, ambient day/night tinting, radial vignette, and floating atmospheric particles.
  - Entity Y-sorting depth ensuring realistic walking perspective around world objects.
- **Classic Round-Based Combat**:
  - Full 4-member party battle formation (Rowan, Lyra, Caelen, Melissa).
  - Speed-ordered turn resolution with damage mitigation formulas, elemental affinities, critical hits, and status effects.
  - Battle menu: *Attack*, *Skills*, *Item*, *Defend* (+60% damage mitigation), and *Flee*.
- **Party Management & Camp Journal (`ESC`)**:
  - **Roster**: Active 4-member battle squad + reserve bench swapping.
  - **Inventory**: Consumables, weapons, armor, accessories.
  - **Equipment**: Gear equipping with live effective stat recalculation.
  - **Skill Trees**: Unique talent graphs per archetype with prerequisites and skill point (SP) investment.
  - **Save / Load**: Multi-slot save engine with corrupt file recovery.
- **Narrative & Dialogue Engine**:
  - Dialogue box with typewriter text, character portraits, and multi-choice branching conversations.
  - Playable Prologue: Oakhaven Village, Elder Tomas quest, and Briarwood Verge boss encounter against the Corrupted Treant.

---

## Controls

| Key | Action |
|---|---|
| `WASD` / `Arrow Keys` | Move Rowan / Navigate menus |
| `Left Shift` | Dash / Sprint in exploration |
| `Space` / `Enter` | Interact with NPCs, talk, confirm choices |
| `ESC` / `Backspace` | Open Camp Journal in exploration / Back out in menus |
| `Q` / `E` | Switch Camp Journal tabs |
| `M` | Toggle Music & Audio Mute |
| `F11` | Toggle Fullscreen |

---

## Running the Game

Launch using Python 3.11+:

```powershell
python main.py
```

To run the complete automated test suite (67 unit and integration tests):

```powershell
pytest
```
