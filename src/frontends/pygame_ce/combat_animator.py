"""Combat animation engine and enemy sprite manager.

Provides procedural SNES/HD-2D combat animations:
- Idle rhythmic breathing/bobbing
- Forward lunging attack animation
- Recoil knockback and high-frequency hurt wobble
- High-intensity white hit-flash highlight
- Defeated/KO dissolve fading
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.entities.character import Character
    from src.entities.enemy import Enemy


@dataclass
class CombatantAnimState:
    """Tracks procedural animation state for combat participants."""

    phase_offset: float = 0.0
    is_player: bool = False
    anim_type: str = "idle"  # "idle", "attack", "spell", "hurt"
    anim_timer: float = 0.0
    anim_duration: float = 0.0
    spell_frame_count: int = 8
    flash_timer: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    lunge_dist: float = 32.0
    recoil_dist: float = 12.0
    ko_alpha: float = 255.0

    def trigger_attack(self, duration: float = 0.45, distance: float = 32.0) -> None:
        self.anim_type = "attack"
        self.anim_timer = duration
        self.anim_duration = duration
        self.lunge_dist = distance

    def trigger_spell(self, duration: float = 0.8, frame_count: int = 8) -> None:
        """Play a character-specific casting animation once, without changing combat logic."""
        self.anim_type = "spell"
        self.anim_timer = max(0.01, duration)
        self.anim_duration = self.anim_timer
        self.spell_frame_count = max(1, frame_count)
        self.offset_x = 0.0
        self.offset_y = 0.0

    @property
    def spell_frame_index(self) -> int:
        if self.anim_type != "spell" or self.anim_duration <= 0.0:
            return 0
        progress = 1.0 - self.anim_timer / self.anim_duration
        return min(self.spell_frame_count - 1, max(0, int(progress * self.spell_frame_count)))

    def trigger_hurt(self, duration: float = 0.38, recoil: float = 12.0) -> None:
        self.anim_type = "hurt"
        self.anim_timer = duration
        self.anim_duration = duration
        self.recoil_dist = recoil
        self.flash_timer = 0.22

    def update(self, dt: float, is_alive: bool = True) -> None:
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

        if not is_alive:
            self.anim_type = "idle"
            self.offset_x = 0.0
            self.offset_y = 0.0
            self.ko_alpha = max(0.0, self.ko_alpha - 280.0 * dt)
            return

        self.ko_alpha = 255.0

        if self.anim_timer > 0.0:
            self.anim_timer = max(0.0, self.anim_timer - dt)
            if self.anim_timer <= 0.0:
                self.anim_type = "idle"
                self.offset_x = 0.0
            else:
                progress = 1.0 - (self.anim_timer / self.anim_duration) if self.anim_duration > 0.0 else 1.0

                if self.anim_type == "attack":
                    # Forward lunge arc towards opposing side
                    direction = -1.0 if self.is_player else 1.0
                    self.offset_x = direction * math.sin(progress * math.pi) * self.lunge_dist
                    self.offset_y = -math.sin(progress * math.pi) * 4.0
                elif self.anim_type == "spell":
                    # Subtle upward anticipation; frame art carries the hand/flame pose.
                    self.offset_x = 0.0
                    self.offset_y = -math.sin(progress * math.pi) * 2.0
                elif self.anim_type == "hurt":
                    # Recoil displacement away from hit + rapid horizontal wobble
                    direction = 1.0 if self.is_player else -1.0
                    decay = 1.0 - progress
                    wobble = math.sin(progress * 32.0) * 8.0 * decay
                    self.offset_x = (direction * decay * self.recoil_dist) + wobble
                    self.offset_y = math.cos(progress * 24.0) * 3.0 * decay
        else:
            self.anim_type = "idle"
            self.offset_x = 0.0
            bob_speed = 3.2 if self.is_player else 2.5
            bob_amp = 1.8 if self.is_player else 2.5
            self.phase_offset += dt * bob_speed
            self.offset_y = math.sin(self.phase_offset) * bob_amp


class EnemySpriteManager:
    """Loads, scales, and caches 16-bit enemy sprites with hit-flash generation."""

    SPRITE_ALIASES = {
        "corrupted_treant": "corpse_treant.png",
        "treant_boss": "corpse_treant.png",
        "boss_treant": "corpse_treant.png",
        "bramble_hound": "bramble_hound.png",
        "thornvein_creeper": "thornvein_creeper.png",
        "spore_pod": "spore_pod.png",
        "corrupted_spore_pod": "spore_pod.png",
        "mandragora_matron": "mandragora_matron.png",
    }

    def __init__(self, assets_dir: Path | str | None = None) -> None:
        if assets_dir is None:
            self.assets_root = Path(__file__).resolve().parent.parent.parent.parent / "assets"
            self.assets_dir = self.assets_root / "sprites" / "enemies"
        else:
            self.assets_dir = Path(assets_dir)
            self.assets_root = self.assets_dir.parent.parent

        self.char_sprites_dir = self.assets_root / "sprites"
        self.portraits_dir = self.assets_root / "portraits"

        self._raw_cache: dict[str, pygame.Surface] = {}
        self._scaled_cache: dict[tuple[str, int, int], tuple[pygame.Surface, pygame.Surface]] = {}
        self._portrait_cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self._action_frame_cache: dict[tuple[str, str, int], pygame.Surface | None] = {}
        self._action_scaled_cache: dict[
            tuple[str, str, int, float | None], tuple[pygame.Surface, pygame.Surface]
        ] = {}
        self._projectile_frame_cache: dict[tuple[str, str, int], pygame.Surface | None] = {}

    def _resolve_filename(self, sprite_id: str, name: str) -> str | None:
        # 1. Alias lookup
        if sprite_id in self.SPRITE_ALIASES:
            return self.SPRITE_ALIASES[sprite_id]

        # 2. Direct filename
        candidate = f"{sprite_id}.png"
        if (self.assets_dir / candidate).exists():
            return candidate

        # 3. Clean name lookup
        clean_name = name.lower().replace(" ", "_")
        if clean_name in self.SPRITE_ALIASES:
            return self.SPRITE_ALIASES[clean_name]
        candidate = f"{clean_name}.png"
        if (self.assets_dir / candidate).exists():
            return candidate

        # 4. Partial substring matching
        for f in self.assets_dir.glob("*.png"):
            stem = f.stem.lower()
            if stem in sprite_id.lower() or sprite_id.lower() in stem:
                return f.name
            if stem in clean_name or clean_name in stem:
                return f.name

        # Fallback to thornvein_creeper or first available
        fallback = self.assets_dir / "thornvein_creeper.png"
        if fallback.exists():
            return "thornvein_creeper.png"
        return None

    def get_enemy_sprite(
        self,
        sprite_id: str,
        name: str,
        max_w: int = 72,
        max_h: int = 60,
        pixel_scale: float | None = None,
    ) -> tuple[pygame.Surface, pygame.Surface]:
        """Return (base_sprite, flash_sprite) scaled to fit max_w/max_h or by pixel_scale."""
        cache_key = (f"{sprite_id}:{name}", max_w, max_h, pixel_scale)
        if cache_key in self._scaled_cache:
            return self._scaled_cache[cache_key]

        fn = self._resolve_filename(sprite_id, name)
        raw_surf: pygame.Surface | None = None

        if fn:
            if fn not in self._raw_cache:
                path = self.assets_dir / fn
                if path.exists():
                    try:
                        loaded = pygame.image.load(str(path))
                        if pygame.display.get_surface() is not None:
                            loaded = loaded.convert_alpha()
                        self._raw_cache[fn] = loaded
                    except Exception:
                        pass
            raw_surf = self._raw_cache.get(fn)

        # Fallback surface if asset missing or headless
        if raw_surf is None:
            raw_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            raw_surf.fill((180, 60, 60))
            pygame.draw.rect(raw_surf, (240, 180, 180), (4, 4, 24, 24), 2)

        ow, oh = raw_surf.get_size()
        scale = pixel_scale if pixel_scale is not None else min(max_w / ow, max_h / oh)
        tw = max(16, int(round(ow * scale)))
        th = max(16, int(round(oh * scale)))

        scaled_surf = raw_surf if (tw, th) == (ow, oh) else pygame.transform.scale(raw_surf, (tw, th))

        # Create white hit-flash surface
        flash_surf = scaled_surf.copy()
        flash_surf.fill((255, 255, 255, 220), special_flags=pygame.BLEND_RGBA_ADD)

        pair = (scaled_surf, flash_surf)
        self._scaled_cache[cache_key] = pair
        return pair

    def draw_enemy(
        self,
        surface: pygame.Surface,
        enemy: Enemy,
        base_x: float,
        base_y: float,
        anim_state: CombatantAnimState,
        is_elite_or_boss: bool = False,
        max_w: int | None = None,
        max_h: int | None = None,
        pixel_scale: float | None = None,
        anchor_bottom_center: bool = False,
    ) -> tuple[int, int, int, int]:
        """Renders enemy with shadow, animation offsets, hit-flash, and KO fade.

        Returns (render_x, render_y, sprite_w, sprite_h) of the enemy on screen.
        """
        if max_w is None:
            max_w = 96 if is_elite_or_boss else 72
        if max_h is None:
            max_h = 90 if is_elite_or_boss else 60

        base_sprite, flash_sprite = self.get_enemy_sprite(
            sprite_id=getattr(enemy, "sprite_id", "") or enemy.id,
            name=enemy.name,
            max_w=max_w,
            max_h=max_h,
            pixel_scale=pixel_scale,
        )

        sw, sh = base_sprite.get_size()
        if anchor_bottom_center:
            rx = int(base_x - sw / 2 + anim_state.offset_x)
            ry = int(base_y - sh + anim_state.offset_y)
        else:
            rx = int(base_x + anim_state.offset_x)
            ry = int(base_y + anim_state.offset_y)

        if anim_state.ko_alpha <= 0.0:
            return (rx, ry, sw, sh)

        # Ground drop shadow (positioned under the base of the sprite)
        shadow_w = int(sw * 0.75)
        shadow_h = 10
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        shadow_alpha = int(120 * (anim_state.ko_alpha / 255.0))
        pygame.draw.ellipse(shadow_surf, (10, 10, 18, shadow_alpha), (0, 0, shadow_w, shadow_h))
        surface.blit(shadow_surf, (rx + (sw - shadow_w) // 2, ry + sh - 4))

        # Blit main sprite or hit-flash
        if anim_state.flash_timer > 0.0:
            active_sprite = flash_sprite
        else:
            active_sprite = base_sprite

        if anim_state.ko_alpha < 255.0:
            temp = active_sprite.copy()
            temp.set_alpha(int(anim_state.ko_alpha))
            surface.blit(temp, (rx, ry))
        else:
            surface.blit(active_sprite, (rx, ry))

        return (rx, ry, sw, sh)

    def _resolve_character_filename(self, char_id: str, class_id: str) -> str:
        mapping = {
            "rowan": "rowan.png",
            "vanguard": "rowan.png",
            "lyra": "lyra.png",
            "botanist": "lyra.png",
            "caelen": "caelen.png",
            "scout": "caelen.png",
            "melissa": "melissa.png",
            "weave_mage": "melissa.png",
        }
        cand = mapping.get(char_id.lower()) or mapping.get(class_id.lower())
        if cand and (self.char_sprites_dir / cand).exists():
            return cand
        # Check direct filename
        direct = f"{char_id.lower()}.png"
        if (self.char_sprites_dir / direct).exists():
            return direct
        return "rowan.png"

    def get_character_sprite(
        self,
        char_id: str,
        class_id: str = "",
        max_w: int = 56,
        max_h: int = 56,
        pixel_scale: float | None = None,
    ) -> tuple[pygame.Surface, pygame.Surface]:
        """Return (base_sprite, flash_sprite) for party member facing left."""
        cache_key = (f"char:{char_id}:{class_id}", max_w, max_h, pixel_scale)
        if cache_key in self._scaled_cache:
            return self._scaled_cache[cache_key]

        fn = self._resolve_character_filename(char_id, class_id)
        raw_surf: pygame.Surface | None = None
        if fn not in self._raw_cache:
            p = self.char_sprites_dir / fn
            if p.exists():
                try:
                    loaded = pygame.image.load(str(p))
                    if pygame.display.get_surface() is not None:
                        loaded = loaded.convert_alpha()
                    self._raw_cache[fn] = loaded
                except Exception:
                    pass
        raw_surf = self._raw_cache.get(fn)

        if raw_surf is None:
            raw_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            raw_surf.fill((70, 110, 190))

        ow, oh = raw_surf.get_size()
        scale = pixel_scale if pixel_scale is not None else min(max_w / ow, max_h / oh)
        tw = max(16, int(round(ow * scale)))
        th = max(16, int(round(oh * scale)))

        scaled_surf = raw_surf if (tw, th) == (ow, oh) else pygame.transform.scale(raw_surf, (tw, th))
        flash_surf = scaled_surf.copy()
        flash_surf.fill((255, 255, 255, 220), special_flags=pygame.BLEND_RGBA_ADD)

        pair = (scaled_surf, flash_surf)
        self._scaled_cache[cache_key] = pair
        return pair

    def get_character_action_frame(
        self, char_id: str, action_id: str, frame_index: int
    ) -> pygame.Surface | None:
        """Load a transparent per-character action frame, e.g. Rachel's Violet Ember."""
        cache_key = (char_id.lower(), action_id.lower(), max(0, int(frame_index)))
        if cache_key in self._action_frame_cache:
            return self._action_frame_cache[cache_key]

        filename = f"{action_id.lower()}_{max(0, int(frame_index)):02d}.png"
        path = self.char_sprites_dir / "characters" / char_id.lower() / "attack" / filename
        if not path.is_file():
            self._action_frame_cache[cache_key] = None
            return None
        try:
            loaded = pygame.image.load(str(path))
            if pygame.display.get_surface() is not None:
                loaded = loaded.convert_alpha()
            self._action_frame_cache[cache_key] = loaded
            return loaded
        except (pygame.error, OSError):
            self._action_frame_cache[cache_key] = None
            return None

    def get_projectile_frame(
        self, effect_id: str, frame_index: int, prefix: str = "projectile"
    ) -> pygame.Surface | None:
        """Load a transparent projectile/VFX frame from assets/sprites/effects."""
        clean_prefix = prefix.lower()
        cache_key = (effect_id.lower(), clean_prefix, max(0, int(frame_index)))
        if cache_key in self._projectile_frame_cache:
            return self._projectile_frame_cache[cache_key]

        filename = f"{clean_prefix}_{max(0, int(frame_index)):02d}.png"
        path = self.char_sprites_dir / "effects" / effect_id.lower() / filename
        if not path.is_file():
            self._projectile_frame_cache[cache_key] = None
            return None
        try:
            loaded = pygame.image.load(str(path))
            if pygame.display.get_surface() is not None:
                loaded = loaded.convert_alpha()
            self._projectile_frame_cache[cache_key] = loaded
            return loaded
        except (pygame.error, OSError):
            self._projectile_frame_cache[cache_key] = None
            return None

    def draw_party_member(
        self,
        surface: pygame.Surface,
        char: Character,
        base_x: float,
        base_y: float,
        anim_state: CombatantAnimState,
        max_w: int = 56,
        max_h: int = 56,
        pixel_scale: float | None = None,
        anchor_bottom_center: bool = False,
    ) -> tuple[int, int, int, int]:
        """Renders 16-bit party member sprite facing left with animations and shadow."""
        base_sprite, flash_sprite = self.get_character_sprite(
            char_id=char.id,
            class_id=char.class_id,
            max_w=max_w,
            max_h=max_h,
            pixel_scale=pixel_scale,
        )

        # Rachel's Violet Ember replaces the static battle pose for this action.
        if char.id.lower() == "rachel" and anim_state.anim_type == "spell":
            frame_index = anim_state.spell_frame_index
            action_key = ("rachel", "violet_ember", frame_index, pixel_scale)
            action_pair = self._action_scaled_cache.get(action_key)
            if action_pair is None:
                raw_action = self.get_character_action_frame("rachel", "violet_ember", frame_index)
                if raw_action is not None:
                    ow, oh = raw_action.get_size()
                    scale = pixel_scale if pixel_scale is not None else min(max_w / ow, max_h / oh)
                    tw = max(16, int(round(ow * scale)))
                    th = max(16, int(round(oh * scale)))
                    action_sprite = raw_action if (tw, th) == (ow, oh) else pygame.transform.scale(
                        raw_action, (tw, th)
                    )
                    action_flash = action_sprite.copy()
                    action_flash.fill((255, 255, 255, 220), special_flags=pygame.BLEND_RGBA_ADD)
                    action_pair = (action_sprite, action_flash)
                    self._action_scaled_cache[action_key] = action_pair
            if action_pair is not None:
                base_sprite, flash_sprite = action_pair

        sw, sh = base_sprite.get_size()
        if anchor_bottom_center:
            rx = int(base_x - sw / 2 + anim_state.offset_x)
            ry = int(base_y - sh + anim_state.offset_y)
        else:
            rx = int(base_x + anim_state.offset_x)
            ry = int(base_y + anim_state.offset_y)

        # Ground drop shadow
        shadow_w = int(sw * 0.7)
        shadow_h = 8
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        shadow_alpha = 120 if char.is_alive else 60
        pygame.draw.ellipse(shadow, (10, 10, 18, shadow_alpha), (0, 0, shadow_w, shadow_h))
        surface.blit(shadow, (rx + (sw - shadow_w) // 2, ry + sh - 4))

        # Blit active sprite
        if anim_state.flash_timer > 0.0:
            surface.blit(flash_sprite, (rx, ry))
        elif not char.is_alive:
            fallen_surf = base_sprite.copy()
            fallen_surf.set_alpha(110)
            surface.blit(fallen_surf, (rx, ry))
        else:
            surface.blit(base_sprite, (rx, ry))

        return (rx, ry, sw, sh)

    def get_portrait(self, speaker_id: str, size: int = 72) -> pygame.Surface | None:
        """Loads and caches character portrait facing right."""
        cache_key = (f"prt:{speaker_id}", size, size)
        if cache_key in self._portrait_cache:
            return self._portrait_cache[cache_key]

        fn = f"{speaker_id.lower()}.png"
        path = self.portraits_dir / fn
        if not path.exists():
            mapping = {
                "vanguard": "rowan.png",
                "botanist": "lyra.png",
                "scout": "caelen.png",
                "weave_mage": "melissa.png",
            }
            if speaker_id.lower() in mapping:
                path = self.portraits_dir / mapping[speaker_id.lower()]

        if path.exists():
            try:
                loaded = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    loaded = loaded.convert_alpha()
                scaled = pygame.transform.smoothscale(loaded, (size, size))
                self._portrait_cache[cache_key] = scaled
                return scaled
            except Exception:
                pass
        return None
