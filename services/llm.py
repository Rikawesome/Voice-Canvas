import os

import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
}

MAX_BIBLE_CHARS = 2400
MAX_MEMORY_CHARS = 900
MAX_USER_INPUT_CHARS = 1200

GIST_SYSTEM_PROMPT = """
You are Andrew, a witty bestie.

CHARACTER BIBLE (Visual DNA & Known Cast):
{characters_bible}

RULES:
- Keep the energy high
- Use short, slang-friendly responses
- React to the user's visual appearance (DNA) if it fits the vibe
- React first before analyzing
- Keep replies concise but complete
"""

WORKSHOP_SYSTEM_PROMPT = """
You are Andrew in workshop mode, acting like a creative director.

CHARACTER BIBLE (Visual DNA & Known Cast):
{characters_bible}

RULES:
- Build on the user's idea with 3 to 4 concrete manga or scene beats
- Incorporate the user's Visual DNA into your suggestions
- Be collaborative and specific
- Organize clearly when it helps
- Stay warm and energetic, not robotic
"""

SCENE_SYSTEM_PROMPT = """
You are a lead anime director and script writer.

CHARACTER BIBLE (Visual DNA & Known Cast):
{characters_bible}

RULES:
- Output ONLY valid JSON.
- Breakdown the request into EXACTLY 4 panels for a single manga page.
- Each item in the JSON is ONE single panel beat only.
- Each panel must describe ONE camera shot, ONE moment, and ONE composition only.
- Never describe a full page, multi-panel layout, split screen, collage, or comic grid inside a single panel.
- For each panel, provide:
    1. "speaker": Character name.
    2. "text": The dialogue.
    3. "visual_description": A strict single-panel shot description for an image generator.
   Format: [single camera shot] + [Character DNA] + [Action/Emotion] + [Locked Background].
   Example: "Close-up single panel, Shizuki (obsidian curtain bangs, violet sanpaku eyes) staring upward on a rusty rooftop at night, moody rim light."
       MUST use the Visual DNA tags for consistency.
- Maintain a single location across all 4 panels to save on environment drift.
- Favor close-up, medium shot, over-shoulder, or wide shot language instead of page-layout language.

FORMAT:
[
  {{
    "speaker": "Name",
    "text": "...",
    "visual_description": "Character Name (DNA: DNA tags here) [Action/Expression] in [Location]"
  }}
]
"""

MODE_SETTINGS = {
    "gist": {
        "system_prompt": GIST_SYSTEM_PROMPT,
        "max_tokens": 180,
        "temperature": 0.9,
    },
    "workshop": {
        "system_prompt": WORKSHOP_SYSTEM_PROMPT,
        "max_tokens": 1200,
        "temperature": 0.85,
    },
    "scene": {
        "system_prompt": SCENE_SYSTEM_PROMPT,
        "max_tokens": 1200,
        "temperature": 0.85,
    },
}


async def call_llm(messages, max_tokens=120, temperature=0.8):
    timeout = httpx.Timeout(connect=20.0, read=45.0, write=20.0, pool=20.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                GROQ_URL,
                headers=HEADERS,
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            if response.status_code == 413:
                raise RuntimeError("Groq request failed: 413 Payload Too Large")
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RuntimeError(f"Groq request failed: {str(exc)}")


async def complete_if_needed(messages, draft: str, max_tokens: int, temperature: float) -> str:
    trimmed = (draft or "").rstrip()
    if not trimmed or trimmed[-1] in ".!?]}\"'":
        return trimmed

    continuation_messages = list(messages) + [
        {"role": "assistant", "content": trimmed},
        {"role": "user", "content": "Continue from the exact last sentence and finish cleanly."},
    ]
    continuation = await call_llm(continuation_messages, max_tokens=200, temperature=temperature)
    return f"{trimmed} {continuation}".strip()


def clamp_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)] + "..."


def build_character_bible(session):
    known = getattr(session, "characters", {})
    temp = getattr(session, "temp_characters", {})
    user_dna = getattr(session, "visual_dna", "")

    lines = []
    if user_dna:
        lines.append(f"LEAD CHARACTER (User): Visual DNA=[{user_dna}]")
        lines.append("---")

    full_cast = {**(known or {}), **(temp or {})}
    for name, data in full_cast.items():
        char_dna = data.get("dna", "") or "No visual DNA locked (use generic anime style)"
        traits = ", ".join(data.get("traits", []))
        vibe = data.get("vibe", "unknown")

        lines.append(f"CHARACTER: {name}")
        lines.append(f"  - Visual DNA: {char_dna}")
        lines.append(f"  - Traits: {traits}")
        lines.append(f"  - Vibe: {vibe}")
        lines.append("")

    bible = "\n".join(lines).strip() if lines else "No characters or DNA defined."
    return clamp_text(bible, MAX_BIBLE_CHARS)


def build_memory_anchor(session) -> str:
    if not session:
        return ""

    story_lore = getattr(session, "story_lore", "") or ""
    location_context = getattr(session, "location_context", "") or ""
    recent_messages = getattr(session, "messages", [])[-5:]
    recent_bits = [
        f"{message.get('role')}: {clamp_text(message.get('content', ''), 120)}"
        for message in recent_messages
        if message.get("content")
    ]

    sections = []
    if story_lore:
        sections.append(f"Story so far: {story_lore}")
    if location_context:
        sections.append(f"Locked location: {location_context}")
    if recent_bits:
        sections.append("Recent exchange:\n" + "\n".join(recent_bits))
    return clamp_text("\n\n".join(sections), MAX_MEMORY_CHARS)


def _match_character_name(text: str, session) -> str | None:
    normalized = (text or "").strip().lower()
    if not normalized or not session:
        return None

    full_cast = {**getattr(session, "characters", {}), **getattr(session, "temp_characters", {})}
    for name in full_cast.keys():
        if name.lower() in normalized:
            return name
    return None


async def identify_character_from_text(text: str, session) -> str | None:
    if not text or not session:
        return None

    direct_match = _match_character_name(text, session)
    if direct_match:
        return direct_match

    names = list(getattr(session, "characters", {}).keys()) + list(getattr(session, "temp_characters", {}).keys())
    if not names:
        return None

    prompt = f"""
User said: "{text}"
Known characters: {", ".join(names)}

Which character is the user referring to? Return ONLY one of:
- an exact character name from the known characters list
- lead

Return lead if the user is referring to themselves, introducing no known character, or the target is unclear.
"""

    response = await call_llm(
        [{"role": "user", "content": prompt}],
        max_tokens=12,
        temperature=0,
    )
    name = (response or "").strip()
    if not name or name.lower() == "lead":
        return None

    for known_name in names:
        if known_name.lower() == name.lower():
            return known_name
    return None


def looks_like_location_update(text: str) -> bool:
    normalized = (text or "").lower()
    if not normalized:
        return False

    triggers = [
        "we are at",
        "we're at",
        "we are in",
        "we're in",
        "set this at",
        "set the scene at",
        "set the scene in",
        "scene takes place",
        "at a ",
        "at the ",
        "in a ",
        "in the ",
    ]
    return any(trigger in normalized for trigger in triggers)


async def extract_location_context(text: str) -> str | None:
    if not looks_like_location_update(text):
        return None

    prompt = f"""
Extract the location/background anchor from this user request.

User request: "{text}"

Return ONLY a short location phrase, 3 to 12 words, suitable for reuse in visual prompts.
Examples:
- rainy Lagos bus stop
- neon arcade rooftop at night
- cramped Tokyo convenience store aisle

If no clear location is present, return NONE.
"""

    response = await call_llm(
        [{"role": "user", "content": prompt}],
        max_tokens=20,
        temperature=0,
    )
    location = (response or "").strip().strip("\"'")
    if not location or location.upper() == "NONE":
        return None
    return location


async def generate_chat_response(user_input: str, session=None, mode: str = "gist"):
    settings = MODE_SETTINGS[mode]
    bible = build_character_bible(session)
    memory_anchor = build_memory_anchor(session)

    clean_input = clamp_text(user_input, MAX_USER_INPUT_CHARS)
    user_content = clean_input if not memory_anchor else f"{memory_anchor}\n\nUser request: {clean_input}"

    messages = [
        {"role": "system", "content": settings["system_prompt"].format(characters_bible=bible)},
        {"role": "user", "content": user_content},
    ]

    data = await call_llm(messages, max_tokens=settings["max_tokens"], temperature=settings["temperature"])
    data = await complete_if_needed(messages, data, settings["max_tokens"], settings["temperature"])
    return {"type": mode, "data": data}


async def generate_scene(session, prompt: str):
    settings = MODE_SETTINGS["scene"]
    bible = build_character_bible(session)
    memory_anchor = build_memory_anchor(session)
    location_context = getattr(session, "location_context", "") if session else ""

    clean_prompt = clamp_text(prompt, MAX_USER_INPUT_CHARS)
    prompt_content = clean_prompt if not memory_anchor else f"{memory_anchor}\n\nScene request: {clean_prompt}"
    batch_instruction = "\n\nINSTRUCTION: Return ONLY JSON. 4 panels. Use visual_dna for all character descriptions."
    if location_context:
        batch_instruction += (
            f"\nUse this exact location anchor for all 4 panels: {location_context}."
            "\nEvery visual_description must keep that same background/location context."
        )

    messages = [
        {"role": "system", "content": settings["system_prompt"].format(characters_bible=bible) + batch_instruction},
        {"role": "user", "content": prompt_content},
    ]

    data = await call_llm(messages, max_tokens=settings["max_tokens"], temperature=settings["temperature"])
    data = await complete_if_needed(messages, data, settings["max_tokens"], settings["temperature"])
    return {"type": "scene", "data": data}


def detect_scene_mode(user_input: str) -> bool:
    normalized = user_input.lower()
    triggers = ["act it out", "make a scene", "create a scene", "roleplay", "script this", "play it out"]
    return any(trigger in normalized for trigger in triggers)


async def generate_response(user_input: str, session=None, requested_mode: str | None = None):
    mode = (requested_mode or (getattr(session, "mode", "gist") if session else "gist")).strip().lower()
    if mode == "production":
        mode = "scene"

    if detect_scene_mode(user_input):
        mode = "scene"
    if mode not in MODE_SETTINGS:
        mode = "gist"

    if session:
        session.refresh_story_lore()
        session.set_mode(mode)

        location_context = await extract_location_context(user_input)
        if location_context:
            session.location_context = location_context

    if mode == "scene":
        return await generate_scene(session, user_input)

    return await generate_chat_response(user_input, session=session, mode=mode)
