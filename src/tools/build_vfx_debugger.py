"""Build a self-contained static HTML/JS Sprite Sheet & Combat Skill VFX Debugger.

Reads characters, abilities, skill trees, SKILL_VFX_REGISTRY, and assets/
directly so the debugger always stays in sync with the game's real combat rules.

Usage:
    python -m src.tools.build_vfx_debugger
    python -m src.tools.build_vfx_debugger --out _site
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

from src.data.abilities import ABILITY_REGISTRY
from src.data.characters import create_character
from src.data.classes import CLASS_REGISTRY
from src.data.skill_trees import CHARACTER_TREES
from src.frontends.pygame_ce.skill_vfx import SKILL_VFX_REGISTRY, SkillVFXConfig

CHARACTER_ORDER: tuple[str, ...] = ("rowan", "lyra", "caelen", "melissa", "jack", "rachel")


def _discover_sequence(directory: Path, prefix: str) -> dict[str, Any] | None:
    """Discover numbered frames, CxR sheet, or single static PNG for a prefix."""
    if not directory.is_dir():
        return None
    clean = prefix.lower()
    num_pat = re.compile(rf"^{re.escape(clean)}_(\d+)\.png$", re.IGNORECASE)
    sheet_pat = re.compile(rf"^{re.escape(clean)}_(\d+)x(\d+)\.png$", re.IGNORECASE)

    numbered: list[tuple[int, Path]] = []
    sheet_match: tuple[int, int, Path] | None = None
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            continue
        m_num = num_pat.match(entry.name)
        if m_num:
            numbered.append((int(m_num.group(1)), entry))
            continue
        m_sheet = sheet_pat.match(entry.name)
        if m_sheet and sheet_match is None:
            sheet_match = (int(m_sheet.group(1)), int(m_sheet.group(2)), entry)

    if numbered:
        numbered.sort(key=lambda item: item[0])
        frames = [p for _, p in numbered]
        with Image.open(frames[0]) as im:
            w, h = im.size
        return {
            "kind": "frames",
            "paths": frames,
            "frame_count": len(frames),
            "cell_w": w,
            "cell_h": h,
        }

    if sheet_match is not None:
        cols, rows, sheet_path = sheet_match
        with Image.open(sheet_path) as im:
            sw, sh = im.size
        return {
            "kind": "sheet",
            "path": sheet_path,
            "cols": cols,
            "rows": rows,
            "frame_count": cols * rows,
            "cell_w": sw // max(1, cols),
            "cell_h": sh // max(1, rows),
        }

    single = directory / f"{clean}.png"
    if single.is_file():
        with Image.open(single) as im:
            w, h = im.size
        return {
            "kind": "single",
            "path": single,
            "frame_count": 1,
            "cell_w": w,
            "cell_h": h,
        }
    return None


def _copy_asset(src_path: Path, project_root: Path, out_dir: Path) -> str:
    rel = src_path.relative_to(project_root)
    dst = out_dir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dst)
    return rel.as_posix()


def _serialize_sequence(seq: dict[str, Any], project_root: Path, out_dir: Path) -> dict[str, Any]:
    if seq["kind"] == "frames":
        return {
            "kind": "frames",
            "frame_count": seq["frame_count"],
            "cell_w": seq["cell_w"],
            "cell_h": seq["cell_h"],
            "urls": [_copy_asset(p, project_root, out_dir) for p in seq["paths"]],
        }
    if seq["kind"] == "sheet":
        return {
            "kind": "sheet",
            "cols": seq["cols"],
            "rows": seq["rows"],
            "frame_count": seq["frame_count"],
            "cell_w": seq["cell_w"],
            "cell_h": seq["cell_h"],
            "url": _copy_asset(seq["path"], project_root, out_dir),
        }
    return {
        "kind": "single",
        "frame_count": 1,
        "cell_w": seq["cell_w"],
        "cell_h": seq["cell_h"],
        "url": _copy_asset(seq["path"], project_root, out_dir),
    }


def _collect_character_abilities(char_id: str, class_id: str) -> list[str]:
    seen: list[str] = []
    cls_def = CLASS_REGISTRY.get(class_id)
    if cls_def:
        for ab_id in cls_def.starting_abilities:
            if ab_id not in seen:
                seen.append(ab_id)
    tree = CHARACTER_TREES.get(char_id, {})
    for node in tree.values():
        ab_id = node.unlocked_ability_id
        if ab_id and ab_id not in seen:
            seen.append(ab_id)
    return seen


def _serialize_vfx_config(
    cfg: SkillVFXConfig, effects_dir: Path, project_root: Path, out_dir: Path
) -> dict[str, Any]:
    phases_out: list[dict[str, Any]] = []
    effect_folder = effects_dir / cfg.effect_id
    for phase in cfg.phases:
        seq = _discover_sequence(effect_folder, phase.prefix)
        phases_out.append(
            {
                "prefix": phase.prefix,
                "placement": phase.placement,
                "start_time": phase.start_time,
                "duration": phase.duration,
                "frame_count": phase.frame_count or (seq["frame_count"] if seq else 0),
                "offset": [phase.offset[0], phase.offset[1]],
                "arc_height": phase.arc_height,
                "scale": phase.scale,
                "flip_for_enemy": phase.flip_for_enemy,
                "sequence": _serialize_sequence(seq, project_root, out_dir) if seq else None,
            }
        )
    return {
        "effect_id": cfg.effect_id,
        "caster_anim": cfg.caster_anim,
        "total_duration": cfg.total_duration,
        "impact_time": cfg.impact_time,
        "spell_duration": cfg.spell_duration,
        "phases": phases_out,
    }


def build_debugger(out_dir: Path, project_root: Path | None = None) -> Path:
    """Generate the static VFX & Sprite Sheet Debugger bundle at ``out_dir``."""
    root = project_root or Path(__file__).resolve().parent.parent.parent
    assets_dir = root / "assets"
    sprites_dir = assets_dir / "sprites"
    effects_dir = sprites_dir / "effects"

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Characters, poses, and their ability lists
    characters_data: list[dict[str, Any]] = []
    for cid in CHARACTER_ORDER:
        char = create_character(cid)
        idle_path = sprites_dir / f"{cid}.png"
        if not idle_path.is_file():
            idle_path = sprites_dir / f"{char.class_id}.png"
        idle_seq = (
            {
                "kind": "single",
                "frame_count": 1,
                "cell_w": Image.open(idle_path).size[0],
                "cell_h": Image.open(idle_path).size[1],
                "url": _copy_asset(idle_path, root, out_dir),
            }
            if idle_path.is_file()
            else None
        )

        attack_dir = sprites_dir / "characters" / cid / "attack"
        poses: dict[str, Any] = {}
        if idle_seq:
            poses["idle"] = idle_seq
        for pose_name in ("attack", "cast"):
            seq = _discover_sequence(attack_dir, pose_name)
            if seq:
                poses[pose_name] = _serialize_sequence(seq, root, out_dir)

        ab_ids = _collect_character_abilities(cid, char.class_id)
        for ab_id in ab_ids:
            seq = _discover_sequence(attack_dir, ab_id)
            if seq:
                poses[ab_id] = _serialize_sequence(seq, root, out_dir)

        abilities_out: list[dict[str, Any]] = []
        for ab_id in ab_ids:
            ab = ABILITY_REGISTRY.get(ab_id)
            if not ab:
                continue
            vfx_cfg = SKILL_VFX_REGISTRY.get(ab_id)
            abilities_out.append(
                {
                    "id": ab.id,
                    "name": ab.name,
                    "description": ab.description,
                    "mp_cost": ab.mp_cost,
                    "scope": ab.scope.name,
                    "element": ab.element.name,
                    "vfx": (
                        _serialize_vfx_config(vfx_cfg, effects_dir, root, out_dir)
                        if vfx_cfg
                        else None
                    ),
                }
            )

        characters_data.append(
            {
                "id": char.id,
                "name": char.name,
                "class_id": char.class_id,
                "poses": poses,
                "abilities": abilities_out,
            }
        )

    # 2. Combat backgrounds & dummy enemy sprites for realistic arena preview
    backgrounds: list[dict[str, str]] = []
    bg_root = assets_dir / "backgrounds" / "combat"
    if bg_root.is_dir():
        for zone_dir in sorted(bg_root.iterdir()):
            if not zone_dir.is_dir():
                continue
            for bg_file in sorted(zone_dir.glob("*.png")):
                backgrounds.append(
                    {
                        "label": f"{zone_dir.name} / {bg_file.name}",
                        "url": _copy_asset(bg_file, root, out_dir),
                    }
                )

    dummies: list[dict[str, Any]] = []
    for eid, ename in (
        ("root_crawler", "Root Crawler"),
        ("bramble_hound", "Bramble Hound"),
        ("root_guardian_elite", "Root Guardian (Elite)"),
    ):
        epath = sprites_dir / "enemies" / f"{eid}.png"
        if epath.is_file():
            with Image.open(epath) as im:
                ew, eh = im.size
            dummies.append(
                {
                    "id": eid,
                    "name": ename,
                    "w": ew,
                    "h": eh,
                    "url": _copy_asset(epath, root, out_dir),
                }
            )

    payload = {
        "characters": characters_data,
        "backgrounds": backgrounds,
        "dummies": dummies,
    }
    (out_dir / "data.js").write_text(
        f"window.VFX_DEBUGGER_DATA = {json.dumps(payload, indent=2)};\n",
        encoding="utf-8",
    )
    (out_dir / "index.html").write_text(_HTML_TEMPLATE, encoding="utf-8")
    return out_dir / "index.html"


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>The Rise of Aethelgard — Sprite &amp; VFX Debugger</title>
  <style>
    :root {
      --bg: #0e1018;
      --panel: #171a26;
      --border: #2e344b;
      --gold: #e6c265;
      --text: #eef1f7;
      --muted: #98a2b8;
      --accent: #8b5cf6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      min-height: 100vh;
    }
    .sidebar {
      width: 340px;
      flex-shrink: 0;
      background: var(--panel);
      border-right: 1px solid var(--border);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      overflow-y: auto;
      max-height: 100vh;
    }
    h1 {
      margin: 0;
      font-size: 16px;
      color: var(--gold);
      letter-spacing: 0.4px;
    }
    .group {
      background: rgba(10, 12, 18, 0.55);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .group h2 {
      margin: 0;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--muted);
    }
    label {
      font-size: 12px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }
    select, input[type="number"], input[type="text"] {
      background: #0d1018;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 5px;
      padding: 5px 8px;
      font-size: 13px;
    }
    select { width: 100%; }
    input[type="number"] { width: 84px; }
    .row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    button {
      background: #23283b;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 10px;
      font-size: 12px;
      cursor: pointer;
    }
    button:hover { border-color: var(--gold); }
    button.active { background: var(--accent); border-color: #a78bfa; color: #fff; }
    .main {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      padding: 16px;
      gap: 12px;
      overflow: auto;
    }
    .toolbar {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 14px;
      width: 100%;
      max-width: 1280px;
    }
    .stage-wrap {
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: auto;
      width: 100%;
      max-width: 1280px;
      background: #0a0c12;
      box-shadow: 0 12px 32px rgba(0,0,0,0.45);
    }
    canvas {
      display: block;
      width: 100%;
      height: auto;
      image-rendering: pixelated;
      image-rendering: crisp-edges;
    }
    .timeline {
      width: 100%;
      max-width: 1280px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 14px;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }
    .timeline input[type="range"] { flex: 1; min-width: 160px; }
    @media (max-width: 960px) {
      body {
        flex-direction: column;
      }
      .main {
        order: 1;
        padding: 10px;
        width: 100%;
      }
      .sidebar {
        order: 2;
        width: 100%;
        max-height: none;
        border-right: none;
        border-top: 1px solid var(--border);
        padding: 12px;
      }
      .toolbar, .timeline {
        padding: 8px 10px;
      }
      button, select, input[type="number"] {
        min-height: 38px;
      }
    }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
    .phase-card {
      border-top: 1px solid var(--border);
      padding-top: 8px;
      margin-top: 4px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .badge {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
      background: #22273a;
      color: var(--gold);
    }
  </style>
</head>
<body>
  <aside class="sidebar">
    <h1>Aethelgard VFX Debugger</h1>

    <div class="group">
      <h2>Personaje &amp; Pose</h2>
      <label>Personaje <select id="charSelect"></select></label>
      <label>Pose <select id="poseSelect"></select></label>
      <div id="poseMeta" class="mono" style="color: var(--muted);"></div>
    </div>

    <div class="group">
      <h2>Habilidad / Animación</h2>
      <label>Habilidad <select id="abilitySelect"></select></label>
      <div id="abilityMeta" style="font-size: 12px; color: var(--muted);"></div>
      <div class="row">
        <button id="playSkillBtn" class="active">▶ Reproducir Skill</button>
        <label style="gap: 4px;"><input type="checkbox" id="loopCheck" checked /> Loop</label>
      </div>
    </div>

    <div class="group" id="editorGroup">
      <h2>Editor en vivo (skill_vfx.py)</h2>
      <div id="phaseEditors"></div>
      <button id="copyPyBtn">📋 Copiar Python para skill_vfx.py</button>
      <div id="copyStatus" class="mono" style="color: #6ee7b7;"></div>
    </div>
  </aside>

  <main class="main">
    <div class="toolbar">
      <div class="row">
        <span style="font-size:12px; color:var(--muted);">Escala:</span>
        <button class="scale-btn" data-scale="1">1x (Original)</button>
        <button class="scale-btn active" data-scale="2">2x (Combate)</button>
        <button class="scale-btn" data-scale="4">4x (Zoom)</button>
      </div>
      <div class="row">
        <span style="font-size:12px; color:var(--muted);">Escenario:</span>
        <select id="bgSelect" style="width:auto;"></select>
        <select id="dummySelect" style="width:auto;"></select>
      </div>
      <label style="gap:4px;"><input type="checkbox" id="guidesCheck" checked /> Guías visuales</label>
      <label style="gap:4px;"><input type="checkbox" id="bannerCheck" checked /> Banner habilidad</label>
    </div>

    <div class="timeline">
      <button id="playPauseBtn">⏸ Pausa</button>
      <button id="stepBtn">⏭ +1 Frame</button>
      <select id="speedSelect" style="width:auto;">
        <option value="0.25">0.25x</option>
        <option value="0.5">0.5x</option>
        <option value="1" selected>1x</option>
      </select>
      <input id="timeSlider" type="range" min="0" max="1.7" step="0.01" value="0" />
      <span id="timeLabel" class="mono">0.00s / 1.70s</span>
    </div>

    <div class="stage-wrap">
      <canvas id="stage" width="1280" height="720"></canvas>
    </div>
  </main>

  <script src="data.js"></script>
  <script>
    const DATA = window.VFX_DEBUGGER_DATA;
    const canvas = document.getElementById("stage");
    const ctx = canvas.getContext("2d");

    const charSelect = document.getElementById("charSelect");
    const poseSelect = document.getElementById("poseSelect");
    const poseMeta = document.getElementById("poseMeta");
    const abilitySelect = document.getElementById("abilitySelect");
    const abilityMeta = document.getElementById("abilityMeta");
    const bgSelect = document.getElementById("bgSelect");
    const dummySelect = document.getElementById("dummySelect");
    const guidesCheck = document.getElementById("guidesCheck");
    const bannerCheck = document.getElementById("bannerCheck");
    const loopCheck = document.getElementById("loopCheck");
    const playPauseBtn = document.getElementById("playPauseBtn");
    const stepBtn = document.getElementById("stepBtn");
    const playSkillBtn = document.getElementById("playSkillBtn");
    const speedSelect = document.getElementById("speedSelect");
    const timeSlider = document.getElementById("timeSlider");
    const timeLabel = document.getElementById("timeLabel");
    const phaseEditors = document.getElementById("phaseEditors");
    const copyPyBtn = document.getElementById("copyPyBtn");
    const copyStatus = document.getElementById("copyStatus");

    const imageCache = new Map();
    function loadImg(url) {
      if (!url) return null;
      if (imageCache.has(url)) return imageCache.get(url);
      const img = new Image();
      img.src = url;
      imageCache.set(url, img);
      return img;
    }

    let state = {
      charIdx: 0,
      poseKey: "idle",
      abilityIdx: 0,
      scaleMode: 2,
      playing: true,
      speed: 1.0,
      elapsed: 0.0,
      liveVfx: null,
    };

    function getChar() { return DATA.characters[state.charIdx]; }
    function getAbility() { return getChar().abilities[state.abilityIdx]; }

    function populateChars() {
      charSelect.innerHTML = "";
      DATA.characters.forEach((c, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${c.name} (${c.class_id})`;
        charSelect.appendChild(opt);
      });
    }

    function populatePoses() {
      const c = getChar();
      poseSelect.innerHTML = "";
      Object.keys(c.poses).forEach((k) => {
        const p = c.poses[k];
        const opt = document.createElement("option");
        opt.value = k;
        opt.textContent = `${k} (${p.cell_w}x${p.cell_h}, ${p.frame_count}f)`;
        poseSelect.appendChild(opt);
      });
      state.poseKey = c.poses[state.poseKey] ? state.poseKey : "idle";
      poseSelect.value = state.poseKey;
      updatePoseMeta();
    }

    function updatePoseMeta() {
      const p = getChar().poses[state.poseKey];
      poseMeta.textContent = p ? `Celda: ${p.cell_w}x${p.cell_h}px | Frames: ${p.frame_count}` : "Sin sprite";
    }

    function populateAbilities() {
      const c = getChar();
      abilitySelect.innerHTML = "";
      c.abilities.forEach((ab, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${ab.name} (${ab.mp_cost} MP)${ab.vfx ? " ★ VFX" : " (Failsafe)"}`;
        abilitySelect.appendChild(opt);
      });
      state.abilityIdx = 0;
      loadAbilityVfx();
    }

    function loadAbilityVfx() {
      const ab = getAbility();
      state.liveVfx = ab && ab.vfx ? JSON.parse(JSON.stringify(ab.vfx)) : null;
      abilityMeta.innerHTML = ab
        ? `<span class="badge">${ab.scope}</span> <span class="badge">${ab.element}</span><br>${ab.description}`
        : "";
      if (state.liveVfx && getChar().poses[ab.id]) {
        state.poseKey = ab.id;
        poseSelect.value = ab.id;
      } else if (state.liveVfx && state.liveVfx.caster_anim === "spell" && getChar().poses["cast"]) {
        state.poseKey = "cast";
        poseSelect.value = "cast";
      } else if (getChar().poses["attack"] && !state.liveVfx) {
        state.poseKey = "attack";
        poseSelect.value = "attack";
      }
      updatePoseMeta();
      renderPhaseEditors();
      state.elapsed = 0.0;
    }

    function renderPhaseEditors() {
      phaseEditors.innerHTML = "";
      if (!state.liveVfx) {
        phaseEditors.innerHTML = `<div style="font-size:12px;color:var(--muted);">Sin VFX registrado en SKILL_VFX_REGISTRY (usa failsafe lunge + 1.50s).</div>`;
        return;
      }
      const impRow = document.createElement("label");
      impRow.innerHTML = `impact_time (s) <input type="number" step="0.05" value="${state.liveVfx.impact_time}">`;
      impRow.querySelector("input").oninput = (e) => { state.liveVfx.impact_time = parseFloat(e.target.value) || 0; };
      phaseEditors.appendChild(impRow);

      state.liveVfx.phases.forEach((ph, i) => {
        const card = document.createElement("div");
        card.className = "phase-card";
        card.innerHTML = `<div style="font-size:12px;color:var(--gold);">Fase ${i + 1}: <b>${ph.prefix}</b> (${ph.placement})</div>`;
        const fields = [
          ["start_time", "start_time", 0.05],
          ["duration", "duration", 0.05],
          ["offset_x", "ox", 2],
          ["offset_y", "oy", 2],
          ["scale", "scale", 0.05],
          ["arc_height", "arc", 2],
        ];
        fields.forEach(([labelTxt, key, step]) => {
          const val = key === "ox" ? ph.offset[0] : key === "oy" ? ph.offset[1] : ph[key];
          const lbl = document.createElement("label");
          lbl.innerHTML = `${labelTxt} <input type="number" step="${step}" value="${val}">`;
          lbl.querySelector("input").oninput = (e) => {
            const v = parseFloat(e.target.value) || 0;
            if (key === "ox") ph.offset[0] = v;
            else if (key === "oy") ph.offset[1] = v;
            else ph[key] = v;
          };
          card.appendChild(lbl);
        });
        phaseEditors.appendChild(card);
      });
    }

    function populateScenery() {
      bgSelect.innerHTML = `<option value="grid">Lienzo transparente (cuadrícula)</option>`;
      DATA.backgrounds.forEach((b, i) => {
        const opt = document.createElement("option");
        opt.value = i;
        opt.textContent = b.label;
        bgSelect.appendChild(opt);
      });
      if (DATA.backgrounds.length > 0) bgSelect.value = "0";

      dummySelect.innerHTML = "";
      DATA.dummies.forEach((d, i) => {
        const opt = document.createElement("option");
        opt.value = i;
        opt.textContent = `Enemigo: ${d.name}`;
        dummySelect.appendChild(opt);
      });
    }

    function drawSequenceFrame(seq, frameIdx, cx, cy, scale, flipX = false, anchorBottom = false) {
      if (!seq) return;
      let img = null;
      let sx = 0, sy = 0, sw = seq.cell_w, sh = seq.cell_h;
      if (seq.kind === "frames") {
        img = loadImg(seq.urls[Math.min(seq.urls.length - 1, Math.max(0, frameIdx))]);
      } else if (seq.kind === "sheet") {
        img = loadImg(seq.url);
        const col = frameIdx % seq.cols;
        const row = Math.floor(frameIdx / seq.cols);
        sx = col * sw;
        sy = row * sh;
      } else {
        img = loadImg(seq.url);
      }
      if (!img || !img.complete || img.naturalWidth === 0) return;
      const dw = sw * scale;
      const dh = sh * scale;
      const dx = Math.round(cx - dw / 2);
      const dy = Math.round(anchorBottom ? cy - dh : cy - dh / 2);

      ctx.save();
      if (flipX) {
        ctx.translate(dx + dw, dy);
        ctx.scale(-1, 1);
        ctx.drawImage(img, sx, sy, sw, sh, 0, 0, dw, dh);
      } else {
        ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw, dh);
      }
      ctx.restore();
    }

    function drawCheckerboard(w, h) {
      const sz = 16;
      for (let y = 0; y < h; y += sz) {
        for (let x = 0; x < w; x += sz) {
          ctx.fillStyle = ((x / sz + y / sz) % 2 === 0) ? "#1a1d28" : "#131620";
          ctx.fillRect(x, y, sz, sz);
        }
      }
    }

    function render() {
      const ab = getAbility();
      const vfx = state.liveVfx;
      const fadeIn = 0.20;
      const animDur = vfx ? vfx.total_duration : 1.50;
      const fadeOut = 0.30;
      const totalDur = fadeIn + animDur;
      timeSlider.max = totalDur.toFixed(2);
      timeSlider.value = state.elapsed.toFixed(2);
      timeLabel.textContent = `${state.elapsed.toFixed(2)}s / ${totalDur.toFixed(2)}s`;

      const scale = state.scaleMode;
      const isArena = bgSelect.value !== "grid";
      const W = isArena ? (scale === 4 ? 1280 : 1280) : (scale === 4 ? 1120 : 960);
      const H = isArena ? 720 : (scale === 4 ? 640 : 540);
      if (canvas.width !== W || canvas.height !== H) {
        canvas.width = W;
        canvas.height = H;
      }
      ctx.imageSmoothingEnabled = false;

      if (!isArena) {
        drawCheckerboard(W, H);
      } else {
        const bg = DATA.backgrounds[parseInt(bgSelect.value, 10)];
        const bgImg = bg ? loadImg(bg.url) : null;
        if (bgImg && bgImg.complete) ctx.drawImage(bgImg, 0, 0, W, H);
        else { ctx.fillStyle = "#101420"; ctx.fillRect(0, 0, W, H); }
      }

      // Reference anchors (matching CombatView 1280x720)
      const casterX = isArena ? 915 : Math.round(W * 0.72);
      const casterFootY = isArena ? 380 : Math.round(H * 0.68);
      const enemyX = isArena ? 280 : Math.round(W * 0.25);
      const enemyFootY = isArena ? 432 : Math.round(H * 0.68);

      // Draw dummy enemy in Arena mode
      const dummy = DATA.dummies[parseInt(dummySelect.value, 10) || 0];
      if (isArena && dummy) {
        const dImg = loadImg(dummy.url);
        if (dImg && dImg.complete) {
          const dw = dummy.w * scale;
          const dh = dummy.h * scale;
          ctx.drawImage(dImg, Math.round(enemyX - dw / 2), Math.round(enemyFootY - dh), dw, dh);
        }
      }

      // Caster pose + lunge
      const localT = Math.max(0, state.elapsed - fadeIn);
      let lungeX = 0;
      if (!vfx && state.elapsed >= fadeIn && localT < 0.45) {
        lungeX = -Math.sin((localT / 0.45) * Math.PI) * 34 * (scale / 2);
      }
      const c = getChar();
      const poseSeq = c.poses[state.poseKey] || c.poses["idle"];
      let poseFrame = 0;
      if (poseSeq && poseSeq.frame_count > 1 && state.elapsed >= fadeIn) {
        const spDur = vfx ? vfx.spell_duration : 0.80;
        const pProg = Math.min(1, localT / Math.max(0.01, spDur));
        poseFrame = Math.min(poseSeq.frame_count - 1, Math.floor(pProg * poseSeq.frame_count));
      }
      drawSequenceFrame(poseSeq, poseFrame, casterX + lungeX, casterFootY, scale, false, true);

      // Impact flash indicator
      const impactTime = fadeIn + (vfx ? vfx.impact_time : 0.75);
      if (guidesCheck.checked && Math.abs(state.elapsed - impactTime) < 0.08) {
        ctx.save();
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(enemyX, enemyFootY - 60, 44, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      // Active VFX phases
      if (vfx && state.elapsed >= fadeIn) {
        const isAllySkill = ab && (ab.scope === "SINGLE_ALLY" || ab.scope === "ALL_ALLIES" || ab.scope === "SELF");
        const targetX = isAllySkill ? casterX : enemyX;
        const targetFootY = isAllySkill ? casterFootY : enemyFootY;

        vfx.phases.forEach((ph) => {
          const phLocal = localT - ph.start_time;
          if (phLocal < 0 || phLocal > ph.duration || !ph.sequence) return;
          const prog = Math.min(1, Math.max(0, phLocal / Math.max(0.01, ph.duration)));
          const fCount = ph.frame_count || ph.sequence.frame_count || 1;
          const fIdx = Math.min(fCount - 1, Math.floor(prog * fCount));

          const ox = ph.offset[0] * (scale / 2);
          const oy = ph.offset[1] * (scale / 2);
          let px = casterX + ox;
          let py = casterFootY + oy;
          if (ph.placement === "projectile_to_target") {
            const endX = targetX + 24 * (scale / 2);
            const endY = targetFootY - 54 * (scale / 2);
            px = (casterX + ox) + (endX - (casterX + ox)) * prog;
            py = (casterFootY + oy) + (endY - (casterFootY + oy)) * prog - Math.sin(prog * Math.PI) * ph.arc_height * (scale / 2);
          } else if (ph.placement === "target_each" || ph.placement === "target_group_center") {
            px = targetX + ox;
            py = targetFootY + oy;
          }
          drawSequenceFrame(ph.sequence, fIdx, px, py, scale * ph.scale, false, false);
        });
      }

      // Visual guides
      if (guidesCheck.checked) {
        ctx.save();
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 1.5;
        [[casterX, casterFootY, "Caster"], [enemyX, enemyFootY, "Target"]].forEach(([gx, gy, lbl]) => {
          ctx.beginPath();
          ctx.moveTo(gx - 10, gy); ctx.lineTo(gx + 10, gy);
          ctx.moveTo(gx, gy - 10); ctx.lineTo(gx, gy + 10);
          ctx.stroke();
          ctx.fillStyle = "#38bdf8";
          ctx.font = "11px monospace";
          ctx.fillText(lbl, gx + 8, gy - 6);
        });
        ctx.restore();
      }

      // Action-name banner with fade-in & fade-out
      if (bannerCheck.checked && ab) {
        let alpha = 1;
        if (state.elapsed < fadeIn) alpha = state.elapsed / fadeIn;
        else if (state.elapsed > totalDur - fadeOut) alpha = Math.max(0, (totalDur - state.elapsed) / fadeOut);
        if (alpha > 0.01) {
          ctx.save();
          ctx.globalAlpha = alpha;
          const bw = 340, bh = 38;
          const bx = (W - bw) / 2, by = 82;
          ctx.fillStyle = "rgba(18, 22, 34, 0.90)";
          ctx.strokeStyle = "#d4b25c";
          ctx.lineWidth = 2;
          ctx.fillRect(bx, by, bw, bh);
          ctx.strokeRect(bx, by, bw, bh);
          ctx.fillStyle = "#faf2dc";
          ctx.font = "bold 18px system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(ab.name, W / 2, by + bh / 2);
          ctx.restore();
        }
      }
    }

    let lastTs = performance.now();
    function tick(now) {
      const dt = Math.min(0.05, (now - lastTs) / 1000);
      lastTs = now;
      if (state.playing) {
        const totalDur = 0.20 + (state.liveVfx ? state.liveVfx.total_duration : 1.50);
        state.elapsed += dt * state.speed;
        if (state.elapsed >= totalDur) {
          if (loopCheck.checked) state.elapsed = 0.0;
          else { state.elapsed = totalDur; state.playing = false; playPauseBtn.textContent = "▶ Play"; }
        }
      }
      render();
      requestAnimationFrame(tick);
    }

    charSelect.onchange = () => { state.charIdx = parseInt(charSelect.value, 10); populatePoses(); populateAbilities(); };
    poseSelect.onchange = () => { state.poseKey = poseSelect.value; updatePoseMeta(); };
    abilitySelect.onchange = () => { state.abilityIdx = parseInt(abilitySelect.value, 10); loadAbilityVfx(); };
    playSkillBtn.onclick = () => { state.elapsed = 0.0; state.playing = true; playPauseBtn.textContent = "⏸ Pausa"; };
    playPauseBtn.onclick = () => { state.playing = !state.playing; playPauseBtn.textContent = state.playing ? "⏸ Pausa" : "▶ Play"; };
    stepBtn.onclick = () => { state.playing = false; playPauseBtn.textContent = "▶ Play"; state.elapsed += 1 / 24; };
    speedSelect.onchange = () => { state.speed = parseFloat(speedSelect.value); };
    timeSlider.oninput = () => { state.playing = false; playPauseBtn.textContent = "▶ Play"; state.elapsed = parseFloat(timeSlider.value); };
    document.querySelectorAll(".scale-btn").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll(".scale-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.scaleMode = parseInt(btn.dataset.scale, 10);
      };
    });
    copyPyBtn.onclick = async () => {
      if (!state.liveVfx) return;
      const v = state.liveVfx;
      const phasesStr = v.phases.map((p) =>
        `        VFXPhase(\n            prefix="${p.prefix}",\n            placement="${p.placement}",\n            start_time=${p.start_time},\n            duration=${p.duration},\n            frame_count=${p.frame_count},\n            offset=(${p.offset[0]}, ${p.offset[1]}),\n            arc_height=${p.arc_height},\n            scale=${p.scale},\n        ),`
      ).join("\\n");
      const snippet = `"${getAbility().id}": SkillVFXConfig(\n    effect_id="${v.effect_id}",\n    caster_anim="${v.caster_anim}",\n    total_duration=${v.total_duration},\n    impact_time=${v.impact_time},\n    spell_duration=${v.spell_duration},\n    phases=(\n${phasesStr}\n    ),\n),`;
      await navigator.clipboard.writeText(snippet);
      copyStatus.textContent = "Copiado al portapapeles!";
      setTimeout(() => { copyStatus.textContent = ""; }, 2000);
    };

    populateChars();
    populatePoses();
    populateAbilities();
    populateScenery();
    requestAnimationFrame(tick);
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build static Sprite & Combat VFX Debugger.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("dist/vfx_debugger"),
        help="Output directory for static HTML/JS and copied sprite assets.",
    )
    args = parser.parse_args()
    index_path = build_debugger(args.out)
    print(f"Built VFX Debugger at {index_path}")


if __name__ == "__main__":
    main()
