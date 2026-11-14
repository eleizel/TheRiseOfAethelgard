"""Unit tests for 2D Camera tracking and frustum culling."""

from src.frontends.pygame_ce.camera import Camera


def test_camera_clamping():
    cam = Camera(view_width=640, view_height=360)
    map_w, map_h = 960, 640

    # Target near top-left: camera should clamp to (0, 0)
    cam.update(target_x=50, target_y=50, map_width=map_w, map_height=map_h, dt=1.0)
    assert cam.x == 0.0
    assert cam.y == 0.0

    # Target near center: camera should center on target
    cam.update(target_x=480, target_y=320, map_width=map_w, map_height=map_h, dt=1.0)
    assert abs(cam.x - (480 - 320)) <= 2.0
    assert abs(cam.y - (320 - 180)) <= 2.0

    # Target near bottom-right: camera should clamp to (map_w - 640, map_h - 360)
    cam.update(target_x=950, target_y=630, map_width=map_w, map_height=map_h, dt=1.0)
    assert abs(cam.x - (960 - 640)) <= 2.0
    assert abs(cam.y - (640 - 360)) <= 2.0


def test_camera_frustum_visibility():
    cam = Camera(view_width=640, view_height=360)
    cam.x = 100
    cam.y = 100

    # Inside view
    assert cam.is_visible(world_x=200, world_y=200, width=32, height=32) is True
    # Off to the left
    assert cam.is_visible(world_x=20, world_y=200, width=32, height=32) is False
    # Off to the right
    assert cam.is_visible(world_x=800, world_y=200, width=32, height=32) is False
