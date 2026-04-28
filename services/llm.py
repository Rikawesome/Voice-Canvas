import os

import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json",
}

GIST_SYSTEM_PROMPT = """
You are Andrew, a witty bestie.

RULES:
- Keep the energy high
- Use short, slang-friendly responses
- React first before analyzing
- Do not over-plan
- Keep replies concise but complete
"""

WORKSHOP_SYSTEM_PROMPT = """
You are Andrew in workshop mode, acting like a creative director.

RULES:
- Build on the user's idea with 3 to 4 concrete manga or scene beats
- Be collaborative and specific
- Organize clearly when it helps
- Suggest next steps, stakes, character turns, or scene escalation
- Stay warm and energetic, not robotic
"""

SCENE_SYSTEM_PROMPT = """
You are a lead anime script writer.

CHARACTER BIBLE:
{characters_bible}

RULES:
- Output ONLY valid JSON
- STRICT: invalid JSON = FAILURE
- Write 8 to 14 dialogue lines
- No narration outside JSON
- Each line must be concise and speakable
- Use recurring character names as the speaker field
- Do not invent generic speaker labels like "Voice", "Man", or "Woman" unless the user explicitly asked for that
- Escape quotes inside text so the JSON stays valid
- Every item must follow the exact schema shown below

FORMAT:
[
  {{"speaker": "Name", "text": "..."}}
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
        "system_prompt": None,
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

            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
    except httpx.TimeoutException as exc:
        raise RuntimeError("Groq request timed out. Please try again in a moment.") from exc
    except httpx.HTTPStatusError as exc:
        details = exc.response.text.strip() or str(exc)
        raise RuntimeError(f"Groq request failed: {details}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Could not reach Groq. Check your internet connection and API settings.") from exc


async def complete_if_needed(messages, draft: str, max_tokens: int, temperature: float) -> str:
    trimmed = (draft or "").rstrip()
    if not trimmed or trimmed[-1] in ".!?]}\"'":
        return trimmed

    continuation_messages = list(messages) + [
        {"role": "assistant", "content": trimmed},
        {
            "role": "user",
            "content": "Continue from the exact last sentence and finish cleanly. Do not restart or repeat.",
        },
    ]

    continuation = await call_llm(
        continuation_messages,
        max_tokens=max(80, min(220, max_tokens // 3)),
        temperature=min(temperature, 0.7),
    )
    return f"{trimmed} {continuation}".strip()


def build_character_bible(known: dict, temp: dict):
    lines = []

    for name, data in (known or {}).items():
        traits = ", ".join(data.get("traits", []))
        vibe = data.get("vibe", "unknown")
        lines.append(f"{name}: traits=[{traits}], vibe={vibe}")

    for name, data in (temp or {}).items():
        desc = data.get("description", "")
        traits = ", ".join(data.get("traits", []))
        vibe = data.get("vibe", "unknown")
        lines.append(f"{name}: desc={desc}, traits=[{traits}], vibe={vibe}")

    return "\n".join(lines) if lines else "No characters defined"


def build_memory_anchor(session) -> str:
    if not session:
        return ""

    story_lore = getattr(session, "story_lore", "") or ""
    recent_messages = getattr(session, "messages", [])[-5:]
    recent_bits = []

    for message in recent_messages:
        role = message.get("role", "unknown")
        content = " ".join(str(message.get("content", "")).split())
        if not content:
            continue
        if len(content) > 180:
            content = content[:177] + "..."
        recent_bits.append(f"{role}: {content}")

    sections = []
    if story_lore:
        sections.append(f"Story so far: {story_lore}")
    if recent_bits:
        sections.append("Recent exchange:\n" + "\n".join(recent_bits))

    return "\n\n".join(sections)


async def generate_chat_response(user_input: str, session=None, mode: str = "gist"):
    settings = MODE_SETTINGS[mode]
    memory_anchor = build_memory_anchor(session)
    user_content = user_input if not memory_anchor else f"{memory_anchor}\n\nUser request: {user_input}"
    messages = [
        {"role": "system", "content": settings["system_prompt"]},
        {"role": "user", "content": user_content},
    ]

    data = await call_llm(
        messages,
        max_tokens=settings["max_tokens"],
        temperature=settings["temperature"],
    )
    data = await complete_if_needed(messages, data, settings["max_tokens"], settings["temperature"])

    return {
        "type": mode,
        "data": data,
    }


async def generate_scene(session, prompt: str):
    settings = MODE_SETTINGS["scene"]
    bible = build_character_bible(
        getattr(session, "characters", {}),
        getattr(session, "temp_characters", {}),
    )
    memory_anchor = build_memory_anchor(session)
    prompt_content = prompt if not memory_anchor else f"{memory_anchor}\n\nScene request: {prompt}"

    messages = [
        {
            "role": "system",
            "content": SCENE_SYSTEM_PROMPT.format(characters_bible=bible),
        },
        {"role": "user", "content": prompt_content},
    ]

    data = await call_llm(
        messages,
        max_tokens=settings["max_tokens"],
        temperature=settings["temperature"],
    )
    data = await complete_if_needed(messages, data, settings["max_tokens"], settings["temperature"])

    return {
        "type": "scene",
        "data": data,
    }


def detect_scene_mode(user_input: str) -> bool:
    normalized = user_input.lower()
    triggers = [
        "act it out",
        "make a scene",
        "write a scene",
        "create a scene",
        "scene between",
        "dialogue",
        "turn this into dialogue",
        "make them talk",
        "play it out",
        "roleplay",
        "role-play",
        "script this",
        "dramatize",
        "dramatic scene",
        "conversation between",
        "talking scene",
    ]
    return any(trigger in normalized for trigger in triggers)


async def generate_response(user_input: str, session=None, requested_mode: str | None = None):
    normalized_mode = (requested_mode or "").strip().lower()
    if normalized_mode == "production":
        normalized_mode = "scene"

    if session:
        session.refresh_story_lore()

    if normalized_mode in {"gist", "workshop", "scene"}:
        if session:
            session.set_mode(normalized_mode)

        if normalized_mode == "scene":
            target_session = session or type(
                "Empty",
                (),
                {"characters": {}, "temp_characters": {}, "messages": [], "story_lore": ""},
            )()
            return await generate_scene(target_session, user_input)

        return await generate_chat_response(user_input, session=session, mode=normalized_mode)

    if detect_scene_mode(user_input):
        target_session = session or type(
            "Empty",
            (),
            {"characters": {}, "temp_characters": {}, "messages": [], "story_lore": ""},
        )()
        if session:
            session.set_mode("scene")
        return await generate_scene(target_session, user_input)

    active_mode = getattr(session, "mode", "gist") if session else "gist"
    if active_mode not in {"gist", "workshop"}:
        active_mode = "gist"

    return await generate_chat_response(user_input, session=session, mode=active_mode)
