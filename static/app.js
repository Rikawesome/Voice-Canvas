let currentSessionId = localStorage.getItem('voicecanvas_session_id') || null;
let autoTTSEnabled = true;

// =========================
// LIVE STATE ENGINE
// =========================
let isLiveMode = false;
let liveStream = null;

let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

let currentAudio = null;

// =========================
// DOM
// =========================
const inputField = document.getElementById('user-input');
const messagesDiv = document.getElementById('messages');
const micBtn = document.getElementById('mic-btn');
const sendBtn = document.getElementById('send-btn');
const ttsToggle = document.getElementById('toggle-tts-btn');
const castingModal = document.getElementById('casting-modal');
const charList = document.getElementById('character-list');

// =========================
// 💬 TEXT CHAT
// =========================
async function sendMessage() {
    const text = inputField.value.trim();
    if (!text) return;

    inputField.value = '';
    toggleInputButtons(false);

    appendMessage('user', text);
    const typingDiv = appendMessage('assistant', '...');

    try {
        const res = await fetch('/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: currentSessionId
            })
        });

        const data = await res.json();
        updateSessionState(data);

        animateText(typingDiv, data.reply);

        if (data.trigger_cast) {
            openCastingOffice(data.characters);
        }

        if (autoTTSEnabled && !data.trigger_cast) {
            speakExactText(data.reply);
        }

    } catch (e) {
        typingDiv.innerText = "Network wahala 😭";
    }
}

// =========================
// TEXT ANIMATION
// =========================
function animateText(element, text) {
    element.innerText = "";

    const words = text.split(" ");
    let i = 0;

    const interval = setInterval(() => {
        if (i < words.length) {
            element.innerText += words[i] + " ";
            i++;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        } else {
            clearInterval(interval);
        }
    }, 35);
}

// =========================
// 🔊 EXACT VOICE SYNC (FIXED)
// =========================
async function speakExactText(text) {
    try {
        const res = await fetch('/chat/speak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: currentSessionId
            })
        });

        if (!res.ok) return;

        const blob = await res.blob();
        playAudio(URL.createObjectURL(blob));

    } catch (e) {
        console.error("TTS error", e);
    }
}

// =========================
// 🔊 AUDIO PLAYER (INTERRUPT SAFE)
// =========================
function playAudio(source) {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }

    currentAudio = new Audio(source);
    currentAudio.play().catch(() => {});
}

// =========================
// 🎤 LIVE MODE ENGINE (FIXED CORE)
// =========================
micBtn.onclick = () => {
    if (!isLiveMode) {
        startLiveMode();
    } else {
        stopLiveMode();
    }
};

async function startLiveMode() {
    try {
        liveStream = await navigator.mediaDevices.getUserMedia({ audio: true });

        isLiveMode = true;
        micBtn.classList.add('active-live');
        micBtn.innerText = "🟢 LIVE";

        appendMessage("assistant", "🎙️ Live session ON — I'm listening...");

        startRecordingLoop(liveStream);

    } catch (e) {
        alert("Mic permission blocked");
    }
}

function stopLiveMode() {
    isLiveMode = false;

    micBtn.classList.remove('active-live');
    micBtn.innerText = "🎙️";

    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
    }

    if (liveStream) {
        liveStream.getTracks().forEach(t => t.stop());
        liveStream = null;
    }

    appendMessage("assistant", "🛑 Live session OFF");
}

// =========================
// 🔁 TRUE LIVE LOOP (KEY FIX)
// =========================
function startRecordingLoop(stream) {
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });

        if (isLiveMode) {
            await sendLiveAudio(blob);

            // 🔥 CRITICAL: keeps session alive
            startRecordingLoop(stream);
        }
    };

    mediaRecorder.start();
    isRecording = true;
}

// =========================
// 🎧 SEND LIVE AUDIO
// =========================
async function sendLiveAudio(blob) {
    const fd = new FormData();
    fd.append('audio', blob);
    if (currentSessionId) fd.append('session_id', currentSessionId);

    const typingDiv = appendMessage('assistant', '...');

    try {
        const res = await fetch('/chat/live-session', {
            method: 'POST',
            body: fd
        });

        const data = await res.json();
        updateSessionState(data);

        typingDiv.innerText = data.reply;

        if (data.audio) {
            playAudio("data:audio/mpeg;base64," + data.audio);
        }

        if (data.trigger_cast) {
            openCastingOffice(data.characters);
        }

    } catch (e) {
        typingDiv.innerText = "Mic error 😭";
    }
}

// =========================
// 🎭 CASTING OFFICE
// =========================
function openCastingOffice(characters) {
    charList.innerHTML = '';

    const voices = [
        { value: "narrator", label: "Narrator" },
        { value: "lead_male", label: "Lead Male" },
        { value: "lead_female", label: "Lead Female" },
        { value: "villain", label: "Villain" }
    ];

    const chars = characters || {};

    Object.keys(chars).forEach(name => {
        const card = document.createElement('div');
        card.className = 'char-card';

        card.innerHTML = `
            <div>
                <strong>${name}</strong><br>
                <small>${chars[name].vibe || 'Character'}</small>
            </div>

            <select class="voice-select" data-char="${name}">
                ${voices.map(v => `<option value="${v.value}">${v.label}</option>`).join('')}
            </select>
        `;

        charList.appendChild(card);
    });

    castingModal.style.display = 'flex';
    messagesDiv.style.opacity = '0.2';
}

// =========================
// 🎬 PRODUCTION
// =========================
async function handleProduction() {
    const cast = {};
    document.querySelectorAll('.voice-select').forEach(s => {
        cast[s.dataset.char] = s.value;
    });

    const lastMsg = [...document.querySelectorAll('.assistant')].pop();
    const scriptText = lastMsg?.innerText || "";

    castingModal.style.display = 'none';
    messagesDiv.style.opacity = '1';

    appendMessage("assistant", "🎬 Producing scene...");

    try {
        const res = await fetch('/chat/produce', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                script: scriptText,
                cast,
                session_id: currentSessionId
            })
        });

        if (!res.ok) {
            const errorData = await res.json().catch(() => null);
            const message = errorData?.details || errorData?.error || "Production failed";
            throw new Error(message);
        }

        const blob = await res.blob();
        playAudio(URL.createObjectURL(blob));

    } catch (e) {
        appendMessage("assistant", `Production failed: ${e.message}`);
    }
}

// =========================
// 🛠 UI HELPERS
// =========================
function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = text;

    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    return div;
}

function updateSessionState(data) {
    if (data.session_id) {
        currentSessionId = data.session_id;
        localStorage.setItem('voicecanvas_session_id', currentSessionId);
    }
}

function toggleInputButtons(hasText) {
    sendBtn.style.display = hasText ? 'flex' : 'none';
    micBtn.style.display = hasText ? 'none' : 'flex';
}

// =========================
// 🚀 INIT
// =========================
window.onload = () => {
    inputField.addEventListener('input', () =>
        toggleInputButtons(inputField.value.trim().length > 0)
    );

    sendBtn.onclick = sendMessage;
    inputField.onkeypress = (e) => {
        if (e.key === 'Enter') sendMessage();
    };

    document.getElementById('start-production-btn').onclick = handleProduction;

    ttsToggle.onclick = () => {
        autoTTSEnabled = !autoTTSEnabled;
        ttsToggle.innerText = autoTTSEnabled ? "🔊" : "🔇";
    };

    document.getElementById('new-session-btn').onclick = () => {
        localStorage.removeItem('voicecanvas_session_id');
        location.reload();
    };

    appendMessage("assistant", "VoiceCanvas ready 🎙️ — tap mic for live mode or type");
};
