"""Unit tests for Party management, active/reserve slots, and character mechanics."""

from src.data.characters import create_character
from src.entities.party import MAX_ACTIVE_PARTY_SIZE, Party


def test_party_max_active_limit_and_reserve():
    party = Party()
    chars = [
        create_character("rowan"),
        create_character("lyra"),
        create_character("caelen"),
        create_character("melissa"),
        create_character("goran"),
    ]

    for char in chars:
        party.add_character(char)

    assert len(party.active_members) == MAX_ACTIVE_PARTY_SIZE
    assert len(party.reserve_members) == 1
    assert party.active_members[0].id == "rowan"
    assert party.reserve_members[0].id == "goran"


def test_party_swap_active_with_reserve():
    party = Party()
    rowan = create_character("rowan")
    lyra = create_character("lyra")
    caelen = create_character("caelen")
    melissa = create_character("melissa")
    goran = create_character("goran")

    for c in [rowan, lyra, caelen, melissa, goran]:
        party.add_character(c)

    # Slot 0 (Rowan) is permanently locked; slots 1..3 can swap with reserve
    assert party.swap_active_with_reserve(0, 0) is False
    assert party.active_members[0].id == "rowan"

    assert party.swap_active_with_reserve(1, 0) is True
    assert party.active_members[1].id == "goran"
    assert party.reserve_members[0].id == "lyra"


def test_party_defeat_condition():
    party = Party()
    rowan = create_character("rowan")
    lyra = create_character("lyra")
    party.add_character(rowan)
    party.add_character(lyra)

    assert party.is_party_defeated is False

    rowan.take_damage(999)
    assert rowan.is_alive is False
    assert party.is_party_defeated is False  # Lyra is still alive

    lyra.take_damage(999)
    assert lyra.is_alive is False
    assert party.is_party_defeated is True


def test_party_inventory():
    party = Party()
    party.add_item("healing_poultice", 3)
    assert party.has_item("healing_poultice", 3) is True
    assert party.has_item("healing_poultice", 4) is False

    assert party.remove_item("healing_poultice", 2) is True
    assert party.inventory["healing_poultice"] == 1

    assert party.remove_item("healing_poultice", 1) is True
    assert "healing_poultice" not in party.inventory


def test_party_reorder_bench_and_deploy():
    party = Party()
    rowan = create_character("rowan")
    lyra = create_character("lyra")
    caelen = create_character("caelen")
    for c in [rowan, lyra, caelen]:
        party.add_character(c)

    # Slot 0 is locked from reordering
    assert party.reorder_active(0, 1) is False
    # Slots 1 and 2 can reorder
    assert party.reorder_active(1, 2) is True
    assert [m.id for m in party.active_members] == ["rowan", "caelen", "lyra"]

    # Benching preserves HP/MP and equipment, and refuses slot 0
    caelen.take_damage(15)
    assert party.bench_active(0) is False
    assert party.bench_active(1) is True
    assert [m.id for m in party.active_members] == ["rowan", "lyra"]
    assert party.reserve_members[0].id == "caelen"
    assert party.reserve_members[0].current_hp == caelen.current_hp
    assert party.reserve_members[0].equipment.weapon == "twin_stiletto"

    # Bench down to 1 active (Rowan), then cannot bench last member
    assert party.bench_active(1) is True
    assert len(party.active_members) == 1
    assert party.bench_active(0) is False

    # Deploy reserve back to active
    assert party.deploy_reserve(0) is True
    assert [m.id for m in party.active_members] == ["rowan", "caelen"]


def test_jack_hunter_parity_and_starting_reserve():
    from src.core.session import GameSession
    from src.data.skill_trees import CHARACTER_TREES

    jack = create_character("jack", level=1)
    assert jack.name == "Jack"
    assert jack.class_id == "hunter"
    assert len(jack.learned_abilities) == 3
    assert jack.learned_abilities == ["aimed_shot", "piercing_arrow", "hunters_mark"]
    assert jack.equipment.weapon == "hunter_longbow"
    assert len(CHARACTER_TREES["jack"]) == 6

    session = GameSession(seed=42)
    session.initialize_new_game()
    assert len(session.party.active_members) == 4
    assert any(m.id == "jack" for m in session.party.reserve_members)


def test_party_view_keyboard_actions():
    import os

    import pygame

    from src.core.fsm import GameMode
    from src.core.session import GameSession
    from src.frontends.pygame_ce.ui_manager import GameUIManager
    from src.frontends.pygame_ce.views.party_view import PartyView

    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1280, 720))

    session = GameSession(seed=42)
    session.initialize_new_game()
    session.transition_to(GameMode.EXPLORATION)
    assert session.transition_to(GameMode.PARTY) is True

    ui_mgr = GameUIManager((1280, 720))
    view = PartyView(session=session, ui_manager=ui_mgr)
    view.on_enter()
    view.update(0.016)
    ui_mgr.update(0.016)

    # Selecting slot 0 (Rowan) does not open sub-menu
    view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert view.sub_menu_open is False

    # Move down to slot 1 (Lyra), open sub-menu, choose Bench to Reserve
    view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert view.sub_menu_open is True
    bench_idx = next(i for i, (aid, _) in enumerate(view.sub_menu_options) if aid == "bench")
    view.sub_menu_index = bench_idx
    view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert len(session.party.active_members) == 3
    assert any(m.id == "lyra" for m in session.party.reserve_members)

    # Esc exits back to exploration
    view.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert session.current_mode == GameMode.EXPLORATION
    view.on_exit()
