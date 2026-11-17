# Gameplay & Encounter Specification: Main Quest 02 — "Shadows over the Verge"

As Lead Game Designer in the Design department, this document defines the complete gameplay mechanics, encounter balance, entity data structures, and implementation constraints for **Main Quest 02: "Shadows over the Verge"**, fully grounded in the canonical project architecture (`eleizel/TheRiseOfAethelgard`).

---

## 1. Quest Progression & State Machine Specification (`src/systems/quests/quest_manager.py`)

The quest `shadows_over_the_verge` utilizes a 4-stage linear progression tracked via the canonical `QuestManager`.

| Stage ID | Stage Name | Objective Description | Completion Trigger / Condition |
| :--- | :--- | :--- | :--- |
| **0** | *The Elder's Debrief* | Return to Oakhaven Village and speak with Elder Tomas at the `inn_interior_oakhaven`. | Trigger dialogue `tomas_post_treant_debrief`; receive *Verge Gate Key* item. |
| **1** | *Verge Incursion* | Investigate the atmospheric anomaly and travel to the **Verge Outpost Ruins** (`verge_outpost_ruins`). | Player map transition triggers entry into `verge_outpost_ruins`. |
| **2** | *Intercept the Patrol* | Locate Scout Vane near the ruins and defeat the elite Root Blight patrol. | Defeat enemy formation (2x *Blight-Touched Skulks*, 1x *Verge Corrupted Sentinel* in round combat). |
| **3** | *Mission Complete* | Recover the corrupted dispatch and secure the *Blighted Core*. | Interact with Scout Vane's post-combat prompt; trigger `vane_dying_warning` and flag quest complete. |

---

## 2. Dialogue Registry Entries (`src/data/dialogues.py`)

The dialogue trees must be registered in `src/data/dialogues.py` without importing any UI or display libraries, preserving strict architecture boundaries.

```python
# Snippet representation for src/data/dialogues.py
DIALOGUE_REGISTRY = {
    "tomas_post_treant_debrief": {
        "speaker": "Elder Tomas",
        "portrait": "assets/portraits/elder_tomas.png",
        "lines": [
            "Captain Rowan, the Corrupted Treant was merely a symptom. The Root Blight pulse is intensifying.",
            "Take this Verge Gate Key. The old outpost ruins past the boundary road are compromised.",
            "Find out what the Blight is carrying through the corridors before it reaches our gates."
        ],
        "reward_item": "verge_gate_key",
        "next_quest_stage": 1
    },
    "vane_dying_warning": {
        "speaker": "Scout Vane",
        "portrait": "assets/portraits/vane.png",
        "lines": [
            "Captain... they aren't just wild beasts. They're being commanded...",
            "Take the dispatches... and the Blight Core... warn the High Kingdom..."
        ],
        "reward_item": "blighted_core",
        "next_quest_stage": 3
    }
}
```

---

## 3. Enemy Encounter Balance & Mechanics (`src/systems/combat/round_combat.py`)

### Encounter Formation: *Verge Patrol Ambush*
* **Active Combatant Limit:** 4 Party Members (Rowan, Lyra, Caelen, Rachel / Reserve Swapping Active) vs. 3 Enemies.
* **Initiative Order Sorting:** Speed-ordered round combat (`src/systems/combat/round_combat.py`).

#### Enemy 1 & 2: Blight-Touched Skulk (x2)
* **Role:** Fast skirmisher / glass cannon.
* **Base Stats:**
  * HP: 120
  * ATK: 32
  * DEF: 10
  * SPD: 45
* **Affinities & Weaknesses:**
  * Weakness: `FIRE` (+50% damage taken, triggers 1-turn `BURN`).
  * Resistance: `PHYSICAL` (-30% damage taken).
  * Immunities: `POISON`, `BLEED`.
* **Actions / AI Routine:**
  * *Claw Flurry*: Deals physical damage with a 25% chance to apply `BLEED`.
  * *Blight Dart*: Ranged magical attack dealing `ARCANE` damage.

#### Enemy 3: Verge Corrupted Sentinel (x1)
* **Role:** Elite tank / debuff controller.
* **Base Stats:**
  * HP: 320
  * ATK: 45
  * DEF: 28
  * SPD: 20
* **Affinities & Weaknesses:**
  * Weakness: `HOLY` (+40% damage taken).
  * Resistance: `PHYSICAL`, `EARTH` (-25% damage taken).
  * Immunities: `STUN`, `POISON`.
* **Actions / AI Routine:**
  * *Crushing Slam*: Heavy physical strike applying canonical status effect `VULNERABLE` (increases incoming damage by 50 for 2 turns).
  * *Root Aegis*: Self-buff ability granting `DEFENSE_UP` for 2 rounds.

---

## 4. Map, Lighting, & Atmospheric Specifications (`assets/maps/`, `src/frontends/pygame_ce/hd2d_renderer.py`)

* **Map Asset:** `assets/maps/verge_outpost_ruins.tmx`
* **HD-2D Renderer Integration (`hd2d_renderer.py`):**
  * **Atmospheric Tint Override:** Apply a specialized radial vignette combined with an amber/purple Root Blight color tint (`RGBA(75, 30, 90, 110)`) to signal corrupt environmental hazards.
  * **Dynamic Lighting:** Place flickering torchlight entities across broken stone pillars with dynamic radius flicker (`radius_min=48`, `radius_max=64`).
  * **Y-Sorted Depth Layers:** Ensure all fallen masonry, scout debris, and combat trigger volumes conform strictly to Y-sorted tile rendering.

---

## 5. Implementation Constraints & Verification Checklist

1. **Strict Architecture Boundaries:** 
   * Files under `src/core/`, `src/entities/`, `src/systems/`, and `src/data/` must **never** import `pygame` or `pygame_gui`. 
   * All rendering, window creation, and audio handling remain strictly in `src/frontends/pygame_ce/`.
2. **Quality Assurance Commands:**
   * Run unit tests: `python -m pytest -q` (Must pass 100% of quest state, inventory reward, and combat calculation tests).
   * Run linter: `python -m ruff check src tests` (Must report zero style violations).