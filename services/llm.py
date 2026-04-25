import os
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# =========================
# 🎭 SYSTEM PROMPTS
# =========================

ANDREW_SYSTEM_PROMPT = """
You are Andrew — a real-time conversational partner.

RULES:
- Short responses (1–6 lines max)
- Interrupt-style speech: "Wait—", "Nah—", "Omo—"
- React first, explain later (or never)
- Feels like live conversation, not assistant
- Never repeat user input
- Never restate full context
"""

SCENE_SYSTEM_PROMPT = """
You are a professional anime scene writer.

CHARACTER BIBLE:
{characters_bible}

RULES:
- Output ONLY valid JSON
- STRICT: invalid JSON = FAILURE
- Max 5 lines
- No narration outside JSON
- Each line must be short

FORMAT:
[
  {{"speaker": "Name", "text": "..."}}
]
"""

# =========================
# ⚡ CORE CALL (SINGLE SOURCE OF TRUTH)
# =========================

async def call_llm(messages, max_tokens=120, temperature=0.8):
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(
            GROQ_URL,
            headers=HEADERS,
            json={
                "model": "llama-3.1-8b-instant",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )

        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


# =========================
# 🧠 CHARACTER BIBLE
# =========================

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


# =========================
# 💬 CHAT MODE
# =========================

async def generate_chat_response(user_input: str):
    messages = [
        {"role": "system", "content": ANDREW_SYSTEM_PROMPT},
        {"role": "user", "content": user_input}
    ]

    return {
        "type": "chat",
        "data": await call_llm(messages, max_tokens=90, temperature=0.9)
    }


# =========================
# 🎬 SCENE MODE
# =========================

async def generate_scene(session, prompt: str):
    bible = build_character_bible(
        getattr(session, "characters", {}),
        getattr(session, "temp_characters", {})
    )

    messages = [
        {
            "role": "system",
            "content": SCENE_SYSTEM_PROMPT.format(characters_bible=bible)
        },
        {"role": "user", "content": prompt}
    ]

    return {
        "type": "scene",
        "data": await call_llm(messages, max_tokens=220, temperature=0.7)
    }


# =========================
# 🔍 MODE DETECTOR
# =========================

def detect_scene_mode(user_input: str) -> bool:
    triggers = [
        "act it out",
        "make a scene",
        "dialogue",
        "play it out",
        "conversation between"
    ]
    return any(t in user_input.lower() for t in triggers)


# =========================
# 🚀 SINGLE ENTRY POINT (IMPORTANT FIX)
# =========================

async def generate_response(user_input: str, session=None):
    """
    ONE brain function only.
    No duplicate calls anywhere else.
    """

    if detect_scene_mode(user_input):
        if session:
            return await generate_scene(session, user_input)

        fake_session = type("Empty", (), {
            "characters": {},
            "temp_characters": {}
        })()

        return await generate_scene(fake_session, user_input)

    return await generate_chat_response(user_input)
