// TITrack Overlay v3 - Fixed columns, game state sync, scale control

const API_BASE = '/api';
const POLL_INTERVAL = 2000;
const BAR_HEIGHT = 30;
const SETTINGS_POPUP_HEIGHT = 50;

// --- Formatting ---

function formatTime(sec) {
    if (sec == null || sec < 0) return '--:--';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    if (h > 0) return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}

function formatFE(v) {
    if (v == null) return '--';
    const n = parseFloat(v);
    if (isNaN(n)) return '--';
    if (Math.abs(n) >= 100000) return (n / 1000).toFixed(0) + 'k';
    if (Math.abs(n) >= 10000) return (n / 1000).toFixed(1) + 'k';
    return n.toFixed(1);
}

// --- DOM ---

const el = {
    profit: document.getElementById('s-profit'),
    runTime: document.getElementById('s-run-time'),
    totalProfit: document.getElementById('s-total-profit'),
    totalTime: document.getElementById('s-total-time'),
    mapHr: document.getElementById('s-map-hr'),
    totalHr: document.getElementById('s-total-hr'),
    contract: document.getElementById('s-contract'),
    settingsBtn: document.getElementById('settings-btn'),
    settingsPopup: document.getElementById('settings-popup'),
    opacitySlider: document.getElementById('opacity-slider'),
    opacityVal: document.getElementById('opacity-val'),
    scaleSlider: document.getElementById('scale-slider'),
    scaleVal: document.getElementById('scale-val'),
    dragHandle: document.getElementById('drag-handle'),
};

// --- Local timer ---

let localRunSec = 0, localTotalSec = 0;
let isMappingPlaying = false, isTotalPlaying = false;

setInterval(function() {
    if (isMappingPlaying) {
        localRunSec++;
        el.runTime.textContent = formatTime(localRunSec);
    }
    if (isTotalPlaying) {
        localTotalSec++;
        el.totalTime.textContent = formatTime(localTotalSec);
    }
}, 1000);

// --- API polling ---

async function fetchActiveRun() {
    try {
        const res = await fetch(API_BASE + '/runs/active');
        if (res.status === 200) {
            const d = await res.json();
            if (d) {
                const val = d.net_value_fe != null ? d.net_value_fe : (d.total_value || 0);
                el.profit.textContent = formatFE(val);
                el.profit.classList.toggle('negative', val < 0);
                return;
            }
        }
        el.profit.textContent = '--';
        el.profit.classList.remove('negative');
    } catch (e) {}
}

async function fetchTimeState() {
    try {
        const res = await fetch(API_BASE + '/time');
        if (res.status === 200) {
            const d = await res.json();
            localRunSec = d.current_map_play_seconds || 0;
            localTotalSec = d.total_play_seconds || 0;
            isMappingPlaying = d.mapping_play_state === 'playing';
            isTotalPlaying = d.total_play_state === 'playing';

            el.runTime.textContent = (d.mapping_play_state === 'stopped' && localRunSec === 0)
                ? '--:--' : formatTime(localRunSec);
            el.totalTime.textContent = formatTime(localTotalSec);
            el.contract.textContent = d.contract_setting || '--';
        }
    } catch (e) {}
}

async function fetchPerformance() {
    try {
        const res = await fetch(API_BASE + '/runs/performance');
        if (res.status === 200) {
            const d = await res.json();
            el.mapHr.textContent = formatFE(d.profit_per_hour_mapping || 0);
            el.totalHr.textContent = formatFE(d.profit_per_hour_total || 0);
            el.totalProfit.textContent = formatFE(d.total_net_profit_fe || 0);
        }
    } catch (e) {}
}

async function pollAll() {
    await Promise.all([fetchActiveRun(), fetchTimeState(), fetchPerformance()]);
}

// --- JS Drag ---

let isDragging = false;
let dragStartX = 0, dragStartY = 0, winStartX = 0, winStartY = 0;

el.dragHandle.addEventListener('mousedown', async function(e) {
    e.preventDefault();
    isDragging = true;
    dragStartX = e.screenX;
    dragStartY = e.screenY;

    if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.set_overlay_interactive(true);
        const geo = await window.pywebview.api.get_overlay_geometry();
        if (geo) {
            winStartX = geo.x;
            winStartY = geo.y;
        }
    }
});

document.addEventListener('mousemove', function(e) {
    if (!isDragging) return;
    const dx = e.screenX - dragStartX;
    const dy = e.screenY - dragStartY;
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.move_overlay(winStartX + dx, winStartY + dy);
    }
});

document.addEventListener('mouseup', function() {
    if (isDragging) {
        isDragging = false;
        if (el.settingsPopup.classList.contains('hidden')) {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.set_overlay_interactive(false);
            }
        }
    }
});

// --- Settings popup ---

let settingsOpen = false;

el.settingsBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    if (settingsOpen) {
        closeSettings();
    } else {
        openSettings();
    }
});

function openSettings() {
    settingsOpen = true;
    el.settingsPopup.classList.remove('hidden');
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.resize_overlay(null, BAR_HEIGHT + SETTINGS_POPUP_HEIGHT);
        window.pywebview.api.set_overlay_interactive(true);
    }
}

function closeSettings() {
    settingsOpen = false;
    el.settingsPopup.classList.add('hidden');
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.resize_overlay(null, BAR_HEIGHT);
        window.pywebview.api.set_overlay_interactive(false);
    }
}

document.addEventListener('click', function(e) {
    if (settingsOpen && !el.settingsPopup.contains(e.target) && e.target !== el.settingsBtn) {
        closeSettings();
    }
});

// --- Opacity slider ---
(function() {
    const saved = localStorage.getItem('overlay_opacity');
    if (saved) {
        el.opacitySlider.value = saved;
        el.opacityVal.textContent = saved + '%';
    }

    el.opacitySlider.addEventListener('input', function(e) {
        const val = parseInt(e.target.value);
        el.opacityVal.textContent = val + '%';
        localStorage.setItem('overlay_opacity', val);
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.set_overlay_opacity(val / 100);
        }
    });
})();

// --- Scale slider ---
(function() {
    const saved = localStorage.getItem('overlay_scale');
    if (saved) {
        el.scaleSlider.value = saved;
        el.scaleVal.textContent = saved + '%';
    }

    el.scaleSlider.addEventListener('input', function(e) {
        const val = parseInt(e.target.value);
        el.scaleVal.textContent = val + '%';
        localStorage.setItem('overlay_scale', val);
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.set_overlay_scale(val / 100);
        }
    });
})();

// Apply saved settings on pywebview ready
window.addEventListener('pywebviewready', function() {
    const opacity = parseInt(el.opacitySlider.value);
    if (opacity < 100 && window.pywebview && window.pywebview.api) {
        window.pywebview.api.set_overlay_opacity(opacity / 100);
    }
    const scale = parseInt(el.scaleSlider.value);
    if (scale !== 100 && window.pywebview && window.pywebview.api) {
        window.pywebview.api.set_overlay_scale(scale / 100);
    }
});

// --- Init ---

pollAll();
setInterval(pollAll, POLL_INTERVAL);
