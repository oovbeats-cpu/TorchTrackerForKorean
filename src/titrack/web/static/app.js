// 결정 트래커 Dashboard - Frontend Logic

const API_BASE = '/api';
let REFRESH_INTERVAL = 1000; // 1 second (default, can be changed via settings)

// Frameless window detection and controls
let isFramelessMode = false;

function showCustomTitlebar() {
    isFramelessMode = true;
    const titlebar = document.getElementById('custom-titlebar');
    if (titlebar) {
        titlebar.classList.remove('hidden');
        document.body.classList.add('has-titlebar');
    }

    // Show resize handles
    const resizeHandles = document.getElementById('resize-handles');
    if (resizeHandles) {
        resizeHandles.classList.remove('hidden');
        initResizeHandles();
    }
}

let resizeState = null;
const MIN_WIDTH = 580;
const MIN_HEIGHT = 400;

function initResizeHandles() {
    const handles = document.querySelectorAll('.resize-handle');
    handles.forEach(handle => {
        handle.addEventListener('mousedown', startResize);
    });
    
    document.addEventListener('mousemove', doResize);
    document.addEventListener('mouseup', stopResize);
}

async function startResize(e) {
    e.preventDefault();
    e.stopPropagation();
    
    if (!window.pywebview || !window.pywebview.api) return;
    
    const edge = e.target.dataset.edge;
    const geometry = await window.pywebview.api.get_window_geometry();
    
    if (!geometry) return;
    
    resizeState = {
        edge: edge,
        startMouseX: e.screenX,
        startMouseY: e.screenY,
        startX: geometry.x,
        startY: geometry.y,
        startWidth: geometry.width,
        startHeight: geometry.height
    };
}

function doResize(e) {
    if (!resizeState) return;
    if (!window.pywebview || !window.pywebview.api) return;
    
    const deltaX = e.screenX - resizeState.startMouseX;
    const deltaY = e.screenY - resizeState.startMouseY;
    const edge = resizeState.edge;
    
    let newX = resizeState.startX;
    let newY = resizeState.startY;
    let newWidth = resizeState.startWidth;
    let newHeight = resizeState.startHeight;
    
    if (edge.includes('e')) {
        newWidth = Math.max(MIN_WIDTH, resizeState.startWidth + deltaX);
    }
    if (edge.includes('w')) {
        const widthDelta = Math.min(deltaX, resizeState.startWidth - MIN_WIDTH);
        newX = resizeState.startX + widthDelta;
        newWidth = resizeState.startWidth - widthDelta;
    }
    if (edge.includes('s')) {
        newHeight = Math.max(MIN_HEIGHT, resizeState.startHeight + deltaY);
    }
    if (edge.includes('n')) {
        const heightDelta = Math.min(deltaY, resizeState.startHeight - MIN_HEIGHT);
        newY = resizeState.startY + heightDelta;
        newHeight = resizeState.startHeight - heightDelta;
    }
    
    window.pywebview.api.set_window_geometry(newX, newY, newWidth, newHeight);
}

function stopResize() {
    resizeState = null;
}

function initFramelessMode() {
    // Check if already ready
    if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
        showCustomTitlebar();
        return;
    }
    
    // Listen for pywebview ready event (more reliable)
    window.addEventListener('pywebviewready', function() {
        showCustomTitlebar();
        // Show always-on-top toggle in native window mode
        const onTopToggle = document.getElementById('always-on-top-group');
        if (onTopToggle) onTopToggle.style.display = '';
        // Show overlay button in native window mode
        const overlayBtn = document.getElementById('overlay-toggle-btn');
        if (overlayBtn) overlayBtn.style.display = '';
    });
}

function minimizeWindow() {
    if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
        window.pywebview.api.minimize();
    }
}

function closeWindow() {
    if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
        window.pywebview.api.close();
    }
}

let refreshTimer = null;
let lastRunsData = null;
let lastInventoryData = null;
let lastRunsHash = null;
let lastInventoryHash = null;
let lastStatsHash = null;
let lastPlayerHash = null;
const failedIcons = new Set(); // Track icons that failed to load

// Chart instances
let cumulativeValueChart = null;
let valueRateChart = null;
let priceHistoryChart = null;
let lootReportChart = null;

// Loot report data cache
let lastLootReportData = null;

// Cloud sync state
let cloudSyncEnabled = false;
let cloudPricesCache = {};
let sparklineHistoryCache = {}; // Cache for sparkline history data
let sparklineFetchInProgress = new Set(); // Track in-flight fetches

// Cloud settings state
let cloudAutoRefresh = true;
let cloudMidnightRefresh = true;
let cloudExchangeOverride = true;
let cloudStartupRefresh = true;

// Map costs state
let mapCostsEnabled = false;

// Update state
let updateStatus = null;
let updateCheckInterval = null;

// Time tracking state
let timeState = {
    total_play_state: 'stopped',
    total_play_seconds: 0,
    mapping_play_state: 'stopped',
    mapping_play_seconds: 0,
    auto_pause_on_inventory: false,
    surgery_count: 0,
    avg_surgery_time_seconds: 0,
    surgery_prep_start_ts: null,
    surgery_total_seconds: 0,
    last_displayed_surgery_avg: 0
};
let timeUpdateInterval = null;

let perfState = {
    run_count: 0,
    completed_runs_total_seconds: 0
};

let currentRunState = {
    duration_seconds: 0,
    isActive: false
};

// Inventory sorting state
let inventorySortBy = 'value';
let inventorySortOrder = 'desc';

// Sync inventory panel height to match left column (현재 런 + 최근 런)
function syncInventoryHeight() {
    const inventoryPanel = document.getElementById('inventory-panel');
    const leftColumn = document.querySelector('.left-column');
    
    if (!inventoryPanel || !leftColumn) return;
    
    // Skip sync in responsive mode (columns stack vertically)
    if (window.innerWidth <= 950) {
        inventoryPanel.style.height = 'auto';
        return;
    }
    
    // Set inventory panel height to match left column's total height
    const leftColumnHeight = leftColumn.offsetHeight;
    inventoryPanel.style.height = leftColumnHeight + 'px';
}

// Call on window resize
window.addEventListener('resize', () => {
    syncInventoryHeight();
    // Trigger chart resize
    if (cumulativeValueChart) cumulativeValueChart.resize();
    if (valueRateChart) valueRateChart.resize();
});

// Scrollbar visibility on scroll
function initScrollbarVisibility() {
    const scrollContainers = document.querySelectorAll('.inventory-scroll-container, .runs-scroll-container');
    
    scrollContainers.forEach(container => {
        let scrollTimeout;
        
        container.addEventListener('scroll', () => {
            container.classList.add('scrolling');
            
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                container.classList.remove('scrolling');
            }, 1000);
        });
    });
}

// Initialize scrollbar visibility on load
document.addEventListener('DOMContentLoaded', initScrollbarVisibility);

// --- API Calls ---

async function fetchJson(endpoint) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        return null;
    }
}

async function fetchStatus() {
    return fetchJson('/status');
}

async function fetchStats() {
    return fetchJson('/runs/stats');
}

async function fetchRuns(page = 1, pageSize = 20) {
    return fetchJson(`/runs?page=${page}&page_size=${pageSize}&exclude_hubs=true`);
}

async function fetchActiveRun() {
    return fetchJson('/runs/active');
}

async function fetchInventory(sortBy = inventorySortBy, sortOrder = inventorySortOrder) {
    return fetchJson(`/inventory?sort_by=${sortBy}&sort_order=${sortOrder}`);
}

async function fetchStatsHistory(hours = 24) {
    return fetchJson(`/stats/history?hours=${hours}`);
}

async function fetchPlayer() {
    return fetchJson('/player');
}

async function fetchPrices() {
    return fetchJson('/prices');
}

// --- Cloud Sync API Calls ---

async function fetchCloudStatus() {
    return fetchJson('/cloud/status');
}

async function toggleCloudSync(enabled) {
    try {
        const response = await fetch(`${API_BASE}/cloud/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error toggling cloud sync:', error);
        return null;
    }
}

async function triggerCloudSync() {
    try {
        const response = await fetch(`${API_BASE}/cloud/sync`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error triggering cloud sync:', error);
        return null;
    }
}

async function fetchCloudPrices() {
    return fetchJson('/cloud/prices');
}

// Trade tax setting functions
async function fetchTradeTaxSetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/trade_tax_enabled`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        console.error('Error fetching trade tax setting:', error);
        return false;
    }
}

async function updateTradeTaxSetting(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/trade_tax_enabled`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating trade tax setting:', error);
        return false;
    }
}

async function handleTradeTaxToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;

    // Disable toggle while processing
    toggle.disabled = true;

    const success = await updateTradeTaxSetting(enabled);

    if (success) {
        // Refresh all data to reflect new values
        await refreshAll(true);
    } else {
        // Revert toggle on failure
        toggle.checked = !enabled;
        alert('거래 수수료 설정 업데이트 실패');
    }

    toggle.disabled = false;
}

// Map costs setting functions
async function fetchMapCostsSetting() {
    try {
        const response = await fetch(`${API_BASE}/settings/map_costs_enabled`);
        if (!response.ok) return false;
        const data = await response.json();
        return data.value === 'true';
    } catch (error) {
        console.error('Error fetching map costs setting:', error);
        return false;
    }
}

async function updateMapCostsSetting(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/map_costs_enabled`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: enabled ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error updating map costs setting:', error);
        return false;
    }
}

async function handleMapCostsToggle(event) {
    const enabled = event.target.checked;
    const toggle = event.target;

    // Disable toggle while processing
    toggle.disabled = true;

    const success = await updateMapCostsSetting(enabled);

    if (success) {
        mapCostsEnabled = enabled;
        // Refresh all data to reflect new values
        await refreshAll(true);
    } else {
        // Revert toggle on failure
        toggle.checked = !enabled;
        alert('맵 비용 설정 업데이트 실패');
    }

    toggle.disabled = false;
}

// Pause settings functions
async function loadPauseSettings() {
    const state = await fetchTimeState();
    if (state && state.pause_settings) {
        const ps = state.pause_settings;
        document.getElementById('pause-bag').checked = ps.bag;
        document.getElementById('pause-pet').checked = ps.pet;
        document.getElementById('pause-talent').checked = ps.talent;
        document.getElementById('pause-settings').checked = ps.settings;
        document.getElementById('pause-skill').checked = ps.skill;
        document.getElementById('pause-auction').checked = ps.auction;
    }
}

async function savePauseSettings() {
    const settings = {
        bag: document.getElementById('pause-bag').checked,
        pet: document.getElementById('pause-pet').checked,
        talent: document.getElementById('pause-talent').checked,
        settings: document.getElementById('pause-settings').checked,
        skill: document.getElementById('pause-skill').checked,
        auction: document.getElementById('pause-auction').checked,
    };
    try {
        const response = await fetch(`${API_BASE}/time/pause-settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        return response.ok;
    } catch (error) {
        console.error('Error saving pause settings:', error);
        return false;
    }
}

async function handlePauseSettingChange(event) {
    const toggle = event.target;
    toggle.disabled = true;
    const success = await savePauseSettings();
    if (!success) {
        toggle.checked = !toggle.checked;
        alert('일시정지 설정 저장 실패');
    }
    toggle.disabled = false;
}

async function fetchCloudPriceHistory(configBaseId) {
    return fetchJson(`/cloud/prices/${configBaseId}/history`);
}

async function fetchLootReport() {
    return fetchJson('/runs/report');
}

// --- Time Tracking API Calls ---

async function fetchTimeState() {
    return fetchJson('/time');
}

async function togglePlayTime() {
    try {
        const response = await fetch(`${API_BASE}/time/toggle`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error toggling play time:', error);
        return null;
    }
}

async function setAutoPauseOnInventory(enabled) {
    try {
        const response = await fetch(`${API_BASE}/time/auto-pause`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error setting auto-pause:', error);
        return null;
    }
}

async function postResetStats() {
    try {
        const response = await fetch(`${API_BASE}/runs/reset`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error resetting stats:', error);
        return null;
    }
}

// --- Rendering ---

function formatDuration(seconds) {
    if (!seconds) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}분 ${secs}초`;
}

function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    return num.toLocaleString();
}

function formatFEValue(value) {
    // Format FE values with 2 decimal places
    if (value === null || value === undefined) return '--';
    return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatFE(value) {
    if (value === null || value === undefined) return '--';
    if (value > 0) {
        return `<span class="positive">+${formatNumber(value)}</span>`;
    } else if (value < 0) {
        return `<span class="negative">${formatNumber(value)}</span>`;
    }
    return formatNumber(value);
}

function formatValue(value) {
    if (value === null || value === undefined) return '--';
    const formatted = value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (value > 0) {
        return `<span class="positive">+${formatted}</span>`;
    } else if (value < 0) {
        return `<span class="negative">${formatted}</span>`;
    }
    return formatted;
}

function buildCostTooltip(costItems) {
    if (!costItems || costItems.length === 0) return '';
    const lines = costItems.map(item => {
        const qty = Math.abs(item.quantity);
        const value = item.total_value_fe !== null
            ? `${item.total_value_fe.toFixed(2)} 결정`
            : '? 결정';
        return `${item.name} x${qty} = ${value}`;
    });
    // Escape for HTML attribute and use newline character
    return escapeAttr(lines.join('\n'));
}

function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function renderStats(stats, inventory) {
    document.getElementById('net-worth').textContent = formatNumber(Math.round(inventory?.net_worth_fe || 0));
}

async function fetchPerformanceStats() {
    try {
        const response = await fetch('/api/runs/performance');
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching performance stats:', error);
        return null;
    }
}

function formatSecondsToMinSec(seconds) {
    if (!seconds || seconds <= 0) return '0분 0초';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}분 ${secs}초`;
}

function renderPerformanceStats(data) {
    if (!data) return;

    // Total play time based stats (white box)
    const totalMinAvg = document.getElementById('total-min-avg');
    const totalHourAvg = document.getElementById('total-hour-avg');
    if (totalMinAvg) totalMinAvg.textContent = formatNumber(Math.round(data.profit_per_minute_total || 0));
    if (totalHourAvg) totalHourAvg.textContent = formatNumber(Math.round(data.profit_per_hour_total || 0));

    // Mapping time based stats (red box)
    const mappingMinAvg = document.getElementById('mapping-min-avg');
    const mappingHourAvg = document.getElementById('mapping-hour-avg');
    if (mappingMinAvg) mappingMinAvg.textContent = formatNumber(Math.round(data.profit_per_minute_mapping || 0));
    if (mappingHourAvg) mappingHourAvg.textContent = formatNumber(Math.round(data.profit_per_hour_mapping || 0));

    // Grid stats
    const totalRunsGrid = document.getElementById('total-runs-grid');
    const avgRunTimeGrid = document.getElementById('avg-run-time-grid');
    const totalCostGrid = document.getElementById('total-cost-grid');
    const totalIncomeGrid = document.getElementById('total-income-grid');

    // Update perfState for live average calculation
    perfState.run_count = data.run_count || 0;
    perfState.completed_runs_total_seconds = data.completed_runs_total_seconds || 0;

    if (totalRunsGrid) totalRunsGrid.textContent = `${formatNumber(data.run_count || 0)}회`;
    // avgRunTimeGrid is now updated in updateTimeDisplay() for live calculation
    if (totalCostGrid) totalCostGrid.textContent = `${formatNumber(Math.round(data.total_entry_cost_fe || 0))}결정`;
    if (totalIncomeGrid) totalIncomeGrid.textContent = `${formatNumber(Math.round(data.total_net_profit_fe || 0))}결정`;
}

function renderRuns(data, forceRender = false) {
    const newHash = simpleHash(data?.runs?.map(r => ({ id: r.id, val: r.total_value, dur: r.duration_seconds, cost: r.map_cost_fe })));
    if (!forceRender && newHash === lastRunsHash) {
        return; // No change, skip re-render
    }
    lastRunsHash = newHash;

    const tbody = document.getElementById('runs-body');

    if (!data || !data.runs || data.runs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading">아직 기록된 런이 없습니다</td></tr>';
        return;
    }

    tbody.innerHTML = data.runs.map(run => {
        const nightmareClass = run.is_nightmare ? ' nightmare' : '';
        const consolidatedInfo = run.consolidated_run_ids ? ` (${run.consolidated_run_ids.length}개 구간)` : '';

        // Show net value if costs are enabled and there are costs
        let valueDisplay;
        if (run.net_value_fe !== null && run.net_value_fe !== undefined && run.map_cost_fe > 0) {
            const warningIcon = run.map_cost_has_unpriced ? ' <span class="cost-warning" title="일부 비용의 가격을 알 수 없음">⚠</span>' : '';
            valueDisplay = `${formatValue(run.net_value_fe)}${warningIcon}`;
        } else {
            valueDisplay = formatValue(run.total_value);
        }

        return `
            <tr class="${nightmareClass}">
                <td class="zone-name" title="${run.zone_signature}${consolidatedInfo}">${escapeHtml(run.zone_name)}</td>
                <td class="duration">${formatDuration(run.duration_seconds)}</td>
                <td>${valueDisplay}</td>
                <td>
                    <button class="expand-btn" onclick="showRunDetails(${run.id})">
                        상세
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

let lastActiveRunHash = null;

let lastActiveRunId = null;

// --- Time Tracking UI Functions ---

function formatTimeDisplay(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours}시간 ${minutes}분 ${secs}초`;
}

function formatShortTimeDisplay(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}분 ${secs}초`;
}

function updateTimeDisplay() {
    const totalTimeEl = document.getElementById('total-play-time');
    const mappingTimeEl = document.getElementById('mapping-play-time');
    const avgSurgeryTimeEl = document.getElementById('avg-surgery-time');
    const surgeryCountEl = document.getElementById('total-surgery-count');
    const playBtn = document.getElementById('play-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const avgRunTimeGrid = document.getElementById('avg-run-time-grid');
    
    if (!totalTimeEl || !mappingTimeEl) return;
    
    totalTimeEl.textContent = formatTimeDisplay(timeState.total_play_seconds);
    mappingTimeEl.textContent = formatTimeDisplay(timeState.mapping_play_seconds);
    
    // Calculate live average surgery time (including current prep time)
    let liveAvgSurgerySeconds = 0;
    if (timeState.surgery_prep_start_ts) {
        // During prep: calculate live average including current prep time
        const currentPrepSeconds = (Date.now() / 1000) - timeState.surgery_prep_start_ts;
        const totalWithCurrent = timeState.surgery_total_seconds + currentPrepSeconds;
        liveAvgSurgerySeconds = totalWithCurrent / (timeState.surgery_count + 1);
        timeState.last_displayed_surgery_avg = liveAvgSurgerySeconds;
    } else if (timeState.avg_surgery_time_seconds > 0) {
        // Use API-provided average first (already calculated by backend, most reliable)
        liveAvgSurgerySeconds = timeState.avg_surgery_time_seconds;
        timeState.last_displayed_surgery_avg = liveAvgSurgerySeconds;
    } else if (timeState.surgery_count > 0 && timeState.surgery_total_seconds > 0) {
        // Fallback: calculate average from raw totals
        liveAvgSurgerySeconds = timeState.surgery_total_seconds / timeState.surgery_count;
        timeState.last_displayed_surgery_avg = liveAvgSurgerySeconds;
    } else if (timeState.last_displayed_surgery_avg > 0) {
        // Fallback: preserve last displayed value
        liveAvgSurgerySeconds = timeState.last_displayed_surgery_avg;
    }
    
    if (avgSurgeryTimeEl) {
        avgSurgeryTimeEl.textContent = formatShortTimeDisplay(liveAvgSurgerySeconds);
    }
    if (surgeryCountEl) {
        const displayCount = timeState.surgery_prep_start_ts 
            ? (timeState.surgery_count + 1) 
            : (timeState.surgery_count > 0 ? timeState.surgery_count : (timeState.last_displayed_surgery_avg > 0 ? 1 : 0));
        surgeryCountEl.textContent = `${displayCount || 0}회`;
    }
    
    // Calculate live average run time (including current run duration)
    if (avgRunTimeGrid) {
        let liveAvgRunSeconds = 0;
        if (currentRunState.isActive && currentRunState.duration_seconds > 0) {
            const totalWithCurrent = perfState.completed_runs_total_seconds + currentRunState.duration_seconds;
            const countWithCurrent = perfState.run_count + 1;
            liveAvgRunSeconds = countWithCurrent > 0 ? totalWithCurrent / countWithCurrent : 0;
        } else if (perfState.run_count > 0) {
            liveAvgRunSeconds = perfState.completed_runs_total_seconds / perfState.run_count;
        }
        avgRunTimeGrid.textContent = formatSecondsToMinSec(liveAvgRunSeconds);
    }
    
    // Update current run duration display (synced with mapping timer)
    if (currentRunState.isActive) {
        const durationEl = document.getElementById('active-run-duration');
        if (durationEl) {
            durationEl.textContent = `(${formatDuration(currentRunState.duration_seconds)})`;
        }
    }

    if (timeState.total_play_state === 'playing') {
        playBtn.classList.add('hidden');
        pauseBtn.classList.remove('hidden');
    } else {
        playBtn.classList.remove('hidden');
        pauseBtn.classList.add('hidden');
    }
}

function startTimeUpdater() {
    if (timeUpdateInterval) return;
    
    timeUpdateInterval = setInterval(() => {
        // Increment local counters if playing
        if (timeState.total_play_state === 'playing') {
            timeState.total_play_seconds += 1;
        }
        if (timeState.mapping_play_state === 'playing') {
            timeState.mapping_play_seconds += 1;
            // Increment current run duration only if mapping timer is playing
            if (currentRunState.isActive) {
                currentRunState.duration_seconds += 1;
            }
        }
        updateTimeDisplay();
    }, 1000);
}

function stopTimeUpdater() {
    if (timeUpdateInterval) {
        clearInterval(timeUpdateInterval);
        timeUpdateInterval = null;
    }
}

async function syncTimeState() {
    const state = await fetchTimeState();
    if (state) {
        timeState.total_play_state = state.total_play_state;
        timeState.total_play_seconds = state.total_play_seconds;
        timeState.mapping_play_state = state.mapping_play_state;
        timeState.mapping_play_seconds = state.mapping_play_seconds;
        timeState.auto_pause_on_inventory = state.auto_pause_on_inventory;
        timeState.surgery_count = state.surgery_count || 0;
        timeState.avg_surgery_time_seconds = state.avg_surgery_time_seconds || 0;
        timeState.surgery_prep_start_ts = state.surgery_prep_start_ts || null;
        timeState.surgery_total_seconds = state.surgery_total_seconds || 0;
        
        // Preserve last_displayed_surgery_avg if API returns valid average
        if (state.avg_surgery_time_seconds > 0) {
            timeState.last_displayed_surgery_avg = state.avg_surgery_time_seconds;
        }

        // Sync current map play time from TimeTracker (pause-aware)
        // Only update when actively in a map (mapping_play_state check prevents
        // stale values from overwriting after map ends)
        if (currentRunState.isActive && state.mapping_play_state !== 'stopped'
            && state.current_map_play_seconds !== undefined) {
            currentRunState.duration_seconds = state.current_map_play_seconds;
        }

        if (state.pause_settings) {
            timeState.pause_settings = state.pause_settings;
        }
        updateTimeDisplay();

        // Update contract badge in active run panel
        const contractBadge = document.getElementById('active-run-contract');
        if (contractBadge) {
            if (state.contract_setting) {
                contractBadge.textContent = '계약: ' + state.contract_setting;
                contractBadge.classList.remove('hidden');
            } else {
                contractBadge.classList.add('hidden');
            }
        }
    }
}

async function handlePlayPauseClick() {
    const result = await togglePlayTime();
    if (result) {
        timeState.total_play_state = result.new_state;
        timeState.total_play_seconds = result.total_play_seconds;
        updateTimeDisplay();
    }
}

function initTimeTracking() {
    const playBtn = document.getElementById('play-btn');
    const pauseBtn = document.getElementById('pause-btn');
    
    if (playBtn) {
        playBtn.addEventListener('click', handlePlayPauseClick);
    }
    if (pauseBtn) {
        pauseBtn.addEventListener('click', handlePlayPauseClick);
    }
    
    // Initial sync and start updater
    syncTimeState();
    startTimeUpdater();
    
    // Periodic sync with server (every 5 seconds for responsive state updates)
    setInterval(syncTimeState, 5000);
}

function initAlwaysOnTop() {
    const toggle = document.getElementById('always-on-top-group');
    const checkbox = document.getElementById('always-on-top-checkbox');
    if (!toggle || !checkbox) return;

    // Only show in native window mode (pywebview)
    if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
        toggle.style.display = '';
    }

    // Load saved state
    const saved = localStorage.getItem('alwaysOnTop');
    if (saved === 'true') {
        checkbox.checked = true;
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.toggle_on_top(true);
        }
    }

    checkbox.addEventListener('change', async function() {
        if (window.pywebview && window.pywebview.api) {
            await window.pywebview.api.toggle_on_top(checkbox.checked);
        }
        localStorage.setItem('alwaysOnTop', checkbox.checked.toString());
    });
}

function initOverlayToggle() {
    const btn = document.getElementById('overlay-toggle-btn');
    if (!btn) return;

    function showOverlayUI() {
        btn.style.display = '';
        const overlaySection = document.getElementById('overlay-settings-section');
        if (overlaySection) overlaySection.style.display = '';
    }

    // Check immediately
    if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
        showOverlayUI();
    } else {
        // Retry after pywebview might be ready
        window.addEventListener('pywebviewready', showOverlayUI);
        // Also retry with timeout as fallback
        setTimeout(() => {
            if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
                showOverlayUI();
            }
        }, 1000);
    }

    // Restore saved state
    const saved = localStorage.getItem('overlay_enabled');
    if (saved === 'false') {
        btn.classList.remove('active');
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.toggle_overlay();
        }
    }

    btn.addEventListener('click', async function() {
        if (window.pywebview && window.pywebview.api) {
            await window.pywebview.api.toggle_overlay();
            btn.classList.toggle('active');
            localStorage.setItem('overlay_enabled', btn.classList.contains('active').toString());
        }
    });
}

function initOverlaySettings() {
    // Opacity slider in settings modal
    const opacitySlider = document.getElementById('settings-overlay-opacity');
    const opacityVal = document.getElementById('settings-overlay-opacity-val');
    if (opacitySlider) {
        opacitySlider.addEventListener('input', function(e) {
            const val = parseInt(e.target.value);
            opacityVal.textContent = val + '%';
        });
    }

    // Scale slider in settings modal
    const scaleSlider = document.getElementById('settings-overlay-scale');
    const scaleVal = document.getElementById('settings-overlay-scale-val');
    if (scaleSlider) {
        scaleSlider.addEventListener('input', function(e) {
            const val = parseInt(e.target.value);
            scaleVal.textContent = val + '%';
        });
    }

    // Preset buttons
    const presetDescs = {
        '1': '가로 1행',
        '2': '가로 2행',
        '3': '세로 왼쪽'
    };
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const desc = document.getElementById('preset-desc');
            if (desc) desc.textContent = presetDescs[this.dataset.preset] || '';
        });
    });
}

function initModalScrollbars() {
    document.querySelectorAll('.modal-content').forEach(el => {
        let scrollTimeout;
        el.addEventListener('scroll', () => {
            el.classList.add('scrolling');
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                el.classList.remove('scrolling');
            }, 1000);
        });
    });
}

function renderActiveRun(data, forceRender = false) {
    const panel = document.getElementById('active-run-panel');
    const zoneEl = document.getElementById('active-run-zone');
    const durationEl = document.getElementById('active-run-duration');
    const valueEl = document.getElementById('active-run-value');
    const lootEl = document.getElementById('active-run-loot');

    // No active run - hide and clear panel
    if (!data) {
        panel.classList.add('hidden');
        lastActiveRunHash = null;
        lastActiveRunId = null;
        // Clear content so old data doesn't flash when new run starts
        zoneEl.textContent = '--';
        valueEl.textContent = '0';
        lootEl.innerHTML = '';
        // Update currentRunState
        currentRunState.isActive = false;
        currentRunState.duration_seconds = 0;
        return;
    }
    
    // Update currentRunState for live average calculation
    // Use server's duration_seconds (now based on TimeTracker, excludes paused time)
    currentRunState.isActive = true;
    currentRunState.duration_seconds = data.duration_seconds || 0;

    // Check if data changed (exclude duration from hash - it's updated by local timer)
    const newHash = simpleHash({
        id: data.id,
        val: data.total_value,
        loot: data.loot?.length,
        cost: data.map_cost_fe
    });
    if (!forceRender && newHash === lastActiveRunHash) {
        // Just update duration display from local timer state
        durationEl.textContent = `(${formatDuration(currentRunState.duration_seconds)})`;
        return;
    }
    lastActiveRunHash = newHash;
    lastActiveRunId = data.id;

    // Show panel and update content
    panel.classList.remove('hidden');
    zoneEl.textContent = data.zone_name;
    durationEl.textContent = `(${formatDuration(currentRunState.duration_seconds)})`;

    // Show value with cost info if map costs are enabled
    if (data.map_cost_fe !== null && data.map_cost_fe !== undefined && data.map_cost_fe > 0) {
        const netValue = data.net_value_fe !== null ? data.net_value_fe : data.total_value;
        const warningIcon = data.map_cost_has_unpriced ? ' <span class="cost-warning" title="일부 비용의 가격을 알 수 없음">⚠</span>' : '';
        const costTooltip = buildCostTooltip(data.map_cost_items);
        valueEl.innerHTML = `${formatValue(netValue)} <span class="cost-info">(총액: ${formatNumber(Math.round(data.total_value))}, 비용: <span class="cost-hover" title="${costTooltip}">-${formatNumber(Math.round(data.map_cost_fe))}</span>${warningIcon})</span>`;
    } else {
        valueEl.innerHTML = formatValue(data.total_value);
    }

    // Render loot items - sorted by value descending, max 3 items
    if (!data.loot || data.loot.length === 0) {
        lootEl.innerHTML = '<span class="no-loot">아직 드랍 없음...</span>';
    } else {
        // Sort by total_value_fe descending (items without value go to end)
        const sortedLoot = [...data.loot].sort((a, b) => {
            const aVal = a.total_value_fe || 0;
            const bVal = b.total_value_fe || 0;
            return bVal - aVal;
        }).slice(0, 3); // Limit to 3 items

        lootEl.innerHTML = sortedLoot.map(item => {
            const isNegative = item.quantity < 0;
            const negativeClass = isNegative ? ' negative' : '';
            const qtyPrefix = item.quantity > 0 ? '+' : '';
            const valueText = item.total_value_fe ? formatValue(item.total_value_fe) : '--';
            const iconHtml = getIconHtml(item.config_base_id, 'loot-icon');

            return `
                <div class="loot-item${negativeClass}">
                    ${iconHtml}
                    <span class="loot-name">${escapeHtml(item.name)}</span>
                    <span class="loot-qty">${qtyPrefix}${item.quantity}</span>
                    <span class="loot-value">${valueText}</span>
                </div>
            `;
        }).join('');
    }
}

function renderInventory(data, forceRender = false) {
    const newHash = simpleHash(data?.items?.map(i => ({ id: i.config_base_id, qty: i.quantity })));
    if (!forceRender && newHash === lastInventoryHash) {
        return; // No change, skip re-render
    }
    lastInventoryHash = newHash;

    const tbody = document.getElementById('inventory-body');
    const sparklineHeader = document.getElementById('sparkline-header');
    const inventoryTable = document.getElementById('inventory-table');

    // Show/hide sparkline column based on cloud sync status only
    if (sparklineHeader && inventoryTable) {
        if (cloudSyncEnabled) {
            sparklineHeader.classList.remove('hidden');
            inventoryTable.classList.remove('no-sparkline');
        } else {
            sparklineHeader.classList.add('hidden');
            inventoryTable.classList.add('no-sparkline');
        }
    }

    const colSpan = cloudSyncEnabled ? 5 : 4;

    if (!data || !data.items || data.items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${colSpan}" class="loading">인벤토리에 아이템 없음</td></tr>`;
        return;
    }

    tbody.innerHTML = data.items.map(item => {
        const isFE = item.config_base_id === 100300;
        const iconHtml = getIconHtml(item.config_base_id, 'item-icon');

        // Check if we have cloud price for this item
        const cloudPrice = cloudPricesCache[item.config_base_id];
        // Show cloud indicator only if:
        // 1. We have 3+ contributors (community validated)
        // 2. The effective price is actually from cloud (not exchange-learned)
        const hasValidatedCloudPrice = cloudPrice && cloudPrice.unique_devices >= 3;
        const isUsingCloudPrice = item.price_source === 'cloud';
        // Show sparkline for any cloud price (even single contributor for personal tracking)
        const hasAnyCloudPrice = !!cloudPrice;

        // Cloud price indicator (only for validated prices AND when actually using cloud price)
        const cloudIndicator = (hasValidatedCloudPrice && isUsingCloudPrice)
            ? `<span class="cloud-price-indicator" title="커뮤니티 가격 (${cloudPrice.unique_devices}명 기여)"></span>`
            : '';

        // Sparkline cell - always render for column alignment, but hide content when cloud sync disabled
        // Note: Canvas needs explicit width/height attributes (not just CSS) to render correctly
        const sparklineCell = cloudSyncEnabled
            ? `<td class="sparkline-cell" onclick="showPriceHistory(${item.config_base_id}, '${escapeHtml(item.name).replace(/'/g, "\\'")}')">
                ${hasAnyCloudPrice ? '<canvas class="sparkline" data-config-id="' + item.config_base_id + '" width="60" height="24"></canvas>' : '<div class="sparkline-placeholder"></div>'}
               </td>`
            : '<td class="sparkline-cell hidden"></td>';

        // Calculate unit price
        const unitPrice = (item.total_value_fe && item.quantity > 0)
            ? item.total_value_fe / item.quantity
            : null;

        return `
            <tr>
                <td>
                    <div class="item-row">
                        ${iconHtml}
                        <span class="item-name ${isFE ? 'fe' : ''}">${escapeHtml(item.name)}${cloudIndicator}</span>
                    </div>
                </td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${unitPrice !== null ? formatFEValue(unitPrice) : '--'}</td>
                <td>${item.total_value_fe ? formatFEValue(item.total_value_fe) : '--'}</td>
                ${sparklineCell}
            </tr>
        `;
    }).join('');

    // Render sparklines after DOM update
    // Use setTimeout to ensure DOM is fully ready (requestAnimationFrame can fire too early)
    if (cloudSyncEnabled) {
        setTimeout(() => renderSparklines(), 50);
    }
}

function renderSparklines() {
    const sparklines = document.querySelectorAll('.sparkline[data-config-id]');
    sparklines.forEach(canvas => {
        const configId = parseInt(canvas.dataset.configId);
        const cloudPrice = cloudPricesCache[configId];
        if (!cloudPrice) return;

        // Check if we have cached history
        if (sparklineHistoryCache[configId] !== undefined) {
            // Render with cached data (may be empty array if no history)
            renderSparklineGraph(canvas, sparklineHistoryCache[configId]);
        } else if (!sparklineFetchInProgress.has(configId)) {
            // Show loading state and fetch history
            renderSparklineLoading(canvas);
            fetchSparklineHistory(configId);
        }
    });
}

async function fetchSparklineHistory(configId) {
    if (sparklineFetchInProgress.has(configId)) return;
    sparklineFetchInProgress.add(configId);

    try {
        const response = await fetch(`${API_BASE}/cloud/prices/${configId}/history`);
        if (response.ok) {
            const data = await response.json();
            sparklineHistoryCache[configId] = data.history || [];
        } else {
            sparklineHistoryCache[configId] = [];
        }
    } catch (error) {
        console.error(`Failed to fetch sparkline history for ${configId}:`, error);
        sparklineHistoryCache[configId] = [];
    } finally {
        sparklineFetchInProgress.delete(configId);
        // Re-render this specific sparkline
        const canvas = document.querySelector(`.sparkline[data-config-id="${configId}"]`);
        if (canvas) {
            renderSparklineGraph(canvas, sparklineHistoryCache[configId]);
        }
    }
}

function renderSparklineLoading(canvas) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Draw three dots to indicate loading
    const midY = height / 2;
    ctx.fillStyle = '#4ecca3';
    for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.arc(width / 2 - 10 + i * 10, midY, 2, 0, Math.PI * 2);
        ctx.fill();
    }
}

function renderSparklineGraph(canvas, history) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 2;

    ctx.clearRect(0, 0, width, height);
    
    // If no history or only one point, show a simple indicator
    if (!history || history.length < 2) {
        renderSparklinePlaceholder(canvas);
        return;
    }

    // Extract price values
    const prices = history.map(h => h.price_fe_median);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = maxPrice - minPrice;

    // Determine trend (up, down, or flat)
    const firstPrice = prices[0];
    const lastPrice = prices[prices.length - 1];
    const trend = lastPrice > firstPrice * 1.01 ? 'up' :
                  lastPrice < firstPrice * 0.99 ? 'down' : 'flat';

    // Choose color based on trend
    const colors = {
        up: '#4ecca3',    // Green
        down: '#e94560',  // Red
        flat: '#7f8c8d'   // Gray
    };
    const color = colors[trend];

    // Calculate points
    const points = prices.map((price, i) => {
        const x = padding + (i / (prices.length - 1)) * (width - padding * 2);
        // If price range is 0 (all same price), draw flat line in middle
        const y = priceRange === 0
            ? height / 2
            : padding + (1 - (price - minPrice) / priceRange) * (height - padding * 2);
        return { x, y };
    });

    // Draw fill gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, color + '40'); // 25% opacity at top
    gradient.addColorStop(1, color + '00'); // 0% opacity at bottom

    ctx.beginPath();
    ctx.moveTo(points[0].x, height);
    points.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Draw end dot
    const lastPoint = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(lastPoint.x, lastPoint.y, 2, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
}

function renderSparklinePlaceholder(canvas) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const midY = height / 2;

    ctx.clearRect(0, 0, width, height);

    // Draw a visible dashed line to indicate "no trend data"
    ctx.strokeStyle = '#7f8c8d';  // More visible gray
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(4, midY);
    ctx.lineTo(width - 8, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw a visible dot at the end
    ctx.fillStyle = '#7f8c8d';
    ctx.beginPath();
    ctx.arc(width - 6, midY, 3, 0, Math.PI * 2);
    ctx.fill();
}

function renderStatus(status) {
    const indicator = document.getElementById('status-indicator');
    const collectorStatus = document.getElementById('collector-status');

    if (status?.collector_running) {
        indicator.classList.add('active');
        collectorStatus.textContent = '수집기: 실행 중';
    } else {
        indicator.classList.remove('active');
        collectorStatus.textContent = '수집기: 중지됨';
    }

    // Show/hide awaiting player message
    const awaitingMessage = document.getElementById('awaiting-player-message');
    if (awaitingMessage) {
        if (status?.awaiting_player && !status?.log_path_missing) {
            awaitingMessage.classList.remove('hidden');
        } else {
            awaitingMessage.classList.add('hidden');
        }
    }

}

function renderPlayer(player) {
    const playerInfo = document.getElementById('player-info');
    const playerName = document.getElementById('player-name');
    const playerDetails = document.getElementById('player-details');

    if (player) {
        playerName.textContent = player.name;
        playerDetails.textContent = player.season_name;
        playerInfo.classList.remove('hidden');
    } else {
        playerInfo.classList.add('hidden');
    }
}

// --- Cloud Sync UI ---

function renderCloudStatus(status) {
    const checkbox = document.getElementById('cloud-sync-checkbox');
    const indicator = document.getElementById('cloud-sync-status');
    const cloudSettingsSection = document.getElementById('cloud-settings-section');

    if (!status) {
        checkbox.checked = false;
        checkbox.disabled = true;
        indicator.className = 'cloud-status-indicator';
        indicator.title = '클라우드 동기화 불가';
        if (cloudSettingsSection) cloudSettingsSection.style.display = 'none';
        return;
    }

    // Always enable checkbox so user can try to connect
    checkbox.disabled = false;
    checkbox.checked = status.enabled;
    cloudSyncEnabled = status.enabled;
    
    // Show/hide cloud settings section based on enabled state
    if (cloudSettingsSection) {
        cloudSettingsSection.style.display = status.enabled ? 'block' : 'none';
    }
    
    // Enable/disable force refresh button
    const forceRefreshBtn = document.getElementById('cloud-force-refresh-btn');
    if (forceRefreshBtn) {
        forceRefreshBtn.disabled = !status.enabled;
    }

    // Update indicator
    indicator.className = 'cloud-status-indicator';
    if (status.status === 'connected') {
        indicator.classList.add('connected');
        indicator.title = '클라우드 동기화 연결됨';
    } else if (status.status === 'syncing') {
        indicator.classList.add('syncing');
        indicator.title = '동기화 중...';
    } else if (status.status === 'error') {
        indicator.classList.add('error');
        indicator.title = status.last_error || '클라우드 동기화 오류';
    } else if (status.status === 'offline') {
        indicator.classList.add('offline');
        indicator.title = '클라우드 동기화 오프라인';
    } else {
        indicator.title = '클라우드 동기화 비활성화됨';
    }

    // Add queue info to title
    if (status.queue_pending > 0) {
        indicator.title += ` (${status.queue_pending} pending)`;
    }
}

async function handleCloudSyncToggle() {
    const checkbox = document.getElementById('cloud-sync-checkbox');
    const enabled = checkbox.checked;

    // Disable checkbox while processing
    checkbox.disabled = true;

    const result = await toggleCloudSync(enabled);

    if (result) {
        cloudSyncEnabled = result.enabled;
        checkbox.checked = result.enabled;

        if (!result.success && result.error) {
            alert(`클라우드 동기화 오류: ${result.error}`);
        }

        // Refresh cloud status
        const status = await fetchCloudStatus();
        renderCloudStatus(status);

        // Load cloud prices if newly enabled, start auto-refresh
        if (result.enabled) {
            await loadCloudPrices(cloudExchangeOverride);
            startCloudPriceAutoRefresh();
        } else {
            stopCloudPriceAutoRefresh();
        }
    } else {
        // Revert on error
        checkbox.checked = !enabled;
    }

    checkbox.disabled = false;
}

async function fetchExchangePriceIds() {
    return fetchJson('/prices/exchange');
}

// Track exchange-learned prices to exclude from hourly auto-refresh
let exchangePriceIds = new Set();

async function loadCloudPrices(preserveExchange = false) {
    if (!cloudSyncEnabled) return;

    // If preserving exchange prices, fetch the list of user-learned items
    if (preserveExchange) {
        const exchangeIds = await fetchExchangePriceIds();
        if (exchangeIds && Array.isArray(exchangeIds)) {
            exchangePriceIds = new Set(exchangeIds);
        }
    }

    const data = await fetchCloudPrices();
    if (data && data.prices) {
        // If preserving exchange, keep existing cache entries for exchange items
        if (!preserveExchange) {
            cloudPricesCache = {};
            sparklineHistoryCache = {};
            sparklineFetchInProgress.clear();
        } else {
            // Clear sparkline cache only for non-exchange items
            for (const configId of Object.keys(sparklineHistoryCache)) {
                if (!exchangePriceIds.has(parseInt(configId))) {
                    delete sparklineHistoryCache[configId];
                    sparklineFetchInProgress.delete(parseInt(configId));
                }
            }
        }

        for (const price of data.prices) {
            // Skip if this item has an exchange-learned price
            if (preserveExchange && exchangePriceIds.has(price.config_base_id)) {
                continue;
            }
            cloudPricesCache[price.config_base_id] = price;
        }
    }
}

// Cloud settings functions
async function loadCloudSettings() {
    try {
        const [autoRefresh, midnightRefresh, exchangeOverride, startupRefresh] = await Promise.all([
            fetchJson('/settings/cloud_auto_refresh'),
            fetchJson('/settings/cloud_midnight_refresh'),
            fetchJson('/settings/cloud_exchange_override'),
            fetchJson('/settings/cloud_startup_refresh'),
        ]);
        
        cloudAutoRefresh = autoRefresh?.value !== 'false';
        cloudMidnightRefresh = midnightRefresh?.value !== 'false';
        cloudExchangeOverride = exchangeOverride?.value !== 'false';
        cloudStartupRefresh = startupRefresh?.value !== 'false';
        
        // Update UI
        const autoRefreshToggle = document.getElementById('cloud-auto-refresh');
        const midnightRefreshToggle = document.getElementById('cloud-midnight-refresh');
        const exchangeOverrideToggle = document.getElementById('cloud-exchange-override');
        const startupRefreshToggle = document.getElementById('cloud-startup-refresh');
        
        if (autoRefreshToggle) autoRefreshToggle.checked = cloudAutoRefresh;
        if (midnightRefreshToggle) midnightRefreshToggle.checked = cloudMidnightRefresh;
        if (exchangeOverrideToggle) exchangeOverrideToggle.checked = cloudExchangeOverride;
        if (startupRefreshToggle) startupRefreshToggle.checked = cloudStartupRefresh;
    } catch (error) {
        console.error('Error loading cloud settings:', error);
    }
}

async function saveCloudSetting(key, value) {
    try {
        const response = await fetch(`${API_BASE}/settings/${key}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: value ? 'true' : 'false' })
        });
        return response.ok;
    } catch (error) {
        console.error('Error saving cloud setting:', error);
        return false;
    }
}

async function handleCloudSettingChange(event) {
    const toggle = event.target;
    const id = toggle.id;
    toggle.disabled = true;
    
    let key = '';
    if (id === 'cloud-auto-refresh') {
        key = 'cloud_auto_refresh';
        cloudAutoRefresh = toggle.checked;
    } else if (id === 'cloud-midnight-refresh') {
        key = 'cloud_midnight_refresh';
        cloudMidnightRefresh = toggle.checked;
    } else if (id === 'cloud-exchange-override') {
        key = 'cloud_exchange_override';
        cloudExchangeOverride = toggle.checked;
    } else if (id === 'cloud-startup-refresh') {
        key = 'cloud_startup_refresh';
        cloudStartupRefresh = toggle.checked;
    }
    
    const success = await saveCloudSetting(key, toggle.checked);
    if (!success) {
        toggle.checked = !toggle.checked;
        // Revert the variable
        if (id === 'cloud-auto-refresh') cloudAutoRefresh = !cloudAutoRefresh;
        else if (id === 'cloud-midnight-refresh') cloudMidnightRefresh = !cloudMidnightRefresh;
        else if (id === 'cloud-exchange-override') cloudExchangeOverride = !cloudExchangeOverride;
        else if (id === 'cloud-startup-refresh') cloudStartupRefresh = !cloudStartupRefresh;
        alert('클라우드 설정 저장 실패');
    } else {
        // Restart auto-refresh if settings changed
        if (cloudSyncEnabled) {
            stopCloudPriceAutoRefresh();
            startCloudPriceAutoRefresh();
        }
    }
    toggle.disabled = false;
}

async function handleCloudForceRefresh() {
    const btn = document.getElementById('cloud-force-refresh-btn');
    if (!cloudSyncEnabled || !btn) return;
    
    btn.disabled = true;
    btn.textContent = '갱신 중...';
    
    try {
        console.log('[Cloud] Manual force refresh triggered');
        await triggerCloudSync();
        await loadCloudPrices(false);
        const inventory = await fetchInventory(inventorySortBy, inventorySortOrder);
        renderInventory(inventory, true);
        btn.textContent = '완료!';
        setTimeout(() => {
            btn.textContent = '클라우드 강제 갱신';
            btn.disabled = false;
        }, 1500);
    } catch (error) {
        console.error('Error during force refresh:', error);
        btn.textContent = '실패';
        setTimeout(() => {
            btn.textContent = '클라우드 강제 갱신';
            btn.disabled = false;
        }, 1500);
    }
}

// Auto-refresh cloud prices
let cloudPriceRefreshInterval = null;
let midnightRefreshTimeout = null;

function startCloudPriceAutoRefresh() {
    if (cloudPriceRefreshInterval) {
        clearInterval(cloudPriceRefreshInterval);
    }
    if (midnightRefreshTimeout) {
        clearTimeout(midnightRefreshTimeout);
    }

    // Hourly refresh (preserve exchange-learned prices)
    cloudPriceRefreshInterval = setInterval(async () => {
        if (cloudSyncEnabled && cloudAutoRefresh) {
            console.log('[Cloud] Hourly refresh (preserving exchange prices)');
            await loadCloudPrices(cloudExchangeOverride);
            const inventory = await fetchInventory(inventorySortBy, inventorySortOrder);
            renderInventory(inventory, true);
        }
    }, 3600000);  // 1 hour

    // Schedule daily midnight full refresh
    if (cloudMidnightRefresh) {
        scheduleMidnightRefresh();
    }
}

function scheduleMidnightRefresh() {
    const now = new Date();
    const midnight = new Date(now);
    midnight.setHours(24, 0, 0, 0);  // Next midnight
    const msUntilMidnight = midnight.getTime() - now.getTime();

    console.log(`[Cloud] Scheduled full refresh at midnight (in ${Math.round(msUntilMidnight / 60000)} minutes)`);

    midnightRefreshTimeout = setTimeout(async () => {
        if (cloudSyncEnabled && cloudMidnightRefresh) {
            console.log('[Cloud] Midnight full refresh (triggering backend sync)');
            // Trigger backend sync to update cloud_price_cache timestamps
            await triggerCloudSync();
            // Then load the updated prices (force refresh, no preservation)
            await loadCloudPrices(false);
            const inventory = await fetchInventory(inventorySortBy, inventorySortOrder);
            renderInventory(inventory, true);
        }
        // Schedule next midnight
        scheduleMidnightRefresh();
    }, msUntilMidnight);
}

function stopCloudPriceAutoRefresh() {
    if (cloudPriceRefreshInterval) {
        clearInterval(cloudPriceRefreshInterval);
        cloudPriceRefreshInterval = null;
    }
    if (midnightRefreshTimeout) {
        clearTimeout(midnightRefreshTimeout);
        midnightRefreshTimeout = null;
    }
}

// --- No Character Modal ---

let noCharacterModalShown = false;

function showNoCharacterModal() {
    // Only show once per session
    if (noCharacterModalShown) return;
    noCharacterModalShown = true;
    document.getElementById('no-character-modal').classList.remove('hidden');
}

function closeNoCharacterModal() {
    document.getElementById('no-character-modal').classList.add('hidden');
}

// Close no-character modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'no-character-modal') {
        closeNoCharacterModal();
    }
});

// --- Settings Modal ---

let settingsModalShown = false;
let validatedLogPath = null;

// Store original settings when modal opens (for cancel functionality)
let originalSettings = {};
// Store pending settings changes (applied on save)
let pendingSettings = {};

async function openSettingsModal() {
    const modal = document.getElementById('settings-modal');
    const currentPathEl = document.getElementById('current-log-path');
    const inputEl = document.getElementById('log-directory-input');
    const statusEl = document.getElementById('log-path-status');
    const saveBtn = document.getElementById('save-log-dir-btn');
    const tradeTaxToggle = document.getElementById('settings-trade-tax');
    const mapCostsToggle = document.getElementById('settings-map-costs');

    // Reset log path state
    statusEl.textContent = '';
    statusEl.className = 'log-path-status';
    saveBtn.disabled = true;
    saveBtn.textContent = '저장 및 재시작';
    validatedLogPath = null;

    // Load current settings and store originals
    const tradeTaxValue = await fetchTradeTaxSetting();
    const mapCostsValue = await fetchMapCostsSetting();
    tradeTaxToggle.checked = tradeTaxValue;
    mapCostsToggle.checked = mapCostsValue;
    
    // Load pause settings from time state
    await loadPauseSettings();
    
    // Load refresh interval from localStorage
    const savedInterval = parseFloat(localStorage.getItem('refreshInterval')) || 1;
    document.getElementById('refresh-interval-slider').value = savedInterval;
    document.getElementById('refresh-interval-input').value = savedInterval;
    
    // Store original values for cancel functionality
    originalSettings = {
        tradeTax: tradeTaxValue,
        mapCosts: mapCostsValue,
        pauseBag: document.getElementById('pause-bag').checked,
        pausePet: document.getElementById('pause-pet').checked,
        pauseTalent: document.getElementById('pause-talent').checked,
        pauseSettings: document.getElementById('pause-settings').checked,
        pauseSkill: document.getElementById('pause-skill').checked,
        pauseAuction: document.getElementById('pause-auction').checked,
        cloudAutoRefresh: document.getElementById('cloud-auto-refresh').checked,
        cloudMidnightRefresh: document.getElementById('cloud-midnight-refresh').checked,
        cloudExchangeOverride: document.getElementById('cloud-exchange-override').checked,
        cloudStartupRefresh: document.getElementById('cloud-startup-refresh').checked,
        refreshInterval: savedInterval,
        // Overlay settings (loaded from API)
        overlayOpacity: 90,
        overlayScale: 100,
        overlayTextShadow: true,
        overlayColumns: ['profit','run_time','total_profit','total_time','map_hr','total_hr','contract']
    };

    // Reset pending settings
    pendingSettings = {};

    // Ensure overlay settings section is visible in pywebview mode
    if (typeof window.pywebview !== 'undefined') {
        const overlaySection = document.getElementById('overlay-settings-section');
        if (overlaySection) overlaySection.style.display = '';
    }

    // Load overlay settings from API if in pywebview mode
    if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
        try {
            const overlayResp = await fetch(`${API_BASE}/overlay/config`);
            if (overlayResp.ok) {
                const overlayConfig = await overlayResp.json();
                const bgOpacityPct = Math.round((overlayConfig.bg_opacity != null ? overlayConfig.bg_opacity : 0.7) * 100);
                const scalePct = Math.round((overlayConfig.scale || 1.0) * 100);

                document.getElementById('settings-overlay-opacity').value = bgOpacityPct;
                document.getElementById('settings-overlay-opacity-val').textContent = bgOpacityPct + '%';
                document.getElementById('settings-overlay-scale').value = scalePct;
                document.getElementById('settings-overlay-scale-val').textContent = scalePct + '%';
                document.getElementById('settings-overlay-text-shadow').checked = overlayConfig.text_shadow !== false;

                // Set column checkboxes
                const cols = overlayConfig.visible_columns || ['profit','run_time','total_profit','total_time','map_hr','total_hr','contract'];
                document.querySelectorAll('.overlay-col-toggle input').forEach(cb => {
                    cb.checked = cols.includes(cb.value);
                });

                // Load preset
                const preset = overlayConfig.preset || 1;
                document.querySelectorAll('.preset-btn').forEach(b => {
                    b.classList.toggle('active', parseInt(b.dataset.preset) === preset);
                });
                const desc = document.getElementById('preset-desc');
                if (desc) {
                    const descs = {'1':'가로 1행','2':'가로 2행','3':'세로 왼쪽'};
                    desc.textContent = descs[preset] || '가로 1행';
                }

                // Store originals
                originalSettings.overlayOpacity = bgOpacityPct;
                originalSettings.overlayScale = scalePct;
                originalSettings.overlayTextShadow = overlayConfig.text_shadow !== false;
                originalSettings.overlayColumns = [...cols];
                originalSettings.overlayPreset = preset;
            }
        } catch (e) {
            console.error('Failed to load overlay config:', e);
        }
    }

    // Fetch current log path from status
    try {
        const status = await fetchStatus();
        if (status && status.log_path) {
            currentPathEl.textContent = status.log_path;
            // Extract game directory from full path
            const pathParts = status.log_path.split('\\');
            if (pathParts.length > 5) {
                const gameDir = pathParts.slice(0, -5).join('\\');
                inputEl.value = gameDir;
            }
        } else {
            currentPathEl.textContent = 'Not found - please configure below';
            inputEl.value = '';
        }
    } catch (error) {
        currentPathEl.textContent = 'Unable to fetch current path';
    }

    modal.classList.remove('hidden');
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.add('hidden');
}

// Cancel settings - revert to original values and close
function cancelSettings() {
    // Revert all toggles to original values
    document.getElementById('settings-trade-tax').checked = originalSettings.tradeTax;
    document.getElementById('settings-map-costs').checked = originalSettings.mapCosts;
    document.getElementById('pause-bag').checked = originalSettings.pauseBag;
    document.getElementById('pause-pet').checked = originalSettings.pausePet;
    document.getElementById('pause-talent').checked = originalSettings.pauseTalent;
    document.getElementById('pause-settings').checked = originalSettings.pauseSettings;
    document.getElementById('pause-skill').checked = originalSettings.pauseSkill;
    document.getElementById('pause-auction').checked = originalSettings.pauseAuction;
    document.getElementById('cloud-auto-refresh').checked = originalSettings.cloudAutoRefresh;
    document.getElementById('cloud-midnight-refresh').checked = originalSettings.cloudMidnightRefresh;
    document.getElementById('cloud-exchange-override').checked = originalSettings.cloudExchangeOverride;
    document.getElementById('cloud-startup-refresh').checked = originalSettings.cloudStartupRefresh;
    document.getElementById('refresh-interval-slider').value = originalSettings.refreshInterval;
    document.getElementById('refresh-interval-input').value = originalSettings.refreshInterval;

    // Revert overlay settings
    if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
        document.getElementById('settings-overlay-opacity').value = originalSettings.overlayOpacity;
        document.getElementById('settings-overlay-opacity-val').textContent = originalSettings.overlayOpacity + '%';
        document.getElementById('settings-overlay-scale').value = originalSettings.overlayScale;
        document.getElementById('settings-overlay-scale-val').textContent = originalSettings.overlayScale + '%';
        document.getElementById('settings-overlay-text-shadow').checked = originalSettings.overlayTextShadow;
        document.querySelectorAll('.overlay-col-toggle input').forEach(cb => {
            cb.checked = (originalSettings.overlayColumns || []).includes(cb.value);
        });
    }

    // Clear pending and close
    pendingSettings = {};
    closeSettingsModal();
}

// Save all settings at once
async function saveAllSettings() {
    try {
        // Get current toggle values
        const tradeTaxVal = document.getElementById('settings-trade-tax').checked;
        const mapCostsVal = document.getElementById('settings-map-costs').checked;
        const pauseBagVal = document.getElementById('pause-bag').checked;
        const pausePetVal = document.getElementById('pause-pet').checked;
        const pauseTalentVal = document.getElementById('pause-talent').checked;
        const pauseSettingsVal = document.getElementById('pause-settings').checked;
        const pauseSkillVal = document.getElementById('pause-skill').checked;
        const pauseAuctionVal = document.getElementById('pause-auction').checked;
        const cloudAutoRefreshVal = document.getElementById('cloud-auto-refresh').checked;
        const cloudMidnightRefreshVal = document.getElementById('cloud-midnight-refresh').checked;
        const cloudExchangeOverrideVal = document.getElementById('cloud-exchange-override').checked;
        const cloudStartupRefreshVal = document.getElementById('cloud-startup-refresh').checked;
        const refreshIntervalVal = parseFloat(document.getElementById('refresh-interval-input').value) || 1;
        
        // Save trade tax setting using existing function
        if (tradeTaxVal !== originalSettings.tradeTax) {
            await updateTradeTaxSetting(tradeTaxVal);
        }
        
        // Save map costs setting using existing function
        if (mapCostsVal !== originalSettings.mapCosts) {
            await updateMapCostsSetting(mapCostsVal);
            mapCostsEnabled = mapCostsVal;
        }
        
        // Save pause settings if changed
        const pauseChanged = 
            pauseBagVal !== originalSettings.pauseBag ||
            pausePetVal !== originalSettings.pausePet ||
            pauseTalentVal !== originalSettings.pauseTalent ||
            pauseSettingsVal !== originalSettings.pauseSettings ||
            pauseSkillVal !== originalSettings.pauseSkill ||
            pauseAuctionVal !== originalSettings.pauseAuction;
        
        if (pauseChanged) {
            // Use correct keys matching savePauseSettings format
            await fetch(`${API_BASE}/time/pause-settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bag: pauseBagVal,
                    pet: pausePetVal,
                    talent: pauseTalentVal,
                    settings: pauseSettingsVal,
                    skill: pauseSkillVal,
                    auction: pauseAuctionVal
                })
            });
        }
        
        // Save cloud settings if changed
        const cloudChanged =
            cloudAutoRefreshVal !== originalSettings.cloudAutoRefresh ||
            cloudMidnightRefreshVal !== originalSettings.cloudMidnightRefresh ||
            cloudExchangeOverrideVal !== originalSettings.cloudExchangeOverride ||
            cloudStartupRefreshVal !== originalSettings.cloudStartupRefresh;
        
        if (cloudChanged) {
            await fetch(`${API_BASE}/cloud/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    auto_refresh: cloudAutoRefreshVal,
                    midnight_refresh: cloudMidnightRefreshVal,
                    exchange_override: cloudExchangeOverrideVal,
                    startup_refresh: cloudStartupRefreshVal
                })
            });
            // Update global state with correct variable names
            cloudAutoRefresh = cloudAutoRefreshVal;
            cloudMidnightRefresh = cloudMidnightRefreshVal;
            cloudExchangeOverride = cloudExchangeOverrideVal;
            cloudStartupRefresh = cloudStartupRefreshVal;
        }
        
        // Save refresh interval
        if (refreshIntervalVal !== originalSettings.refreshInterval) {
            updateRefreshInterval(refreshIntervalVal);
        }

        // Save overlay settings if in pywebview mode
        if (typeof window.pywebview !== 'undefined' && window.pywebview.api) {
            const newOpacity = parseInt(document.getElementById('settings-overlay-opacity').value);
            const newScale = parseInt(document.getElementById('settings-overlay-scale').value);
            const newTextShadow = document.getElementById('settings-overlay-text-shadow').checked;
            const newColumns = [];
            document.querySelectorAll('.overlay-col-toggle input:checked').forEach(cb => {
                newColumns.push(cb.value);
            });

            const presetBtn = document.querySelector('.preset-btn.active');
            const newPreset = presetBtn ? parseInt(presetBtn.dataset.preset) : 1;

            const overlayUpdates = {};
            if (newOpacity !== originalSettings.overlayOpacity) {
                overlayUpdates.bg_opacity = newOpacity / 100;
                localStorage.setItem('overlay_opacity', newOpacity);
            }
            if (newScale !== originalSettings.overlayScale) {
                overlayUpdates.scale = newScale / 100;
                localStorage.setItem('overlay_scale', newScale);
            }
            if (newTextShadow !== originalSettings.overlayTextShadow) {
                overlayUpdates.text_shadow = newTextShadow;
            }
            const origCols = (originalSettings.overlayColumns || []).sort().join(',');
            const newCols = newColumns.sort().join(',');
            if (origCols !== newCols) {
                overlayUpdates.visible_columns = newColumns;
            }
            if (newPreset !== (originalSettings.overlayPreset || 1)) {
                overlayUpdates.preset = newPreset;
            }

            if (Object.keys(overlayUpdates).length > 0) {
                try {
                    await fetch(`${API_BASE}/overlay/config`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(overlayUpdates)
                    });
                } catch (e) {
                    console.error('Failed to save overlay config:', e);
                }
            }
        }

        // Close modal
        closeSettingsModal();
        
        // Refresh data to apply changes
        refreshAll(true);
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('설정 저장 중 오류가 발생했습니다.');
    }
}

// Show settings modal when log path missing (called from renderStatus)
function showLogPathModal() {
    // Only show once per session
    if (settingsModalShown) return;
    settingsModalShown = true;
    openSettingsModal();
}

// Close settings modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'settings-modal') {
        closeSettingsModal();
    }
});

// Browse for game folder using native dialog (only works in pywebview window mode)
async function browseForGameFolder() {
    // Check if pywebview API is available
    if (window.pywebview && window.pywebview.api) {
        try {
            const path = await window.pywebview.api.browse_folder();
            if (path) {
                document.getElementById('log-directory-input').value = path;
                // Automatically validate after selection
                validateLogDirectory();
            }
        } catch (e) {
            console.error('Browse dialog error:', e);
        }
    } else {
        alert('Browse is only available in native window mode.');
    }
}

// Initialize browse button visibility (show only if pywebview is available)
function initBrowseButton() {
    const browseBtn = document.getElementById('browse-folder-btn');
    if (browseBtn) {
        // pywebview.api may not be immediately available, check with a small delay
        setTimeout(() => {
            if (window.pywebview && window.pywebview.api) {
                browseBtn.style.display = 'inline-block';
            }
        }, 500);
    }
}

// Call on page load
document.addEventListener('DOMContentLoaded', initBrowseButton);

async function validateLogDirectory() {
    const input = document.getElementById('log-directory-input');
    const status = document.getElementById('log-path-status');
    const saveBtn = document.getElementById('save-log-dir-btn');
    const path = input.value.trim();

    if (!path) {
        status.textContent = '경로를 입력해주세요';
        status.className = 'log-path-status error';
        saveBtn.disabled = true;
        return;
    }

    status.textContent = '확인 중...';
    status.className = 'log-path-status validating';
    saveBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/settings/log-directory/validate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.valid) {
            status.textContent = `찾음: ${result.log_path}`;
            status.className = 'log-path-status success';
            validatedLogPath = path;
            saveBtn.disabled = false;
        } else {
            status.textContent = result.error || '이 위치에서 로그 파일을 찾을 수 없음';
            status.className = 'log-path-status error';
            validatedLogPath = null;
            saveBtn.disabled = true;
        }
    } catch (error) {
        console.error('Error validating log directory:', error);
        status.textContent = '경로 확인 중 오류. 다시 시도해주세요.';
        status.className = 'log-path-status error';
        validatedLogPath = null;
        saveBtn.disabled = true;
    }
}

async function saveLogDirectory() {
    if (!validatedLogPath) return;

    const saveBtn = document.getElementById('save-log-dir-btn');
    const status = document.getElementById('log-path-status');

    saveBtn.disabled = true;
    saveBtn.textContent = '저장 중...';

    try {
        const response = await fetch(`${API_BASE}/settings/log_directory`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: validatedLogPath })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        status.textContent = '저장됨! 변경사항을 적용하려면 결정 트래커를 재시작하세요.';
        status.className = 'log-path-status success';
        saveBtn.textContent = '저장됨 - 재시작 필요';

        // Show a more prominent message
        alert('로그 경로가 저장되었습니다! 변경사항을 적용하려면 결정 트래커를 재시작하세요.');

    } catch (error) {
        console.error('Error saving log directory:', error);
        status.textContent = '저장 중 오류. 다시 시도해주세요.';
        status.className = 'log-path-status error';
        saveBtn.disabled = false;
        saveBtn.textContent = '저장 및 재시작';
    }
}

// Chart configuration
const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
        intersect: false,
        mode: 'index',
    },
    plugins: {
        legend: {
            display: false,
        },
        tooltip: {
            backgroundColor: 'rgba(22, 33, 62, 0.9)',
            titleColor: '#eaeaea',
            bodyColor: '#eaeaea',
            borderColor: '#2a2a4a',
            borderWidth: 1,
        },
    },
    scales: {
        x: {
            type: 'time',
            time: {
                displayFormats: {
                    hour: 'HH:mm',
                    minute: 'HH:mm',
                },
            },
            grid: {
                color: 'rgba(42, 42, 74, 0.5)',
            },
            ticks: {
                color: '#a0a0a0',
                maxTicksLimit: 6,
            },
        },
        y: {
            beginAtZero: true,
            grid: {
                color: 'rgba(42, 42, 74, 0.5)',
            },
            ticks: {
                color: '#a0a0a0',
            },
        },
    },
};

function renderCharts(data, forceRender = false) {
    const newHash = simpleHash(data);
    if (!forceRender && newHash === lastStatsHash) {
        return; // No change
    }
    lastStatsHash = newHash;

    // Prepare data for cumulative value chart
    const cumulativeValueData = (data?.cumulative_value || []).map(p => ({
        x: new Date(p.timestamp),
        y: p.value,
    }));

    // Prepare data for value/hour chart
    const valueRateData = (data?.value_per_hour || []).map(p => ({
        x: new Date(p.timestamp),
        y: p.value,
    }));

    // Render or update Cumulative Value chart
    const cumulativeValueCtx = document.getElementById('cumulative-value-chart');
    if (cumulativeValueCtx) {
        if (cumulativeValueChart) {
            cumulativeValueChart.data.datasets[0].data = cumulativeValueData;
            cumulativeValueChart.update('none');
        } else {
            cumulativeValueChart = new Chart(cumulativeValueCtx, {
                type: 'line',
                data: {
                    datasets: [{
                        data: cumulativeValueData,
                        borderColor: '#e94560',
                        backgroundColor: 'rgba(233, 69, 96, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                    }],
                },
                options: {
                    ...chartOptions,
                    plugins: {
                        ...chartOptions.plugins,
                        tooltip: {
                            ...chartOptions.plugins.tooltip,
                            callbacks: {
                                label: (ctx) => `Value: ${formatNumber(Math.round(ctx.parsed.y))} 결정`,
                            },
                        },
                    },
                },
            });
        }
    }

    // Render or update Value Rate chart
    const valueRateCtx = document.getElementById('value-rate-chart');
    if (valueRateCtx) {
        if (valueRateChart) {
            valueRateChart.data.datasets[0].data = valueRateData;
            valueRateChart.update('none');
        } else {
            valueRateChart = new Chart(valueRateCtx, {
                type: 'line',
                data: {
                    datasets: [{
                        data: valueRateData,
                        borderColor: '#4ecca3',
                        backgroundColor: 'rgba(78, 204, 163, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                    }],
                },
                options: {
                    ...chartOptions,
                    plugins: {
                        ...chartOptions.plugins,
                        tooltip: {
                            ...chartOptions.plugins.tooltip,
                            callbacks: {
                                label: (ctx) => `Value/hr: ${formatNumber(Math.round(ctx.parsed.y))} 결정`,
                            },
                        },
                    },
                },
            });
        }
    }
}

function updateLastRefresh() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    document.getElementById('last-update').textContent = `마지막 업데이트: ${timeStr}`;
}

// --- Modal ---

async function showRunDetails(runId) {
    const run = lastRunsData?.runs?.find(r => r.id === runId);
    if (!run) return;

    const modal = document.getElementById('loot-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');

    title.textContent = `${run.zone_name} - ${formatDuration(run.duration_seconds)}`;

    let content = '';

    // Show summary at top (fixed position)
    const netValue = run.net_value_fe !== null ? run.net_value_fe : run.total_value;
    const hasCosts = run.map_cost_fe !== null && run.map_cost_fe !== undefined && run.map_cost_fe > 0;
    const costTooltip = hasCosts ? buildCostTooltip(run.map_cost_items) : '';
    const warningIcon = run.map_cost_has_unpriced
        ? ' <span class="cost-warning" title="가격 미확인 아이템 포함">⚠</span>'
        : '';
    
    content += `
        <div class="run-summary-fixed">
            <div class="run-summary-row">
                <span class="run-summary-label">총 수익</span>
                <span class="run-summary-value">${formatFEValue(run.total_value)} 결정</span>
            </div>
            ${hasCosts ? `
            <div class="run-summary-row">
                <span class="run-summary-label">입장 비용</span>
                <span class="run-summary-value negative cost-hover" title="${costTooltip}">-${formatFEValue(run.map_cost_fe)} 결정${warningIcon}</span>
            </div>
            ` : ''}
            <div class="run-summary-row total">
                <span class="run-summary-label">순수익</span>
                <span class="run-summary-value ${netValue >= 0 ? 'positive' : 'negative'}">${formatFEValue(netValue)} 결정</span>
            </div>
        </div>
    `;

    // Scrollable items section
    content += '<div class="run-items-scroll">';

    // Show consumed items (map costs) in red
    if (run.map_cost_items && run.map_cost_items.length > 0) {
        content += `
            <div class="run-items-section consumed">
                <h4 class="run-items-header">소모된 아이템</h4>
                <ul class="loot-list">
                    ${run.map_cost_items.map(item => {
                        const iconHtml = getIconHtml(item.config_base_id, 'loot-item-icon');
                        const valueStr = item.total_value_fe !== null
                            ? `${item.total_value_fe.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} 결정`
                            : '<span class="no-price">가격 미확인</span>';
                        return `
                            <li class="loot-item consumed-item">
                                <div class="loot-item-name">
                                    ${iconHtml}
                                    <span>${escapeHtml(item.name)}</span>
                                </div>
                                <div class="loot-item-values">
                                    <span class="loot-item-qty negative">-${valueStr}</span>
                                    <span class="loot-item-value">x${formatNumber(Math.abs(item.quantity))}</span>
                                </div>
                            </li>
                        `;
                    }).join('')}
                </ul>
            </div>
        `;
    }

    // Show loot section
    if (!run.loot || run.loot.length === 0) {
        content += '<p class="no-loot-message">기록된 전리품이 없습니다.</p>';
    } else {
        // Sort by FE value (highest first), items without price at the end
        const sortedLoot = [...run.loot].sort((a, b) => {
            const aVal = a.total_value_fe ?? -Infinity;
            const bVal = b.total_value_fe ?? -Infinity;
            return bVal - aVal;
        });
        content += `
            <div class="run-items-section loot">
                <h4 class="run-items-header">획득한 아이템</h4>
                <ul class="loot-list">
                    ${sortedLoot.map(item => {
                        const iconHtml = getIconHtml(item.config_base_id, 'loot-item-icon');
                        const valueStr = item.total_value_fe !== null
                            ? `${item.total_value_fe.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} 결정`
                            : '<span class="no-price">가격 미확인</span>';
                        return `
                            <li class="loot-item">
                                <div class="loot-item-name">
                                    ${iconHtml}
                                    <span>${escapeHtml(item.name)}</span>
                                </div>
                                <div class="loot-item-values">
                                    <span class="loot-item-qty ${item.total_value_fe !== null ? (item.total_value_fe > 0 ? 'positive' : 'negative') : ''}">${valueStr}</span>
                                    <span class="loot-item-value">x${formatNumber(Math.abs(item.quantity))}</span>
                                </div>
                            </li>
                        `;
                    }).join('')}
                </ul>
            </div>
        `;
    }

    content += '</div>'; // Close run-items-scroll

    body.innerHTML = content;
    modal.classList.remove('hidden');
}

function closeModal() {
    document.getElementById('loot-modal').classList.add('hidden');
}

// Close modal on outside click
document.getElementById('loot-modal').addEventListener('click', (e) => {
    if (e.target.id === 'loot-modal') {
        closeModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeHelpModal();
        closePriceHistoryModal();
        closeSettingsModal();
        closeLootReportModal();
    }
});

// --- Price History Modal ---

async function showPriceHistory(configBaseId, itemName) {
    const modal = document.getElementById('price-history-modal');
    const title = document.getElementById('price-history-title');
    const chartCanvas = document.getElementById('price-history-chart');

    title.textContent = `Price History: ${itemName}`;

    // Show loading state
    document.getElementById('price-stat-median').textContent = '...';
    document.getElementById('price-stat-p10').textContent = '...';
    document.getElementById('price-stat-p90').textContent = '...';
    document.getElementById('price-stat-contributors').textContent = '...';

    modal.classList.remove('hidden');

    // Fetch history data
    const data = await fetchCloudPriceHistory(configBaseId);

    if (!data || !data.history || data.history.length === 0) {
        // No history available
        if (priceHistoryChart) {
            priceHistoryChart.destroy();
            priceHistoryChart = null;
        }
        document.getElementById('price-stat-median').textContent = 'No data';
        document.getElementById('price-stat-p10').textContent = '--';
        document.getElementById('price-stat-p90').textContent = '--';
        document.getElementById('price-stat-contributors').textContent = '--';
        return;
    }

    // Prepare chart data
    const chartData = data.history.map(h => ({
        x: new Date(h.hour_bucket),
        y: h.price_fe_median
    }));

    const p10Data = data.history.map(h => ({
        x: new Date(h.hour_bucket),
        y: h.price_fe_p10 || h.price_fe_median
    }));

    const p90Data = data.history.map(h => ({
        x: new Date(h.hour_bucket),
        y: h.price_fe_p90 || h.price_fe_median
    }));

    // Update stats from latest point
    const latest = data.history[data.history.length - 1];
    document.getElementById('price-stat-median').textContent = formatFEValue(latest.price_fe_median);
    document.getElementById('price-stat-p10').textContent = latest.price_fe_p10 ? formatFEValue(latest.price_fe_p10) : '--';
    document.getElementById('price-stat-p90').textContent = latest.price_fe_p90 ? formatFEValue(latest.price_fe_p90) : '--';

    // Get contributors from cloud cache
    const cloudPrice = cloudPricesCache[configBaseId];
    document.getElementById('price-stat-contributors').textContent = cloudPrice?.unique_devices || '--';

    // Create or update chart
    if (priceHistoryChart) {
        priceHistoryChart.destroy();
    }

    priceHistoryChart = new Chart(chartCanvas, {
        type: 'line',
        data: {
            datasets: [
                {
                    label: 'Median',
                    data: chartData,
                    borderColor: '#e94560',
                    backgroundColor: 'rgba(233, 69, 96, 0.1)',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                },
                {
                    label: 'P10 (Low)',
                    data: p10Data,
                    borderColor: 'rgba(78, 204, 163, 0.5)',
                    backgroundColor: 'rgba(78, 204, 163, 0.1)',
                    fill: '+1',
                    tension: 0.3,
                    pointRadius: 0,
                    borderDash: [5, 5],
                },
                {
                    label: 'P90 (High)',
                    data: p90Data,
                    borderColor: 'rgba(255, 107, 107, 0.5)',
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    borderDash: [5, 5],
                }
            ],
        },
        options: {
            ...chartOptions,
            plugins: {
                ...chartOptions.plugins,
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#a0a0a0',
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    ...chartOptions.plugins.tooltip,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatFEValue(ctx.parsed.y)} 결정`,
                    },
                },
            },
        },
    });
}

function closePriceHistoryModal() {
    document.getElementById('price-history-modal').classList.add('hidden');
}

// Close price history modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'price-history-modal') {
        closePriceHistoryModal();
    }
});

// --- Loot Report Modal ---

function formatDurationLong(seconds) {
    if (!seconds) return '--';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
        return `${hours}시간 ${mins}분`;
    }
    return `${mins}분`;
}

async function showLootReport() {
    const modal = document.getElementById('loot-report-modal');
    const tableBody = document.getElementById('loot-report-table-body');

    // Show loading state
    tableBody.innerHTML = '<tr><td colspan="5" class="loading">리포트 로딩 중...</td></tr>';
    document.getElementById('report-total-value').textContent = '...';
    document.getElementById('report-profit').textContent = '...';
    document.getElementById('report-total-items').textContent = '...';
    document.getElementById('report-run-count').textContent = '...';
    document.getElementById('report-total-time').textContent = '...';
    document.getElementById('report-profit-per-hour').textContent = '...';
    document.getElementById('report-profit-per-map').textContent = '...';

    modal.classList.remove('hidden');

    // Fetch report data
    const data = await fetchLootReport();
    lastLootReportData = data;

    if (!data) {
        tableBody.innerHTML = '<tr><td colspan="5" class="loading">리포트 로딩 실패</td></tr>';
        return;
    }

    // Update summary stats
    document.getElementById('report-total-value').textContent = formatFEValue(data.total_value_fe) + ' 결정';
    document.getElementById('report-profit').textContent = formatFEValue(data.profit_fe) + ' 결정';
    document.getElementById('report-total-items').textContent = formatNumber(data.total_items);
    document.getElementById('report-run-count').textContent = formatNumber(data.run_count);
    document.getElementById('report-total-time').textContent = formatDurationLong(data.total_duration_seconds);
    document.getElementById('report-profit-per-hour').textContent = formatNumber(Math.round(data.profit_per_hour)) + ' 결정';
    document.getElementById('report-profit-per-map').textContent = formatNumber(Math.round(data.profit_per_map)) + ' 결정';

    // Show/hide map costs based on setting
    const costStat = document.getElementById('report-cost-stat');
    if (data.map_costs_enabled && data.total_map_cost_fe > 0) {
        document.getElementById('report-map-costs').textContent = '-' + formatFEValue(data.total_map_cost_fe) + ' 결정';
        costStat.classList.remove('hidden');
    } else {
        costStat.classList.add('hidden');
    }

    // Handle empty state
    if (!data.items || data.items.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="loading">아직 기록된 루팅이 없습니다. 런을 완료하면 리포트가 표시됩니다.</td></tr>';
        // Clear any existing chart
        if (lootReportChart) {
            lootReportChart.destroy();
            lootReportChart = null;
        }
        return;
    }

    // Render table
    tableBody.innerHTML = data.items.map(item => {
        const iconHtml = getIconHtml(item.config_base_id, 'item-icon');
        const priceText = item.price_fe !== null ? formatFEValue(item.price_fe) : '<span class="no-price">--</span>';
        const valueText = item.total_value_fe !== null ? formatFEValue(item.total_value_fe) : '<span class="no-price">--</span>';
        const percentText = item.percentage !== null ? `${item.percentage.toFixed(1)}%` : '--';

        return `
            <tr>
                <td>
                    <div class="item-col">
                        ${iconHtml}
                        <span>${escapeHtml(item.name)}</span>
                    </div>
                </td>
                <td>${formatNumber(item.quantity)}</td>
                <td>${priceText}</td>
                <td>${valueText}</td>
                <td>${percentText}</td>
            </tr>
        `;
    }).join('');

    // Render chart (top 10 items + "Other")
    renderLootReportChart(data);
}

function renderLootReportChart(data) {
    const canvas = document.getElementById('loot-report-chart');

    // Destroy existing chart
    if (lootReportChart) {
        lootReportChart.destroy();
        lootReportChart = null;
    }

    // Filter items with value and sort by value
    const pricedItems = data.items.filter(item => item.total_value_fe !== null && item.total_value_fe > 0);

    if (pricedItems.length === 0) {
        return;
    }

    // Take top 10, group rest as "Other"
    const top10 = pricedItems.slice(0, 10);
    const others = pricedItems.slice(10);

    const labels = top10.map(item => item.name);
    const values = top10.map(item => item.total_value_fe);

    // Add "Other" category if there are more items
    if (others.length > 0) {
        const otherValue = others.reduce((sum, item) => sum + (item.total_value_fe || 0), 0);
        labels.push(`기타 (${others.length}개 아이템)`);
        values.push(otherValue);
    }

    // Color palette matching app theme
    const colors = [
        '#e94560',  // Accent red
        '#4ecca3',  // Positive green
        '#ff6b6b',  // Accent secondary
        '#64b5f6',  // Light blue
        '#ffb74d',  // Orange
        '#ba68c8',  // Purple
        '#4db6ac',  // Teal
        '#f06292',  // Pink
        '#7986cb',  // Indigo
        '#aed581',  // Light green
        '#9e9e9e',  // Gray (for "Other")
    ];

    // Include percentage in labels for the legend
    const labelsWithPercent = labels.map((label, i) => {
        const total = values.reduce((a, b) => a + b, 0);
        const percentage = ((values[i] / total) * 100).toFixed(1);
        const truncLabel = label.length > 18 ? label.substring(0, 16) + '...' : label;
        return `${truncLabel} (${percentage}%)`;
    });

    lootReportChart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labelsWithPercent,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: 'rgba(22, 33, 62, 0.8)',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#a0a0a0',
                        padding: 8,
                        usePointStyle: true,
                        font: {
                            size: 11,
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 33, 62, 0.9)',
                    titleColor: '#eaeaea',
                    bodyColor: '#eaeaea',
                    borderColor: '#2a2a4a',
                    borderWidth: 1,
                    callbacks: {
                        label: function(ctx) {
                            const value = ctx.parsed;
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${formatFEValue(value)} 결정 (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

function closeLootReportModal() {
    document.getElementById('loot-report-modal').classList.add('hidden');
}

// Close loot report modal on outside click
document.addEventListener('click', (e) => {
    if (e.target.id === 'loot-report-modal') {
        closeLootReportModal();
    }
});

async function exportLootReportCSV() {
    if (!lastLootReportData || !lastLootReportData.items) {
        alert('내보낼 데이터가 없습니다');
        return;
    }

    try {
        // Fetch CSV from server
        const response = await fetch(`${API_BASE}/runs/report/csv`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const csvContent = await response.text();
        const filename = `titrack-loot-report-${new Date().toISOString().split('T')[0]}.csv`;

        // Try using the File System Access API (modern browsers)
        if (window.showSaveFilePicker) {
            try {
                const handle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: [{
                        description: 'CSV Files',
                        accept: { 'text/csv': ['.csv'] },
                    }],
                });
                const writable = await handle.createWritable();
                await writable.write(csvContent);
                await writable.close();
                showToast(`${handle.name}으로 내보냄`, 'success');
                return;
            } catch (err) {
                // User cancelled or API not supported, fall through to legacy method
                if (err.name === 'AbortError') {
                    return; // User cancelled
                }
            }
        }

        // Fallback: Create blob and download link
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        showToast(`다운로드 폴더에 ${filename}으로 내보냄`, 'success');
    } catch (error) {
        console.error('Error exporting CSV:', error);
        showToast('CSV 내보내기 실패', 'error');
    }
}

// --- Help Modal ---

function openHelpModal() {
    document.getElementById('help-modal').classList.remove('hidden');
}

function closeHelpModal() {
    document.getElementById('help-modal').classList.add('hidden');
}

// Close help modal on outside click
document.getElementById('help-modal').addEventListener('click', (e) => {
    if (e.target.id === 'help-modal') {
        closeHelpModal();
    }
});

// --- Data Refresh ---

async function refreshAll(forceRender = false) {
    try {
        const [status, stats, runs, inventory, statsHistory, player, cloudStatus, activeRun, perfStats] = await Promise.all([
            fetchStatus(),
            fetchStats(),
            fetchRuns(),
            fetchInventory(),
            fetchStatsHistory(24),
            fetchPlayer(),
            fetchCloudStatus(),
            fetchActiveRun(),
            fetchPerformanceStats()
        ]);

        lastRunsData = runs;
        lastInventoryData = inventory;

        renderStatus(status);
        renderStats(stats, inventory);
        renderPerformanceStats(perfStats);
        renderCloudStatus(cloudStatus);
        renderActiveRun(activeRun, forceRender);

        // Filter out active/incomplete runs from recent runs list
        // A run is complete if it has end_ts set
        let filteredRuns = runs;
        if (runs?.runs) {
            filteredRuns = {
                ...runs,
                runs: runs.runs.filter(r => r.end_ts != null)
            };
        }
        renderRuns(filteredRuns, forceRender);

        // Load cloud prices if sync is enabled
        if (cloudStatus && cloudStatus.enabled && Object.keys(cloudPricesCache).length === 0) {
            await loadCloudPrices(cloudExchangeOverride);
        }

        renderInventory(inventory, forceRender);
        renderCharts(statsHistory, forceRender);

        // Check if player changed and update display
        const playerHash = simpleHash(player);
        if (forceRender || playerHash !== lastPlayerHash) {
            renderPlayer(player);
            lastPlayerHash = playerHash;

            // Auto-close no-character modal when character is detected
            if (player && noCharacterModalShown) {
                closeNoCharacterModal();
            }
        }

        updateLastRefresh();
        
        // Sync inventory height after rendering
        syncInventoryHeight();
    } catch (error) {
        console.error('Error refreshing data:', error);
    }
}

function startAutoRefresh() {
    if (refreshTimer) return;
    refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

function updateRefreshInterval(seconds) {
    // Clamp to valid range
    seconds = Math.max(1, Math.min(5, parseFloat(seconds) || 1));
    REFRESH_INTERVAL = seconds * 1000;
    
    // Update UI controls
    const slider = document.getElementById('refresh-interval-slider');
    const input = document.getElementById('refresh-interval-input');
    if (slider) slider.value = seconds;
    if (input) input.value = seconds;
    
    // Restart the timer with new interval
    if (refreshTimer) {
        stopAutoRefresh();
        startAutoRefresh();
    }
    
    // Save to localStorage
    localStorage.setItem('refreshInterval', seconds);
}

function initRefreshIntervalControls() {
    const slider = document.getElementById('refresh-interval-slider');
    const input = document.getElementById('refresh-interval-input');
    
    // Load saved value and apply it
    const saved = localStorage.getItem('refreshInterval');
    if (saved) {
        const seconds = parseFloat(saved);
        REFRESH_INTERVAL = seconds * 1000;
        if (slider) slider.value = seconds;
        if (input) input.value = seconds;
    }
    
    // Slider event - sync with input (UI only, save happens on Save button)
    if (slider) {
        slider.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            if (input) input.value = val;
        });
    }
    
    // Input event - sync with slider (UI only, save happens on Save button)
    if (input) {
        input.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            if (slider) slider.value = val;
        });
    }
}

// --- Reset Stats Modal ---

function resetStats() {
    document.getElementById('reset-modal').classList.remove('hidden');
}

function closeResetModal() {
    document.getElementById('reset-modal').classList.add('hidden');
}

async function executeReset(type) {
    const btn = event.target.closest('.reset-option-btn');
    if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.5';
    }
    
    let success = false;
    
    try {
        if (type === 'runs') {
            const result = await postResetStats();
            success = result && result.success;
        } else if (type === 'mapping') {
            const response = await fetch(`${API_BASE}/time/reset/mapping`, { method: 'POST' });
            const result = await response.json();
            success = result && result.success;
        } else if (type === 'total') {
            const response = await fetch(`${API_BASE}/time/reset/total`, { method: 'POST' });
            const result = await response.json();
            success = result && result.success;
        } else if (type === 'all') {
            const runsResult = await postResetStats();
            const timeResponse = await fetch(`${API_BASE}/time/reset/all`, { method: 'POST' });
            const timeResult = await timeResponse.json();
            success = (runsResult && runsResult.success) && (timeResult && timeResult.success);
        }
        
        if (success) {
            lastRunsHash = null;
            lastStatsHash = null;
            lastInventoryHash = null;
            lastActiveRunHash = null;
            lastActiveRunId = null;
            lastPlayerHash = null;
            
            await refreshAll(true);
            await syncTimeState();
            closeResetModal();
        } else {
            alert('초기화 실패. 다시 시도해주세요.');
        }
    } catch (error) {
        console.error('Reset error:', error);
        alert('초기화 중 오류가 발생했습니다.');
    }
    
    if (btn) {
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

// --- Inventory Sorting ---

async function sortInventory(field) {
    // Toggle order if same field, otherwise default to desc
    if (inventorySortBy === field) {
        inventorySortOrder = inventorySortOrder === 'desc' ? 'asc' : 'desc';
    } else {
        inventorySortBy = field;
        inventorySortOrder = 'desc';
    }

    // Update UI indicators
    updateSortIndicators();

    // Fetch and render with new sort
    const inventory = await fetchInventory();
    lastInventoryData = inventory;
    renderInventory(inventory, true);
}

function updateSortIndicators() {
    // Remove active class from all sortable headers
    document.querySelectorAll('th.sortable').forEach(th => {
        th.classList.remove('active', 'asc', 'desc');
    });

    // Add active class to current sort column
    const activeHeader = document.querySelector(`th.sortable[data-sort="${inventorySortBy}"]`);
    if (activeHeader) {
        activeHeader.classList.add('active', inventorySortOrder);
    }
}

// --- Utility ---

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function simpleHash(obj) {
    // Simple hash for comparing data changes
    return JSON.stringify(obj);
}

function handleIconError(img) {
    // Track failed icon and hide it
    if (img.dataset.configId) {
        failedIcons.add(img.dataset.configId);
    }
    img.style.display = 'none';
}

function getIconHtml(configBaseId, cssClass) {
    // Don't render icons that have previously failed
    if (!configBaseId || failedIcons.has(String(configBaseId))) {
        return '';
    }
    // Use proxy endpoint to fetch icons (handles CDN headers server-side)
    const proxyUrl = `/api/icons/${configBaseId}`;
    return `<img src="${proxyUrl}" alt="" class="${cssClass}" data-config-id="${configBaseId}" onerror="handleIconError(this)">`;
}

// --- Update System ---

async function fetchUpdateStatus() {
    return fetchJson('/update/status');
}

async function triggerUpdateCheck() {
    try {
        const response = await fetch(`${API_BASE}/update/check`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error checking for updates:', error);
        return null;
    }
}

async function triggerUpdateDownload() {
    try {
        const response = await fetch(`${API_BASE}/update/download`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error downloading update:', error);
        return null;
    }
}

async function triggerUpdateInstall() {
    try {
        const response = await fetch(`${API_BASE}/update/install`, {
            method: 'POST'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error installing update:', error);
        return null;
    }
}

function renderVersion(status) {
    const versionEl = document.getElementById('app-version');
    const badgeEl = document.getElementById('update-badge');
    const checkBtn = document.getElementById('check-updates-btn');

    if (!status) {
        if (versionEl) versionEl.textContent = 'v--';
        return;
    }

    if (versionEl) versionEl.textContent = `v${status.current_version}`;

    // Show/hide update badge (if element exists)
    if (badgeEl) {
        if (status.status === 'available' || status.status === 'ready') {
            badgeEl.classList.remove('hidden');
            badgeEl.title = `Update available: v${status.latest_version}`;
        } else {
            badgeEl.classList.add('hidden');
        }
    }

    // Update button state (if element exists)
    if (checkBtn) {
        if (!status.can_update) {
            checkBtn.style.display = 'none'; // Hide in dev mode
        } else {
            checkBtn.style.display = '';
        }
        if (status.status === 'checking') {
            checkBtn.textContent = '확인 중...';
            checkBtn.disabled = true;
        } else if (status.status === 'available') {
            checkBtn.textContent = '업데이트 가능!';
            checkBtn.disabled = false;
            checkBtn.classList.add('update-available');
        } else if (status.status === 'downloading') {
            checkBtn.textContent = '다운로드 중...';
            checkBtn.disabled = true;
        } else if (status.status === 'ready') {
            checkBtn.textContent = '업데이트 설치';
            checkBtn.disabled = false;
            checkBtn.classList.add('update-ready');
        } else {
            checkBtn.textContent = '업데이트 확인';
            checkBtn.disabled = false;
            checkBtn.classList.remove('update-available', 'update-ready');
        }
    }
}

async function checkForUpdates() {
    const status = await fetchUpdateStatus();

    if (status && (status.status === 'available' || status.status === 'ready')) {
        showUpdateModal(status);
        return;
    }

    // Trigger update check
    await triggerUpdateCheck();

    // Start polling for result
    startUpdateStatusPolling();
}

function startUpdateStatusPolling() {
    if (updateCheckInterval) return;

    updateCheckInterval = setInterval(async () => {
        const status = await fetchUpdateStatus();
        updateStatus = status;
        renderVersion(status);

        // Stop polling when done checking
        if (status && status.status !== 'checking' && status.status !== 'downloading') {
            stopUpdateStatusPolling();

            if (status.status === 'available') {
                showUpdateModal(status);
            } else if (status.status === 'up_to_date') {
                showToast(`최신 버전입니다 (v${status.current_version})`, 'success');
            } else if (status.status === 'error') {
                showToast('업데이트 확인 실패: ' + (status.error_message || '알 수 없는 오류'), 'error');
            }
        }
    }, 1000);
}

function stopUpdateStatusPolling() {
    if (updateCheckInterval) {
        clearInterval(updateCheckInterval);
        updateCheckInterval = null;
    }
}

function showUpdateModal(status) {
    const modal = document.getElementById('update-modal');
    const currentVersionEl = document.getElementById('update-current-version');
    const newVersionEl = document.getElementById('update-new-version');
    const releaseNotesEl = document.getElementById('update-release-notes');
    const progressContainer = document.getElementById('update-progress-container');
    const actionsEl = document.getElementById('update-actions');

    currentVersionEl.textContent = `v${status.current_version}`;
    newVersionEl.textContent = `v${status.latest_version}`;

    // Show release notes (simple markdown to HTML)
    if (status.release_notes) {
        releaseNotesEl.innerHTML = simpleMarkdown(status.release_notes);
    } else {
        releaseNotesEl.textContent = '릴리스 노트 없음.';
    }

    // Reset progress
    progressContainer.classList.add('hidden');
    actionsEl.classList.remove('hidden');

    modal.classList.remove('hidden');
}

function closeUpdateModal() {
    document.getElementById('update-modal').classList.add('hidden');
    stopUpdateStatusPolling();
}

async function downloadAndInstallUpdate() {
    const downloadBtn = document.getElementById('update-download-btn');
    const progressContainer = document.getElementById('update-progress-container');
    const progressBar = document.getElementById('update-progress-bar');
    const progressText = document.getElementById('update-progress-text');

    // Start download
    downloadBtn.disabled = true;
    downloadBtn.textContent = '다운로드 중...';

    const result = await triggerUpdateDownload();
    if (!result || !result.success) {
        alert('다운로드 시작 실패: ' + (result?.message || '알 수 없는 오류'));
        downloadBtn.disabled = false;
        downloadBtn.textContent = '다운로드 및 설치';
        return;
    }

    // Show progress
    progressContainer.classList.remove('hidden');

    // Poll for download progress
    const progressInterval = setInterval(async () => {
        const status = await fetchUpdateStatus();
        updateStatus = status;

        if (status) {
            if (status.download_size > 0) {
                const percent = Math.round((status.download_progress / status.download_size) * 100);
                progressBar.style.width = `${percent}%`;
                const mb = (status.download_progress / 1024 / 1024).toFixed(1);
                const totalMb = (status.download_size / 1024 / 1024).toFixed(1);
                progressText.textContent = `다운로드 중... ${mb} / ${totalMb} MB`;
            }

            if (status.status === 'ready') {
                clearInterval(progressInterval);
                progressText.textContent = '다운로드 완료. 설치 중...';
                progressBar.style.width = '100%';

                // Confirm and install
                if (confirm('업데이트가 다운로드되었습니다. 결정 트래커가 재시작되어 업데이트가 적용됩니다.\n\n계속하시겠습니까?')) {
                    await triggerUpdateInstall();
                    // If we get here, install failed
                    alert('설치 시작 실패. 다시 시도해주세요.');
                } else {
                    downloadBtn.disabled = false;
                    downloadBtn.textContent = '업데이트 설치';
                    progressText.textContent = '설치 준비 완료';
                }
            } else if (status.status === 'error') {
                clearInterval(progressInterval);
                progressText.textContent = '다운로드 실패: ' + (status.error_message || '알 수 없는 오류');
                downloadBtn.disabled = false;
                downloadBtn.textContent = '재시도';
            }
        }
    }, 500);
}

function simpleMarkdown(text) {
    // Very basic markdown to HTML conversion
    return text
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/^### (.+)$/gm, '<h5>$1</h5>')
        .replace(/^## (.+)$/gm, '<h4>$1</h4>')
        .replace(/^# (.+)$/gm, '<h3>$1</h3>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
}

// Close update modal on outside click and escape
document.addEventListener('click', (e) => {
    if (e.target.id === 'update-modal') {
        closeUpdateModal();
    }
});

// --- Browser Mode / Exit App ---

async function checkBrowserMode() {
    try {
        const response = await fetch(`${API_BASE}/browser-mode`);
        if (response.ok) {
            const data = await response.json();
            if (data.browser_mode) {
                // Show Exit button and toast notification
                document.getElementById('exit-app-btn').classList.remove('hidden');
                showToast('Running in browser mode (native window unavailable)', 'info');
            }
        }
    } catch (error) {
        console.error('Error checking browser mode:', error);
    }
}

async function exitApp() {
    if (!confirm('결정 트래커를 종료하시겠습니까?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/shutdown`, { method: 'POST' });
        if (response.ok) {
            showToast('Shutting down...', 'info');
            // Close the browser tab after a short delay
            setTimeout(() => {
                window.close();
                // If window.close() doesn't work (most browsers block it),
                // show a message
                document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#1a1a2e;color:#eaeaea;font-family:sans-serif;"><h1>결정 트래커가 종료되었습니다. 이 탭을 닫으셔도 됩니다.</h1></div>';
            }, 500);
        }
    } catch (error) {
        console.error('Error shutting down:', error);
        showToast('Failed to shut down', 'error');
    }
}

// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
    // Initialize frameless mode if running in pywebview
    initFramelessMode();
    
    // Initialize refresh interval controls
    initRefreshIntervalControls();

    // Set initial sort indicators
    updateSortIndicators();

    // Check if running in browser fallback mode
    await checkBrowserMode();

    // Fetch and display version info
    const versionStatus = await fetchUpdateStatus();
    updateStatus = versionStatus;
    renderVersion(versionStatus);

    // Fetch player info initially
    const player = await fetchPlayer();
    renderPlayer(player);
    lastPlayerHash = simpleHash(player);

    // Show warning modal if no character detected
    if (!player) {
        showNoCharacterModal();
    }

    // Load initial map costs state
    mapCostsEnabled = await fetchMapCostsSetting();

    // Set up cloud sync toggle (now a checkbox toggle switch)
    const cloudSyncCheckbox = document.getElementById('cloud-sync-checkbox');
    if (cloudSyncCheckbox) {
        cloudSyncCheckbox.addEventListener('change', handleCloudSyncToggle);
    }

    // Initial cloud status check
    const cloudStatus = await fetchCloudStatus();
    renderCloudStatus(cloudStatus);

    // Load cloud settings from API
    await loadCloudSettings();
    
    // Set up force refresh button
    const forceRefreshBtn = document.getElementById('cloud-force-refresh-btn');
    if (forceRefreshBtn) {
        forceRefreshBtn.addEventListener('click', handleCloudForceRefresh);
    }

    // Load cloud prices if already enabled and start auto-refresh
    if (cloudStatus && cloudStatus.enabled) {
        // Force refresh on startup if setting is enabled
        if (cloudStartupRefresh) {
            console.log('[Cloud] Startup force refresh triggered');
            await triggerCloudSync();
            await loadCloudPrices(false);
        } else {
            await loadCloudPrices(cloudExchangeOverride);
        }
        startCloudPriceAutoRefresh();
    }

    // Initial load (force render on first load)
    refreshAll(true);
    
    // Sync inventory/runs heights on initial load
    syncInventoryHeight();

    // Auto-refresh toggle (now a checkbox toggle switch)
    const autoRefreshCheckbox = document.getElementById('auto-refresh-checkbox');
    if (autoRefreshCheckbox) {
        autoRefreshCheckbox.addEventListener('change', () => {
            if (autoRefreshCheckbox.checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
        // Start auto-refresh by default (checkbox starts checked)
        if (autoRefreshCheckbox.checked) {
            startAutoRefresh();
        }
    }
    
    // Initialize time tracking
    initTimeTracking();

    // Initialize always-on-top toggle
    initAlwaysOnTop();

    // Initialize overlay toggle
    initOverlayToggle();
    initOverlaySettings();

    // Initialize modal scrollbar detection
    initModalScrollbars();

    // Scroll detection for scrollbar visibility
    let scrollTimeouts = {};
    
    function setupScrollDetection(element, id) {
        if (!element) return;
        element.addEventListener('scroll', () => {
            element.classList.add('scrolling');
            if (scrollTimeouts[id]) clearTimeout(scrollTimeouts[id]);
            scrollTimeouts[id] = setTimeout(() => {
                element.classList.remove('scrolling');
            }, 1500);
        });
    }
    
    // Page-level scroll detection
    window.addEventListener('scroll', () => {
        document.documentElement.classList.add('scrolling');
        if (scrollTimeouts['html']) clearTimeout(scrollTimeouts['html']);
        scrollTimeouts['html'] = setTimeout(() => {
            document.documentElement.classList.remove('scrolling');
        }, 1500);
    });
    
    // Table scroll detection
    const inventoryTbody = document.querySelector('#inventory-table tbody');
    const runsTbody = document.querySelector('#runs-table tbody');
    setupScrollDetection(inventoryTbody, 'inventory');
    setupScrollDetection(runsTbody, 'runs');
});
