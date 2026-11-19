---
name: aethelgard-asset-guide
description: >-
  Complete visual asset creation and technical integration guide for The Rise of
  Aethelgard. Use whenever generating, editing, slicing, or integrating 16-bit
  SNES/HD-2D pixel art sprites, characters, cast/attack poses, NPCs, enemies,
  skill VFX, maps, collision overlays, props, combat backgrounds, portraits, or
  UI/status icons.
---

# The Rise of Aethelgard — Visual Asset & Art Direction Guide

This skill is the authoritative reference for creating, exporting, and wiring **all visual assets** in *The Rise of Aethelgard*. Every pixel dimension, directory convention, and code loader behavior documented below is enforced by the engine.

---

## 1. Art Style & Visual Direction (16-Bit SNES Classic RPG / HD-2D)

- **Aesthetic Era:** Late 16-bit SNES RPG (*Chrono Trigger*, *Final Fantasy VI*, *Tales of Phantasia*) enhanced with modern HD-2D lighting (*Octopath Traveler*): crisp pixel clusters, rich painterly shading, atmospheric contrast, and zero blurry anti-aliased edges.
- **Pixel Discipline:**
  - **Crisp pixel art only:** No soft airbrush gradients, no painterly smear, no pillow shading, no anti-aliased outer halos against white/black.
  - **Outlines:** Deep tinted dark outlines (dark plum/charcoal/mahogany `#18121e`–`#281e2c`, never harsh pure `#000000` unless deep shadow) for readability against dark mossy/cavern backgrounds.
  - **Lighting & Shading:** Consistent top-left directional key light (`~45°`) with 3–4 value ramps per material, rim highlights on armor/crystals/foliage, and subtle purple/teal ambient bounce in corrupted zones (*Rooted Hollows*).
  - **Transparency:** All sprites, portraits (if circular/framed), props, VFX, and icons **MUST** be exported as **32-bit RGBA PNG** with **true alpha transparency** (`alpha = 0` background — never baked white, black, or checkerboard backgrounds).
  - **Color Harmony by Zone:**
    - *Sunvale Village:* Warm golden sunlight, timber browns, mossy stone, terracotta roofs, emerald grass.
    - *Briarwood Verge:* Twilight forest greens, muted teal mist, earthy bark, thorny vines, dappled moonlight.
    - *Rooted Hollows:* Deep subterranean slate/indigo, glowing amethyst/magenta corruption crystals, bioluminescent spores, gnarled dark roots.

---

## 2. Strict Sprite Dimensions & Facing Rules

All character, NPC, and enemy sprites **MUST** match these exact pixel dimensions. `map_editor.py` stamps props at 1:1 native pixel size, and `CombatView` scales combat sprites uniformly with `pixel_scale = 2.0 * min(sx, sy)` (`1280×720` reference).

| Category | Exact Cell / Image Size (`W × H`) | Facing Direction | Examples |
| :--- | :--- | :--- | :--- |
| **Child NPC** | `64×64` | Front / 3-4 overworld | `nino_*.png`, `nina_*.png` |
| **Adult NPC / Playable Character (Battle Idle)** | `64×80` | **Facing Left** (`←`) in combat | `rowan.png`, `rachel.png`, `lyra.png`, `caelen.png`, `melissa.png`, `jack.png` |
| **Walk Sheet Frame (Overworld)** | `64×80` per cell | 4-directional (`down`, `left`, `right`, `up`) | `assets/sprites/characters/<char_id>/walk/*.png` |
| **Cast / Attack Pose Frame (Combat)** | `64×80` per cell | **Facing Left** (`←`) | `assets/sprites/characters/<char_id>/attack/` |
| **Large NPC / Large Character** | `80×96` | Front / 3-4 overworld | Bulky armored NPCs or tall figures |
| **Normal Enemy (`MINION`)** | `80×80` | **Facing Right** (`→`) in combat | `thornvein_creeper.png`, `root_crawler.png`, `corrupt_bloom.png`, `crystal_viper.png`, `root_wraith.png`, `shadow_fungus.png` |
| **Elite Enemy (`ELITE`)** | `112×112` | **Facing Right** (`→`) in combat | `mandragora_matron.png`, `malignant_belladonna.png`, `corrupt_geomancer_elite.png`, `root_guardian_elite.png` |
| **Boss Enemy (`BOSS`)** | `128×144` | **Facing Right** (`→`) in combat | `root_goliath.png`, `corpse_treant.png` |
| **Skill VFX / Projectile Frame** | `64×80` (or `48×48`–`96×96`) | **Shooting Left** (`←`) for party skills | `assets/sprites/effects/<effect_id>/` |
| **Character Portrait** | `64×64` or `128×128` (square) | Front / 3-4 bust | `assets/portraits/<char_id>.png` |
| **Status Icon** | `24×24` | Centered badge | `assets/sprites/status/<status>.png` |

> **Combat Facing Rule:** Party members stand on the **right** side of the battle arena and **face left** (`←`). Enemies stand on the **left** side and **face right** (`→`). Projectiles created for player skills should travel **right-to-left** (`←`); when an enemy casts a registered VFX, `CombatView` mirrors `flip_x` automatically if `flip_for_enemy=True`.

---

## 3. Directory Layout & How Every Asset Is Loaded in Code

### A. Playable Characters & Walk / Cast / Attack Poses
- **Battle Idle Sprite:** `assets/sprites/<char_id>.png` (`64×80` RGBA, facing left).
  - Loaded by `EnemySpriteManager.get_character_sprite()` in `src/frontends/pygame_ce/combat_animator.py` (uses `CHAR_CLASS_ALIASES` as fallback if `<char_id>.png` is missing).
  - Rendered at `pixel_scale = 2.0 * min(sx, sy)` (`128×160` on a `1280×720` screen) with bottom-center anchoring (`anchor_bottom_center=True`).
- **Portraits:** `assets/portraits/<speaker_id>.png`
  - Loaded by `EnemySpriteManager.get_portrait()` and displayed in `DialogueView`, `MenuView`, `PartyView`, and `SkillTreeView`.
- **Overworld Walk Sheets:** `assets/sprites/characters/<char_id>/walk/` (each frame `64×80` RGBA).
  - Loaded by `HD2DRenderer._init_character_animations()` in `src/frontends/pygame_ce/hd2d_renderer.py`.
- **Combat Cast & Attack Poses:** `assets/sprites/characters/<char_id>/attack/` (`64×80` RGBA per frame, facing left).
  - `EnemySpriteManager` automatically discovers sequences in priority order:
    1. **Numbered frames:** `<pose>_00.png`, `<pose>_01.png`, ... (e.g. `cast_00.png..07.png`, `attack_00.png..07.png`, or `<ability_id>_00.png..`).
    2. **Auto-sliced spritesheet:** `<pose>_<cols>x<rows>.png` (e.g. `cast_8x1.png`, `attack_4x2.png`). Sliced row-by-row, left-to-right in memory.
    3. **Single static pose:** `<pose>.png` (e.g. `cast.png` or `attack.png`).
  - Lookup order during combat (`CombatView._trigger_attacker_animation()`):
    - For skills (`caster_anim="spell"` or any skill when `cast` frames exist): looks for `<ability_id>` first, then falls back to `cast`.
    - For basic attacks (`caster_anim="lunge"`): looks for `<ability_id>` / `attack`; if none exist on disk, falls back cleanly to the idle battle sprite with a procedural lunge (`offset_x`).

### B. Enemies
- **Path:** `assets/sprites/enemies/<template_id>.png` (and optional corpse/prop sprites `corpse_<name>.png`).
- **Loader:** `EnemySpriteManager.get_sprite()` in `src/frontends/pygame_ce/combat_animator.py` checks `<sprite_id>.png`, `SPRITE_ALIASES`, and normalized name variants.
- **Scale & Display:** Rendered with `pixel_scale = 2.0 * min(sx, sy)` (`anchor_bottom_center=True`). Above each living enemy, `CombatView` renders `(<level>) <name>` and an HP bar clamped below the top banner (`bar_y >= 86 * sy`).

### C. Skill VFX & Projectiles (`assets/sprites/effects/<effect_id>/`)
- **Supported File Formats** (identical auto-loader to character poses):
  - Numbered PNGs: `<prefix>_00.png`, `<prefix>_01.png`, ... (e.g. `charge_00..07.png`, `projectile_00..07.png`).
  - Auto-sliced grids: `<prefix>_<cols>x<rows>.png` (e.g. `buff_4x2.png`, `impact_8x1.png`).
  - Single frame: `<prefix>.png`.
- **Declarative Wiring (`src/frontends/pygame_ce/skill_vfx.py`):**
  Register `SkillVFXConfig` in `SKILL_VFX_REGISTRY["<ability_id>"]`:
  - `effect_id`: folder name under `assets/sprites/effects/`.
  - `caster_anim`: `"lunge"`, `"spell"`, or `"none"`.
  - `total_duration`: `1.50` seconds (synchronized with the centered action-name banner fade-in `0.20 s` and fade-out `0.30 s`).
  - `impact_time`: timestamp (relative to animation start) when damage/healing/buffs, white hit-flash, hurt recoil, and floating numbers trigger.
  - `phases`: tuple of `VFXPhase` objects:
    - `prefix`: file prefix (`"charge"`, `"projectile"`, `"buff"`, `"impact"`, `"slash"`, `"aura"`).
    - `placement`:
      - `"caster"` — anchored at caster (`offset` applied; mirrored on `X` if enemy casts and `flip_for_enemy=True`).
      - `"projectile_to_target"` — travels from caster `+ offset` to each target `(tx + 24, ty - 54)` with optional `arc_height`.
      - `"target_each"` — spawns one simultaneous instance on **every** target (ideal for party-wide buffs like Rowan's `DEF UP`, AoE heals, or multi-target spells).
      - `"target_group_center"` — spawns one centered instance over the centroid of all targets (ideal for massive AoE explosions).
    - `start_time`, `duration`, `frame_count` (`None` = auto-detected), `offset`, `arc_height`, `scale`, `flip_for_enemy`.

### D. Maps, Collision Overlays & Overworld Props
- **Map Folder:** `assets/maps/<map_id>/`
  - `background.png` (or `<map_id>.png`): Top-down / 3/4 SNES overworld map image. Recommended canvas: **`1280×720`** (or larger multi-screen dimensions; `1280×720` fits `16:9` natively).
  - `foreground.png` (optional): Overhead canopy/arch layer drawn above the player/NPCs.
  - `collision_overlay.png`: Debug overlay generated by `python -m src.tools.generate_collision_overlay`.
  - `map.json`: Authoritative map metadata (`spawn`, `colliders`, `lights`, `triggers`, `props`).
- **Props (`assets/sprites/npcs/*.png` and `assets/sprites/props/*.png`):**
  - Placed via `python -m src.tools.map_editor` (`[5] NPC / Sprite Prop`).
  - Stamped at **exact native image dimensions** (`w × h` in pixels, no automatic downscaling/upscaling).
  - Rendered Y-sorted by `HD2DRenderer.draw_prop()` with a ground drop shadow.

### E. Combat Backgrounds
- **Path:** `assets/backgrounds/combat/<map_id>/combat_background_01.png`, `combat_background_02.png`, ...
- **Recommended Size:** **`1280×720`** (`16:9`, opaque RGB/RGBA PNG).
- **Loader:** `CombatBackgroundManager.get_random_background()` (`src/frontends/pygame_ce/combat_background.py`) scans `assets/backgrounds/combat/<map_id>/` for any `.png` containing `"combat_background"` in the filename, scales to viewport if needed, and picks one at random per encounter.
  - **Composition Tip:** Keep the upper `y = 0..130` band relatively uncluttered (top announcement banner sits at `y=14..62` and action-name banner sits at `y=82..120`) and leave clear ground footing around `y = 330..480` on the left (enemies) and `y = 330..470` on the right (party).

### F. Status Icons & UI Assets
- **Status Icons:** `assets/sprites/status/status_<status_name>.png` (`24×24` RGBA PNG).
  - 15 statuses: `poison`, `bleed`, `burn`, `stun`, `blind`, `vulnerable`, `weaken`, `regeneration`, `attack_up`, `fortify`, `haste`, `thorns`, `shield`, `crit_up`, `magic_defense_up`.
  - Loaded by `get_status_icon()` in `src/frontends/pygame_ce/ui_manager.py`.

---

## 4. Quick Checklist Before Committing New Assets

1. **RGBA transparency verified** (no white/black matte boxes or stray alpha fringe pixels).
2. **Exact dimensions** match Section 2 (`64×64`, `64×80`, `80×96`, `80×80`, `112×112`, `128×144`, `1280×720`, `24×24`).
3. **Correct facing direction** (party & player projectiles face **left** `←`; enemies face **right** `→`).
4. **No `pygame` imports** introduced in `src/data/` or `src/core/` (verified by `tests/test_architecture_boundary.py`).
5. Run `python -m pytest -q` and `python -m ruff check src tests` after adding/wiring assets.
