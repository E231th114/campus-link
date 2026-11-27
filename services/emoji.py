"""Unicode Emoji catalog and deployment-managed moderation policy."""
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECOMMENDED = {
    "heart": ("❤️", "共感した"), "cheer": ("🙌", "応援"),
    "idea": ("💡", "なるほど"), "thanks": ("😊", "ありがとう"),
    "watch": ("👀", "気になる"), "party": ("🎉", "おめでとう"),
    "think": ("🤔", "考え中"), "clap": ("👏", "すごい"),
}
def sequence(text):
    return unicodedata.normalize("NFC", text).replace("\ufe0f", "").replace("\ufe0e", "")


def policy_sequence(text):
    return "".join(ch for ch in sequence(text) if not 0x1F3FB <= ord(ch) <= 0x1F3FF)


def load_catalog():
    catalog, aliases = {}, {}
    old_ids = {sequence(pair[0]): code for code, pair in RECOMMENDED.items()}
    for line in (ROOT / "data/unicode/emoji-test.txt").read_text().splitlines():
        if line.startswith("# group: "):
            group = line[9:]
        if "; fully-qualified" not in line:
            continue
        points, description = line.split(";", 1)
        glyph = "".join(chr(int(cp, 16)) for cp in points.split())
        name = description.split("# ", 1)[1].split(" ", 2)[2]
        normalized = sequence(glyph)
        code = old_ids.get(normalized) or "u-" + "-".join(f"{ord(ch):x}" for ch in normalized)
        catalog[code] = (glyph, RECOMMENDED.get(code, (glyph, name))[1], group)
        aliases[normalized] = code
    return catalog, aliases


CATALOG, ALIASES = load_catalog()
POLICY = json.loads((ROOT / "config/emoji_moderation.json").read_text())
BLOCKED = tuple(policy_sequence("".join(chr(int(cp, 16)) for cp in rule["codepoints"]))
                for rule in POLICY["rules"] if rule["enabled"])


def allowed_code(value, post):
    if not isinstance(value, str) or len(value) > 160:
        return None
    code = value if value in CATALOG else ALIASES.get(sequence(value))
    if code is None or code in POLICY["hidden_by_post"].get(post, []):
        return None
    if any(pattern in policy_sequence(CATALOG[code][0]) for pattern in BLOCKED):
        return None
    return code
