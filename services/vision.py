import base64
import os

import httpx


async def extract_visual_dna(image_bytes: bytes):
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = "gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {
                    "text": """
Analyze this image like a strict professional mangaka building a reusable character bible.
Return EXACTLY 16 comma-separated visual DNA tags ordered from most identity-critical to least.

Rules:
- Prioritize stable identity traits over pose, camera angle, or background details.
- Use short, technical, identity-locking tags suitable for manga image prompting.
- Avoid generic words like cool, stylish, beautiful, handsome, anime, detailed, aesthetic.
- Avoid vague fashion language unless it is truly signature and repeatable.
- Focus on traits that remain consistent across outfits, scenes, and angles.
- The first 8 tags must lock face structure, eye shape, hair silhouette, body silhouette, and age/gender presentation as visible.
- Use exact visual language, not personality labels unless directly visible.
- Do NOT describe background, lighting, pose, camera angle, or mood unless it defines the character's identity.
- We need tags strong enough to stop gender drift and face drift across multiple manga panels.

Capture:
1. Face shape, jawline, chin structure
2. Eye shape, lid type, iris color, gaze quality
3. Hair cut, silhouette, volume, parting, exact color
4. Body build and silhouette
5. Visible age/gender presentation cues
6. Signature clothing elements and fabric/material cues
7. Accessories, markings, piercings, scars, or standout features
8. Manga rendering cues useful for consistency, such as line-weight, cel-shaded, character sheet look

Output style example:
sharp tapered jaw, narrow heavy-lidded eyes, short spiky black hair, left-side undercut, lean teenage male build, flat chest silhouette, dark zip hoodie, silver chain necklace

Return ONLY the tags.
""".strip()
                },
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64,
                    }
                },
            ]
        }]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=60.0)

        if response.status_code == 429:
            raise Exception("Quota reached. Try again in 60 seconds.")

        if response.status_code != 200:
            print(f"DEBUG: Google Error Body: {response.text}")
            raise Exception(f"Vision API Error: {response.status_code}")

        result = response.json()
        try:
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise Exception("Google returned an empty response.")
