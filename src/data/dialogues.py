"""Narrative dialogues and conversation trees for the Prologue."""

from __future__ import annotations

from typing import Final

from src.systems.dialogue.dialogue_models import DialogueChoice, DialogueNode, DialogueTree

PROLOGUE_INTRO_NODES: Final[dict[str, DialogueNode]] = {
    "intro_1": DialogueNode(
        id="intro_1",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="Oakhaven at last... After three seasons on the road, this quiet frontier feels like another world.",
        next_node_id="intro_2",
    ),
    "intro_2": DialogueNode(
        id="intro_2",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="I hope to see Elder Tomas in the village square—he'll know what has been stirring in these woods.",
        next_node_id=None,
    ),
}

ELDER_TOMAS_NODES: Final[dict[str, DialogueNode]] = {
    "elder_1": DialogueNode(
        id="elder_1",
        speaker_name="Elder Tomas",
        speaker_id="elder",
        text="Captain Rowan! Bless the stars you are here. The frontier has turned foul overnight.",
        next_node_id="elder_choices",
    ),
    "elder_choices": DialogueNode(
        id="elder_choices",
        speaker_name="Elder Tomas",
        speaker_id="elder",
        text="The southern Briarwood Verge is weeping black ichor. What can we do?",
        choices=[
            DialogueChoice(text="Tell me about the forest corruption.", target_node_id="elder_forest"),
            DialogueChoice(text="Where is young Lyra?", target_node_id="elder_lyra"),
            DialogueChoice(text="I will investigate the woods myself.", target_node_id="elder_ready"),
        ],
    ),
    "elder_forest": DialogueNode(
        id="elder_forest",
        speaker_name="Elder Tomas",
        speaker_id="elder",
        text="Roots thicker than temple pillars are twisting upward from deep beneath the earth. The beasts have gone mad with red eyes.",
        next_node_id="elder_choices",
    ),
    "elder_lyra": DialogueNode(
        id="elder_lyra",
        speaker_name="Elder Tomas",
        speaker_id="elder",
        text="She took her herb satchel south at sunrise to gather purging bark. She hasn't returned. Please, Rowan... bring her back safely.",
        next_node_id="elder_choices",
    ),
    "elder_ready": DialogueNode(
        id="elder_ready",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="Bar your gates, Elder. I'm heading south into Briarwood now.",
        next_node_id="elder_end",
    ),
    "elder_end": DialogueNode(
        id="elder_end",
        speaker_name="Elder Tomas",
        speaker_id="elder",
        text="May the ancient Sunwardens guide your blade, Captain.",
        next_node_id=None,
        action_trigger="FLAG_MET_ELDER",
    ),
}

TREANT_BOSS_NODES: Final[dict[str, DialogueNode]] = {
    "boss_1": DialogueNode(
        id="boss_1",
        speaker_name="Corrupted Treant",
        speaker_id="treant",
        text="GROOOAAARGH... FLESH OF THE CROWN... YOU SHALL FEED THE PRIMEVAL ROOTS...",
        next_node_id="boss_2",
    ),
    "boss_2": DialogueNode(
        id="boss_2",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="This creature is soaked in the same abyssal blight from the capital crypts! Stand your ground!",
        next_node_id=None,
        action_trigger="START_BOSS_COMBAT",
    ),
}

PROLOGUE_VICTORY_NODES: Final[dict[str, DialogueNode]] = {
    "vic_1": DialogueNode(
        id="vic_1",
        speaker_name="Lyra",
        speaker_id="lyra",
        text="Rowan! Look at the core of that beast... it wasn't just corrupted by nature. There is a royal warden seal embedded in the bark!",
        next_node_id="vic_2",
    ),
    "vic_2": DialogueNode(
        id="vic_2",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="The High Prelate's crest. The Council didn't just exile me to hide the blight... they are orchestrating it.",
        next_node_id="vic_3",
    ),
    "vic_3": DialogueNode(
        id="vic_3",
        speaker_name="Lyra",
        speaker_id="lyra",
        text="Then our only choice is to march to the High Capital. We must purge this rot before it swallows the whole realm.",
        next_node_id="vic_4",
    ),
    "vic_4": DialogueNode(
        id="vic_4",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="Pack your balms, Lyra. The Sunwardens march once more. For Aethelgard!",
        next_node_id=None,
        action_trigger="COMPLETE_PROLOGUE",
    ),
}

ROWAN_HOUSE_INSPECT_NODES: Final[dict[str, DialogueNode]] = {
    "house_1": DialogueNode(
        id="house_1",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="My frontier cottage is a quiet place to regroup. Would you like to organize the party before heading out?",
        choices=[
            DialogueChoice(text="Manage Party Composition", target_node_id="house_party"),
            DialogueChoice(text="Leave", target_node_id="house_leave"),
        ],
    ),
    "house_party": DialogueNode(
        id="house_party",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="Let's review who marches in the vanguard and who holds the reserve.",
        action_trigger="OPEN_PARTY_COMPOSITION",
        next_node_id=None,
    ),
    "house_leave": DialogueNode(
        id="house_leave",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="No time to linger while the blighted roots spread south.",
        next_node_id=None,
    ),
}

INNKEEPER_PARTY_NODES: Final[dict[str, DialogueNode]] = {
    "inn_1": DialogueNode(
        id="inn_1",
        speaker_name="Innkeeper",
        speaker_id="elder_tomas",
        text="Welcome traveler! Your companions are resting upstairs. Would you like to rearrange your party?",
        choices=[
            DialogueChoice(text="Manage Party Composition", target_node_id="inn_party"),
            DialogueChoice(text="Not right now", target_node_id="inn_leave"),
        ],
    ),
    "inn_party": DialogueNode(
        id="inn_party",
        speaker_name="Innkeeper",
        speaker_id="elder_tomas",
        text="I'll call everyone down to the common room.",
        action_trigger="OPEN_PARTY_COMPOSITION",
        next_node_id=None,
    ),
    "inn_leave": DialogueNode(
        id="inn_leave",
        speaker_name="Innkeeper",
        speaker_id="elder_tomas",
        text="Safe travels out there.",
        next_node_id=None,
    ),
}

SPECIAL_ENCOUNTER_NODES: Final[dict[str, DialogueNode]] = {
    "special_1": DialogueNode(
        id="special_1",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="I feel something is odd about this pillar...",
        next_node_id="special_2",
    ),
    "special_2": DialogueNode(
        id="special_2",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="What should I do?",
        choices=[
            DialogueChoice(text="Ignore it, we need to hurry deep into the woods.", target_node_id="special_3"),
            DialogueChoice(text="I think I can reach that glowing spiral...", target_node_id="special_4"),
        ],
    ),
    "special_3": DialogueNode(
        id="special_3",
        speaker_name="Rowan",
        speaker_id="rowan",
        text="We will have a look later, we need to hurry and investigate Briarwood.",
        next_node_id=None,
    ),
    "special_4": DialogueNode(
        id="special_4",
        speaker_name="Mandragora Matron",
        speaker_id="mandragora_matron",
        text="RAWWRRRRRRRRR!!!",
        next_node_id="special_5",
    ),
    "special_5": DialogueNode(
        id="special_5",
        speaker_name="Melissa",
        speaker_id="melissa",
        text="Well, it seems we will have to fight that first...",
        next_node_id=None,
        action_trigger="START_SPECIAL_COMBAT",
    ),
}

DIALOGUE_REGISTRY: Final[dict[str, DialogueTree]] = {
    "prologue_intro": DialogueTree(
        id="prologue_intro",
        nodes=PROLOGUE_INTRO_NODES,
        start_node_id="intro_1",
    ),
    "elder_tomas": DialogueTree(
        id="elder_tomas",
        nodes=ELDER_TOMAS_NODES,
        start_node_id="elder_1",
    ),
    "rowan_house_inspect": DialogueTree(
        id="rowan_house_inspect",
        nodes=ROWAN_HOUSE_INSPECT_NODES,
        start_node_id="house_1",
    ),
    "innkeeper_party": DialogueTree(
        id="innkeeper_party",
        nodes=INNKEEPER_PARTY_NODES,
        start_node_id="inn_1",
    ),
    "treant_boss": DialogueTree(
        id="treant_boss",
        nodes=TREANT_BOSS_NODES,
        start_node_id="boss_1",
    ),
    "prologue_victory": DialogueTree(
        id="prologue_victory",
        nodes=PROLOGUE_VICTORY_NODES,
        start_node_id="vic_1",
    ),
    "special_encounter": DialogueTree(
        id="special_encounter",
        nodes=SPECIAL_ENCOUNTER_NODES,
        start_node_id="special_1",
    ),
    "elder_tomas_complete": DialogueTree(
        id="elder_tomas_complete",
        nodes={
            "tomas_done_1": DialogueNode(
                id="tomas_done_1",
                speaker_name="Elder Tomas",
                speaker_id="elder",
                text="Rowan! You returned from Briarwood Verge! The dark trembling in the earth has stopped.",
                next_node_id="tomas_done_2",
            ),
            "tomas_done_2": DialogueNode(
                id="tomas_done_2",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="A Corrupted Treant was choking the roots deep in the grove. It won't trouble Oakhaven again.",
                next_node_id="tomas_done_3",
            ),
            "tomas_done_3": DialogueNode(
                id="tomas_done_3",
                speaker_name="Elder Tomas",
                speaker_id="elder",
                text="Oakhaven owes you and your companions a great debt. Take these supplies with our gratitude.",
                next_node_id=None,
            ),
        },
        start_node_id="tomas_done_1",
    ),
    "monolith_discovery": DialogueTree(
        id="monolith_discovery",
        nodes={
            "mono_disc_1": DialogueNode(
                id="mono_disc_1",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="Hold on... do you feel that? A foul energy is pulsing from that ancient monolith ahead.",
                next_node_id="mono_disc_2",
            ),
            "mono_disc_2": DialogueNode(
                id="mono_disc_2",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="We shouldn't leave it unchecked. Let's inspect the monolith closely.",
                next_node_id=None,
            ),
        },
        start_node_id="mono_disc_1",
    ),
    "enter_shop_oakhaven": DialogueTree(
        id="enter_shop_oakhaven",
        nodes={
            "shop_door_1": DialogueNode(
                id="shop_door_1",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="Oakhaven General Goods. The lantern inside is lit. Would you like to step in?",
                choices=[
                    DialogueChoice(text="Enter the shop", target_node_id="shop_enter"),
                    DialogueChoice(text="Stay outside", target_node_id=None),
                ],
            ),
            "shop_enter": DialogueNode(
                id="shop_enter",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="You push open the wooden door and step inside.",
                next_node_id=None,
                action_trigger="ENTER_MAP:shop_interior_oakhaven:320:300",
            ),
        },
        start_node_id="shop_door_1",
    ),
    "oakhaven_shop_open": DialogueTree(
        id="oakhaven_shop_open",
        nodes={
            "shop_greet_1": DialogueNode(
                id="shop_greet_1",
                speaker_name="Shopkeeper",
                speaker_id="elder",
                text="Welcome to Oakhaven General Goods! Feel free to browse the shelves — we'll have fresh stock ready for trade soon.",
                next_node_id=None,
            ),
        },
        start_node_id="shop_greet_1",
    ),
    "enter_armory_oakhaven": DialogueTree(
        id="enter_armory_oakhaven",
        nodes={
            "armory_door_1": DialogueNode(
                id="armory_door_1",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="Oakhaven Armory. The heat of the forge radiates from within. Step inside?",
                choices=[
                    DialogueChoice(text="Enter the armory", target_node_id="armory_enter"),
                    DialogueChoice(text="Stay outside", target_node_id=None),
                ],
            ),
            "armory_enter": DialogueNode(
                id="armory_enter",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="You pull open the heavy oak door and step into the armory.",
                next_node_id=None,
                action_trigger="ENTER_MAP:armory_interior_oakhaven:320:300",
            ),
        },
        start_node_id="armory_door_1",
    ),
    "oakhaven_armory_open": DialogueTree(
        id="oakhaven_armory_open",
        nodes={
            "armory_greet_1": DialogueNode(
                id="armory_greet_1",
                speaker_name="Armorer",
                speaker_id="elder",
                text="Fine steel and sturdy mail! Give me a bit more time at the anvil and I'll have fresh gear ready for your party.",
                next_node_id=None,
            ),
        },
        start_node_id="armory_greet_1",
    ),
    "alchemist_shop": DialogueTree(
        id="alchemist_shop",
        nodes={
            "alchemist_1": DialogueNode(
                id="alchemist_1",
                speaker_name="Alchemist",
                speaker_id="elder",
                text="Careful with those phials, traveler! Once Briarwood's sap settles, I'll have fresh tinctures ready for sale.",
                next_node_id=None,
            ),
        },
        start_node_id="alchemist_1",
    ),
    "enter_inn_oakhaven": DialogueTree(
        id="enter_inn_oakhaven",
        nodes={
            "inn_door_1": DialogueNode(
                id="inn_door_1",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="Oakhaven Tavern & Inn. Warm lantern light and hearthfire glow inside. Step in?",
                choices=[
                    DialogueChoice(text="Enter the inn", target_node_id="inn_enter"),
                    DialogueChoice(text="Stay outside", target_node_id=None),
                ],
            ),
            "inn_enter": DialogueNode(
                id="inn_enter",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="You step inside the cozy tavern.",
                next_node_id=None,
                action_trigger="ENTER_MAP:inn_interior_oakhaven:320:300",
            ),
        },
        start_node_id="inn_door_1",
    ),
    "oakhaven_inn_open": DialogueTree(
        id="oakhaven_inn_open",
        nodes={
            "inn_greet_1": DialogueNode(
                id="inn_greet_1",
                speaker_name="Innkeeper",
                speaker_id="elder",
                text="Pull up a stool by the hearth! Once the Briarwood trouble settles, we'll have hot meals and beds ready for travelers.",
                next_node_id=None,
            ),
        },
        start_node_id="inn_greet_1",
    ),
    "enter_townhall_oakhaven": DialogueTree(
        id="enter_townhall_oakhaven",
        nodes={
            "townhall_door_1": DialogueNode(
                id="townhall_door_1",
                speaker_name="Rowan",
                speaker_id="rowan",
                text="Oakhaven Town Hall. The council chamber doors are shut while Elder Tomas oversees the village perimeter.",
                next_node_id=None,
            ),
        },
        start_node_id="townhall_door_1",
    ),
}


def get_dialogue_tree(tree_id: str) -> DialogueTree:
    if tree_id not in DIALOGUE_REGISTRY:
        raise ValueError(f"Unknown dialogue tree: '{tree_id}'")
    return DIALOGUE_REGISTRY[tree_id]
