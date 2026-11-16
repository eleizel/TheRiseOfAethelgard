# Rowan walk-cycle assets

## Cell and direction contract

All Rowan exploration walk-cycle cells use a **64x80 RGBA canvas**.

The runtime supports:
- 4 columns x 4 rows: legacy 4-frame cycle, matrix 256x320, strips 256x80.
- 8 columns x 4 rows: expanded 8-frame cycle, matrix 512x320, strips 512x80.

Direction row order is always: down/front, up/back, right, left.
Frame order runs left-to-right and loops from the final frame back to frame 0.

## Currently installed asset

The files currently in this folder remain the legacy 4-frame version:
- `rowan_walk_matrix.png` — 256x320.
- `rowan_walk_down.png`, `rowan_walk_up.png`, `rowan_walk_right.png`, `rowan_walk_left.png` — each 256x80.

Their source was a 192x256 sheet with 48x64 cells. The earlier 64x80 normalization used a uniform nearest-neighbor scale of 1.25, a 60x80 artwork canvas and 2px transparent padding on each horizontal side, bottom-anchored.

## 8-frame upgrade candidate

A reviewed 8-frame replacement pack has been prepared separately as `rowan_walk_8frame_64x80_review_pack.zip`.
It contains the 512x320 matrix, four 512x80 strips, 32 individual PNG frames and 12.5fps previews. It is not automatically copied over these active files; review the package and run its included `install_rowan_8frame.ps1` to back up and install it.

The 8-frame art is authored as two alternating steps: contact A, compression, passing, transfer, contact B, compression, passing, transfer back to the loop. Keep the four direction rows and the 64x80 cell size unchanged.

## Runtime timing

`src/frontends/pygame_ce/hd2d_renderer.py` accepts four or more 64px-wide columns over four 80px-high direction rows.

The walk cycle timing is:
- 4 frames: 6.5fps (about 154ms per frame; ~615ms per cycle).
- 8 frames: 12.5fps (80ms per frame; 640ms per cycle).

The 8-frame cycle is about 4% slower than the legacy 4-frame cycle, while providing twice the pose samples. `ExplorationView` maintains a dedicated walk-animation clock. It advances only when collision resolution results in actual movement and resets to frame 0 when movement stops or the map changes. This prevents random phase starts and idle animation while pressed against a wall.

The video extraction utility `src/tools/animation_extractor.py` defaults to 64x80 and proportionally fits generated video crops into a transparent canvas, bottom-aligned.

## Backups

The five original 64x80-normalization assets were preserved with suffix:

`.before_64x80_20261115_112220.bak`

The original static Rowan sprite was not modified.
