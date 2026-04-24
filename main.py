from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from routers import chat # This is the crucial link to your logic

app = FastAPI(title="VoiceCanvas")

# This helps prevent browser "CORS" errors when your frontend talks to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Connect the Chat Router (The logic for Gist/Workshop/Write)
app.include_router(chat.router, prefix="/chat", tags=["chat"])

# 2. Mount the static directory for your HTML/JS
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    # Automatically take us to the UI when we open the site
    return RedirectResponse(url='/static/index.html')
# Add this to main.py (after app = FastAPI(...))
@app.get("/test")
async def test():
    from services.llm import gist
    try:
        result = gist([{"role": "user", "content": "Say 'Omo testing dey work' in Pidgin"}])
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}
if __name__ == "__main__":
    import uvicorn
    # reload=True is peak for vibe-coding; it restarts when you save a file
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)