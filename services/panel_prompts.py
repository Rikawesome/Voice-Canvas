from typing import Dict


def _build_identity_lock(speaker: str, full_cast: Dict, session) -> str:
    parts = []
    entry = full_cast.get(speaker, {}) if speaker else {}

    dna = str(entry.get("dna", "") or "").strip()
    traits = [str(item).strip() for item in entry.get("traits", []) if str(item).strip()]
    description = str(entry.get("description", "") or "").strip()
    vibe = str(entry.get("vibe", "") or "").strip()

    if speaker:
        parts.append(f"Same exact character across all panels: {speaker}")

    if dna:
        parts.append(f"Locked visual DNA: {dna}")

    if traits:
        parts.append(f"Traits to preserve: {', '.join(traits[:8])}")

    if description:
        parts.append(f"Character description: {description}")

    if vibe and vibe.lower() != "unknown":
        parts.append(f"Character vibe: {vibe}")

    if not parts:
        lead_dna = str(getattr(session, "visual_dna", "") or "").strip()
        if lead_dna:
            parts.append("Same exact lead character across all panels")
            parts.append(f"Locked visual DNA: {lead_dna}")

    return ". ".join(parts).strip()


def build_panel_prompt(panel: Dict, session) -> str:
    speaker = str(panel.get("speaker", "")).strip()
    visual_description = str(panel.get("visual_description", "")).strip()
    dialogue = str(panel.get("text", "")).strip()
    location = str(getattr(session, "location_context", "") or "").strip()

    full_cast = {
        **(getattr(session, "characters", {}) or {}),
        **(getattr(session, "temp_characters", {}) or {}),
    }

    dna = ""
    if speaker and speaker in full_cast:
        dna = str(full_cast[speaker].get("dna", "")).strip()

    if not dna:
        dna = str(getattr(session, "visual_dna", "") or "").strip()

    identity_lock = _build_identity_lock(speaker, full_cast, session)

    prompt_parts = [
        "Single manga panel only",
        "black-and-white ink",
        "clean lineart",
        "high contrast screentone",
        "cinematic composition",
        "one frame only",
        "one moment only",
        "close control of anatomy and face structure",
    ]

    if identity_lock:
        prompt_parts.append(identity_lock)

    if visual_description:
        prompt_parts.append(f"Scene action: {visual_description}")

    if speaker and dna and dna.lower() not in visual_description.lower():
        prompt_parts.append(f"Repeat visual DNA exactly for {speaker}: {dna}")
    elif dna and dna.lower() not in visual_description.lower():
        prompt_parts.append(f"Repeat lead visual DNA exactly: {dna}")

    if location and location.lower() not in visual_description.lower():
        prompt_parts.append(f"Locked location: {location}")

    if dialogue:
        prompt_parts.append(f"Emotional beat: {dialogue}")

    prompt_parts.append(
        "Critical consistency rule: do not gender-swap, do not redesign the face, do not change hair silhouette, do not add extra limbs, do not distort anatomy."
    )
    prompt_parts.append(
        "Keep the same face shape, eye structure, hairline, body build, and signature features in every panel."
    )
    prompt_parts.append(
        "Do not generate a full manga page, do not generate multiple panels, do not create a comic strip, do not split the image into boxes."
    )
    prompt_parts.append(
        "Output exactly one standalone storyboard panel with a single composition."
    )

    return ", ".join(part for part in prompt_parts if part)
