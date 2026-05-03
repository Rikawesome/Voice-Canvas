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
let pendingImageFile = null;
let pendingImagePreviewUrl = null;

const CHAT_HISTORY_KEY = 'voicecanvas_chat_history';
const MODE_KEY = 'voicecanvas_mode';
const LAST_SCENE_KEY = 'voicecanvas_last_scene_script';

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
const mobileModeIndicator = document.getElementById('mobile-mode-indicator');
const mobileResetBtn = document.getElementById('mobile-reset-btn');
const mobileChatModeBtn = document.getElementById('mobile-chat-mode-btn');
const mobileWorkshopModeBtn = document.getElementById('mobile-workshop-mode-btn');
const mobileSceneModeBtn = document.getElementById('mobile-scene-mode-btn');
const composerChatModeBtn = document.getElementById('composer-chat-mode-btn');
const composerWorkshopModeBtn = document.getElementById('composer-workshop-mode-btn');
const composerSceneModeBtn = document.getElementById('composer-scene-mode-btn');
const attachBtn = document.getElementById('attach-btn');
const dnaInput = document.getElementById('dna-upload');
const attachmentChip = document.getElementById('attachment-chip');
const attachmentThumb = document.getElementById('attachment-thumb');
const attachmentName = document.getElementById('attachment-name');
const attachmentRemove = document.getElementById('attachment-remove');
const composerHint = document.getElementById('composer-hint');

const MODE_META = {
    gist: {
        label: 'GIST',
        placeholder: 'Type a message or add a photo...',
    },
    workshop: {
        label: 'WORKSHOP',
        placeholder: 'Shape the idea, plot beats, or drop a reference image...',
    },
    scene: {
        label: 'PRODUCTION',
        placeholder: 'Describe the scene or attach a character reference...',
    },
};

const PRODUCTION_VOICES = [
    { value: 'narrator', label: 'Narrator' },
    { value: 'lead_male', label: 'Lead Male' },
    { value: 'lead_female', label: 'Lead Female' },
    { value: 'villain', label: 'Villain' },
];

// =========================
// IMAGE ATTACHMENT / DNA
// =========================

if (attachBtn && dnaInput) {
    attachBtn.onclick = () => dnaInput.click();
}

if (dnaInput) {
    dnaInput.onchange = () => {
        const file = dnaInput.files[0];
        if (!file) return;

        if (pendingImagePreviewUrl) {
            URL.revokeObjectURL(pendingImagePreviewUrl);
        }

        pendingImageFile = file;
        pendingImagePreviewUrl = URL.createObjectURL(file);

        if (attachmentThumb) attachmentThumb.src = pendingImagePreviewUrl;
        if (attachmentName) attachmentName.innerText = file.name;
        if (attachmentChip) attachmentChip.classList.add('visible');
        if (composerHint) {
            composerHint.innerText = 'Send the photo with a caption like "This is Andrew" or just send the image.';
        }

        toggleInputButtons(inputField.value.trim().length > 0 || Boolean(pendingImageFile));
    };
}

if (attachmentRemove) {
    attachmentRemove.onclick = clearPendingImage;
}

function clearPendingImage() {
    pendingImageFile = null;

    if (dnaInput) dnaInput.value = '';
    if (attachmentChip) attachmentChip.classList.remove('visible');
    if (attachmentThumb) attachmentThumb.removeAttribute('src');
    if (attachmentName) attachmentName.innerText = '';
    if (composerHint) {
        composerHint.innerText = 'Add a photo with your message and Andrew will sort the DNA automatically.';
    }

    if (pendingImagePreviewUrl) {
        URL.revokeObjectURL(pendingImagePreviewUrl);
        pendingImagePreviewUrl = null;
    }

    toggleInputButtons(inputField.value.trim().length > 0);
}

// =========================
// MODE SYSTEM
// =========================

function setMode(mode) {
    currentMode = MODE_META[mode] ? mode : 'gist';

    document.body.dataset.mode = currentMode;
    localStorage.setItem(MODE_KEY, currentMode);

    if (modeIndicator) {
        modeIndicator.innerText = MODE_META[currentMode].label;
    }
    if (mobileModeIndicator) {
        mobileModeIndicator.innerText = MODE_META[currentMode].label;
    }

    if (inputField) {
        inputField.placeholder = MODE_META[currentMode].placeholder;
    }

    if (chatModeBtn) chatModeBtn.classList.toggle('active', currentMode === 'gist');
    if (workshopModeBtn) workshopModeBtn.classList.toggle('active', currentMode === 'workshop');
    if (sceneModeBtn) sceneModeBtn.classList.toggle('active', currentMode === 'scene');
    if (mobileChatModeBtn) mobileChatModeBtn.classList.toggle('active', currentMode === 'gist');
    if (mobileWorkshopModeBtn) mobileWorkshopModeBtn.classList.toggle('active', currentMode === 'workshop');
    if (mobileSceneModeBtn) mobileSceneModeBtn.classList.toggle('active', currentMode === 'scene');
    if (composerChatModeBtn) composerChatModeBtn.classList.toggle('active', currentMode === 'gist');
    if (composerWorkshopModeBtn) composerWorkshopModeBtn.classList.toggle('active', currentMode === 'workshop');
    if (composerSceneModeBtn) composerSceneModeBtn.classList.toggle('active', currentMode === 'scene');

    if (window.innerWidth <= 960) {
        closeMobileMenu();
    }

    updateLiveStatus();
}

function saveChatToLocal() {
    if (!messagesDiv) return;
    localStorage.setItem(CHAT_HISTORY_KEY, messagesDiv.innerHTML);
}

function loadChatFromLocal() {
    if (!messagesDiv) return false;

    const savedChat = localStorage.getItem(CHAT_HISTORY_KEY);
    if (!savedChat) return false;

    messagesDiv.innerHTML = savedChat;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    return true;
}

function saveLastSceneScript(scriptText) {
    lastSceneScript = scriptText || '';
    localStorage.setItem(LAST_SCENE_KEY, lastSceneScript);
}

function loadLastSceneScript() {
    lastSceneScript = localStorage.getItem(LAST_SCENE_KEY) || null;
}

function isMobileViewport() {
    return window.innerWidth <= 960;
}

function openMobileMenu() {
    return;
}

function closeMobileMenu() {
    return;
}

function toggleMobileMenu() {
    return;
}

function updateLiveStatus(detail = '') {
    if (!liveStatus) return;

    if (!isLiveMode) {
        liveStatus.classList.remove('active');
        liveStatus.innerHTML = '';
        return;
    }

    const modeLabel = MODE_META[currentMode]?.label || 'GIST';
    liveStatus.classList.add('active');
    liveStatus.innerHTML = `<strong>Live Voice Chat</strong> is on in ${modeLabel} mode.${detail ? ` ${detail}` : ''}`;
}

// =========================
// CHAT
// =========================

async function sendMessage() {
    const text = inputField.value.trim();
    const file = pendingImageFile;

    if (!text && !file) return;

    const displayText = text || '(Sent a photo)';

    inputField.value = '';
    clearPendingImage();
    toggleInputButtons(false);
    appendMessage('user', displayText);

    const typingDiv = appendMessage('assistant', '...');

    try {
        const formData = new FormData();
        formData.append('user_input', text);
        formData.append('mode', currentMode);

        if (file) {
            formData.append('file', file);
        }

        const res = await fetch(`/chat/message/${currentSessionId || 'new'}`, {
            method: 'POST',
            body: formData,
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data?.error || 'Request failed');
        }

        updateSessionState(data);

        if (data.trigger_cast) {
            saveLastSceneScript(data.reply || data.data || '');
            setMode('scene');
        }

        animateText(typingDiv, data.reply || data.data || '');

        if (data.dna_status) {
            appendMessage('system', data.dna_status);
        }

        // 🔥 Manga panel rendering support
        if (Array.isArray(data.panels) && data.panels.length > 0) {
            appendMangaPanels(data.panels);
        }

        if (data.manga_page) {
            appendMangaPage(data.manga_page);
        } else if (data.manga_page_url) {
            appendMangaPage(data.manga_page_url);
        }

        if (data.panel_error) {
            appendMessage('system', data.panel_error);
        }

        if (data.trigger_cast) {
            attachSceneActions(typingDiv, data.characters);
        }

        if (autoTTSEnabled && !data.trigger_cast) {
            speakExactText(data.reply || data.data || '');
        }

    } catch (e) {
        typingDiv.innerText = `Request failed: ${e.message}`;
        typingDiv.dataset.rawText = typingDiv.innerText;
    }
}

function animateText(element, text) {
    element.dataset.rawText = text;
    element.innerText = '';

    const words = String(text || '').split(' ');
    let i = 0;

    const interval = setInterval(() => {
        if (i < words.length) {
            element.innerText += words[i] + ' ';
            i += 1;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        } else {
            clearInterval(interval);
            saveChatToLocal();
        }
    }, 35);
}

// =========================
// TTS
// =========================

async function speakExactText(text) {
    if (!text || !text.trim()) return;

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

// =========================
// AUDIO PRODUCTION
// =========================

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
    saveChatToLocal();

    currentAudio = audio;
    audio.play().catch(() => {});
}

function attachSceneActions(messageElement, characters) {
    const actions = document.createElement('div');
    actions.className = 'scene-actions';

    const produceBtn = document.createElement('button');
    produceBtn.className = 'scene-action-btn';
    produceBtn.innerText = 'Cast and Produce';
    produceBtn.dataset.sceneAction = 'produce';

    const workshopBtn = document.createElement('button');
    workshopBtn.className = 'scene-action-btn';
    workshopBtn.innerText = 'Back to Workshop';
    workshopBtn.dataset.sceneAction = 'workshop';

    actions.appendChild(produceBtn);
    actions.appendChild(workshopBtn);
    messageElement.appendChild(actions);
    saveChatToLocal();
}

// =========================
// LIVE SESSION
// =========================

if (micBtn) {
    micBtn.onclick = () => {
        if (!isLiveMode) {
            startLiveMode();
        } else {
            stopLiveMode();
        }
    };
}

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
    micBtn.innerText = '🎙️';

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

        if (Array.isArray(data.panels) && data.panels.length > 0) {
            appendMangaPanels(data.panels);
        }

        if (data.trigger_cast) {
            saveLastSceneScript(data.reply || '');
            setMode('scene');
            attachSceneActions(typingDiv, data.characters);
        }

    } catch (e) {
        updateLiveStatus(`Error: ${e.message}`);
        typingDiv.innerText = `Mic error: ${e.message}`;
    }
}

// =========================
// CASTING OFFICE
// =========================

function openCastingOffice(characters) {
    if (!castingModal || !charList) return;

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
                <strong class="char-name">${name}</strong><br>
                <small class="char-vibe">${chars[name].vibe || 'Character'}</small>
            </div>

            <select class="voice-select" data-char="${name}">
                ${PRODUCTION_VOICES.map(voice =>
                    `<option value="${voice.value}" ${voice.value === selectedVoice ? 'selected' : ''}>${voice.label}</option>`
                ).join('')}
            </select>
        `;

        charList.appendChild(card);
    });

    castingModal.style.display = 'flex';
    messagesDiv.style.opacity = '0.2';
}

function closeCastingOffice() {
    if (castingModal) castingModal.style.display = 'none';
    if (messagesDiv) messagesDiv.style.opacity = '1';
}

async function handleProduction() {
    const cast = {};

    document.querySelectorAll('.voice-select').forEach(select => {
        cast[select.dataset.char] = select.value;
    });

    const scriptText = getLatestSceneScript();

    closeCastingOffice();

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

// =========================
// MESSAGE + MANGA UI
// =========================

function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = text;
    div.dataset.rawText = text;

    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    saveChatToLocal();

    return div;
}

function appendMangaPanels(entries = []) {
    if (!Array.isArray(entries) || entries.length === 0) return;

    const gallery = document.createElement('div');
    gallery.className = 'panel-gallery';

    entries.forEach((entry, index) => {
        const url = typeof entry === 'string' ? entry : entry?.url;
        if (!url) return;

        const card = document.createElement('div');
        card.className = 'panel-card';

        const header = document.createElement('div');
        header.className = 'panel-header';

        const title = document.createElement('div');
        title.className = 'panel-tag';
        title.innerText = `Panel ${index + 1}`;

        const speaker = document.createElement('div');
        speaker.className = 'panel-speaker';
        speaker.innerText = entry?.speaker ? String(entry.speaker) : 'Scene';

        header.appendChild(title);
        header.appendChild(speaker);

        const frame = document.createElement('div');
        frame.className = 'panel-frame';

        const img = document.createElement('img');
        img.src = url;
        img.alt = `Generated manga panel ${index + 1}`;
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';

        frame.appendChild(img);
        card.appendChild(header);
        card.appendChild(frame);
        gallery.appendChild(card);
    });

    if (!gallery.children.length) return;

    messagesDiv.appendChild(gallery);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    saveChatToLocal();
}

function appendMangaPage(source, label = 'Stitched manga page') {
    if (!source) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'message assistant manga-page-card';

    const title = document.createElement('div');
    title.className = 'manga-page-title';
    title.innerText = label;

    const img = document.createElement('img');
    img.src = source;
    img.alt = label;
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';

    wrapper.appendChild(title);
    wrapper.appendChild(img);
    messagesDiv.appendChild(wrapper);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    saveChatToLocal();
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

function toggleInputButtons(canSend) {
    if (!sendBtn || !micBtn) return;

    sendBtn.style.display = canSend ? 'flex' : 'none';
    micBtn.style.display = canSend ? 'none' : 'flex';
}

// =========================
// INIT
// =========================

    window.onload = () => {
    loadLastSceneScript();

    if (inputField) {
        inputField.addEventListener('input', () =>
            toggleInputButtons(inputField.value.trim().length > 0 || Boolean(pendingImageFile))
        );

        inputField.onkeypress = (event) => {
            if (event.key === 'Enter') {
                sendMessage();
            }
        };
    }

    if (sendBtn) sendBtn.onclick = sendMessage;

    if (chatModeBtn) chatModeBtn.onclick = () => setMode('gist');
    if (workshopModeBtn) workshopModeBtn.onclick = () => setMode('workshop');
    if (sceneModeBtn) sceneModeBtn.onclick = () => setMode('scene');
    if (mobileChatModeBtn) mobileChatModeBtn.onclick = () => setMode('gist');
    if (mobileWorkshopModeBtn) mobileWorkshopModeBtn.onclick = () => setMode('workshop');
    if (mobileSceneModeBtn) mobileSceneModeBtn.onclick = () => setMode('scene');
    if (composerChatModeBtn) composerChatModeBtn.onclick = () => setMode('gist');
    if (composerWorkshopModeBtn) composerWorkshopModeBtn.onclick = () => setMode('workshop');
    if (composerSceneModeBtn) composerSceneModeBtn.onclick = () => setMode('scene');
    const productionBtn = document.getElementById('start-production-btn');
    if (productionBtn) productionBtn.onclick = handleProduction;
    const closeCastingBtn = document.getElementById('close-casting-btn');
    if (closeCastingBtn) closeCastingBtn.onclick = closeCastingOffice;

    if (ttsToggle) {
        ttsToggle.onclick = () => {
            autoTTSEnabled = !autoTTSEnabled;
            ttsToggle.innerText = autoTTSEnabled ? '🔊' : '🔇';
        };
    }

    const newSessionBtn = document.getElementById('new-session-btn');
    const resetSession = () => {
        localStorage.removeItem('voicecanvas_session_id');
        localStorage.removeItem(CHAT_HISTORY_KEY);
        localStorage.removeItem(MODE_KEY);
        localStorage.removeItem(LAST_SCENE_KEY);
        location.reload();
    };
    if (newSessionBtn) {
        newSessionBtn.onclick = resetSession;
    }
    if (mobileResetBtn) {
        mobileResetBtn.onclick = resetSession;
    }

    if (messagesDiv) {
        messagesDiv.addEventListener('click', (event) => {
            const actionButton = event.target.closest('[data-scene-action]');
            if (!actionButton) return;

            const action = actionButton.dataset.sceneAction;
            if (action === 'produce') {
                openCastingOffice(inferSceneCharactersFromLastReply());
                return;
            }

            if (action === 'workshop') {
                setMode('workshop');
                inputField?.focus();
            }
        });
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeMobileMenu();
            closeCastingOffice();
        }
    });

    const restoredChat = loadChatFromLocal();
    const savedMode = localStorage.getItem(MODE_KEY) || 'gist';
    setMode(savedMode);
    toggleInputButtons(false);
    if (!restoredChat) {
        appendMessage('assistant', 'VoiceCanvas ready - send a message, attach a photo, or do both together.');
    }
};
