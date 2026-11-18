from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.core.fsm import GameMode
from src.core.session import GameSession
from src.data.classes import CLASS_REGISTRY
from src.data.enemies import create_enemy
from src.frontends.pygame_ce.views.combat_view import CombatView
from src.frontends.pygame_ce.views.dialogue_view import DialogueView
from src.frontends.pygame_ce.views.exploration_view import ExplorationView
from src.systems.combat.round_combat import CombatPhase, RoundCombat


def test_unlock_melissa_and_lyra_with_find_lyra_quest():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))

    session = GameSession(seed=42)
    session.initialize_new_game()
    assert [m.id for m in session.party.active_members] == ["rowan", "rachel"]
    assert session.party.reserve_members == []

    # Level Rowan up to 3 before unlocking companions
    rowan = session.party.active_members[0]
    rowan.gain_exp(rowan.exp_to_next_level)
    rowan.gain_exp(rowan.exp_to_next_level)
    assert rowan.level == 3

    dv = DialogueView(session)

    # Elder Tomas option 2 triggers find_lyra subquest
    dv.start_dialogue("elder_tomas")
    dv._advance_to_node("elder_lyra")
    dv._advance_node()
    assert session.quest_manager.is_quest_active("find_lyra")

    # Monolith option 2 unlocks Melissa at Rowan's level before combat
    dv.start_dialogue("special_encounter")
    dv._advance_to_node("special_melissa_1")
    dv._advance_node()
    melissa = next((m for m in session.party.active_members if m.id == "melissa"), None)
    assert melissa is not None
    assert melissa.level == 3
    mage_growth = CLASS_REGISTRY["weave_mage"].growth_per_level
    assert melissa.base_stats.magic_attack == (
        CLASS_REGISTRY["weave_mage"].base_stats.magic_attack + mage_growth.magic_attack * 2
    )

    # Winning against Mandragora Matron triggers lyra_rescue_dialogue on returning to map
    session.transition_to(GameMode.EXPLORATION)
    matron = create_enemy("mandragora_matron", "mandragora_matron")
    matron.current_hp = 0
    combat = RoundCombat(party=session.party, enemies=[matron], event_bus=session.event_bus, seed=1)
    combat.phase = CombatPhase.VICTORY
    session.combat = combat
    session.transition_to(GameMode.COMBAT)

    cv = CombatView(session)
    cv.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert session.pending_dialogue_id == "lyra_rescue_dialogue"
    assert session.current_mode == GameMode.EXPLORATION

    ev = ExplorationView(session)
    ev.on_enter()
    assert session.current_mode == GameMode.DIALOGUE

    # Completing lyra_rescue_dialogue unlocks Lyra at Rowan's level & completes find_lyra with rewards
    gold_before = session.party.gold
    dv.start_dialogue("lyra_rescue_dialogue")
    dv._advance_to_node("lyra_res_4")
    dv._advance_node()
    lyra = next((m for m in session.party.active_members if m.id == "lyra"), None)
    assert lyra is not None
    assert lyra.level == 3
    assert session.quest_manager.is_quest_completed("find_lyra")
    assert session.party.gold == gold_before + 75


def test_unlock_lyra_without_find_lyra_quest_gives_no_quest_reward():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))

    session = GameSession(seed=42)
    session.initialize_new_game()
    assert not session.quest_manager.is_quest_active("find_lyra")

    session.transition_to(GameMode.EXPLORATION)
    matron = create_enemy("mandragora_matron", "mandragora_matron")
    matron.current_hp = 0
    combat = RoundCombat(party=session.party, enemies=[matron], event_bus=session.event_bus, seed=1)
    combat.phase = CombatPhase.VICTORY
    session.combat = combat
    session.transition_to(GameMode.COMBAT)

    cv = CombatView(session)
    cv.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert session.pending_dialogue_id == "lyra_rescue_dialogue"

    gold_before = session.party.gold
    dv = DialogueView(session)
    dv.start_dialogue("lyra_rescue_dialogue")
    dv._advance_to_node("lyra_res_4")
    dv._advance_node()

    assert session.has_character("lyra") is True
    assert session.party.gold == gold_before
    assert not session.quest_manager.is_quest_completed("find_lyra")
