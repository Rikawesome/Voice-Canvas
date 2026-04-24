import json
import os
import uuid
from typing import List, Dict, Optional

SESSIONS_DIR = "data/sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)


class Session:
    def __init__(
        self,
        session_id: str = None,
        mode: str = "gist",
        messages: List[Dict] = None,
        characters: Dict = None,
        temp_characters: Dict = None
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.mode = mode
        self.messages = messages or []

        # 🧠 Permanent characters (core cast)
        self.characters = characters or {}

        # 🌫️ Temporary scene-only characters
        self.temp_characters = temp_characters or {}

    # =========================
    # 💬 MESSAGE HANDLING
    # =========================

    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content
        })

        # Keep memory tight for performance
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]

    # =========================
    # 🧠 PERMANENT CHARACTERS
    # =========================

    def update_character(self, name: str, traits: List[str] = None, vibe: str = None):
        if name not in self.characters:
            self.characters[name] = {
                "traits": [],
                "vibe": "unknown",
                "voice_mapping": None
            }

        # Merge traits without destroying order
        if traits:
            existing = self.characters[name]["traits"]
            for trait in traits:
                if trait not in existing:
                    existing.append(trait)

        if vibe:
            self.characters[name]["vibe"] = vibe

    # =========================
    # 🌫️ TEMPORARY CHARACTERS
    # =========================

    def add_temp_character(self, name: str, description: str = "", traits: List[str] = None, vibe: str = "unknown"):
        if name not in self.temp_characters:
            self.temp_characters[name] = {
                "description": description,
                "traits": traits or [],
                "vibe": vibe
            }

    def promote_character(self, name: str):
        """
        Move temp character → permanent cast (when they become recurring)
        """
        if name in self.temp_characters:
            temp = self.temp_characters[name]

            self.update_character(
                name=name,
                traits=temp.get("traits", []),
                vibe=temp.get("vibe", "unknown")
            )

            del self.temp_characters[name]

    # =========================
    # 💾 SAVE / LOAD
    # =========================

    def save(self):
        filepath = os.path.join(SESSIONS_DIR, f"{self.session_id}.json")

        data = {
            "session_id": self.session_id,
            "mode": self.mode,
            "messages": self.messages,
            "characters": self.characters,
            "temp_characters": self.temp_characters
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, session_id: str = None):
        if not session_id:
            return cls()

        filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")

        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                return cls(
                    session_id=data.get("session_id"),
                    mode=data.get("mode", "gist"),
                    messages=data.get("messages", []),
                    characters=data.get("characters", {}),
                    temp_characters=data.get("temp_characters", {})
                )

            except Exception as e:
                print(f"⚠️ Session load error: {e}")
                return cls(session_id=session_id)

        return cls(session_id=session_id)