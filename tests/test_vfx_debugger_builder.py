"""Tests for the static Sprite Sheet & Combat Skill VFX Debugger builder."""

from __future__ import annotations

import json

from src.tools.build_vfx_debugger import build_debugger


def test_build_vfx_debugger_outputs_valid_bundle(tmp_path):
    out_dir = tmp_path / "vfx_debugger"
    index_path = build_debugger(out_dir)

    assert index_path.is_file()
    data_js = out_dir / "data.js"
    assert data_js.is_file()

    raw = data_js.read_text(encoding="utf-8")
    prefix = "window.VFX_DEBUGGER_DATA = "
    assert raw.startswith(prefix)
    payload = json.loads(raw[len(prefix) :].rstrip().rstrip(";"))

    char_ids = [c["id"] for c in payload["characters"]]
    assert char_ids == ["rowan", "lyra", "caelen", "melissa", "jack", "rachel"]

    rachel = next(c for c in payload["characters"] if c["id"] == "rachel")
    assert {"idle", "attack", "cast"} <= set(rachel["poses"].keys())
    assert (out_dir / rachel["poses"]["cast"]["url"]).is_file()

    violet_ember = next(ab for ab in rachel["abilities"] if ab["id"] == "violet_ember")
    assert violet_ember["vfx"] is not None
    assert len(violet_ember["vfx"]["phases"]) == 2
    assert len(payload["backgrounds"]) >= 1
    assert len(payload["dummies"]) >= 1
