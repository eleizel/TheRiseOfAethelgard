# Quest & Narrative Specification: Main Quest 02 — "Shadows over the Verge"

**Project:** *The Rise of Aethelgard* (`eleizel/TheRiseOfAethelgard`)  
**Department:** Narrative & Quest Design  
**Target Milestone:** Main Quest 02 Implementation Specification

---

## 1. Quest Overview & Structure

### A. Metadata
* **Quest ID:** `shadows_over_the_verge`
* **Quest Name:** Shadows over the Verge
* **Prerequisites:** Completion of Elder Tomas's Oakhaven directive and victory over the Corrupted Treant in `briarwood_verge`.
* **Trigger Mechanism:** Auto-initiated via `QuestManager` (`src/systems/quests/quest_manager.py`) upon returning to Oakhaven Village.

### B. Quest Stages & Objectives
1. **Stage 0: Return to Oakhaven**
   * *Objective:* Return to *Oakhaven Village* (`oakhaven_village_main`) and debrief with Elder Tomas inside the `inn_interior_oakhaven`.
   * *Success Condition:* Complete dialogue tree `tomas_post_treant_debrief`. Rewards player with the *Verge Gate Key*.
2. **Stage 1: Investigate the Boundary Road**
   * *Objective:* Travel to the northern perimeter of Oakhaven where the atmospheric tinting shifts toward the Root Blight.
   * *Success Condition:* Unlock and transition to the new map node: **Verge Outpost Ruins** (`verge_outpost_ruins`).
3. **Stage 2: Intercept the Corrupted Patrol**
   * *Objective:* Explore the ruins, locate wounded Scout Vane, and survive the ambush by blight-spawned enemies.
   * *Success Condition:* Defeat the elite encounter (2x *Blight-Touched Skulks*, 1x *Verge Corrupted Sentinel*) and trigger dialogue tree `vane_dying_warning`.
4. **Stage 3: Quest Completion**
   * *Objective:* Secure the *Blighted Core* dispatch item and prepare for the deeper journey into the High Kingdom's corrupted frontier.
   * *Success Condition:* Quest status set to `COMPLETED` in `QuestManager`, updating active party progression and unlocking subsequent subquests.

---

## 2. Dialogue Hooks & Scripting (`src/data/dialogues.py`)

### A. Elder Tomas Debrief (`tomas_post_treant_debrief`)
```python
{
    "id": "tomas_post_treant_debrief",
    "speaker": "Elder Tomas",
    "portrait": "assets/portraits/elder_tomas.png",
    "lines": [
        "Captain Rowan, your victory at the Briarwood Verge bought us time, but our scouts report the corruption runs deeper than a single treant.",
        "An eerie amber haze has settled over the old border watchtowers. Worse, Scout Vane has not returned from the Verge Outpost Ruins.",
        "Take this Verge Gate Key. Investigate the ruins, find Vane, and discover what the Root Blight is harvesting from our borders."
    ],
    "rewards": {
        "items": ["verge_gate_key"]
    },
    "next_quest_stage": 1
}
```

### B. Scout Vane Dying Warning (`vane_dying_warning`)
```python
{
    "id": "vane_dying_warning",
    "speaker": "Scout Vane",
    "portrait": "assets/portraits/vane.png",
    "lines": [
        "Captain... ugh... the shadows moved before I could reach the gate. They are bleeding the very stone dry...",
        "Beware the sentinels... their blades carry the rot... Warn the High King...",
        "[Vane succumbs to the poison, leaving behind a glowing Blighted Core dispatch.]"
    ],
    "rewards": {
        "items": ["blighted_core"]
    },
    "next_quest_stage": 3
}
```

---

## 3. Map, Environment, & Asset Integration

### A. Map Specification
* **Map ID:** `verge_outpost_ruins`
* **TMX Asset Path:** `assets/maps/verge_outpost_ruins.tmx`
* **Collision Layers:** Standard blocking layers for crumbled stone walls, broken barricades, and dead timber.
* **HD-2D Atmospheric Settings (`src/frontends/pygame_ce/hd2d_renderer.py`):**
  * *Lighting Override:* Deep amber and bruised purple atmospheric tinting.
  * *Particle Effects:* Floating spore particles (`ROOT_BLIGHT_SPORES`) and flickering torch entities casting dynamic orange light across weathered stonework.

### B. NPC & Sprite Assets
* **Scout Vane Sprite:** `assets/sprites/npcs/vane.png`
* **Scout Vane Portrait:** `assets/portraits/vane.png`

---

## 4. Combat & Encounter Design (`src/systems/combat/round_combat.py`)

### A. Elite Patrol Encounter Composition
* **Enemies:**
  1. *Blight-Touched Skulk A* (Weakness: `FIRE`, Resistance: `PHYSICAL`)
  2. *Blight-Touched Skulk B* (Weakness: `FIRE`, Resistance: `PHYSICAL`)
  3. *Verge Corrupted Sentinel* (Applies status effects: `VULNERABLE`, `BLEED`)
* **Combat Environment:** Ruined outpost courtyard with suppressed ambient lighting and pulsating blight vines.

### B. Item Drops & Quest Integration
* **Drop Item:** *Blighted Core*
* **Usage:** Consumable quest progression token required to unlock subsequent narrative chapters in *The Rise of Aethelgard*.

---

## 5. Architecture & Quality Assurance Compliance

* **Strict Layering Rule:** All quest definitions (`src/systems/quests/quest_manager.py`), dialogue registries (`src/data/dialogues.py`), and combat stat definitions remain strictly free of `pygame` or `pygame_gui` imports, satisfying `tests/test_architecture_boundary.py`.
* **Verification Protocol:**
  ```bash
  python -m pytest -q
  python -m ruff check src tests
  ```