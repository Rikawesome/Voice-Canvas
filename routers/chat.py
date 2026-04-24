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
from typing import Optional, Dict
from pydub import AudioSegment

from services.llm import generate_response
from models.session import Session
import edge_tts

router = APIRouter()

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
        # Clean potential markdown from LLM
        clean_json = re.sub(r"```json|```", "", request.script).strip()
        script_data = json.loads(clean_json)

        # Kick off all TTS tasks at once
        tasks = []
        for line in script_data:
            speaker = line.get("speaker", "Narrator")
            text = line.get("text", "")
            voice = request.cast.get(speaker, "en-US-AndrewNeural")
            tasks.append(text_to_speech(text, voice))

        audio_results = await asyncio.gather(*tasks)

        combined_audio = AudioSegment.empty()
        for audio_bytes in audio_results:
            if audio_bytes:
                segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
                combined_audio += segment + AudioSegment.silent(duration=300)

        buffer = io.BytesIO()
        combined_audio.export(buffer, format="mp3")
        return Response(content=buffer.getvalue(), media_type="audio/mpeg")

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
