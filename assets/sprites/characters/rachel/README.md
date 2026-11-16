# Rachel — walk cycle and Violet Ember animation

## Canonical sprite relationship

These assets are designed to accompany the new combat sprite `assets/sprites/rachel.png` (64x80 RGBA). The static combat sprite is not included in this package and is not overwritten by the installer.

## Walking animation

- Cell canvas: 64x80 RGBA.
- Matrix: `rachel_walk_matrix.png`, 512x320 (8 columns x 4 direction rows).
- Direction strips: 512x80 each.
- Row order: down/front, up/back, right, left.
- Eight frames per direction, left-to-right.
- Playback preview: 80 ms/frame (12.5 fps), 640 ms cycle.
- Common bottom support line: y=71/72 due one-pixel pixel-cluster variations; all frames use the same 64x80 canvas and anchor.
- Nearest-neighbor scaling, transparent background, binary alpha.

The four directional rows were generated as a consistent character family. Front/back movement is deliberately more subtle than the side-view stride because of the depth projection. Inspect the GIFs at normal gameplay scale before treating the movement as final.

## Attack: Violet Ember

- Character attack strip: `rachel_violet_ember_attack.png`, 512x80 (8 frames x 64x80).
- Individual frames: `attack_frames/violet_ember_00.png` through `violet_ember_07.png`.
- Playback: 100 ms/frame (10 fps), 800 ms one-shot.
- Staging: ready/anticipation, hand and wand rise, violet energy gathers and swells, forward release, follow-through/recovery.

## Projectile effect

- Projectile strip: `rachel_violet_projectile.png`, 256x32 (8 frames x 32x32).
- Individual frames: `projectile_frames/projectile_00.png` through `projectile_07.png`.
- Preview: 40 ms/frame (25 fps). Runtime maps the eight frames across a 320 ms flight path.
- Shared 128-colour RGB palette; no dithering.

## In-game paths expected by the updated combat renderer

Install the files to these locations:

```text
assets/sprites/characters/rachel/
  rachel_walk_matrix.png
  rachel_walk_down.png
  rachel_walk_up.png
  rachel_walk_right.png
  rachel_walk_left.png
  attack/
    violet_ember_00.png ... violet_ember_07.png
assets/sprites/effects/violet_ember/
  projectile_00.png ... projectile_07.png
```

The game code change adds a Rachel-only casting state triggered by ability id `violet_ember`; damage calculation, MP cost, target resolution and hit logic remain in the existing combat system. The projectile is drawn from Rachel to the selected living enemy.

Rachel's walk strips are prepared as reusable assets. The current exploration runtime still drives Rowan as the controlled explorer; it does not yet have a party-follow/follower animation system for Rachel.

## Installation

From PowerShell after extracting the package:

```powershell
.\install_rachel_animation.ps1 -ProjectRoot "C:\Users\Sergio\PycharmProjects\TheRiseOfAethelgard"
```

The installer backs up any existing target PNGs before replacing them. It does not touch `assets/sprites/rachel.png`, portraits, map files or other characters.

## Quality notes

The images are generated pixel-art source and then cropped, background-cleaned, uniformly normalized and checked in PixelArtStudio-style tooling. Automated validation checks dimensions, alpha and frame order. It cannot guarantee the animation's artistic smoothness; review the GIFs in-game for foot contact, facing and speed.
