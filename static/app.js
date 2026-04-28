let currentSessionId = localStorage.getItem('voicecanvas_session_id') || null;
let autoTTSEnabled = true;
let currentMode = 'gist';

let isLiveMode = false;
let liveStream = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let currentAudio = null;
let lastSceneScript = null;

const inputField = document.getElementById('user-input');
const messagesDiv = document.getElementById('messages');
const micBtn = document.getElementById('mic-btn');
const sendBtn = document.getElementById('send-btn');
const ttsToggle = document.getElementById('toggle-tts-btn');
const castingModal = document.getElementById('casting-modal');
const charList = document.getElementById('character-list');
const liveStatus = document.getElementById('live-status');
const modeIndicator = document.getElementById('mode-indicator');
const chatModeBtn = document.getElementById('chat-mode-btn');
const workshopModeBtn = document.getElementById('workshop-mode-btn');
const sceneModeBtn = document.getElementById('scene-mode-btn');

const MODE_META = {
    gist: {
        label: 'GIST',
        placeholder: 'Wetin dey sup?...',
    },
    workshop: {
        label: 'WORKSHOP',
        placeholder: 'Shape the idea, plot beats, or story arc...',
    },
    scene: {
        label: 'PRODUCTION',
        placeholder: 'Describe the scene you want played out...',
    },
};

const PRODUCTION_VOICES = [
    { value: 'narrator', label: 'Narrator' },
    { value: 'lead_male', label: 'Lead Male' },
    { value: 'lead_female', label: 'Lead Female' },
    { value: 'villain', label: 'Villain' },
];

function setMode(mode) {
    currentMode = MODE_META[mode] ? mode : 'gist';
    document.body.dataset.mode = currentMode;
    modeIndicator.innerText = MODE_META[currentMode].label;
    inputField.placeholder = MODE_META[currentMode].placeholder;

    chatModeBtn.classList.toggle('active', currentMode === 'gist');
    workshopModeBtn.classList.toggle('active', currentMode === 'workshop');
    sceneModeBtn.classList.toggle('active', currentMode === 'scene');
    updateLiveStatus();
}

function updateLiveStatus(detail = '') {
    if (!isLiveMode) {
        liveStatus.classList.remove('active');
        liveStatus.innerHTML = '';
        return;
    }

    const modeLabel = MODE_META[currentMode]?.label || 'GIST';
    liveStatus.classList.add('active');
    liveStatus.innerHTML = `<strong>Live Voice Chat</strong> is on in ${modeLabel} mode.${detail ? ` ${detail}` : ''}`;
}

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
                session_id: currentSessionId,
                mode: currentMode,
            }),
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data?.error || 'Request failed');
        }

        updateSessionState(data);
        if (data.trigger_cast) {
            lastSceneScript = data.reply;
            setMode('scene');
        }

        animateText(typingDiv, data.reply);

        if (data.trigger_cast) {
            attachSceneActions(typingDiv, data.characters);
            openCastingOffice(data.characters);
        }

        if (autoTTSEnabled && !data.trigger_cast) {
            speakExactText(data.reply);
        }
    } catch (e) {
        typingDiv.innerText = `Request failed: ${e.message}`;
    }
}

function animateText(element, text) {
    element.dataset.rawText = text;
    element.innerText = '';

    const words = text.split(' ');
    let i = 0;

    const interval = setInterval(() => {
        if (i < words.length) {
            element.innerText += words[i] + ' ';
            i += 1;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        } else {
            clearInterval(interval);
        }
    }, 35);
}

async function speakExactText(text) {
    try {
        const res = await fetch('/chat/speak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: currentSessionId,
                mode: currentMode,
            }),
        });

        if (!res.ok) return;

        const blob = await res.blob();
        playAudio(URL.createObjectURL(blob));
    } catch (e) {
        console.error('TTS error', e);
    }
}

function playAudio(source) {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }

    currentAudio = new Audio(source);
    currentAudio.play().catch(() => {});
}

function showProducedAudio(source, label = 'Scene audio ready') {
    const container = document.createElement('div');
    container.className = 'message assistant';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '8px';

    const title = document.createElement('div');
    title.innerText = label;

    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'auto';
    audio.src = source;
    audio.style.width = '100%';

    const download = document.createElement('a');
    download.href = source;
    download.download = 'voicecanvas-scene.mp3';
    download.innerText = 'Download scene audio';
    download.style.color = '#7ee7cf';
    download.style.fontSize = '14px';

    container.appendChild(title);
    container.appendChild(audio);
    container.appendChild(download);
    messagesDiv.appendChild(container);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    currentAudio = audio;
    audio.play().catch(() => {});
}

function attachSceneActions(messageElement, characters) {
    const actions = document.createElement('div');
    actions.className = 'scene-actions';

    const produceBtn = document.createElement('button');
    produceBtn.className = 'scene-action-btn';
    produceBtn.innerText = 'Cast and Produce';
    produceBtn.onclick = () => openCastingOffice(characters);

    const workshopBtn = document.createElement('button');
    workshopBtn.className = 'scene-action-btn';
    workshopBtn.innerText = 'Back to Workshop';
    workshopBtn.onclick = () => {
        setMode('workshop');
        inputField.focus();
    };

    actions.appendChild(produceBtn);
    actions.appendChild(workshopBtn);
    messageElement.appendChild(actions);
}

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
        micBtn.innerText = 'LIVE';
        updateLiveStatus('Listening for your next take...');
        appendMessage('assistant', "Live session ON - I'm listening...");
        startRecordingLoop(liveStream);
    } catch (e) {
        alert('Mic permission blocked');
    }
}

function stopLiveMode() {
    isLiveMode = false;
    micBtn.classList.remove('active-live');
    micBtn.innerText = 'Mic';
    updateLiveStatus();

    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
    }

    if (liveStream) {
        liveStream.getTracks().forEach(track => track.stop());
        liveStream = null;
    }

    appendMessage('assistant', 'Live session OFF');
}

function startRecordingLoop(stream) {
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
            audioChunks.push(event.data);
        }
    };

    mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        if (isLiveMode) {
            updateLiveStatus('Transcribing and replying...');
            await sendLiveAudio(blob);
            startRecordingLoop(stream);
        }
    };

    mediaRecorder.start();
    isRecording = true;
}

async function sendLiveAudio(blob) {
    const fd = new FormData();
    fd.append('audio', blob);
    if (currentSessionId) {
        fd.append('session_id', currentSessionId);
    }
    fd.append('mode', currentMode);

    const typingDiv = appendMessage('assistant', '...');

    try {
        const res = await fetch('/chat/live-session', {
            method: 'POST',
            body: fd,
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data?.error || 'Live session failed');
        }

        updateSessionState(data);
        typingDiv.innerText = data.reply;
        typingDiv.dataset.rawText = data.reply;
        updateLiveStatus(data.user_text ? `Heard: "${data.user_text}"` : 'Listening for your next take...');

        if (data.audio) {
            playAudio('data:audio/mpeg;base64,' + data.audio);
        }

        if (data.trigger_cast) {
            lastSceneScript = data.reply;
            setMode('scene');
            attachSceneActions(typingDiv, data.characters);
            openCastingOffice(data.characters);
        }
    } catch (e) {
        updateLiveStatus(`Error: ${e.message}`);
        typingDiv.innerText = `Mic error: ${e.message}`;
    }
}

function openCastingOffice(characters) {
    charList.innerHTML = '';

    const chars = (characters && Object.keys(characters).length)
        ? characters
        : inferSceneCharactersFromLastReply();

    Object.keys(chars).forEach(name => {
        const card = document.createElement('div');
        card.className = 'char-card';
        const selectedVoice = chars[name].voice_mapping || guessVoiceForCharacter(name, chars[name]);

        card.innerHTML = `
            <div>
                <strong>${name}</strong><br>
                <small>${chars[name].vibe || 'Character'}</small>
            </div>

            <select class="voice-select" data-char="${name}">
                ${PRODUCTION_VOICES.map(voice => `<option value="${voice.value}" ${voice.value === selectedVoice ? 'selected' : ''}>${voice.label}</option>`).join('')}
            </select>
        `;

        charList.appendChild(card);
    });

    castingModal.style.display = 'flex';
    messagesDiv.style.opacity = '0.2';
}

async function handleProduction() {
    const cast = {};
    document.querySelectorAll('.voice-select').forEach(select => {
        cast[select.dataset.char] = select.value;
    });

    const scriptText = getLatestSceneScript();
    castingModal.style.display = 'none';
    messagesDiv.style.opacity = '1';
    appendMessage('assistant', 'Producing scene...');

    try {
        const res = await fetch('/chat/produce', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                script: scriptText,
                cast,
                session_id: currentSessionId,
            }),
        });

        if (!res.ok) {
            const errorData = await res.json().catch(() => null);
            const message = errorData?.details || errorData?.error || 'Production failed';
            throw new Error(message);
        }

        const blob = await res.blob();
        if (!blob.size) {
            throw new Error('Production returned empty audio');
        }

        const audioUrl = URL.createObjectURL(blob);
        showProducedAudio(audioUrl);
    } catch (e) {
        appendMessage('assistant', `Production failed: ${e.message}`);
    }
}

function inferSceneCharactersFromLastReply() {
    const scriptText = getLatestSceneScript();
    const characters = {};

    try {
        const parsed = JSON.parse(scriptText);
        if (!Array.isArray(parsed)) return characters;

        parsed.forEach(line => {
            const speaker = (line?.speaker || '').trim();
            if (!speaker) return;

            characters[speaker] = characters[speaker] || {
                vibe: 'Generated for this scene',
                voice_mapping: guessVoiceForCharacter(speaker),
            };
        });
    } catch (e) {
        console.warn('Unable to infer scene characters from last reply', e);
    }

    return characters;
}

function getLatestSceneScript() {
    if (lastSceneScript && lastSceneScript.trim()) {
        return lastSceneScript;
    }

    const assistantMessages = [...document.querySelectorAll('.assistant')];
    const lastMsg = assistantMessages[assistantMessages.length - 1];
    return lastMsg?.dataset?.rawText || lastMsg?.innerText || '';
}

function guessVoiceForCharacter(name, details = {}) {
    const lowered = (name || '').toLowerCase();
    const vibe = (details?.vibe || '').toLowerCase();

    if (lowered.includes('narrator') || vibe.includes('narrator')) {
        return 'narrator';
    }
    if (vibe.includes('female') || ['mikasa', 'historia', 'sasha', 'annie'].includes(lowered)) {
        return 'lead_female';
    }
    if (vibe.includes('villain') || ['reiner', 'zeke', 'villain'].includes(lowered)) {
        return 'villain';
    }

    return 'lead_male';
}

function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = text;
    div.dataset.rawText = text;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    return div;
}

function updateSessionState(data) {
    if (data.session_id) {
        currentSessionId = data.session_id;
        localStorage.setItem('voicecanvas_session_id', currentSessionId);
    }
    if (data.mode && MODE_META[data.mode]) {
        setMode(data.mode);
    }
}

function toggleInputButtons(hasText) {
    sendBtn.style.display = hasText ? 'flex' : 'none';
    micBtn.style.display = hasText ? 'none' : 'flex';
}

window.onload = () => {
    inputField.addEventListener('input', () =>
        toggleInputButtons(inputField.value.trim().length > 0)
    );

    sendBtn.onclick = sendMessage;
    chatModeBtn.onclick = () => setMode('gist');
    workshopModeBtn.onclick = () => setMode('workshop');
    sceneModeBtn.onclick = () => setMode('scene');

    inputField.onkeypress = (event) => {
        if (event.key === 'Enter') {
            sendMessage();
        }
    };

    document.getElementById('start-production-btn').onclick = handleProduction;

    ttsToggle.onclick = () => {
        autoTTSEnabled = !autoTTSEnabled;
        ttsToggle.innerText = autoTTSEnabled ? 'Audio On' : 'Audio Off';
    };

    document.getElementById('new-session-btn').onclick = () => {
        localStorage.removeItem('voicecanvas_session_id');
        location.reload();
    };

    ttsToggle.innerText = 'Audio On';
    micBtn.innerText = 'Mic';
    setMode('gist');
    appendMessage('assistant', 'VoiceCanvas ready - gist, workshop, or produce a full scene.');
};
