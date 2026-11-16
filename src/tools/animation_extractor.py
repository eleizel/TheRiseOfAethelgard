"""Animation & Sprite Sheet Extractor for The Rise of Aethelgard.

Extracts walk cycles and character animations from video files (such as Gemini-generated animations).
Supports:
- Auto-backend selection: Uses ffmpeg CLI or cv2 (OpenCV).
- Segmented directional extraction (Down, Up, Right, Left).
- Precise character bounding-box cropping and resizing.
- Exporting directional strips and a unified 4x4 animation matrix.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageOps

# Default timestamps for Gemini-generated 10s character showcase videos (4 directions)
DEFAULT_DIRECTIONS: dict[str, tuple[float, float]] = {
    "down": (0.4, 2.0),
    "up": (2.7, 4.3),
    "right": (5.0, 6.6),
    "left": (7.4, 9.0),
}

# Rowan's default bounding box in 1280x720 video: (x, y, width, height)
DEFAULT_CROP_BOX = (500, 210, 250, 390)


def extract_frame_ffmpeg(video_path: str, timestamp_sec: float) -> Image.Image | None:
    """Extract a single frame from video at given timestamp using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_name = tmp.name

    try:
        cmd = [
            "ffmpeg",
            "-ss", f"{timestamp_sec:.3f}",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            tmp_name,
            "-y",
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0 and os.path.exists(tmp_name) and os.path.getsize(tmp_name) > 0:
            im = Image.open(tmp_name)
            im.load()
            return im
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass
    return None


def extract_frame_cv2(cap, frame_idx: int) -> Image.Image | None:
    """Extract a single frame using OpenCV VideoCapture."""
    import cv2  # type: ignore

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if not ret or frame is None:
        return None
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_frame)


def find_default_video() -> Path | None:
    """Locate the default video in assets/video or assets/videos."""
    project_root = Path(__file__).resolve().parent.parent.parent
    for folder_name in ("video", "videos"):
        video_dir = project_root / "assets" / folder_name
        if video_dir.exists():
            for vid in sorted(video_dir.glob("*.mp4")):
                return vid
    return None


def isolate_character(crop_im: Image.Image) -> Image.Image:
    """Isolate character from environmental background using edge flood-fill and component analysis."""
    from collections import deque

    import numpy as np

    im = crop_im.convert("RGB")
    arr = np.array(im).astype(float)
    h, w, _ = arr.shape

    outside_x = (np.arange(w) < 25) | (np.arange(w) > (w - 25))
    bg_samples = arr[:, outside_x, :3].reshape(-1, 3)
    bg_mean = bg_samples.mean(axis=0)
    bg_std = bg_samples.std(axis=0)

    dist = np.sqrt(np.sum(((arr[:, :, :3] - bg_mean) / (bg_std + 1e-5)) ** 2, axis=-1))

    is_bg = np.zeros((h, w), dtype=bool)
    q = deque()

    for x in range(w):
        is_bg[0, x] = True
        q.append((0, x))
        is_bg[h - 1, x] = True
        q.append((h - 1, x))

    for y in range(h):
        is_bg[y, 0] = True
        q.append((y, 0))
        is_bg[y, w - 1] = True
        q.append((y, w - 1))

    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
            if 0 <= ny < h and 0 <= nx < w and not is_bg[ny, nx]:
                if dist[ny, nx] < 2.05:
                    is_bg[ny, nx] = True
                    q.append((ny, nx))

    fg = ~is_bg
    visited = np.zeros((h, w), dtype=bool)
    components = []

    for y in range(h):
        for x in range(w):
            if fg[y, x] and not visited[y, x]:
                comp = []
                cq = deque([(y, x)])
                visited[y, x] = True
                while cq:
                    py, px = cq.popleft()
                    comp.append((py, px))
                    for ny, nx in ((py + 1, px), (py - 1, px), (py, px + 1), (py, px - 1)):
                        if 0 <= ny < h and 0 <= nx < w and fg[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            cq.append((ny, nx))
                components.append(comp)

    clean_fg = np.zeros((h, w), dtype=bool)
    for comp in components:
        if len(comp) > 400:
            for py, px in comp:
                clean_fg[py, px] = True

    alpha = (clean_fg.astype(np.uint8) * 255)
    rgba = im.convert("RGBA")
    rgba.putalpha(Image.fromarray(alpha))
    return rgba


def fit_frame_to_canvas(
    frame: Image.Image,
    target_size: tuple[int, int],
) -> Image.Image:
    """Fit a frame proportionally into a transparent canvas, bottom-aligned.

    This avoids stretching a character when the source crop and target sprite
    canvas have different aspect ratios.
    """
    target_w, target_h = (int(target_size[0]), int(target_size[1]))
    if target_w <= 0 or target_h <= 0:
        raise ValueError("Target frame dimensions must be positive")

    rgba = frame.convert("RGBA")
    fitted = ImageOps.contain(
        rgba, (target_w, target_h), method=Image.Resampling.LANCZOS
    )
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    x = (target_w - fitted.width) // 2
    y = target_h - fitted.height
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def extract_directional_spritesheets(
    video_path: str | Path,
    output_dir: str | Path,
    directions: dict[str, tuple[float, float]] | None = None,
    num_frames: int = 4,
    crop_box: tuple[int, int, int, int] | None = DEFAULT_CROP_BOX,
    target_size: tuple[int, int] | None = (64, 80),
    transparent: bool = True,
) -> dict[str, list[Image.Image]]:
    """Extract multi-directional animation frames and generate sprite sheets.

    :param video_path: Path to input MP4 video.
    :param output_dir: Directory where sprite sheets will be saved.
    :param directions: Dict of direction_name -> (start_sec, end_sec).
    :param num_frames: Frames to sample per direction.
    :param crop_box: Bounding box (x, y, width, height) to isolate character.
    :param target_size: Optional (width, height) to scale down sprites.
    :return: Dict mapping direction name to extracted PIL Images.
    """
    v_path = Path(video_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not v_path.exists():
        raise FileNotFoundError(f"Video file not found: {v_path}")

    dirs = directions or DEFAULT_DIRECTIONS

    # Determine backend
    has_ffmpeg = shutil.which("ffmpeg") is not None
    cap = None

    if not has_ffmpeg:
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(str(v_path))
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        except ImportError:
            raise RuntimeError("Neither 'ffmpeg' nor 'opencv-python' (cv2) is available.")

    results: dict[str, list[Image.Image]] = {}

    for d_name, (start_sec, end_sec) in dirs.items():
        step = (end_sec - start_sec) / max(1, num_frames)
        frames: list[Image.Image] = []

        for i in range(num_frames):
            timestamp = start_sec + (i + 0.5) * step
            frame: Image.Image | None = None

            if has_ffmpeg:
                frame = extract_frame_ffmpeg(str(v_path), timestamp)
            elif cap is not None:
                fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
                f_idx = int(timestamp * fps)
                frame = extract_frame_cv2(cap, f_idx)

            if frame is None:
                continue

            if crop_box:
                cx, cy, cw, ch = crop_box
                frame = frame.crop((cx, cy, cx + cw, cy + ch))

            if transparent:
                frame = isolate_character(frame)

            if target_size:
                frame = fit_frame_to_canvas(frame, target_size)

            frames.append(frame)

        results[d_name] = frames

        # Save individual directional strip
        if frames:
            fw, fh = frames[0].size
            strip = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
            for i, f in enumerate(frames):
                strip.paste(f, (i * fw, 0))
            strip_path = out_dir / f"rowan_walk_{d_name}.png"
            strip.save(strip_path)
            print(f"Saved: {strip_path} ({strip.size[0]}x{strip.size[1]})")

    if cap is not None:
        cap.release()

    # Generate unified 4x4 matrix (Rows: Down, Up, Right, Left)
    row_keys = ["down", "up", "right", "left"]
    if all(k in results and results[k] for k in row_keys):
        fw, fh = results["down"][0].size
        matrix = Image.new("RGBA", (fw * num_frames, fh * 4), (0, 0, 0, 0))
        for r_idx, r_key in enumerate(row_keys):
            for c_idx, f in enumerate(results[r_key][:num_frames]):
                matrix.paste(f, (c_idx * fw, r_idx * fh))
        matrix_path = out_dir / "rowan_walk_matrix.png"
        matrix.save(matrix_path)
        print(f"Saved Unified Matrix: {matrix_path} ({matrix.size[0]}x{matrix.size[1]})")

    return results


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract walk cycles from video into sprite sheets.")
    default_vid = find_default_video()

    parser.add_argument(
        "--video",
        type=str,
        default=str(default_vid) if default_vid else None,
        help="Path to input video (.mp4)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="assets/sprites/characters/rowan",
        help="Directory to save generated sprite sheets",
    )
    parser.add_argument(
        "--num-frames",
        type=int,
        default=4,
        help="Number of animation frames per direction (default: 4)",
    )
    parser.add_argument(
        "--target-w",
        type=int,
        default=64,
        help="Target sprite width in pixels (default: 64, set 0 for raw crop)",
    )
    parser.add_argument(
        "--target-h",
        type=int,
        default=80,
        help="Target sprite height in pixels (default: 80, set 0 for raw crop)",
    )

    args = parser.parse_args(argv)

    if not args.video:
        print("Error: No video file found. Please provide --video <path_to_mp4>.")
        return

    target_size = (args.target_w, args.target_h) if (args.target_w > 0 and args.target_h > 0) else None

    print(f"Extracting animations from: {args.video}")
    print(f"Output directory: {args.output_dir}")
    print(f"Frames per direction: {args.num_frames}")
    print(f"Target size: {target_size or 'Raw Crop'}")

    extract_directional_spritesheets(
        video_path=args.video,
        output_dir=args.output_dir,
        num_frames=args.num_frames,
        crop_box=DEFAULT_CROP_BOX,
        target_size=target_size,
    )
    print("Animation extraction complete.")


if __name__ == "__main__":
    main()
