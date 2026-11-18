# The Rise of Aethelgard — Developer Expansion Guide

This guide documents how to extend **The Rise of Aethelgard** with new characters, skills, maps, quests, equipment, consumables, enemies, and status-effect integrations.

---

## 1. Architecture & Layering Rules

The codebase follows a strict **domain-first** architecture enforced by [tests/test_architecture_boundary.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/tests/test_architecture_boundary.py):

- **Pure Domain / Data Layers (NO `pygame` or `pygame_gui` imports allowed):**
  - `src/core/` — FSM (`fsm.py`), `EventBus` (`events.py`), `GameSession` (`session.py`), `SaveManager` (`save_manager.py`)
  - `src/entities/` — `Actor` / `Stats` / `StatusType` (`actor.py`), `Character` (`character.py`), `Enemy` (`enemy.py`), `Party` (`party.py`)
  - `src/systems/` — `RoundCombat` (`systems/combat/round_combat.py`), `QuestManager` (`systems/quests/quest_manager.py`), `Tilemap` (`systems/exploration/map_data.py`), `CharacterSkillTree` (`systems/progression/skill_tree.py`)
  - `src/data/` — Declarative registries (`abilities.py`, `characters.py`, `classes.py`, `dialogues.py`, `enemies.py`, `items.py`, `quests.py`, `skill_trees.py`)
- **Frontend Layer:**
  - `src/frontends/pygame_ce/` — Views (`views/`), `GameUIManager` (`ui_manager.py`), `EnemySpriteManager` (`combat_animator.py`), `HD2DRenderer` (`hd2d_renderer.py`), `DynamicMusicEngine` (`music_engine.py`).
- **Developer Tools & CI:**
  - `src/tools/` — Visual map editor ([map_editor.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/tools/map_editor.py), [map_editor_utils.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/tools/map_editor_utils.py)), debug overlay exporter ([generate_collision_overlay.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/tools/generate_collision_overlay.py)), sprite sheet extractor ([animation_extractor.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/tools/animation_extractor.py)).
  - [ci.yml](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/.github/workflows/ci.yml) — Runs `ruff check src tests`, headless `pytest -q`, and Windows PyInstaller packaging (`TheRiseOfAethelgard.exe`).

Always run both checks after any change:
```powershell
python -m pytest -q
python -m ruff check src tests
```

---

## 2. Adding a New Character

1. **Define or reuse a Class** in [src/data/classes.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/classes.py):
   - Add a `ClassDefinition` entry to `CLASS_REGISTRY` with `base_stats`, `growth_per_level`, and `starting_abilities` (list of ability IDs from `ABILITY_REGISTRY`).
2. **Register the Character** in [src/data/characters.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/characters.py):
   - Add an entry to `catalog` inside `create_character()` with `name`, `class_id`, and starting `Equipment(weapon=..., armor=..., accessory=...)`.
3. **Create a Skill Tree** in [src/data/skill_trees.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/skill_trees.py):
   - Define `<CHAR>_TREE_NODES: dict[str, SkillNode]` and register it in `CHARACTER_TREES["<char_id>"]`.
4. **Add Visual Assets:**
   - **Portrait:** `assets/portraits/<char_id>.png`
   - **Combat Sprite:** `assets/sprites/<char_id>.png` (resolved directly by `EnemySpriteManager` in [src/frontends/pygame_ce/combat_animator.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/frontends/pygame_ce/combat_animator.py); add class aliases if reusing a sprite).
   - **Optional Animations / Overworld Walk Sheets:** Place multi-frame walk sheets or attack/effect frames in `assets/sprites/characters/<char_id>/` and `assets/sprites/effects/` (see `HD2DRenderer._init_character_animations()` and `combat_animator.py`).
5. **Add to Starting Party or Recruitment:**
   - **Starting party:** Add `"<char_id>"` to the list in `GameSession.initialize_new_game()` ([src/core/session.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/core/session.py), currently `rowan`, `lyra`, `caelen`, `melissa`, `jack`, `rachel`). Characters 1–4 go to `active_members`; character 5+ go to `reserve_members` (accessible in `PartyView` at Inns / Rowan's cottage).
   - **Mid-game recruitment:** Call `session.party.add_character(create_character("<char_id>"))` and `session.skill_trees["<char_id>"] = create_character_skill_tree("<char_id>")` from a dialogue `action_trigger` or quest reward.

---

## 3. Adding New Skills (Abilities)

1. **Define the Ability** in [src/data/abilities.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/abilities.py) inside `ABILITY_REGISTRY`:
   ```python
   "ember_volley": AbilityDefinition(
       id="ember_volley",
       name="Ember Volley",
       description="Launches fiery arrows at all enemies with a chance to Burn.",
       mp_cost=14,
       scope=TargetScope.ALL_ENEMIES,   # SINGLE_ENEMY, ALL_ENEMIES, SINGLE_ALLY, ALL_ALLIES, SELF
       element=AbilityElement.FIRE,     # PHYSICAL, FIRE, FROST, EARTH, HOLY, DARK, HEAL
       power=24,
       status_inflict="BURN",           # Optional StatusType name or alias
       status_chance=0.50,              # 0.0 to 1.0
   ),
   ```
2. **Grant the Skill:**
   - **Starting skill:** Add `"ember_volley"` to `ClassDefinition.starting_abilities` in [src/data/classes.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/classes.py).
   - **Unlockable skill:** Add a `SkillNode` with `node_type=NodeType.ABILITY` and `unlocked_ability_id="ember_volley"` in [src/data/skill_trees.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/skill_trees.py).

---

## 4. Adding New Maps

1. **Create Map Folder & `map.json`:**
   - Place `assets/maps/<map_id>/map.json` (plus background/overlay images). Author collision boxes, light markers, dialogue triggers, map transitions, and NPC/sprite props with the built-in editor (validates unique IDs before saving):
     ```powershell
     python -m src.tools.map_editor
     ```
   - Regenerate debug overlays (`collision_overlay.png`) with `python src/tools/generate_collision_overlay.py`.
2. **Register Map Loading / Fallback** in [src/systems/exploration/map_data.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/systems/exploration/map_data.py):
   - `load_map(map_id)` automatically loads `assets/maps/<map_id>/map.json` if present (and falls back to `MAP_REGISTRY` if defined).
3. **Wire Transitions:**
   - **Automatic doorway/edge transition:** Add a `transition` trigger in `map.json` pointing to `target_map_id="<map_id>"`, `target_x`, `target_y`, and a return transition back.
   - **Dialogue-prompted transition (e.g. village building doors):** Add a `dialogue` trigger in `map.json`, then give the confirming `DialogueNode` `action_trigger="ENTER_MAP:<map_id>:<spawn_x>:<spawn_y>"` (handled by `DialogueView._execute_action_trigger()` and `ExplorationView.on_enter()`).
4. **Configure Safe Zones, Encounters, Backgrounds & Music:**
   - **Safe Zones:** Add town/interior map IDs to `EncounterSystem.SAFE_ZONES` ([src/systems/exploration/encounter_system.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/systems/exploration/encounter_system.py)) to disable random encounters.
   - **Enemy Encounter Pool:** Add a branch for `map_id` in `generate_encounter_for_map()` ([src/data/enemies.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/enemies.py)).
   - **Combat Backdrop:** Map `map_id` to a background asset in [src/frontends/pygame_ce/combat_background.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/frontends/pygame_ce/combat_background.py).
   - **Music Context:** Add/map `MusicContext` in [src/frontends/pygame_ce/music_engine.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/frontends/pygame_ce/music_engine.py).

---

## 5. Adding New Quests

Quests are purely declarative in [src/data/quests.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/quests.py) (`QUEST_REGISTRY`). `QuestManager` ([src/systems/quests/quest_manager.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/systems/quests/quest_manager.py)) automatically evaluates objectives, updates the Exploration HUD tracker, displays toast notifications, updates the Camp Journal **Quests** tab, auto-claims rewards, and persists state in `SaveManager`.

### Example Side Quest
```python
"wolf_cull": QuestDefinition(
    id="wolf_cull",
    title="Hounds of the Moor",
    category=QuestCategory.SIDE,
    description="Clear out the rabid Bramble Hounds prowling Briarwood.",
    auto_start=False,                 # True to start on New Game or when prereq_quests finish
    prereq_quests=("shadow_in_briarwood",),
    steps=(
        QuestStep(
            id="kill_hounds",
            description="Defeat Bramble Hounds in Briarwood",
            objective_type=ObjectiveType.KILL_ENEMY,
            target_id="bramble_hound",
            required_count=3,
        ),
        QuestStep(
            id="return_tomas",
            description="Report back to Elder Tomas",
            objective_type=ObjectiveType.TALK_TO_NPC,
            target_id="elder_tomas",
        ),
    ),
    reward=QuestReward(
        exp=80,
        gold=100,
        items={"mana_draught": 2},
        flags=("wolf_cull_done",),
    ),
),
```

### Supported `ObjectiveType` Values
| `ObjectiveType` | Matches When | Required Fields |
| :--- | :--- | :--- |
| `TALK_TO_NPC` | Dialogue `target_id` finishes | `target_id` (`dialogue_id`) |
| `DIALOGUE_STARTED` | Dialogue `target_id` begins | `target_id` (`dialogue_id`) |
| `DIALOGUE_CHOICE` | Specific choice index picked in dialogue node | `target_id` (`dialogue_id`), `node_id`, `choice_index` (0-based) |
| `REACH_PROXIMITY` | Player is within `proximity_radius` px of `target_pos` or map trigger `target_id` | `target_id`, `map_id`, `proximity_radius`, optional `target_pos=(x, y)` |
| `ENTER_MAP` | Player moves in `map_id` / `target_id` | `target_id` (or `map_id`) |
| `KILL_ENEMY` | `required_count` enemies with `sprite_id == target_id` defeated | `target_id`, `required_count` |
| `COLLECT_ITEM` | Party inventory holds `>= required_count` of `target_id` | `target_id`, `required_count` |
| `FLAG_SET` | `on_flag_set(target_id)` is triggered | `target_id` |

To start a quest from proximity, set `unlock_proximity=(map_id, trigger_id, radius_px)` (and optional `unlock_dialogue_id`) on `QuestDefinition`. To start a quest from a dialogue node, call `self.session.quest_manager.start_quest("wolf_cull")` inside `DialogueView._execute_action_trigger()` ([dialogue_view.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/frontends/pygame_ce/views/dialogue_view.py)).

### Scripted Quest Combats (One-Time Boss/Encounter Guards)
To prevent re-triggering a scripted quest combat after its `KILL_ENEMY` step completes:
- Register the action trigger in `DialogueView._SCRIPTED_COMBAT_GUARDS` (`action_trigger -> (quest_id, step_id)`) and optional post-defeat flavor text in `DialogueView._DEFEATED_ENCOUNTER_DIALOGUES`.
- `QuestManager.is_step_completed(quest_id, step_id)` automatically blocks re-launching the combat once the step or quest is finished.

---

## 6. Adding New Equipment & Consumables

All items live in `ITEM_REGISTRY` inside [src/data/items.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/items.py).

### Equipment (`WEAPON`, `ARMOR`, `ACCESSORY`)
```python
"sunfire_blade": ItemDefinition(
    id="sunfire_blade",
    name="Sunfire Blade",
    description="A tempered blade glowing with solar embers.",
    item_type=ItemType.WEAPON,
    value=180,
    stat_bonus=Stats(attack=12, magic_attack=4, crit_chance=0.05),
),
```
- `Character.recalculate_stats()` automatically sums `stat_bonus` for equipped `weapon`, `armor`, and `accessory`.
- `MenuView` **Equipment** and **Inventory** tabs automatically list any item in `ITEM_REGISTRY` once added to `party.inventory`.

### Consumables (`CONSUMABLE`)
```python
"elixir_of_dawn": ItemDefinition(
    id="elixir_of_dawn",
    name="Elixir of Dawn",
    description="Restores 100 HP, 40 MP, and cleanses negative ailments.",
    item_type=ItemType.CONSUMABLE,
    value=120,
    heal_hp=100,
    heal_mp=40,
    cleanse_status=True,
),
```
- `RoundCombat._execute_action` ([round_combat.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/systems/combat/round_combat.py)) reads `heal_hp`, `heal_mp`, `cleanse_status`, and `revive` directly from `ITEM_REGISTRY`.

---

## 7. Adding New Enemies

1. **Add Template** to `ENEMY_TEMPLATES` in [src/data/enemies.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/enemies.py):
   - Set `name`, `tier` (`MINION`, `ELITE`, `BOSS`), `level`, `stats`, `weaknesses`, `resistances`, `abilities` (must exist in `ABILITY_REGISTRY`), `exp_reward`, `gold_reward`, and `loot_drops`.
2. **Add Sprite Assets:**
   - Place sprite in `assets/sprites/enemies/<template_id>.png` (and optional corpse sprite `corpse_<name>.png`).
   - If the filename differs from `<template_id>.png`, register the mapping in `EnemySpriteManager.SPRITE_ALIASES` ([combat_animator.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/frontends/pygame_ce/combat_animator.py)).
3. **Add to Encounters:**
   - Reference `<template_id>` in `generate_encounter_for_map()` ([src/data/enemies.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/enemies.py)).

---

## 8. Integrating Status Effects Across All Combat Mechanics

All 11 `StatusType` values live in [src/entities/actor.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/entities/actor.py) with matching `24×24` icons in `assets/sprites/status/`:
- **Negative:** `POISON`, `BLEED`, `BURN`, `STUN`, `BLIND`, `VULNERABLE` (alias `"armor_break"`), `WEAKEN`
- **Positive:** `REGEN`, `ATTACK_UP`, `DEFENSE_UP` (alias `"fortify"`), `SPEED_UP` (alias `"haste"`)

### A. On Skills *(Already Supported)*
Set `status_inflict` and `status_chance` on any `AbilityDefinition` in [src/data/abilities.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/abilities.py). Both offensive and support (`HEAL`, `SINGLE_ALLY`, `ALL_ALLIES`, `SELF`) skills apply their status automatically in `RoundCombat._execute_action`.

### B. On Consumables
Currently `cleanse_status=True` clears all `NEGATIVE_STATUSES` in `RoundCombat._execute_action`. To allow consumables (e.g., *Swiftness Tonic*, *War Draught*) to **grant** buffs:
1. Add `apply_status: str | None = None` and `apply_status_duration: int = 3` to `ItemDefinition` ([src/data/items.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/items.py)).
2. In `RoundCombat._execute_action` under `# 3. Item Action`, resolve `st = resolve_status_type(item_def.apply_status)` and call `self._apply_status(target, st, duration=item_def.apply_status_duration)`.

### C. On Equipment (Passive Buffs, Immunities, On-Hit)
To support status-infused gear (e.g., *Venomous Fang*, *Ring of Clarity*, *Crown of Regeneration*):
1. Extend `ItemDefinition` ([src/data/items.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/items.py)) with optional fields:
   - `on_hit_status: str | None = None` and `on_hit_chance: float = 0.0`
   - `status_immunities: tuple[str, ...] = ()`
   - `passive_statuses: tuple[str, ...] = ()`
2. In `RoundCombat`:
   - **Immunities:** Check equipped `weapon`/`armor`/`accessory` `status_immunities` inside `_apply_status()` before appending.
   - **Start-of-battle passives:** In `RoundCombat.__init__`, apply `passive_statuses` with a long duration (e.g. `99`) to party members wearing that gear.

### D. On Normal Attacks (`basic_attack`)
In `RoundCombat._execute_action` ([src/systems/combat/round_combat.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/systems/combat/round_combat.py)), when `ability.id == "basic_attack"` and `isinstance(actor, Character)`:
- Inspect `ITEM_REGISTRY.get(actor.equipment.weapon)`.
- If the weapon defines `on_hit_status` and `self.rng.random() < weapon.on_hit_chance`, resolve via `resolve_status_type(weapon.on_hit_status)` and call `self._apply_status(target, st, duration=3, magnitude=max(4, dmg // 3))`.

### E. On Receiving an Attack (Thorns / Reactive Armor / Counter-Status)
To inflict a status back onto an attacker when hit (e.g., *Bramble Mail* inflicting `BLEED` or *Shock Shield* inflicting `STUN`):
1. Add `on_hit_received_status: str | None = None` and `on_hit_received_chance: float = 0.0` to `ItemDefinition` (or `Enemy` templates for spiky monsters).
2. In `RoundCombat._execute_action`, right after `actual_dmg = target.take_damage(dmg)` (when `actual_dmg > 0` and `actor.is_alive`):
   - Check the defender's equipped `armor` / `accessory` (or enemy template trait).
   - If `on_hit_received_status` triggers via `self.rng.random() < chance`, call `self._apply_status(actor, st, duration=2, magnitude=max(3, actual_dmg // 4))` and append the counter-status note to `msg`.

---

## 9. Dialogues & NPCs

- **Dialogue Trees:** Defined in `DIALOGUE_REGISTRY` inside [src/data/dialogues.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/data/dialogues.py).
- **Action Triggers:** Add `action_trigger="<KEY>"` on a `DialogueNode` and handle `<KEY>` in `DialogueView._execute_action_trigger()` ([dialogue_view.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/frontends/pygame_ce/views/dialogue_view.py)) to set `quest_flags`, start combats, open `GameMode.PARTY`, start quests, or transition maps via `ENTER_MAP:<map_id>:<spawn_x>:<spawn_y>`.
- **NPC & Sprite Props:**
  - Place NPC sprites in `assets/sprites/npcs/*.png`.
  - In [map_editor.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/tools/map_editor.py), switch to **`[5] NPC / Sprite Prop`** (key `5`), cycle sprites with `<` / `>` (or `[` / `]`) using the live thumbnail preview, and click/drag on the map to stamp a `props` entry (`prop_type: "npc"`, `sprite`, and optional `solid_rect`).
  - `load_zone_map_from_json()` ([map_data.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/systems/exploration/map_data.py)) loads `MapProp.sprite`, and `HD2DRenderer.draw_prop()` ([hd2d_renderer.py](file:///c:/Users/Sergio/PycharmProjects/TheRiseOfAethelgard/src/frontends/pygame_ce/hd2d_renderer.py)) renders it Y-sorted with a ground shadow. Pair with a `dialogue` trigger zone in `map.json` for interaction.
