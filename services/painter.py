import asyncio
import base64
import io
import os
from contextlib import ExitStack
from typing import Dict, List

import httpx
from huggingface_hub import InferenceClient

try:
    import replicate
except ImportError:
    replicate = None

from services.image_stitching import export_page, stitch_panels_2x2
from services.panel_prompts import build_panel_prompt


MODEL_NAME = "black-forest-labs/flux-2-dev"
HF_MODEL_NAME = (os.getenv("HF_IMAGE_MODEL") or "black-forest-labs/FLUX.1-dev").strip()


def _get_replicate_api_token() -> str:
    return (os.getenv("REPLICATE_API_TOKEN") or "").strip()


def _get_huggingface_api_token() -> str:
    return (
        os.getenv("HUGGINGFACE_API_TOKEN")
        or os.getenv("HF_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or ""
    ).strip()


def _get_image_provider() -> str:
    configured = (os.getenv("IMAGE_PROVIDER") or "auto").strip().lower()
    if configured in {"huggingface", "hf", "replicate", "auto"}:
        return configured
    return "auto"


def _normalize_output(output) -> str | None:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        return first if isinstance(first, str) else str(first)
    if output is None:
        return None
    return str(output)


def _reference_paths_for_panel(panel: Dict, session) -> List[str]:
    paths: List[str] = []
    speaker = str(panel.get("speaker", "")).strip()

    if speaker:
        for cast in (getattr(session, "characters", {}) or {}, getattr(session, "temp_characters", {}) or {}):
            if speaker in cast:
                reference_path = cast[speaker].get("reference_image_path")
                if reference_path:
                    paths.append(reference_path)
                break

    lead_reference = getattr(session, "visual_dna_image_path", "") or ""
    if lead_reference and lead_reference not in paths:
        paths.append(lead_reference)

    return [path for path in paths if path and os.path.exists(path)][:4]


def _run_flux_panel(prompt: str, reference_paths: List[str]):
    replicate_api_token = _get_replicate_api_token()

    if replicate is None:
        raise RuntimeError("replicate package is not installed. Run: pip install replicate")
    if not replicate_api_token:
        raise RuntimeError("Missing REPLICATE_API_TOKEN in environment")

    os.environ["REPLICATE_API_TOKEN"] = replicate_api_token

    input_params = {
        "prompt": prompt,
        "aspect_ratio": "1:1",
        "output_format": "webp",
    }

    with ExitStack() as stack:
        if reference_paths:
            input_params["input_images"] = [
                stack.enter_context(open(path, "rb"))
                for path in reference_paths
            ]
            input_params["aspect_ratio"] = "match_input_image"

        output = replicate.run(MODEL_NAME, input=input_params)
    return _normalize_output(output)


def _run_huggingface_panel(prompt: str, reference_paths: List[str]) -> str:
    huggingface_token = _get_huggingface_api_token()
    if not huggingface_token:
        raise RuntimeError("Missing HUGGINGFACE_API_TOKEN in environment")

    client = InferenceClient(
        api_key=huggingface_token,
    )

    image = None
    last_error = None
    negative_prompt = (
        "multiple panels, comic page, manga page, collage, split screen, diptych, triptych, "
        "grid layout, extra limbs, deformed hands, disfigured face, gender swap, duplicate person, blurry anatomy"
    )

    if reference_paths:
        try:
            with open(reference_paths[0], "rb") as reference_file:
                kwargs = {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "num_inference_steps": 30,
                    "guidance_scale": 8.0,
                }
                if HF_MODEL_NAME:
                    kwargs["model"] = HF_MODEL_NAME
                image = client.image_to_image(reference_file.read(), **kwargs)
        except Exception as exc:
            last_error = exc
            print(f"Hugging Face image-to-image fallback triggered: {exc}")

    if image is None:
        try:
            kwargs = {
                "negative_prompt": negative_prompt,
                "num_inference_steps": 30,
                "guidance_scale": 8.0,
            }
            if HF_MODEL_NAME:
                kwargs["model"] = HF_MODEL_NAME
            image = client.text_to_image(prompt, **kwargs)
        except Exception as exc:
            if last_error:
                raise RuntimeError(f"Hugging Face image_to_image failed: {last_error} | text_to_image failed: {exc}") from exc
            raise RuntimeError(f"Hugging Face error: {exc}") from exc

    output = io.BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _use_huggingface_first() -> bool:
    provider = _get_image_provider()
    if provider in {"huggingface", "hf"}:
        return True
    if provider == "replicate":
        return False
    return bool(_get_huggingface_api_token())


def _run_image_generation(prompt: str, reference_paths: List[str]) -> str | None:
    provider = _get_image_provider()
    errors: List[str] = []

    if provider in {"huggingface", "hf"}:
        return _run_huggingface_panel(prompt, reference_paths)

    if provider == "replicate":
        return _run_flux_panel(prompt, reference_paths)

    if _use_huggingface_first():
        try:
            return _run_huggingface_panel(prompt, reference_paths)
        except Exception as exc:
            errors.append(str(exc))
            raise RuntimeError(errors[-1])

    try:
        return _run_flux_panel(prompt, reference_paths)
    except Exception as exc:
        errors.append(str(exc))
        if not _get_huggingface_api_token():
            raise RuntimeError(errors[-1])

    try:
        return _run_huggingface_panel(prompt, reference_paths)
    except Exception as exc:
        errors.append(str(exc))
        raise RuntimeError(" | ".join(errors))


async def _download_panel_bytes(url: str) -> bytes:
    if url.startswith("data:"):
        try:
            _, encoded = url.split(",", 1)
            return base64.b64decode(encoded)
        except Exception as exc:
            raise RuntimeError(f"Invalid data URL panel payload: {exc}") from exc

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def _build_stitched_page(panel_results: List[Dict]) -> str | None:
    successful_urls = [item["url"] for item in panel_results if item.get("url")]
    if len(successful_urls) != 4:
        return None

    try:
        panel_bytes = await asyncio.gather(*[_download_panel_bytes(url) for url in successful_urls])
        stitched = stitch_panels_2x2(panel_bytes)
        page_bytes = export_page(stitched, image_format="WEBP", quality=88)
        encoded = base64.b64encode(page_bytes).decode("utf-8")
        return f"data:image/webp;base64,{encoded}"
    except Exception as exc:
        print(f"Painter Stitching Error: {exc}")
        return None


async def generate_panel(panel: Dict, index: int, session):
    try:
        prompt = build_panel_prompt(panel, session)
        reference_paths = _reference_paths_for_panel(panel, session)
        image_url = await asyncio.to_thread(_run_image_generation, prompt, reference_paths)
        return {"index": index, "url": image_url, "speaker": panel.get("speaker")}
    except Exception as e:
        print(f"Painter Error (Panel {index}): {e}")
        return {"index": index, "url": None, "speaker": panel.get("speaker"), "error": str(e)}


async def generate_manga_page(panels: List[Dict], session):
    results = []
    for index, panel in enumerate(panels):
        result = await generate_panel(panel, index, session)
        results.append(result)

        error_text = str(result.get("error", "") or "")
        fatal_provider_error = any(
            marker in error_text
            for marker in [
                "402 Payment Required",
                "monthly included credits",
                "Insufficient credit",
                "410 Gone",
                "deprecated and no longer supported",
            ]
        )
        if fatal_provider_error:
            break

        # Replicate free-tier accounts are often burst-limited; pace requests a bit.
        if index < len(panels) - 1:
            await asyncio.sleep(1.5)

    sorted_results = sorted(results, key=lambda item: item["index"])
    stitched_page = await _build_stitched_page(sorted_results)
    return {
        "panels": sorted_results,
        "page_data_url": stitched_page,
    }
