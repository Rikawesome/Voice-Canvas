import io
import os
import re
import json
import base64
import asyncio
import tempfile
import traceback
import speech_recognition as sr

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
from pydub import AudioSegment
from dotenv import load_dotenv

from services.llm import generate_response
from models.session import Session
import edge_tts
import httpx

load_dotenv()

router = APIRouter()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

PRODUCTION_VOICE_ENV_MAP = {
    "narrator": "ELEVENLABS_VOICE_NARRATOR_ID",
    "lead_male": "ELEVENLABS_VOICE_LEAD_MALE_ID",
    "lead_female": "ELEVENLABS_VOICE_LEAD_FEMALE_ID",
    "villain": "ELEVENLABS_VOICE_VILLAIN_ID",
}

LEGACY_CAST_FALLBACKS = {
    "en-US-AndrewNeural": "lead_male",
    "en-GB-RyanNeural": "villain",
    "en-NG-EzinneNeural": "lead_female",
    "en-US-AvaNeural": "narrator",
}

# =========================
# REQUEST MODELS
# =========================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    voice_override: Optional[str] = None


class ProductionRequest(BaseModel):
    script: str
    cast: Dict[str, str]
    session_id: Optional[str] = None


# =========================
# 🔊 TTS CORE
# =========================

async def text_to_speech(text: str, voice="en-US-AndrewNeural"):
    if not text or len(text.strip()) < 1:
        return None
    try:
        communicate = edge_tts.Communicate(text, voice)
        audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio
    except Exception as e:
        print(f"TTS Error: {e}")
        return None


def extract_scene_json(script: str) -> List[Dict[str, str]]:
    cleaned = (script or "").strip()
    if not cleaned:
        raise ValueError("Scene script is empty")

    cleaned = re.sub(r"```json|```", "", cleaned, flags=re.IGNORECASE).strip()

    if not cleaned.startswith("["):
        match = re.search(r"(\[[\s\S]*\])", cleaned)
        if match:
            cleaned = match.group(1).strip()

    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("Scene script must be a JSON array")

    normalized = []
    for index, line in enumerate(parsed, start=1):
        if not isinstance(line, dict):
            raise ValueError(f"Scene line {index} must be an object")

        speaker = str(line.get("speaker", "Narrator")).strip() or "Narrator"
        text = str(line.get("text", "")).strip()
        if not text:
            continue

        normalized.append({"speaker": speaker, "text": text})

    if not normalized:
        raise ValueError("Scene script has no spoken lines")

    return normalized


def resolve_production_voice_id(raw_voice: Optional[str]) -> Optional[str]:
    selected = (raw_voice or "").strip()
    if not selected:
        return os.getenv("ELEVENLABS_DEFAULT_VOICE_ID")

    selected = LEGACY_CAST_FALLBACKS.get(selected, selected)
    env_name = PRODUCTION_VOICE_ENV_MAP.get(selected.lower())
    if env_name:
        return os.getenv(env_name) or os.getenv("ELEVENLABS_DEFAULT_VOICE_ID")

    return selected


async def elevenlabs_text_to_speech(text: str, voice_id: str) -> bytes:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
    if not voice_id:
        raise RuntimeError("No ElevenLabs voice ID configured for scene production")
    if not text or not text.strip():
        raise ValueError("Cannot synthesize empty text")

    payload = {
        "text": text.strip(),
        "model_id": ELEVENLABS_MODEL_ID,
        "output_format": ELEVENLABS_OUTPUT_FORMAT,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.15,
            "use_speaker_boost": True,
        },
    }

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{ELEVENLABS_BASE_URL}/{voice_id}",
            headers=headers,
            json=payload,
        )

    response.raise_for_status()
    return response.content


# =========================
# 💬 CHAT ROUTE (Base)
# =========================

@router.post("/")
async def chat(request: ChatRequest):
    session = Session.load(request.session_id)
    session.add_message("user", request.message)

    result = await generate_response(request.message, session)

    reply = result["data"]
    is_scene = result["type"] == "scene"

    session.add_message("assistant", reply)
    session.save()

    return {
        "reply": reply,
        "session_id": session.session_id,
        "trigger_cast": is_scene,
        "characters": session.characters
    }


# =========================
# 🎧 STREAM AUDIO (NEW 🔥)
# =========================

@router.post("/stream-audio")
async def stream_audio(request: ChatRequest):
    session = Session.load(request.session_id)
    result = await generate_response(request.message, session)
    
    reply_text = result["data"]
    voice = request.voice_override or "en-US-AndrewNeural"

    async def audio_generator():
        # ⚡ Illusion: Start with a quick filler
        filler = await text_to_speech("Hmm—", voice)
        if filler: yield filler

        # Split by sentences for smooth streaming
        parts = re.split(r'(?<=[.!?])\s+', reply_text)
        for chunk in [p.strip() for p in parts if p.strip()]:
            audio_bytes = await text_to_speech(chunk, voice)
            if audio_bytes:
                yield audio_bytes

    return StreamingResponse(audio_generator(), media_type="audio/mpeg")


# =========================
# 🎬 SCENE PRODUCTION (Parallel Processing)
# =========================

@router.post("/speak")
async def speak(request: ChatRequest):
    voice = request.voice_override or "en-US-AndrewNeural"
    audio_bytes = await text_to_speech(request.message, voice)

    if not audio_bytes:
        return JSONResponse({"error": "Unable to generate audio"}, status_code=500)

    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/produce")
async def produce_scene(request: ProductionRequest):
    try:
        script_data = extract_scene_json(request.script)
        tasks = []

        for line in script_data:
            speaker = line.get("speaker", "Narrator")
            text = line.get("text", "")
            requested_voice = request.cast.get(speaker) or request.cast.get(speaker.lower())
            voice_id = resolve_production_voice_id(requested_voice)

            if not voice_id:
                fallback_default = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID")
                if fallback_default:
                    voice_id = fallback_default
                else:
                    raise ValueError(
                        f"No ElevenLabs voice configured for '{speaker}'. "
                        "Set ELEVENLABS_DEFAULT_VOICE_ID or a role-specific ELEVENLABS_VOICE_*_ID."
                    )

            tasks.append(elevenlabs_text_to_speech(text, voice_id))

        audio_results = await asyncio.gather(*tasks)

        combined_audio = AudioSegment.empty()
        for audio_bytes in audio_results:
            if audio_bytes:
                segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                combined_audio += segment + AudioSegment.silent(duration=300)

        if len(combined_audio) == 0:
            raise ValueError("Scene production returned no audio segments")

        buffer = io.BytesIO()
        combined_audio.export(buffer, format="mp3")
        return Response(content=buffer.getvalue(), media_type="audio/mpeg")

    except httpx.HTTPStatusError as e:
        error_body = e.response.text.strip()
        print(f"Production TTS HTTP Error: {e.response.status_code} {error_body}")
        return JSONResponse(
            {
                "error": "ElevenLabs scene synthesis failed",
                "details": error_body or str(e),
            },
            status_code=502,
        )
    except Exception as e:
        print(f"Production Error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# =========================
# 🎤 LIVE SESSION
# =========================

@router.post("/live-session")
async def live_session(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    session = Session.load(session_id)
    audio_bytes = await audio.read()
    wav_path = None

    if not audio_bytes:
        return JSONResponse({"error": "No audio received"}, status_code=400)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        try:
            audio_segment = AudioSegment.from_file(tmp_path, format="webm")
        except Exception as conversion_error:
            print("Live conversion error:", conversion_error)
            return JSONResponse(
                {"error": "Audio conversion failed. Check ffmpeg and WebM support on the server."},
                status_code=500
            )

        wav_path = tmp_path.replace(".webm", ".wav")
        audio_segment.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                user_text = recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            return JSONResponse({"error": "Could not understand the recorded audio"}, status_code=422)
        except sr.RequestError as stt_error:
            print("Live STT request error:", stt_error)
            return JSONResponse({"error": "Speech recognition service is unavailable"}, status_code=503)

        session.add_message("user", user_text)
        result = await generate_response(user_text, session)
        reply = result["data"]
        session.add_message("assistant", reply)
        session.save()
        audio_reply = await text_to_speech(reply)

        return JSONResponse({
            "user_text": user_text,
            "reply": reply,
            "audio": base64.b64encode(audio_reply).decode() if audio_reply else None,
            "session_id": session.session_id,
            "trigger_cast": result["type"] == "scene",
            "characters": session.characters
        })

    except Exception as e:
        print("Live error:", e)
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
