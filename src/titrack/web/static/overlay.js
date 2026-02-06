// TITrack Overlay - In-game overlay logic

const API_BASE = '/api';
const POLL_INTERVAL = 2000;

let lastData = {
    currentProfit: null,
    runTime: null,
    totalTime: null,
    fePerHour: null,
};

// --- Formatting helpers ---

function formatTime(seconds) {
    if (seconds == null || seconds < 0) return '--:--';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
        return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatFE(value) {
    if (value == null) return '--';
    const num = parseFloat(value);
    if (isNaN(num)) return '--';
    if (Math.abs(num) >= 1000) {
        return num.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
    }
    return num.toLocaleString('ko-KR', { maximumFractionDigits: 1 });
}

// --- DOM references ---

const elCurrentProfit = document.getElementById('current-profit');
const elRunTime = document.getElementById('run-time');
const elTotalTime = document.getElementById('total-time');
const elFePerHour = document.getElementById('fe-per-hour');
const elSettingsBtn = document.getElementById('settings-btn');
const elSettingsPanel = document.getElementById('settings-panel');
const elOpacitySlider = document.getElementById('opacity-slider');
const elOpacityValue = document.getElementById('opacity-value');
const elCloseBtn = document.getElementById('close-btn');

// --- Local timer for smooth updates ---
let localRunSeconds = 0;
let localTotalSeconds = 0;
let isMappingPlaying = false;
let isTotalPlaying = false;
let localTimerInterval = null;

function startLocalTimer() {
    if (localTimerInterval) return;
    localTimerInterval = setInterval(() => {
        if (isMappingPlaying) {
            localRunSeconds += 1;
            elRunTime.textContent = formatTime(localRunSeconds);
        }
        if (isTotalPlaying) {
            localTotalSeconds += 1;
            elTotalTime.textContent = formatTime(localTotalSeconds);
        }
    }, 1000);
}

// --- API polling ---

async function fetchActiveRun() {
    try {
        const res = await fetch(`${API_BASE}/runs/active`);
        if (res.status === 200) {
            const data = await res.json();
            if (data && data.total_value_fe != null) {
                const val = data.total_value_fe;
                elCurrentProfit.textContent = formatFE(val) + ' FE';
                elCurrentProfit.classList.toggle('negative', val < 0);
                lastData.currentProfit = val;
            } else {
                elCurrentProfit.textContent = '--';
                elCurrentProfit.classList.remove('negative');
            }
        } else {
            elCurrentProfit.textContent = '--';
            elCurrentProfit.classList.remove('negative');
        }
    } catch (e) {
        // Keep last known value on error
    }
}

async function fetchTimeState() {
    try {
        const res = await fetch(`${API_BASE}/time`);
        if (res.status === 200) {
            const data = await res.json();
            // Sync local timers with server
            localRunSeconds = data.current_map_play_seconds || 0;
            localTotalSeconds = data.total_play_seconds || 0;
            isMappingPlaying = data.mapping_play_state === 'playing';
            isTotalPlaying = data.total_play_state === 'playing';

            elRunTime.textContent = (data.mapping_play_state === 'stopped' && localRunSeconds === 0)
                ? '--:--'
                : formatTime(localRunSeconds);
            elTotalTime.textContent = formatTime(localTotalSeconds);
        }
    } catch (e) {
        // Keep last known value
    }
}

async function fetchPerformance() {
    try {
        const res = await fetch(`${API_BASE}/runs/performance`);
        if (res.status === 200) {
            const data = await res.json();
            const feHr = data.fe_per_hour_mapping || data.fe_per_hour_play || 0;
            elFePerHour.textContent = formatFE(feHr);
            lastData.fePerHour = feHr;
        }
    } catch (e) {
        // Keep last known value
    }
}

async function pollAll() {
    await Promise.all([
        fetchActiveRun(),
        fetchTimeState(),
        fetchPerformance(),
    ]);
}

// --- Settings ---

function initSettings() {
    // Restore opacity from localStorage
    const savedOpacity = localStorage.getItem('overlay_opacity');
    if (savedOpacity) {
        const val = parseInt(savedOpacity);
        elOpacitySlider.value = val;
        elOpacityValue.textContent = val + '%';
        applyOpacity(val);
    }

    elSettingsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        elSettingsPanel.classList.toggle('hidden');
    });

    elOpacitySlider.addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        elOpacityValue.textContent = val + '%';
        localStorage.setItem('overlay_opacity', val);
        applyOpacity(val);
    });

    elCloseBtn.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.close_overlay) {
            window.pywebview.api.close_overlay();
        } else {
            window.close();
        }
    });

    // Click outside settings panel to close
    document.addEventListener('click', (e) => {
        if (!elSettingsPanel.contains(e.target) && e.target !== elSettingsBtn) {
            elSettingsPanel.classList.add('hidden');
        }
    });
}

function applyOpacity(percent) {
    const value = percent / 100;
    // Try native Win32 API via pywebview
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_overlay_opacity) {
        window.pywebview.api.set_overlay_opacity(value);
    }
    // Also set CSS opacity as visual feedback / fallback
    document.getElementById('overlay-bar').style.opacity = value;
    document.getElementById('settings-panel').style.opacity = Math.min(1, value + 0.1);
}

// --- Init ---

function init() {
    initSettings();
    startLocalTimer();
    pollAll();
    setInterval(pollAll, POLL_INTERVAL);
}

// Wait for DOM then init
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
