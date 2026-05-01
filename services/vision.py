import os
import base64
import httpx

async def extract_visual_dna(image_bytes: bytes):
    api_key = os.getenv("GOOGLE_API_KEY")
    
    # We are using the EXACT model string that worked in your curl command
    model_name = "gemini-flash-latest" 
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Analyze this character. Provide 10 technical visual tags (e.g., hair color, outfit style) as a comma-separated string only."},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                }
            ]
        }]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=60.0)
        
        if response.status_code == 429:
            raise Exception("Quota reached. Try again in 60 seconds.")
            
        if response.status_code != 200:
            # Log the full error to see what Google is complaining about
            print(f"DEBUG: Google Error Body: {response.text}")
            raise Exception(f"Google API Error: {response.status_code}")
            
        result = response.json()
        try:
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError):
            raise Exception("Google returned an empty response.")