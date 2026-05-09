let currentSessionId = localStorage.getItem('voicecanvas_session_id') || null;
let autoTTSEnabled = true;
let currentMode = 'gist';

let isLiveMode = false;
let liveStream = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let currentAudio = null;

let pendingImageFile = null;
let pendingImagePreviewUrl = null;

let lightboxImages = [];
let lightboxIndex = 0;
let lightboxTouchStartX = 0;
let activeBubbleDrag = null;

const inputField = document.getElementById('user-input');
const messagesDiv = document.getElementById('messages');
const micBtn = document.getElementById('mic-btn');
const sendBtn = document.getElementById('send-btn');

const chatModeBtn = document.getElementById('chat-mode-btn');
const workshopModeBtn = document.getElementById('workshop-mode-btn');
const sceneModeBtn = document.getElementById('scene-mode-btn');

const mobileChatModeBtn = document.getElementById('mobile-chat-mode-btn');
const mobileWorkshopModeBtn = document.getElementById('mobile-workshop-mode-btn');
const mobileSceneModeBtn = document.getElementById('mobile-scene-mode-btn');

const composerChatModeBtn = document.getElementById('composer-chat-mode-btn');
const composerWorkshopModeBtn = document.getElementById('composer-workshop-mode-btn');
const composerSceneModeBtn = document.getElementById('composer-scene-mode-btn');

const modeIndicator = document.getElementById('mode-indicator');
const mobileModeIndicator = document.getElementById('mobile-mode-indicator');

const attachBtn = document.getElementById('attach-btn');
const dnaInput = document.getElementById('dna-upload');

const attachmentChip = document.getElementById('attachment-chip');
const attachmentThumb = document.getElementById('attachment-thumb');
const attachmentName = document.getElementById('attachment-name');
const attachmentRemove = document.getElementById('attachment-remove');

const desktopTestMangaBtn = document.getElementById('test-manga-ui-btn');
const mobileTestMangaBtn = document.getElementById('mobile-test-manga-ui-btn');
const newSessionBtn = document.getElementById('new-session-btn');
const mobileResetBtn = document.getElementById('mobile-reset-btn');

const lightbox = document.getElementById('image-lightbox');
const lightboxImage = document.getElementById('lightbox-image');
const lightboxCloseBtn = document.getElementById('lightbox-close');
const lightboxPrevBtn = document.getElementById('lightbox-prev');
const lightboxNextBtn = document.getElementById('lightbox-next');
const lightboxCounter = document.getElementById('lightbox-counter');

const MODE_META = {
    gist: { label: 'GIST', placeholder: 'Drop an idea...' },
    workshop: { label: 'WORKSHOP', placeholder: 'Develop the story, lore, characters...' },
    scene: { label: 'PRODUCTION', placeholder: 'Describe the exact manga scene...' }
};

const BUBBLE_STYLE_CYCLE = ['speech', 'thought', 'shout', 'caption', 'sfx'];
const PROJECT_STORAGE_KEY = 'voicecanvas_project_v2';

let projectState = { messages: [] };

// =========================
// MANGA-STYLE PLACEHOLDER GENERATOR (FIXED)
// =========================

function createMangaStylePlaceholder({ seed = 'panel', width = 600, height = 800, panelNumber = 1 }) {
    const hash = Array.from(seed).reduce((sum, char) => sum + char.charCodeAt(0), 0);
    
    const bgVariants = [
        '#f5f5f0', '#f0ece4', '#faf7f0', '#f2efe8'
    ];
    const bgColor = bgVariants[(panelNumber - 1) % bgVariants.length];
    
    const getCharacterSVG = (pNum) => {
        const w = width, h = height;
        
        switch(pNum) {
            case 1:
                return `<g transform="translate(${w/4}, ${h/2})">
                    <ellipse cx="0" cy="30" rx="35" ry="70" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="0" cy="-40" r="30" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="-12" cy="-45" r="6" fill="#1a1a20"/>
                    <circle cx="12" cy="-45" r="6" fill="#1a1a20"/>
                    <path d="M-10,-28 Q0,-18 10,-28" stroke="#1a1a20" stroke-width="2.5" fill="none"/>
                </g>
                <g transform="translate(${w * 3/4}, ${h/2})">
                    <ellipse cx="0" cy="30" rx="40" ry="75" fill="#3a3a48" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="0" cy="-45" r="35" fill="#3a3a48" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="-15" cy="-50" r="7" fill="#1a1a20"/>
                    <circle cx="15" cy="-50" r="7" fill="#1a1a20"/>
                    <path d="M-12,-32 Q0,-22 12,-32" stroke="#1a1a20" stroke-width="2.5" fill="none"/>
                </g>`;
            case 2:
                return `<g transform="translate(${w/2}, ${h/2 + 20})">
                    <ellipse cx="-20" cy="20" rx="45" ry="85" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="-20" cy="-45" r="40" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="-40" cy="-52" r="9" fill="#1a1a20"/>
                    <circle cx="-5" cy="-52" r="9" fill="#1a1a20"/>
                    <path d="M-40,-30 L-20,-15 L-5,-30" stroke="#1a1a20" stroke-width="3" fill="none"/>
                    <line x1="30" y1="-80" x2="100" y2="-60" stroke="#888" stroke-width="2.5" stroke-linecap="round"/>
                    <line x1="35" y1="-45" x2="110" y2="-25" stroke="#888" stroke-width="2.5" stroke-linecap="round"/>
                    <line x1="30" y1="-15" x2="90" y2="5" stroke="#888" stroke-width="2.5" stroke-linecap="round"/>
                </g>`;
            case 3:
                return `<rect x="${w*0.05}" y="${h*0.3}" width="${w*0.12}" height="${h*0.65}" fill="#3a3a48" stroke="#1a1a20" stroke-width="2"/>
                    <rect x="${w*0.2}" y="${h*0.2}" width="${w*0.15}" height="${h*0.75}" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                    <rect x="${w*0.4}" y="${h*0.35}" width="${w*0.1}" height="${h*0.6}" fill="#4a4a58" stroke="#1a1a20" stroke-width="2"/>
                    <rect x="${w*0.55}" y="${h*0.25}" width="${w*0.18}" height="${h*0.7}" fill="#353542" stroke="#1a1a20" stroke-width="2"/>
                    <rect x="${w*0.78}" y="${h*0.4}" width="${w*0.12}" height="${h*0.55}" fill="#3a3a48" stroke="#1a1a20" stroke-width="2"/>
                    <g transform="translate(${w/2}, ${h - h*0.2})">
                        <ellipse cx="0" cy="15" rx="20" ry="40" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                        <circle cx="0" cy="-20" r="18" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                        <circle cx="-8" cy="-23" r="4" fill="#1a1a20"/>
                        <circle cx="8" cy="-23" r="4" fill="#1a1a20"/>
                    </g>`;
            default:
                return `<g transform="translate(${w/2}, ${h/2 + 30})">
                    <ellipse cx="0" cy="20" rx="40" ry="75" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="0" cy="-40" r="38" fill="#2a2a35" stroke="#1a1a20" stroke-width="2"/>
                    <circle cx="-14" cy="-46" r="8" fill="#1a1a20"/>
                    <circle cx="14" cy="-46" r="8" fill="#1a1a20"/>
                    <ellipse cx="0" cy="-20" rx="12" ry="8" fill="#1a1a20"/>
                    <path d="M-40,-60 Q-45,-80 -35,-100" stroke="#5a8aaa" stroke-width="2" fill="none"/>
                </g>`;
        }
    };
    
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="100%" height="100%">
        <defs>
            <pattern id="halftone${panelNumber}" width="10" height="10" patternUnits="userSpaceOnUse">
                <circle cx="2" cy="2" r="1.2" fill="#333" opacity="0.1"/>
                <circle cx="7" cy="7" r="0.8" fill="#333" opacity="0.06"/>
            </pattern>
        </defs>
        
        <rect width="${width}" height="${height}" fill="${bgColor}"/>
        <rect width="${width}" height="${height}" fill="url(#halftone${panelNumber})" opacity="0.4"/>
        
        ${getCharacterSVG(panelNumber)}
        
        <rect x="3" y="3" width="${width-6}" height="${height-6}" fill="none" stroke="#1a1a1a" stroke-width="6"/>
        <rect x="8" y="8" width="${width-16}" height="${height-16}" fill="none" stroke="#333" stroke-width="1.5"/>
        
        <path d="M0,0 L20,0 L0,20 Z" fill="#1a1a1a"/>
        <path d="M${width},0 L${width-20},0 L${width},20 Z" fill="#1a1a1a"/>
        <path d="M0,${height} L20,${height} L0,${height-20} Z" fill="#1a1a1a"/>
        <path d="M${width},${height} L${width-20},${height} L${width},${height-20} Z" fill="#1a1a1a"/>
    </svg>`;
    
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

const PLACEHOLDER_PANEL_IMAGES = [
    createMangaStylePlaceholder({ seed: 'panel-1', panelNumber: 1, width: 600, height: 800 }),
    createMangaStylePlaceholder({ seed: 'panel-2', panelNumber: 2, width: 600, height: 800 }),
    createMangaStylePlaceholder({ seed: 'panel-3', panelNumber: 3, width: 600, height: 800 }),
    createMangaStylePlaceholder({ seed: 'panel-4', panelNumber: 4, width: 600, height: 800 })
];

const PLACEHOLDER_PAGE_IMAGE = createMangaStylePlaceholder({ seed: 'page', panelNumber: 1, width: 1200, height: 1600 });

function normalizeBubbles(bubbles = []) {
    if (!Array.isArray(bubbles) || bubbles.length === 0) {
        return [
            { text: "What are you doing here?", x: 0.08, y: 0.12, w: 0.32, type: "speech", tail: "bottom-left" },
            { text: "I've been looking for you.", x: 0.52, y: 0.08, w: 0.34, type: "speech", tail: "bottom-right" },
            { text: "We need to talk.", x: 0.12, y: 0.48, w: 0.28, type: "shout", tail: "top-left" },
            { text: "KRACK", x: 0.68, y: 0.62, w: 0.14, type: "sfx", tail: "none" }
        ];
    }
    return bubbles.map(cloneBubbleData);
}

function cloneBubbleData(bubble = {}) {
    const x = typeof bubble.x === 'number' ? bubble.x : 0.14;
    const y = typeof bubble.y === 'number' ? bubble.y : 0.12;
    const type = bubble.type || bubble.style || 'speech';
    return {
        text: bubble.text || '...',
        x, y,
        w: typeof bubble.w === 'number' ? bubble.w : 0.34,
        type,
        tail: bubble.tail || inferTailFromPosition(x, y, type)
    };
}

function inferTailFromPosition(x, y, type = 'speech') {
    if (type === 'caption' || type === 'sfx') return 'bottom-left';
    const vertical = y <= 0.24 ? 'bottom' : 'top';
    const horizontal = x >= 0.52 ? 'right' : 'left';
    return `${vertical}-${horizontal}`;
}

function applyBubbleLayoutDefaults(bubbles = []) {
    return bubbles.map((bubble, index) => {
        const type = bubble.type || 'speech';
        const width = estimateBubbleWidth(bubble.text || '...', type);
        const placement = inferBubblePlacement(index, bubbles.length, type, bubble.x, bubble.y, width);
        return {
            ...bubble,
            x: placement.x, y: placement.y, w: width,
            tail: bubble.tail || inferTailFromPosition(placement.x, placement.y, type)
        };
    });
}

function estimateBubbleWidth(text = '', type = 'speech') {
    const normalized = String(text).trim().replace(/\s+/g, ' ');
    const length = normalized.length || 1;
    const longestWord = normalized.split(' ').reduce((max, word) => Math.max(max, word.length), 0);
    let width;
    if (type === 'caption') width = 0.22 + Math.min(0.18, length / 220);
    else if (type === 'sfx') width = 0.16 + Math.min(0.12, longestWord / 80);
    else if (type === 'shout') width = 0.24 + Math.min(0.16, length / 150);
    else if (type === 'thought') width = 0.24 + Math.min(0.16, length / 170);
    else width = 0.23 + Math.min(0.18, length / 165);
    width = Math.max(width, 0.16 + Math.min(0.2, longestWord / 60));
    return Math.min(0.56, Math.max(0.18, Number(width.toFixed(3))));
}

function inferBubblePlacement(index, total, type, x, y, width) {
    const hasManualX = typeof x === 'number';
    const hasManualY = typeof y === 'number';
    if (hasManualX && hasManualY) {
        return { x: clampValue(x, 0.04, 0.92 - width), y: clampValue(y, 0.04, 0.8) };
    }
    const presets = total > 1 ? [{ x: 0.08, y: 0.08 }, { x: 0.56, y: 0.16 }, { x: 0.1, y: 0.56 }, { x: 0.54, y: 0.66 }] : [{ x: 0.1, y: 0.1 }];
    const chosen = presets[Math.min(index, presets.length - 1)];
    if (type === 'caption') return { x: hasManualX ? clampValue(x, 0.04, 0.92 - width) : 0.08, y: hasManualY ? clampValue(y, 0.04, 0.8) : 0.05 };
    if (type === 'sfx') return { x: hasManualX ? clampValue(x, 0.04, 0.92 - width) : (index % 2 === 0 ? 0.62 : 0.12), y: hasManualY ? clampValue(y, 0.04, 0.8) : (index % 2 === 0 ? 0.58 : 0.64) };
    return { x: hasManualX ? clampValue(x, 0.04, 0.92 - width) : clampValue(chosen.x, 0.04, 0.92 - width), y: hasManualY ? clampValue(y, 0.04, 0.8) : chosen.y };
}

function clampValue(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function clonePanelData(panel = {}) {
    return { image_url: panel.image_url || panel.url || '', speaker: panel.speaker || 'Scene', bubbles: normalizeBubbles(panel.bubbles).map(cloneBubbleData) };
}

function clonePageData(page = {}) {
    return { image_url: page.image_url || page.url || '', label: page.label || 'Generated manga page', bubbles: normalizeBubbles(page.bubbles).map(cloneBubbleData) };
}

function createBubbleLayer(bubbles = [], location = {}) {
    const layer = document.createElement('div');
    layer.className = 'bubble-layer';
    bubbles.forEach((bubble, index) => {
        const node = document.createElement('div');
        node.className = 'speech-bubble';
        node.dataset.style = bubble.type || bubble.style || 'speech';
        node.dataset.tail = bubble.tail || 'bottom-left';
        node.style.left = `${(bubble.x || 0) * 100}%`;
        node.style.top = `${(bubble.y || 0) * 100}%`;
        node.style.width = `${Math.max(16, (bubble.w || 0.28) * 100)}%`;
        node.dataset.messageIndex = String(location.messageIndex ?? -1);
        node.dataset.panelIndex = String(location.panelIndex ?? -1);
        node.dataset.bubbleIndex = String(index);
        
        const toolbar = document.createElement('div');
        toolbar.className = 'bubble-toolbar';
        const dragTool = document.createElement('button');
        dragTool.className = 'bubble-tool'; dragTool.type = 'button'; dragTool.dataset.action = 'drag'; dragTool.innerText = 'Move';
        const styleTool = document.createElement('button');
        styleTool.className = 'bubble-tool'; styleTool.type = 'button'; styleTool.dataset.action = 'style'; styleTool.innerText = 'Type';
        toolbar.appendChild(dragTool); toolbar.appendChild(styleTool);
        
        const text = document.createElement('div');
        text.className = 'bubble-text';
        text.contentEditable = 'true';
        text.spellcheck = false;
        text.innerText = bubble.text || '...';
        
        const handle = document.createElement('div');
        handle.className = 'bubble-handle';
        handle.dataset.action = 'resize';
        
        node.appendChild(toolbar);
        node.appendChild(text);
        node.appendChild(handle);
        layer.appendChild(node);
    });
    return layer;
}

function renderMangaPage(page = {}, messageIndex = 0) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message assistant manga-page-card';
    const top = document.createElement('div');
    top.className = 'manga-page-top';
    const title = document.createElement('div');
    title.className = 'manga-page-title';
    title.innerText = page.label || 'Generated manga page';
    const hint = document.createElement('div');
    hint.className = 'manga-page-hint';
    hint.innerText = 'Tap to view fullscreen';
    top.appendChild(title); top.appendChild(hint);
    const button = document.createElement('div');
    button.className = 'manga-page-preview';
    button.tabIndex = 0;
    button.setAttribute('role', 'button');
    button.dataset.lightboxImages = JSON.stringify([page.image_url]);
    button.dataset.lightboxIndex = '0';
    const img = document.createElement('img');
    img.src = page.image_url;
    img.alt = page.label || 'Generated manga page';
    button.appendChild(img);
    button.appendChild(createBubbleLayer(normalizeBubbles(page.bubbles), { messageIndex, panelIndex: null }));
    wrapper.appendChild(top); wrapper.appendChild(button);
    return wrapper;
}

function renderMangaPanels(entries = [], messageIndex = 0) {
    if (!Array.isArray(entries) || entries.length === 0) return null;
    const gallery = document.createElement('div');
    gallery.className = 'panel-gallery';
    const title = document.createElement('div');
    title.className = 'panel-gallery-title';
    title.innerHTML = `<strong>Panels</strong><span>Tap to view fullscreen</span>`;
    gallery.appendChild(title);
    const grid = document.createElement('div');
    grid.className = 'panel-grid';
    const urls = entries.map(item => typeof item === 'string' ? item : (item.url || item.image_url));
    entries.forEach((entry, index) => {
        const url = typeof entry === 'string' ? entry : (entry.url || entry.image_url);
        const speaker = typeof entry === 'string' ? 'Scene' : (entry.speaker || 'Scene');
        const card = document.createElement('div');
        card.className = 'panel-card';
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        card.dataset.lightboxImages = JSON.stringify(urls);
        card.dataset.lightboxIndex = String(index);
        const frame = document.createElement('div');
        frame.className = 'panel-frame';
        const img = document.createElement('img');
        img.src = url;
        frame.appendChild(img);
        frame.appendChild(createBubbleLayer(normalizeBubbles(typeof entry === 'string' ? [] : entry.bubbles), { messageIndex, panelIndex: index }));
        const header = document.createElement('div');
        header.className = 'panel-header';
        const idx = document.createElement('div');
        idx.className = 'panel-index';
        idx.innerText = `Panel ${index + 1}`;
        const sp = document.createElement('div');
        sp.className = 'panel-speaker';
        sp.innerText = speaker;
        header.appendChild(idx); header.appendChild(sp);
        card.appendChild(frame); card.appendChild(header);
        grid.appendChild(card);
    });
    gallery.appendChild(grid);
    return gallery;
}

function appendMessage(role, text) {
    projectState.messages.push({ kind: 'text', role, text });
    saveProjectState();
    renderProjectState();
}

function appendMangaPageFromData(page = {}) {
    projectState.messages.push({ kind: 'manga-page', page: clonePageData(page) });
    saveProjectState();
    renderProjectState();
}

function appendMangaPanels(entries = []) {
    if (!Array.isArray(entries) || entries.length === 0) return;
    projectState.messages.push({ kind: 'panel-gallery', panels: entries.map(clonePanelData) });
    saveProjectState();
    renderProjectState();
}

function saveProjectState() {
    localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(projectState));
}

function renderProjectState() {
    messagesDiv.innerHTML = '';
    projectState.messages.forEach((entry, index) => {
        let node = null;
        if (entry.kind === 'text') {
            node = document.createElement('div');
            node.className = `message ${entry.role}`;
            node.innerText = entry.text;
        } else if (entry.kind === 'manga-page') {
            node = renderMangaPage(entry.page, index);
        } else if (entry.kind === 'panel-gallery') {
            node = renderMangaPanels(entry.panels, index);
        }
        if (node) messagesDiv.appendChild(node);
    });
    hydrateSavedMediaCards();
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function hydrateSavedMediaCards() {
    const pageCards = messagesDiv.querySelectorAll('.manga-page-preview');
    pageCards.forEach((card) => {
        const img = card.querySelector('img');
        if (!img || card.dataset.lightboxImages) return;
        card.dataset.lightboxImages = JSON.stringify([img.src]);
        card.dataset.lightboxIndex = '0';
    });
    const panelCards = messagesDiv.querySelectorAll('.panel-card');
    panelCards.forEach((card, index) => {
        if (card.dataset.lightboxImages) return;
        const gallery = card.closest('.panel-gallery');
        const panelImages = gallery ? Array.from(gallery.querySelectorAll('.panel-card img')).map((img) => img.src).filter(Boolean) : [];
        const imageIndex = panelImages.findIndex((src) => { const currentImage = card.querySelector('img'); return currentImage && currentImage.src === src; });
        if (!panelImages.length) return;
        card.dataset.lightboxImages = JSON.stringify(panelImages);
        card.dataset.lightboxIndex = String(imageIndex >= 0 ? imageIndex : index);
    });
}

function getBubbleStateTarget(node) {
    const messageIndex = Number(node.dataset.messageIndex);
    const panelIndex = Number(node.dataset.panelIndex);
    const bubbleIndex = Number(node.dataset.bubbleIndex);
    const message = projectState.messages[messageIndex];
    if (!message || Number.isNaN(bubbleIndex)) return null;
    if (message.kind === 'manga-page') return message.page?.bubbles?.[bubbleIndex] || null;
    if (message.kind === 'panel-gallery') return message.panels?.[panelIndex]?.bubbles?.[bubbleIndex] || null;
    return null;
}

function syncBubbleNodeToState(node) {
    const target = getBubbleStateTarget(node);
    if (!target) return;
    target.text = node.querySelector('.bubble-text')?.innerText?.trim() || '...';
    target.type = node.dataset.style || 'speech';
    target.x = clampPercent(node.style.left, 0.02, 0.88);
    target.y = clampPercent(node.style.top, 0.02, 0.88);
    target.w = clampPercent(node.style.width, 0.16, 0.72);
    target.tail = inferTailFromPosition(target.x, target.y, target.type);
    node.dataset.tail = target.tail;
}

function clampPercent(value, min, max) {
    const numeric = Number.parseFloat(value) / 100;
    if (Number.isNaN(numeric)) return min;
    return Math.min(max, Math.max(min, numeric));
}

function runUIDemo() {
    appendMessage('assistant', 'Demo manga generated successfully.');
    appendMangaPageFromData({ image_url: PLACEHOLDER_PAGE_IMAGE, label: 'Demo manga page', bubbles: [] });
    appendMangaPanels([
        { image_url: PLACEHOLDER_PANEL_IMAGES[0], speaker: 'Opening', bubbles: [] },
        { image_url: PLACEHOLDER_PANEL_IMAGES[1], speaker: 'Reaction', bubbles: [] },
        { image_url: PLACEHOLDER_PANEL_IMAGES[2], speaker: 'Conflict', bubbles: [] },
        { image_url: PLACEHOLDER_PANEL_IMAGES[3], speaker: 'Finale', bubbles: [] }
    ]);
}

function setMode(mode) {
    currentMode = MODE_META[mode] ? mode : 'gist';
    if (modeIndicator) modeIndicator.innerText = MODE_META[currentMode].label;
    if (mobileModeIndicator) mobileModeIndicator.innerText = MODE_META[currentMode].label;
    if (inputField) inputField.placeholder = MODE_META[currentMode].placeholder;
    
    const toggleActive = (element, state) => { if (element) element.classList.toggle('active', state); };
    toggleActive(chatModeBtn, mode === 'gist');
    toggleActive(workshopModeBtn, mode === 'workshop');
    toggleActive(sceneModeBtn, mode === 'scene');
    toggleActive(mobileChatModeBtn, mode === 'gist');
    toggleActive(mobileWorkshopModeBtn, mode === 'workshop');
    toggleActive(mobileSceneModeBtn, mode === 'scene');
    toggleActive(composerChatModeBtn, mode === 'gist');
    toggleActive(composerWorkshopModeBtn, mode === 'workshop');
    toggleActive(composerSceneModeBtn, mode === 'scene');
    localStorage.setItem('voicecanvas_mode', mode);
}

function loadChat() {
    const saved = localStorage.getItem(PROJECT_STORAGE_KEY);
    if (!saved) return false;
    try {
        const parsed = JSON.parse(saved);
        if (!parsed || !Array.isArray(parsed.messages)) return false;
        projectState = parsed;
        renderProjectState();
        return true;
    } catch (error) {
        console.error('Project restore error:', error);
        return false;
    }
}

function resetSession() {
    localStorage.removeItem(PROJECT_STORAGE_KEY);
    projectState = { messages: [] };
    messagesDiv.innerHTML = '';
    appendMessage('assistant', 'Session reset successfully.');
}

// =========================
// EVENT BINDINGS
// =========================

sendBtn.onclick = () => {
    const text = inputField.value.trim();
    if (!text && !pendingImageFile) return;
    if (text) appendMessage('user', text);
    inputField.value = '';
    setTimeout(() => runUIDemo(), 500);
    if (pendingImageFile) { pendingImageFile = null; if (attachmentChip) attachmentChip.classList.remove('visible'); }
};

if (attachBtn && dnaInput) {
    attachBtn.onclick = () => dnaInput.click();
    dnaInput.onchange = () => {
        const file = dnaInput.files[0];
        if (!file) return;
        pendingImageFile = file;
        if (pendingImagePreviewUrl) URL.revokeObjectURL(pendingImagePreviewUrl);
        pendingImagePreviewUrl = URL.createObjectURL(file);
        if (attachmentChip) attachmentChip.classList.add('visible');
        if (attachmentThumb) attachmentThumb.src = pendingImagePreviewUrl;
        if (attachmentName) attachmentName.innerText = file.name;
    };
}

if (attachmentRemove) {
    attachmentRemove.onclick = () => {
        pendingImageFile = null;
        if (dnaInput) dnaInput.value = '';
        if (attachmentChip) attachmentChip.classList.remove('visible');
        if (attachmentThumb) attachmentThumb.removeAttribute('src');
        if (attachmentName) attachmentName.innerText = '';
        if (pendingImagePreviewUrl) { URL.revokeObjectURL(pendingImagePreviewUrl); pendingImagePreviewUrl = null; }
    };
}

chatModeBtn.onclick = () => setMode('gist');
workshopModeBtn.onclick = () => setMode('workshop');
sceneModeBtn.onclick = () => setMode('scene');
mobileChatModeBtn.onclick = () => setMode('gist');
mobileWorkshopModeBtn.onclick = () => setMode('workshop');
mobileSceneModeBtn.onclick = () => setMode('scene');
composerChatModeBtn.onclick = () => setMode('gist');
composerWorkshopModeBtn.onclick = () => setMode('workshop');
composerSceneModeBtn.onclick = () => setMode('scene');

if (desktopTestMangaBtn) desktopTestMangaBtn.onclick = runUIDemo;
if (mobileTestMangaBtn) mobileTestMangaBtn.onclick = runUIDemo;
if (newSessionBtn) newSessionBtn.onclick = resetSession;
if (mobileResetBtn) mobileResetBtn.onclick = resetSession;

function openMobileMenu() { document.body.classList.add('mobile-menu-open'); }
function closeMobileMenu() { document.body.classList.remove('mobile-menu-open'); }
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
if (mobileMenuBtn) mobileMenuBtn.onclick = (e) => { e.stopPropagation(); document.body.classList.toggle('mobile-menu-open'); };
document.addEventListener('click', () => { if (window.innerWidth <= 960) closeMobileMenu(); });

messagesDiv.addEventListener('click', (event) => {
    if (event.target.closest('.speech-bubble')) return;
    const target = event.target.closest('[data-lightbox-images], .panel-card, .manga-page-preview, .panel-frame img, .manga-page-preview img');
    if (!target) return;
    try {
        const activator = target.matches('[data-lightbox-images]') ? target : target.closest('.panel-card, .manga-page-preview');
        if (!activator) return;
        if (!activator.dataset.lightboxImages) hydrateSavedMediaCards();
        const images = JSON.parse(activator.dataset.lightboxImages || '[]');
        const index = Number(activator.dataset.lightboxIndex || '0');
        if (images.length) openLightbox(images, index);
    } catch (error) { console.error('Lightbox payload error:', error); }
});

function openLightbox(images = [], index = 0) {
    lightboxImages = images.filter(Boolean);
    if (!lightboxImages.length) return;
    lightboxIndex = index;
    if (lightboxImage) lightboxImage.src = lightboxImages[lightboxIndex];
    if (lightboxCounter) lightboxCounter.innerText = `${lightboxIndex + 1} / ${lightboxImages.length}`;
    if (lightbox) lightbox.classList.add('active');
    document.body.classList.add('lightbox-open');
}
function closeLightbox() { if (lightbox) lightbox.classList.remove('active'); document.body.classList.remove('lightbox-open'); }
function showLightboxImage(direction) { lightboxIndex = (lightboxIndex + direction + lightboxImages.length) % lightboxImages.length; if (lightboxImage) lightboxImage.src = lightboxImages[lightboxIndex]; if (lightboxCounter) lightboxCounter.innerText = `${lightboxIndex + 1} / ${lightboxImages.length}`; }
if (lightboxCloseBtn) lightboxCloseBtn.onclick = closeLightbox;
if (lightboxPrevBtn) lightboxPrevBtn.onclick = () => showLightboxImage(-1);
if (lightboxNextBtn) lightboxNextBtn.onclick = () => showLightboxImage(1);
if (lightbox) lightbox.onclick = (e) => { if (e.target === lightbox) closeLightbox(); };
if (lightbox) lightbox.addEventListener('touchstart', (e) => { lightboxTouchStartX = e.changedTouches[0].screenX; }, { passive: true });
if (lightbox) lightbox.addEventListener('touchend', (e) => { const diff = e.changedTouches[0].screenX - lightboxTouchStartX; if (Math.abs(diff) > 50) showLightboxImage(diff > 0 ? -1 : 1); }, { passive: true });

messagesDiv.addEventListener('focusin', (event) => { const bubble = event.target.closest('.speech-bubble'); if (bubble) bubble.classList.add('editing'); });
messagesDiv.addEventListener('focusout', (event) => { const bubble = event.target.closest('.speech-bubble'); if (bubble) setTimeout(() => { if (!bubble.contains(document.activeElement)) bubble.classList.remove('editing'); }, 0); });
messagesDiv.addEventListener('input', (event) => { const bubble = event.target.closest('.speech-bubble'); if (bubble) { syncBubbleNodeToState(bubble); saveProjectState(); } });
messagesDiv.addEventListener('keydown', (event) => { if (!event.target.closest('.bubble-text')) return; if (event.key === 'Enter') { event.preventDefault(); event.target.blur(); const bubble = event.target.closest('.speech-bubble'); if (bubble) { syncBubbleNodeToState(bubble); saveProjectState(); } } });

messagesDiv.addEventListener('pointerdown', (event) => {
    const bubble = event.target.closest('.speech-bubble');
    if (!bubble) return;
    const layer = bubble.closest('.bubble-layer');
    if (!layer) return;
    if (event.target.closest('.bubble-text')) return;
    const layerRect = layer.getBoundingClientRect();
    const bubbleRect = bubble.getBoundingClientRect();
    const isResize = Boolean(event.target.closest('[data-action="resize"]'));
    const isDirectMoveHandle = Boolean(event.target.closest('[data-action="drag"]'));
    const canDragBubbleBody = bubble.classList.contains('move-ready') && !event.target.closest('[data-action="style"]');
    if (!isResize && !isDirectMoveHandle && !canDragBubbleBody) return;
    activeBubbleDrag = { bubble, layerRect, startX: event.clientX, startY: event.clientY, startLeft: (bubbleRect.left - layerRect.left) / layerRect.width, startTop: (bubbleRect.top - layerRect.top) / layerRect.height, startWidth: bubbleRect.width / layerRect.width, mode: isResize ? 'resize' : 'drag' };
    bubble.classList.add('dragging');
    bubble.classList.remove('move-ready');
    event.preventDefault();
});

document.addEventListener('pointermove', (event) => {
    if (!activeBubbleDrag) return;
    const { bubble, layerRect, startX, startY, startLeft, startTop, startWidth, mode } = activeBubbleDrag;
    if (mode === 'drag') {
        const left = Math.min(0.88, Math.max(0.02, startLeft + ((event.clientX - startX) / layerRect.width)));
        const top = Math.min(0.88, Math.max(0.02, startTop + ((event.clientY - startY) / layerRect.height)));
        bubble.style.left = `${left * 100}%`;
        bubble.style.top = `${top * 100}%`;
    } else {
        const width = Math.min(0.72, Math.max(0.16, startWidth + ((event.clientX - startX) / layerRect.width)));
        bubble.style.width = `${width * 100}%`;
    }
    event.preventDefault();
});

document.addEventListener('pointerup', () => { if (activeBubbleDrag) { syncBubbleNodeToState(activeBubbleDrag.bubble); activeBubbleDrag.bubble.classList.remove('dragging'); activeBubbleDrag = null; saveProjectState(); } });
document.addEventListener('pointercancel', () => { if (activeBubbleDrag) { syncBubbleNodeToState(activeBubbleDrag.bubble); activeBubbleDrag.bubble.classList.remove('dragging'); activeBubbleDrag = null; saveProjectState(); } });

messagesDiv.addEventListener('mousedown', (event) => {
    const styleToggle = event.target.closest('[data-action="style"]');
    if (!styleToggle) return;
    const bubble = styleToggle.closest('.speech-bubble');
    if (!bubble) return;
    const current = bubble.dataset.style || 'speech';
    const next = BUBBLE_STYLE_CYCLE[(BUBBLE_STYLE_CYCLE.indexOf(current) + 1) % BUBBLE_STYLE_CYCLE.length];
    bubble.dataset.style = next;
    bubble.classList.add('editing');
    syncBubbleNodeToState(bubble);
    saveProjectState();
    event.preventDefault();
});

messagesDiv.addEventListener('click', (event) => {
    const moveToggle = event.target.closest('[data-action="drag"]');
    if (!moveToggle) return;
    const bubble = moveToggle.closest('.speech-bubble');
    if (!bubble) return;
    messagesDiv.querySelectorAll('.speech-bubble.move-ready').forEach((node) => { if (node !== bubble) node.classList.remove('move-ready'); });
    bubble.classList.toggle('move-ready');
    bubble.classList.add('editing');
    event.preventDefault();
});

inputField.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendBtn.click(); });

window.onload = () => {
    const savedMode = localStorage.getItem('voicecanvas_mode') || 'gist';
    setMode(savedMode);
    const restored = loadChat();
    if (!restored) appendMessage('assistant', 'VoiceCanvas ready — drop an idea and generate manga pages.');
};