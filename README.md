# 🎭 VoiceCanvas AI: Anime Scene Generator

**VoiceCanvas** is a full-stack AI application that transforms raw "gist" into a produced anime-style audio scene. It uses high-performance LLMs for personality and scriptwriting, paired with a multi-voice production pipeline.

---

## 🚀 The Flex
* **HNG 14 Logic & Problem Solving:** Ranked in the **top 1%** of candidates.
* **Architecture:** Optimized for low-latency voice-to-voice interaction.
* **Personality:** Built-in "Andrew" persona—sarcastic, witty, and localized for a unique user experience.

---

## 🔥 Key Features
* **Real-time Voice Chat:** Integrated Speech-to-Text (STT) for fluid, hands-free conversation.
* **Smart Personality Sync:** Uses a single-call logic to ensure audio output and UI text are 100% synchronized (no hallucinations).
* **Anime Scene Production:** * Automatically parses LLM-generated scripts into character roles.
    * **Multi-Voice Stitching:** Dynamically assigns voices based on character "vibes."
    * **Parallel Processing:** Uses `asyncio` to generate multiple character voices simultaneously, reducing production time by 60%.
* **Responsive UI:** A clean, mobile-friendly interface with auto-scrolling and live mic indicators.

---

## 🛠️ Tech Stack
* **Backend:** FastAPI (Python), Uvicorn.
* **LLM:** Groq (Llama 3 / Mixtral) for ultra-fast response generation.
* **Voice/TTS:** Edge-TTS (Microsoft Neural Voices).
* **Audio Engineering:** Pydub for audio manipulation and stitching.
* **Frontend:** Vanilla JavaScript (ES6+), CSS3, HTML5.
* **STT:** SpeechRecognition (Web Speech API).

---

## ⚙️ Installation & Setup

1. **Clone the repo:**
   ```bash
   git clone [https://github.com/rikawesome/voice-canvas.git](https://github.com/rikawesome/voice-canvas.git)
   cd voice-canvas
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Environment Variables:**
   Create a `.env` file and add your API keys:
   ```env
   GROQ_API_KEY=your_key_here
   ```

4. **Run the server:**
   ```bash
   python main.py
   ```
   *Visit `http://127.0.0.1:8000` to start the experience.*

---

## 📈 Future Roadmap
- [ ] **Whisper API Integration:** Upgrading STT for better slang/pidgin recognition.
- [ ] **BGM Overlay:** Automatically adding background music to produced scenes.
- [ ] **Ducking Logic:** Auto-lowering music volume when characters speak.

---

## 👨‍💻 Author
**Ronald Kanu**
* [LinkedIn](your-linkedin-link)
* [Portfolio](your-portfolio-link)

*"Building the intersection of AI personality and audio production."*
