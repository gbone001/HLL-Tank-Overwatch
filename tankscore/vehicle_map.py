from __future__ import annotations

# Very lightweight name -> class classifier
# Returns one of: 'LIGHT','MEDIUM','HEAVY','TD' or None if unknown/non-tank

def classify_by_name(name: str) -> str | None:
    if not name:
        return None
    n = name.strip().lower()

    # common HLL vehicle name hints
    heavy_tokens = [
        "tiger", "king tiger", "t-34-85", "is-2", "is2", "pershing",
        "panther", "jumbo 76", "sherman 76"
    ]
    medium_tokens = [
        "sherman", "jumbo", "pz iv", "pzkpfw iv", "t-34", "t34", "comet",
        "cromwell"
    ]
    light_tokens = [
        "stewart", "stuart", "luchs", "m8", "greyhound", "grey hound", "t70",
    ]
    td_tokens = [
        "stuG", "stug", "su-76", "m10", "achilles", "jpz", "jagdpanzer",
    ]

    def has_any(tokens):
        return any(tok in n for tok in tokens)

    if has_any(heavy_tokens):
        return "HEAVY"
    if has_any(medium_tokens):
        return "MEDIUM"
    if has_any(light_tokens):
        return "LIGHT"
    if has_any(td_tokens):
        return "TD"
    return None

