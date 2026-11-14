"""Smooth 2D tracking camera for 640x360 canvas with frustum culling."""

from __future__ import annotations

import pygame


class Camera:
    """Clamped 2D camera with smoothing and frustum visibility checks."""

    def __init__(self, view_width: int = 640, view_height: int = 360) -> None:
        self.view_width = view_width
        self.view_height = view_height
        self.x: float = 0.0
        self.y: float = 0.0

    def update(self, target_x: float, target_y: float, map_width: int, map_height: int, dt: float = 0.016) -> None:
        """Center the camera on (target_x, target_y) with boundary clamping."""
        desired_x = target_x - self.view_width / 2.0
        desired_y = target_y - self.view_height / 2.0

        # Boundary clamping
        max_x = max(0, map_width - self.view_width)
        max_y = max(0, map_height - self.view_height)

        desired_x = max(0.0, min(float(max_x), desired_x))
        desired_y = max(0.0, min(float(max_y), desired_y))

        # Smooth lerp
        lerp_factor = min(1.0, 10.0 * dt) if dt > 0 else 1.0
        self.x += (desired_x - self.x) * lerp_factor
        self.y += (desired_y - self.y) * lerp_factor

    def to_screen(self, world_x: float, world_y: float) -> tuple[int, int]:
        return int(world_x - self.x), int(world_y - self.y)

    def apply_rect(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.move(int(-self.x), int(-self.y))

    def is_visible(self, world_x: float, world_y: float, width: float, height: float) -> bool:
        """Frustum check: True if bounding box intersects current camera view."""
        return not (
            world_x + width < self.x
            or world_x > self.x + self.view_width
            or world_y + height < self.y
            or world_y > self.y + self.view_height
        )
