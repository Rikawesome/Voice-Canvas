import base64
import json
import os
import re
from typing import List, Dict

import httpx


def _normalize_dialogue_lines(raw_lines: List[str] | None) -> List[str]:
    cleaned = [line.strip() for line in (raw_lines or []) if line and line.strip()]
    if cleaned:
        return cleaned[:4]

    return [
        "Where is he?",
        "...behind you.",
        "Move!",
        "This ends tonight.",
    ]


def _extract_json_block(payload_text: str) -> Dict:
    cleaned = re.sub(r"```json|```", "", (payload_text or ""), flags=re.IGNORECASE).strip()
    if cleaned.startswith("{"):
        return json.loads(cleaned)

    match = re.search(r"(\{[\s\S]*\})", cleaned)
    if not match:
        raise ValueError("Gemini returned no JSON block")

    return json.loads(match.group(1))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


async def analyze_manga_layout(image_bytes: bytes, dialogue_lines: List[str] | None = None) -> Dict:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY in environment")

    model_name = os.getenv("GEMINI_LAYOUT_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    lines = _normalize_dialogue_lines(dialogue_lines)

    prompt = f"""
Analyze this manga/comic image as a lettering director.

We need a HIGH-QUALITY default bubble layout so manual editing feels optional.
Return ONLY valid JSON with this exact shape:
{{
  "page_title": "short label",
  "notes": "one short sentence",
  "safe_regions": [
    {{
      "x": 0.08,
      "y": 0.08,
      "w": 0.28,
      "h": 0.18,
      "score": 0.94
    }}
  ],
  "avoid_regions": [
    {{
      "x": 0.44,
      "y": 0.22,
      "w": 0.24,
      "h": 0.34,
      "type": "face"
    }}
  ],
  "speaker_regions": {{
    "Speaker Name": {{
      "x": 0.62,
      "y": 0.18,
      "w": 0.22,
      "h": 0.42
    }}
  }},
  "suggested_bubbles": [
    {{
      "text": "{lines[0]}",
      "type": "speech",
      "x": 0.12,
      "y": 0.10,
      "w": 0.28,
      "tail": "bottom-left"
    }}
  ]
}}

Rules:
- Use normalized 0..1 coordinates.
- Return 2 to 6 safe_regions ranked by usefulness.
- Return avoid_regions for faces, dense action, hands, weapons, or focal art when visible.
- speaker_regions can be approximate if the likely speaker side is visible.
- Return 1 bubble per provided line, max 4 bubbles.
- Prioritize empty negative space.
- Avoid covering faces, eyes, hands, weapons, and focal action.
- Preserve natural reading order from top to bottom, left to right.
- Use "caption" for narration, "speech" for normal dialogue, "thought" for internal lines, "shout" for intense lines, "sfx" only if the line is sound effect text.
- Keep widths readable, usually between 0.20 and 0.42.
- Put captions near top or edge regions.
- If the subject is on the left, prefer bubbles on the opposite side when possible.
- Keep the output practical for manga lettering, not decorative.

Dialogue lines:
{json.dumps(lines, ensure_ascii=True)}
""".strip()

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64,
                    }
                },
            ]
        }]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        if response.status_code == 429:
            raise RuntimeError("Gemini layout quota reached. Try again in a bit.")
        if response.status_code != 200:
            raise RuntimeError(f"Gemini layout error: {response.status_code} {response.text}")

    result = response.json()
    try:
        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError("Gemini returned an empty layout response") from exc

    parsed = _extract_json_block(raw_text)
    bubbles = []

    for bubble in parsed.get("suggested_bubbles", [])[:4]:
        text = str(bubble.get("text", "")).strip()
        if not text:
            continue

        bubble_type = str(bubble.get("type", "speech")).strip().lower()
        if bubble_type not in {"speech", "thought", "shout", "caption", "sfx"}:
            bubble_type = "speech"

        tail = str(bubble.get("tail", "bottom-left")).strip().lower()
        if tail not in {"bottom-left", "bottom-right", "top-left", "top-right"}:
            tail = "bottom-left"

        bubbles.append({
            "text": text,
            "type": bubble_type,
            "x": round(_clamp(float(bubble.get("x", 0.12)), 0.04, 0.82), 3),
            "y": round(_clamp(float(bubble.get("y", 0.06)), 0.04, 0.82), 3),
            "w": round(_clamp(float(bubble.get("w", 0.28)), 0.18, 0.56), 3),
            "tail": tail,
        })

    if not bubbles:
        raise RuntimeError("Gemini returned no usable bubbles")

    safe_regions = []
    for region in parsed.get("safe_regions", [])[:6]:
        try:
            safe_regions.append(
                {
                    "x": round(_clamp(float(region.get("x", 0.08)), 0.02, 0.9), 3),
                    "y": round(_clamp(float(region.get("y", 0.08)), 0.02, 0.9), 3),
                    "w": round(_clamp(float(region.get("w", 0.24)), 0.12, 0.6), 3),
                    "h": round(_clamp(float(region.get("h", 0.18)), 0.1, 0.5), 3),
                    "score": round(_clamp(float(region.get("score", 0.75)), 0.0, 1.0), 3),
                }
            )
        except Exception:
            continue

    avoid_regions = []
    for region in parsed.get("avoid_regions", [])[:8]:
        try:
            avoid_regions.append(
                {
                    "x": round(_clamp(float(region.get("x", 0.3)), 0.0, 1.0), 3),
                    "y": round(_clamp(float(region.get("y", 0.2)), 0.0, 1.0), 3),
                    "w": round(_clamp(float(region.get("w", 0.2)), 0.05, 0.7), 3),
                    "h": round(_clamp(float(region.get("h", 0.2)), 0.05, 0.7), 3),
                    "type": str(region.get("type", "avoid")).strip() or "avoid",
                }
            )
        except Exception:
            continue

    speaker_regions = {}
    for name, region in (parsed.get("speaker_regions", {}) or {}).items():
        try:
            speaker_regions[str(name)] = {
                "x": round(_clamp(float(region.get("x", 0.3)), 0.0, 1.0), 3),
                "y": round(_clamp(float(region.get("y", 0.2)), 0.0, 1.0), 3),
                "w": round(_clamp(float(region.get("w", 0.2)), 0.05, 0.7), 3),
                "h": round(_clamp(float(region.get("h", 0.3)), 0.05, 0.8), 3),
            }
        except Exception:
            continue

    return {
        "page_title": str(parsed.get("page_title", "Gemini layout preview")).strip() or "Gemini layout preview",
        "notes": str(parsed.get("notes", "Gemini suggested a bubble layout.")).strip() or "Gemini suggested a bubble layout.",
        "safe_regions": safe_regions,
        "avoid_regions": avoid_regions,
        "speaker_regions": speaker_regions,
        "suggested_bubbles": bubbles,
    }
