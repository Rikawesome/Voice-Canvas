import io
import os
import re
import json
import base64
import asyncio
import tempfile
import traceback
import uuid
import speech_recognition as sr

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
from pydub import AudioSegment
from dotenv import load_dotenv

from services.llm import generate_response, identify_character_from_text
from models.session import Session
import edge_tts
import httpx

load_dotenv()

router = APIRouter()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"
REFERENCE_IMAGES_DIR = os.path.join("data", "reference_images")
os.makedirs(REFERENCE_IMAGES_DIR, exist_ok=True)

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
    mode: Optional[str] = None


def resolve_session(session_id: Optional[str]) -> Session:
    if session_id in {None, "", "new", "null"}:
        return Session()
    return Session.load(session_id)


def is_user_identity_claim(text: Optional[str]) -> bool:
    normalized = (text or "").strip().lower()
    keywords = [
        "this is me",
        "it's me",
        "its me",
        "i look like",
        "my photo",
        "my picture",
        "my profile",
        "that's me",
        "thats me",
    ]
    return any(keyword in normalized for keyword in keywords)


def save_reference_image(session_id: str, image_bytes: bytes, filename: Optional[str], content_type: Optional[str] = None) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        mime_ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        ext = mime_ext.get((content_type or "").lower(), ".jpg")

    session_dir = os.path.join(REFERENCE_IMAGES_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    path = os.path.join(session_dir, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as image_file:
        image_file.write(image_bytes)
    return os.path.abspath(path)


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

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        repaired = re.sub(r",\s*([}\]])", r"\1", cleaned)
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            parsed = salvage_scene_json(repaired)

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


def salvage_scene_json(script: str) -> List[Dict[str, str]]:
    speaker_pattern = re.compile(r'"speaker"\s*:\s*"([^"]+)"', re.IGNORECASE)
    speakers = list(speaker_pattern.finditer(script))
    salvaged: List[Dict[str, str]] = []

    for index, match in enumerate(speakers):
        speaker = match.group(1).strip() or "Narrator"
        block_start = match.start()
        block_end = speakers[index + 1].start() if index + 1 < len(speakers) else len(script)
        block = script[block_start:block_end]

        text_match = re.search(r'"text"\s*:\s*"', block, re.IGNORECASE)
        if not text_match:
            continue

        text_start = text_match.end()
        text = _read_json_string_value(block, text_start)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        salvaged.append({"speaker": speaker, "text": text})

    if salvaged:
        return salvaged

    raise ValueError("Scene script is invalid JSON and could not be repaired")


def _read_json_string_value(source: str, start_index: int) -> str:
    chars = []
    escaped = False
    i = start_index

    while i < len(source):
        char = source[i]

        if escaped:
            chars.append(char)
            escaped = False
            i += 1
            continue

        if char == "\\":
            escaped = True
            i += 1
            continue

        if char == '"':
            remainder = source[i + 1:].lstrip()
            if remainder.startswith(",") or remainder.startswith("}") or remainder.startswith("]"):
                break

            chars.append(char)
            i += 1
            continue

        chars.append(char)
        i += 1

    return "".join(chars)


def build_scene_character_map(session: Session, script: str) -> Dict[str, Dict[str, str]]:
    characters: Dict[str, Dict[str, str]] = {}

    for name, data in (getattr(session, "characters", {}) or {}).items():
        characters[name] = {
            "vibe": data.get("vibe", "Character"),
            "voice_mapping": data.get("voice_mapping"),
        }

    for name, data in (getattr(session, "temp_characters", {}) or {}).items():
        existing = characters.get(name, {})
        characters[name] = {
            "vibe": existing.get("vibe") or data.get("vibe", "Scene character"),
            "voice_mapping": existing.get("voice_mapping"),
        }

    try:
        for line in extract_scene_json(script):
            speaker = line.get("speaker", "Narrator").strip()
            if not speaker:
                continue

            existing = characters.get(speaker, {})
            characters[speaker] = {
                "vibe": existing.get("vibe") or "Generated for this scene",
                "voice_mapping": existing.get("voice_mapping"),
            }
    except Exception:
        pass

    return characters


async def process_chat_turn(session: Session, user_message: str, requested_mode: Optional[str] = None) -> Dict:
    session.add_message("user", user_message)
    result = await generate_response(user_message, session, requested_mode=requested_mode)

    reply = result["data"]
    is_scene = result["type"] == "scene"
    scene_characters = build_scene_character_map(session, reply) if is_scene else session.characters

    session.add_message("assistant", reply)
    session.save()

    return {
        "reply": reply,
        "session_id": session.session_id,
        "mode": session.mode,
        "trigger_cast": is_scene,
        "characters": scene_characters,
    }


def resolve_production_voice_id(raw_voice: Optional[str]) -> Optional[str]:
    selected = (raw_voice or "").strip()
    if not selected:
        return resolve_any_production_voice_id()

    selected = LEGACY_CAST_FALLBACKS.get(selected, selected)
    env_name = PRODUCTION_VOICE_ENV_MAP.get(selected.lower())
    if env_name:
        return os.getenv(env_name) or resolve_any_production_voice_id()

    return selected


def resolve_any_production_voice_id() -> Optional[str]:
    default_voice = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID")
    if default_voice:
        return default_voice

    for env_name in PRODUCTION_VOICE_ENV_MAP.values():
        configured_voice = os.getenv(env_name)
        if configured_voice:
            return configured_voice

    return None


def choose_edge_voice_for_speaker(speaker: str) -> str:
    lowered = (speaker or "").strip().lower()

    if lowered in {"narrator", "anna", "mikasa", "historia", "sasha"}:
        return "en-US-AvaNeural"
    if lowered in {"villain", "levi", "eren", "reiner", "zeke"}:
        return "en-GB-RyanNeural"

    return "en-US-AndrewNeural"


async def synthesize_scene_line(text: str, speaker: str, requested_voice: Optional[str]) -> bytes:
    voice_id = resolve_production_voice_id(requested_voice)
    if voice_id:
        try:
            return await elevenlabs_text_to_speech(text, voice_id)
        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text.strip()
            should_retry_with_default = (
                exc.response.status_code == 404 and
                '"code":"voice_not_found"' in error_body.replace(" ", "")
            )

            if should_retry_with_default:
                fallback_voice_id = resolve_any_production_voice_id()
                if fallback_voice_id and fallback_voice_id != voice_id:
                    print(
                        f"Production fallback: ElevenLabs voice '{voice_id}' was not found for "
                        f"speaker '{speaker}'. Retrying with default ElevenLabs voice."
                    )
                    return await elevenlabs_text_to_speech(text, fallback_voice_id)

            raise

    fallback_voice = choose_edge_voice_for_speaker(speaker)
    print(
        f"Production fallback: using Edge TTS voice '{fallback_voice}' for speaker '{speaker}' "
        "because no ElevenLabs voice was configured."
    )
    audio_bytes = await text_to_speech(text, fallback_voice)
    if not audio_bytes:
        raise ValueError(
            f"Unable to synthesize audio for '{speaker}'. "
            "Configure ELEVENLABS_DEFAULT_VOICE_ID or provide a cast mapping."
        )

    return audio_bytes


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
        for attempt in range(3):
            response = await client.post(
                f"{ELEVENLABS_BASE_URL}/{voice_id}",
                headers=headers,
                json=payload,
            )

            if response.status_code != 409:
                break

            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {}

            detail = error_payload.get("detail", {})
            if detail.get("code") != "already_running" or attempt == 2:
                break

            await asyncio.sleep(1.0 + attempt * 0.5)

    response.raise_for_status()
    return response.content


# =========================
# 💬 CHAT ROUTE
# =========================

@router.post("/")
async def chat(request: ChatRequest):
    session = resolve_session(request.session_id)

    try:
        return await process_chat_turn(session, request.message, requested_mode=request.mode)
    except Exception as e:
        print(f"Chat Error: {e}")
        session.save()
        return JSONResponse(
            {
                "error": str(e),
                "session_id": session.session_id,
                "mode": session.mode,
                "trigger_cast": False,
                "characters": session.characters,
            },
            status_code=502,
        )


@router.post("/message/{session_id}")
async def chat_message(
    session_id: str,
    user_input: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    session = resolve_session(session_id)
    dna_update_msg = None
    effective_input = (user_input or "").strip()

    try:
        if file:
            image_bytes = await file.read()
            dna_string = await extract_visual_dna(image_bytes)
            reference_image_path = save_reference_image(
                session.session_id,
                image_bytes,
                getattr(file, "filename", None),
                getattr(file, "content_type", None),
            )

            target_name = await identify_character_from_text(effective_input, session)
            if target_name and target_name in session.characters:
                session.characters[target_name]["dna"] = dna_string
                session.characters[target_name]["reference_image_path"] = reference_image_path
                dna_update_msg = f"Locked DNA for {target_name}"
            elif target_name and target_name in session.temp_characters:
                session.temp_characters[target_name]["dna"] = dna_string
                session.temp_characters[target_name]["reference_image_path"] = reference_image_path
                dna_update_msg = f"Locked DNA for temporary character {target_name}"
            elif is_user_identity_claim(effective_input):
                session.visual_dna = dna_string
                session.visual_dna_image_path = reference_image_path
                dna_update_msg = "Locked DNA to your profile."
            else:
                dna_update_msg = "Temporary DNA loaded for this message."
                effective_input = (
                    f"[IMAGE CONTEXT: character traits = {dna_string}] "
                    f"{effective_input}".strip()
                )

            session.save()

        chat_input = effective_input or "Look at this photo"
        payload = await process_chat_turn(session, chat_input, requested_mode=mode)
        if payload["trigger_cast"]:
            try:
                from services.painter import generate_manga_page

                panels = extract_scene_json(payload["reply"])
                manga_result = await generate_manga_page(panels, session)
                payload["panels"] = manga_result.get("panels", [])
                payload["manga_page"] = manga_result.get("page_data_url")
                panel_errors = [item.get("error") for item in payload["panels"] if item.get("error")]
                if panel_errors and not any(item.get("url") for item in payload["panels"]):
                    joined_errors = " | ".join(panel_errors[:2])
                    if "Insufficient credit" in joined_errors:
                        payload["panel_error"] = (
                            "Panel rendering is blocked by Replicate billing. "
                            "Add credit or a payment method in your Replicate account, then try again."
                        )
                    elif "monthly included credits" in joined_errors or "402 Payment Required" in joined_errors:
                        payload["panel_error"] = (
                            "Panel rendering is blocked by Hugging Face Inference credits. "
                            "Your included credits are depleted, so image generation will stay unavailable until you add credits or upgrade."
                        )
                    elif "rate limit" in joined_errors.lower() or "throttled" in joined_errors.lower():
                        payload["panel_error"] = (
                            "Panel rendering hit Replicate rate limits. "
                            "Wait a few seconds and try Production mode again."
                        )
                    else:
                        payload["panel_error"] = joined_errors
            except Exception as painter_error:
                print(f"Painter handoff failed: {painter_error}")
                payload["panels"] = []
                payload["panel_error"] = str(painter_error)
        payload["data"] = payload["reply"]
        payload["dna_status"] = dna_update_msg
        return payload
    except Exception as e:
        print(f"Unified Chat Error: {e}")
        if "413" in str(e):
            return JSONResponse(
                {
                    "error": "Message too long. Try a shorter request.",
                    "session_id": session.session_id,
                    "mode": session.mode,
                    "trigger_cast": False,
                    "characters": session.characters,
                    "dna_status": dna_update_msg,
                },
                status_code=413,
            )
        session.save()
        return JSONResponse(
            {
                "error": str(e),
                "session_id": session.session_id,
                "mode": session.mode,
                "trigger_cast": False,
                "characters": session.characters,
                "dna_status": dna_update_msg,
            },
            status_code=502,
        )


# =========================
# 🎧 STREAM AUDIO
# =========================

@router.post("/stream-audio")
async def stream_audio(request: ChatRequest):
    session = Session.load(request.session_id)
    result = await generate_response(request.message, session, requested_mode=request.mode)
    
    reply_text = result["data"]
    voice = request.voice_override or "en-US-AndrewNeural"

    async def audio_generator():
        filler = await text_to_speech("Hmm—", voice)
        if filler: yield filler

        parts = re.split(r'(?<=[.!?])\s+', reply_text)
        for chunk in [p.strip() for p in parts if p.strip()]:
            audio_bytes = await text_to_speech(chunk, voice)
            if audio_bytes:
                yield audio_bytes

    return StreamingResponse(audio_generator(), media_type="audio/mpeg")


# =========================
# 🎬 PRODUCTION
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
        session = Session.load(request.session_id)
        line_jobs = []

        for line in script_data:
            speaker = line.get("speaker", "Narrator")
            text = line.get("text", "")
            requested_voice = request.cast.get(speaker) or request.cast.get(speaker.lower())
            if requested_voice:
                session.set_voice_mapping(speaker, requested_voice)

            line_jobs.append((speaker, text, requested_voice))

        session.save()
        audio_results = [None] * len(line_jobs)
        for index, speaker, text, requested_voice in [
            (index, speaker, text, requested_voice)
            for index, (speaker, text, requested_voice) in enumerate(line_jobs)
        ]:
            audio_results[index] = await synthesize_scene_line(text, speaker, requested_voice)

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
    session_id: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
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
        result = await generate_response(user_text, session, requested_mode=mode)
        reply = result["data"]
        is_scene = result["type"] == "scene"
        session.add_message("assistant", reply)
        session.save()
        audio_reply = await text_to_speech(reply)
        scene_characters = build_scene_character_map(session, reply) if is_scene else session.characters

        return JSONResponse({
            "user_text": user_text,
            "reply": reply,
            "audio": base64.b64encode(audio_reply).decode() if audio_reply else None,
            "session_id": session.session_id,
            "mode": session.mode,
            "trigger_cast": is_scene,
            "characters": scene_characters
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

# =========================
# 🧬 VISUAL SECTION (FIXED)
# =========================
from services.vision import extract_visual_dna 

@router.post("/upload-dna/{session_id}")
async def upload_dna(
    session_id: str,
    file: UploadFile = File(...),
    target_name: Optional[str] = Form(None),
    user_caption: Optional[str] = Form(None),
):
    try:
        # Resolving "new" sessions or loading existing ones
        if session_id == "new" or not session_id or session_id == "null":
            session = Session()
        else:
            session = Session.load(session_id)
        
        image_bytes = await file.read()
        print(f"🧬 Extracting DNA for session: {session.session_id}")
        
        dna_string = await extract_visual_dna(image_bytes)
        reference_image_path = save_reference_image(
            session.session_id,
            image_bytes,
            getattr(file, "filename", None),
            getattr(file, "content_type", None),
        )
        
        resolved_target = target_name or await identify_character_from_text(user_caption, session)

        if resolved_target and resolved_target in session.characters:
            session.characters[resolved_target]["dna"] = dna_string
            session.characters[resolved_target]["reference_image_path"] = reference_image_path
            message = f"Visual DNA locked for {resolved_target}."
        elif resolved_target and resolved_target in session.temp_characters:
            session.temp_characters[resolved_target]["dna"] = dna_string
            session.temp_characters[resolved_target]["reference_image_path"] = reference_image_path
            message = f"Visual DNA locked for temporary character {resolved_target}."
        elif is_user_identity_claim(user_caption):
            session.visual_dna = dna_string
            session.visual_dna_image_path = reference_image_path
            message = "Visual DNA locked to your profile."
        else:
            message = "Photo context received."
        session.save()
        
        return JSONResponse({
            "status": "success",
            "dna": dna_string,
            "session_id": session.session_id,
            "target": resolved_target or ("Lead User" if is_user_identity_claim(user_caption) else None),
            "caption": user_caption,
            "message": message
        })
    except Exception as e:
        print(f"❌ DNA Upload Error: {e}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)
