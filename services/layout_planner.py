from typing import Dict, List


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def estimate_bubble_width(text: str, bubble_type: str) -> float:
    normalized = " ".join((text or "").split())
    length = max(1, len(normalized))
    longest_word = max((len(word) for word in normalized.split()), default=1)

    if bubble_type == "caption":
        width = 0.22 + min(0.16, length / 230)
    elif bubble_type == "sfx":
        width = 0.18 + min(0.10, longest_word / 90)
    elif bubble_type == "shout":
        width = 0.24 + min(0.15, length / 160)
    elif bubble_type == "thought":
        width = 0.24 + min(0.15, length / 175)
    else:
        width = 0.23 + min(0.18, length / 170)

    width = max(width, 0.16 + min(0.18, longest_word / 65))
    return round(_clamp(width, 0.18, 0.56), 3)


def infer_tail(x: float, y: float, bubble_type: str) -> str:
    if bubble_type in {"caption", "sfx"}:
        return "bottom-left"

    vertical = "bottom" if y <= 0.24 else "top"
    horizontal = "right" if x >= 0.52 else "left"
    return f"{vertical}-{horizontal}"


def _default_regions() -> List[Dict]:
    return [
        {"x": 0.08, "y": 0.08, "w": 0.28, "h": 0.18, "score": 0.92},
        {"x": 0.56, "y": 0.12, "w": 0.26, "h": 0.18, "score": 0.88},
        {"x": 0.10, "y": 0.54, "w": 0.26, "h": 0.18, "score": 0.84},
        {"x": 0.56, "y": 0.62, "w": 0.24, "h": 0.16, "score": 0.8},
    ]


def _line_type(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "speech"
    if cleaned.isupper() and len(cleaned) <= 12:
        return "sfx"
    if cleaned.endswith("!") and len(cleaned) <= 28:
        return "shout"
    if cleaned.startswith("(") and cleaned.endswith(")"):
        return "thought"
    if len(cleaned) > 55:
        return "caption"
    return "speech"


def plan_bubble_layout(
    dialogue_lines: List[str],
    analysis: Dict | None = None,
) -> Dict:
    analysis = analysis or {}
    safe_regions = analysis.get("safe_regions") or _default_regions()
    avoid_regions = analysis.get("avoid_regions") or []
    suggested = analysis.get("suggested_bubbles") or []

    planned_bubbles: List[Dict] = []

    for index, text in enumerate(dialogue_lines[:4]):
        suggested_bubble = suggested[index] if index < len(suggested) else {}
        bubble_type = suggested_bubble.get("type") or _line_type(text)
        width = estimate_bubble_width(text, bubble_type)

        if index < len(safe_regions):
            region = safe_regions[index]
            x = _clamp(float(region.get("x", 0.1)), 0.04, 0.92 - width)
            y = _clamp(float(region.get("y", 0.08)), 0.04, 0.82)
        else:
            x = 0.08 if index % 2 == 0 else 0.56
            y = 0.08 + (index * 0.18)
            x = _clamp(x, 0.04, 0.92 - width)
            y = _clamp(y, 0.04, 0.82)

        planned_bubbles.append(
            {
                "text": text,
                "type": bubble_type,
                "x": round(x, 3),
                "y": round(y, 3),
                "w": width,
                "tail": suggested_bubble.get("tail") or infer_tail(x, y, bubble_type),
            }
        )

    return {
        "safe_regions": safe_regions,
        "avoid_regions": avoid_regions,
        "speaker_regions": analysis.get("speaker_regions") or {},
        "suggested_bubbles": suggested,
        "planned_bubbles": planned_bubbles,
    }
