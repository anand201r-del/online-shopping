"""
Picks a product illustration (templates/static/images/art/*.svg) from the product's
name, falling back to its category. Used when a product has no uploaded photo.
"""

import re

# order matters: more specific words first ("headphone" before "phone", "webcam" before "camera",
# "graphics card" before "card", "laptop stand" before "laptop")
RULES = [
    ("stand",       ["laptop stand", "monitor stand", "phone stand", "stand"]),
    ("case",        ["phone case", "back cover", "mobile cover", "case", "cover"]),
    ("backpack",    ["backpack", "laptop bag", "bag"]),
    ("gpu",         ["graphics card", "gpu", "rtx", "gtx", "radeon", "video card"]),
    ("ram",         ["ram", "ddr4", "ddr5", "ddr", "ram stick"]),
    ("fan",         ["cooler", "cooling", "fan", "heatsink"]),
    ("cpu",         ["processor", "cpu", "ryzen", "intel core", "core i3", "core i5", "core i7", "core i9"]),
    ("motherboard", ["motherboard", "mainboard"]),
    ("psu",         ["power supply", "psu", "smps", "ups"]),
    ("chair",       ["chair", "stool"]),
    ("desk",        ["desk", "table", "workstation"]),
    ("sofa",        ["sofa", "couch", "recliner"]),
    ("bed",         ["bed", "mattress"]),
    ("lamp",        ["lamp", "light", "bulb"]),
    ("shelf",       ["shelf", "bookshelf", "bookcase", "rack", "cabinet", "wardrobe", "cupboard", "drawer"]),
    ("microphone",  ["microphone", "mic"]),
    ("projector",   ["projector"]),
    ("monitor",     ["monitor", "display", "lcd", "led screen"]),
    ("tv",          ["tv", "television", "smart tv", "bravia"]),
    ("mouse",       ["mouse"]),
    ("keyboard",    ["keyboard"]),
    ("laptop",      ["laptop", "notebook", "macbook", "chromebook", "ultrabook"]),
    ("tablet",      ["tablet", "ipad", "tab"]),
    ("watch",       ["watch", "smartwatch", "band"]),
    ("earbuds",     ["earbud", "earbuds", "airpod", "tws", "earphone"]),
    ("headphones",  ["headphone", "headset"]),
    ("webcam",      ["webcam", "web cam"]),
    ("phone",       ["phone", "mobile", "iphone", "galaxy", "smartphone", "redmi", "oneplus", "pixel"]),
    ("printer",     ["printer", "scanner"]),
    ("camera",      ["camera", "dslr", "gopro"]),
    ("speaker",     ["speaker", "soundbar", "alexa", "echo"]),
    ("gamepad",     ["controller", "gamepad", "joystick", "playstation", "xbox", "console"]),
    ("usb",         ["pendrive", "pen drive", "usb", "flash drive", "memory card", "sd card"]),
    ("drive",       ["ssd", "hdd", "hard disk", "hard drive", "storage", "nvme"]),
    ("router",      ["router", "wifi", "wi fi", "modem"]),
    ("charger",     ["charger", "cable", "adapter", "power bank", "powerbank"]),
]

# when the name doesn't match anything, use the category
CATEGORY_FALLBACK = {
    "electronics": "chip",
    "computer": "chip",
    "computers": "chip",
    "components": "chip",
    "furniture": "shelf",
    "home": "lamp",
    "accessories": "backpack",
    "audio": "speaker",
    "gaming": "gamepad",
}


def _has(text, word):
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"s?(?![a-z0-9])", text) is not None


def art_for(name, category=None):
    """Return 'art/<file>.svg' for a product."""
    text = " " + re.sub(r"[^a-z0-9 ]", " ", (name or "").lower()) + " "
    text = re.sub(r"\s+", " ", text)
    for art, words in RULES:
        if any(_has(text, w) for w in words):
            return f"art/{art}.svg"
    fallback = CATEGORY_FALLBACK.get((category or "").strip().lower())
    return f"art/{fallback or 'box'}.svg"
