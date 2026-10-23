// MikroTik Smart Bandwidth Manager v2 - Client Application
let allDevices = [];
let activeFilter = localStorage.getItem('deviceFilter') || 'all';
let activePresetId = null;
let trafficChart = null;
let chartLabels = [];
let chartRxData = [];
let chartTxData = [];
const MAX_CHART_POINTS = 30;

// Terminal xterm.js instance & socket
let terminal = null;
let terminalWs = null;
let terminalFitAddon = null;

// Firewall State
let cachedFirewallData = null;
let activeFwSubTab = 'filter';

// Device Icon Map
const ICON_MAP = {
    phone: 'fa-mobile-screen',
    pc: 'fa-desktop',
    laptop: 'fa-laptop',
    tv: 'fa-tv',
    server: 'fa-server',
    iot: 'fa-microchip',
    guest: 'fa-user-group',
    unknown: 'fa-network-wired'
};

document.addEventListener('DOMContentLoaded', () => {
    initChart();
    initWebSocket();
    refreshAllData();
    checkSetupStatus();

    // Support direct hash navigation (e.g. #logs or #tab-security)
    const hash = window.location.hash.replace('#', '');
    const validTabs = ['devices', 'traffic', 'schedules', 'tools', 'firewall', 'security', 'logs'];
    const requestedTab = hash === 'logs' ? 'logs' : hash.replace('tab-', '');
    switchTab(validTabs.includes(requestedTab) ? `tab-${requestedTab}` : 'tab-devices');

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.setAttribute('role', 'tab');
        btn.setAttribute('aria-controls', `tab-${btn.id.replace('tab-btn-', '')}`);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeTopmostModal();
    });
    document.querySelectorAll('[id^="modal-"]').forEach(modal => {
        modal.addEventListener('mousedown', event => {
            if (event.target === modal && modal.id !== 'modal-terminal') closeModal(modal.id);
        });
    });

    // Periodic refresh of full device list every 5 seconds
    setFilter(activeFilter);
    setInterval(refreshAllData, 5000);
});

// ----------------- TAB SWITCHING -----------------
function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('border-indigo-500', 'text-indigo-400');
        btn.classList.add('border-transparent', 'text-slate-400');
        btn.setAttribute('aria-selected', 'false');
    });

    const targetTab = document.getElementById(tabId);
    if (targetTab) targetTab.classList.remove('hidden');

    const activeBtn = document.getElementById(`tab-btn-${tabId.replace('tab-', '')}`);
    if (activeBtn) {
        activeBtn.classList.remove('border-transparent', 'text-slate-400');
        activeBtn.classList.add('border-indigo-500', 'text-indigo-400');
        activeBtn.setAttribute('aria-selected', 'true');
    }

    if (window.location.hash !== `#${tabId}`) {
        history.replaceState(null, '', `#${tabId}`);
    }

    if (tabId === 'tab-logs') {
        if (activeLogSubTab === 'ros') fetchRouterOSLogs();
        else fetchAuditLogs();
    }
    if (tabId === 'tab-schedules') fetchSchedules();
    if (tabId === 'tab-tools') fetchArpTable();
    if (tabId === 'tab-firewall') fetchFirewallRules();
    if (tabId === 'tab-security') fetchSecurityAudit();
}

// ----------------- DATA FETCHING -----------------
async function refreshAllData() {
    const icon = document.getElementById('btn-refresh-icon');
    if (icon) icon.classList.add('fa-spin');

    try {
        await Promise.all([fetchStats(), fetchDevices()]);
    } catch (e) {
        console.error("Refresh error:", e);
    } finally {
        if (icon) icon.classList.remove('fa-spin');
    }
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const data = await res.json();

        // Update Navbar & Badges
        setText('nav-uptime', `Uptime: ${data.uptime}`);
        setText('nav-wan', data.active_wan || 'ether1');
        setText('nav-rx', data.total_download_str);
        setText('nav-tx', data.total_upload_str);
        setText('nav-cpu', `${data.cpu_load}%`);

        // Update Summary Cards
        setText('stat-online-count', data.total_devices_online);
        setText('stat-free-ram', data.free_memory);
    } catch (e) {
        console.error("Failed to fetch stats:", e);
    }
}

async function fetchDevices() {
    try {
        const res = await fetch('/api/devices');
        if (!res.ok) return;
        allDevices = await res.json();

        // Calculate summary metrics
        const vipCount = allDevices.filter(d => d.rate_mode === 'full').length;
        const limitCount = allDevices.filter(d => ['stream_15m', 'stream_10m', 'standard_4m', 'sosmed_2m', 'low_1m', 'custom'].includes(d.rate_mode)).length;
        
        setText('stat-vip-count', vipCount);
        setText('stat-limit-count', limitCount);

        renderDeviceList();
        updatePresetHighlight();
    } catch (e) {
        console.error("Failed to fetch devices:", e);
    }
}

// ----------------- DEVICE LIST RENDERING -----------------
function setFilter(filter) {
    activeFilter = filter;
    localStorage.setItem('deviceFilter', filter);
    document.querySelectorAll('.filter-chip').forEach(btn => {
        btn.classList.remove('bg-indigo-600', 'text-white');
        btn.classList.add('bg-slate-800', 'text-slate-300');
    });
    const activeChip = document.getElementById(`filter-${filter}`);
    if (activeChip) {
        activeChip.classList.remove('bg-slate-800', 'text-slate-300');
        activeChip.classList.add('bg-indigo-600', 'text-white');
    }
    renderDeviceList();
}

function renderDeviceList() {
    const container = document.getElementById('device-list-container');
    const searchVal = (document.getElementById('search-input')?.value || '').toLowerCase().trim();

    if (!allDevices || allDevices.length === 0) {
        container.innerHTML = `
            <div class="col-span-full py-12 text-center text-slate-500">
                <i class="fa-solid fa-network-wired text-4xl mb-3 text-slate-600"></i>
                <p class="text-sm">Tidak ada perangkat yang ditemukan.</p>
            </div>
        `;
        return;
    }

    let filtered = allDevices.filter(d => {
        const matchSearch = (d.alias_name && d.alias_name.toLowerCase().includes(searchVal)) ||
                            (d.hostname && d.hostname.toLowerCase().includes(searchVal)) ||
                            (d.ip && d.ip.includes(searchVal)) ||
                            (d.mac && d.mac.toLowerCase().includes(searchVal)) ||
                            (d.vendor && d.vendor.toLowerCase().includes(searchVal));

        if (!matchSearch) return false;

        if (activeFilter === 'online') return d.status === 'bound';
        if (activeFilter === 'offline') return d.status !== 'bound';
        if (activeFilter === 'full') return d.rate_mode === 'full';
        if (activeFilter === 'limited') return ['stream_15m', 'stream_10m', 'standard_4m', 'sosmed_2m', 'low_1m', 'custom'].includes(d.rate_mode);
        if (activeFilter === 'blocked') return d.rate_mode === 'blocked';
        return true;
    });

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="col-span-full py-12 text-center text-slate-500">
                <i class="fa-solid fa-filter-circle-xmark text-4xl mb-3 text-slate-600"></i>
                <p class="text-sm">Tidak ada perangkat yang cocok dengan pencarian/filter.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(dev => renderDeviceCard(dev)).join('');
    container.onclick = handleDeviceCardAction;
}

function renderDeviceCard(dev) {
    const iconClass = ICON_MAP[dev.device_type] || 'fa-network-wired';
    const isOnline = dev.status === 'bound';
    const supportsWol = Boolean(dev.mac && dev.mac.length >= 11);
    
    // Rate Badge Styling
    let badgeBg = 'bg-slate-800 text-slate-300 border-slate-700';
    let badgeText = dev.current_limit;
    
    if (dev.rate_mode === 'full') {
        badgeBg = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    } else if (dev.rate_mode === 'blocked') {
        badgeBg = 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    } else if (['stream_15m', 'stream_10m'].includes(dev.rate_mode)) {
        badgeBg = 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30';
    } else if (['standard_4m', 'sosmed_2m'].includes(dev.rate_mode)) {
        badgeBg = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30';
    }

    const upSpeed = dev.upload_rate && dev.upload_rate !== '0bps' ? dev.upload_rate : '0 bps';
    const downSpeed = dev.download_rate && dev.download_rate !== '0bps' ? dev.download_rate : '0 bps';
    const statusBadge = isOnline
        ? '<span class="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>ONLINE</span>'
        : '<span class="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 text-[10px] font-bold flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span>OFFLINE</span>';
    const cardClass = isOnline
        ? 'device-card bg-slate-900/90 border border-slate-800 hover:border-indigo-500/50 rounded-2xl p-4 shadow-lg flex flex-col justify-between transition'
        : 'device-card bg-slate-950/60 border border-dashed border-slate-800 opacity-65 hover:opacity-90 rounded-2xl p-4 shadow-lg flex flex-col justify-between transition';
    const staticBadge = dev.is_static
        ? '<span class="text-[10px] px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 font-mono" title="Static DHCP Lease">STATIC</span>'
        : '';

    return `
        <div class="${cardClass}" data-device-ip="${escapeHtml(dev.ip)}">
            <!-- Card Header -->
            <div class="device-card-header flex items-start justify-between gap-3 mb-3">
                <!-- Device Icon & Info -->
                <div class="device-identity flex items-center space-x-3 min-w-0">
                    <div class="relative w-11 h-11 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                        <i class="fa-solid ${iconClass} text-slate-200 text-lg"></i>
                        <span class="absolute -bottom-1 -right-1 w-3.5 h-3.5 rounded-full ${isOnline ? 'bg-emerald-500' : 'bg-slate-600'} border-2 border-slate-900"></span>
                    </div>
                    <div class="min-w-0">
                        <div class="device-title-row flex items-center gap-1.5">
                            <h4 class="text-sm font-semibold ${isOnline ? 'text-white' : 'text-slate-400'} truncate" title="${escapeHtml(dev.alias_name)}">
                                ${escapeHtml(dev.alias_name)}
                            </h4>
                            <span class="device-header-status flex items-center gap-1.5">${statusBadge}${staticBadge}</span>
                        </div>
                        <p class="device-address text-xs text-slate-400 font-mono" title="${escapeHtml(dev.ip)} • ${escapeHtml(dev.mac)}">${escapeHtml(dev.ip)} <span class="text-slate-600">•</span> ${escapeHtml(dev.mac)}</p>
                    </div>
                </div>

                <!-- Rate Limit Status Pill -->
                <div class="device-rate-badge shrink-0">
                    <span class="px-2.5 py-1 text-xs font-semibold rounded-full border ${badgeBg} flex items-center gap-1">
                        ${escapeHtml(badgeText)}
                    </span>
                </div>
            </div>

            <!-- Meta Details & Live Throughput -->
            <div class="flex items-center justify-between text-xs text-slate-400 py-2 border-t border-slate-800/80 mb-3">
                <span class="truncate max-w-[150px]"><i class="fa-solid fa-tag text-slate-500 mr-1"></i> ${escapeHtml(dev.vendor)}</span>
                <div class="flex items-center space-x-2 font-mono text-[11px]">
                    <span class="text-emerald-400" title="Live Download"><i class="fa-solid fa-arrow-down text-[10px]"></i> ${downSpeed}</span>
                    <span class="text-indigo-400" title="Live Upload"><i class="fa-solid fa-arrow-up text-[10px]"></i> ${upSpeed}</span>
                </div>
            </div>

            <!-- Quick Action 1-Click Buttons -->
            <div class="grid grid-cols-5 gap-1.5">
                <button type="button" data-device-action="speed" data-mode="full"
                        class="px-1.5 py-1.5 rounded-lg text-[11px] font-semibold transition ${dev.rate_mode === 'full' ? 'bg-emerald-600 text-white shadow-emerald-500/20 shadow' : 'bg-slate-800 hover:bg-emerald-900/40 text-slate-300 hover:text-emerald-300'}">
                    🚀 Full
                </button>
                <button type="button" data-device-action="speed" data-mode="stream_10m"
                        class="px-1.5 py-1.5 rounded-lg text-[11px] font-semibold transition ${dev.rate_mode === 'stream_10m' ? 'bg-cyan-600 text-white' : 'bg-slate-800 hover:bg-cyan-900/40 text-slate-300 hover:text-cyan-300'}">
                    🎬 10M
                </button>
                <button type="button" data-device-action="speed" data-mode="standard_4m"
                        class="px-1.5 py-1.5 rounded-lg text-[11px] font-semibold transition ${dev.rate_mode === 'standard_4m' ? 'bg-indigo-600 text-white' : 'bg-slate-800 hover:bg-indigo-900/40 text-slate-300 hover:text-indigo-300'}">
                    ⚡ 4M
                </button>
                <button type="button" data-device-action="speed" data-mode="sosmed_2m"
                        class="px-1.5 py-1.5 rounded-lg text-[11px] font-semibold transition ${dev.rate_mode === 'sosmed_2m' ? 'bg-indigo-700 text-white' : 'bg-slate-800 hover:bg-indigo-900/40 text-slate-300 hover:text-indigo-300'}">
                    📱 2M
                </button>
                <button type="button" data-device-action="speed" data-mode="blocked"
                        class="px-1.5 py-1.5 rounded-lg text-[11px] font-semibold transition ${dev.rate_mode === 'blocked' ? 'bg-rose-600 text-white' : 'bg-slate-800 hover:bg-rose-900/40 text-slate-300 hover:text-rose-300'}">
                    ⛔ Blok
                </button>
            </div>

            <!-- Bottom Extra Tools: Custom Slider, Rename, WOL, Static IP -->
            <div class="flex items-center justify-between mt-2.5 pt-2 border-t border-slate-800/50 text-[11px]">
                <div class="flex items-center space-x-3">
                    <button type="button" data-device-action="custom"
                            class="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1">
                        <i class="fa-solid fa-sliders"></i> Slider
                    </button>
                    <button type="button" data-device-action="edit"
                            class="text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1" title="Rename dan sinkron ke DHCP Lease MikroTik">
                        <i class="fa-solid fa-pen-to-square"></i> Rename
                    </button>
                </div>
                
                <div class="flex items-center space-x-3">
                    ${supportsWol ? `
                        <button type="button" data-device-action="wol"
                                class="text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1" title="Kirim Magic Packet Wake-on-LAN">
                            <i class="fa-solid fa-power-off"></i> Wake (WOL)
                        </button>
                    ` : ''}

                    ${!dev.is_static ? `
                        <button type="button" data-device-action="static"
                                class="text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1">
                            <i class="fa-solid fa-lock"></i> Kunci Static IP
                        </button>
                    ` : `
                        <span class="text-slate-500 font-mono text-[10px]"><i class="fa-solid fa-circle-check text-cyan-400"></i> Static</span>
                    `}
                </div>
            </div>
        </div>
    `;
}

// ----------------- DEVICE CARD EVENT DELEGATION -----------------
// All device-card button actions route here to avoid unsafe inline-handler injection
function handleDeviceCardAction(event) {
    const btn = event.target.closest('[data-device-action]');
    if (!btn) return;
    const action = btn.getAttribute('data-device-action');
    const card = btn.closest('.device-card');
    if (!card) return;
    const ip = card.getAttribute('data-device-ip');
    const dev = allDevices.find(d => d.ip === ip);
    if (!dev) return;
    event.stopPropagation();
    switch (action) {
        case 'speed': {
            const mode = btn.getAttribute('data-mode');
            if (mode) setSpeed(dev.ip, dev.mac, mode);
            break;
        }
        case 'custom':
            openCustomSpeedModal(dev.ip, dev.mac, dev.alias_name);
            break;
        case 'edit':
            openEditDeviceModal(dev.ip, dev.mac, dev.alias_name, dev.device_type, dev.notes, dev.group_name || 'Default');
            break;
        case 'wol':
            sendWol(dev.ip, dev.mac, dev.alias_name);
            break;
        case 'static':
            makeStatic(dev.ip, dev.mac, dev.alias_name);
            break;
    }
}

// ----------------- SPEED & WOL ACTIONS -----------------
async function setSpeed(ip, mac, mode) {
    showToast(`Menerapkan mode ${mode} untuk ${ip}...`, 'info');
    try {
        const res = await fetch(`/api/devices/${ip}/speed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, mac, mode })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            await fetchDevices();
        } else {
            showToast(data.message || 'Gagal mengubah kecepatan', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function sendWol(ip, mac, alias) {
    if (!confirm(`Kirim Magic Packet Wake-on-LAN (WOL) untuk menghidupkan ${alias || ip} (${mac})?`)) return;
    showToast(`Mengirim sinyal Wake-on-LAN ke ${mac}...`, 'info');
    try {
        const res = await fetch(`/api/devices/${ip}/wol`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mac })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
        } else {
            showToast(data.message || 'Gagal mengirim sinyal WOL', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

function updatePresetHighlight() {
    if (!activePresetId) return;
    document.querySelectorAll('.preset-btn').forEach(b => {
        b.classList.remove('ring-2', 'ring-indigo-500', 'bg-indigo-950');
    });
    const activeBtn = document.getElementById(`preset-btn-${activePresetId}`);
    if (activeBtn) {
        activeBtn.classList.add('ring-2', 'ring-indigo-500', 'bg-indigo-950');
    }
}

async function applyPreset(presetId) {
    activePresetId = presetId;
    updatePresetHighlight();

    showToast(`Menerapkan preset jaringan ${presetId}...`, 'info');
    try {
        const res = await fetch(`/api/presets/${presetId}/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            await fetchDevices();
        } else {
            showToast(data.message || 'Gagal menerapkan preset', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function makeStatic(ip, mac, alias) {
    if (!confirm(`Jadikan ${alias} (${ip}) sebagai Static DHCP Lease permanen?`)) return;
    try {
        const res = await fetch(`/api/devices/${ip}/static`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, mac, comment: alias })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            await fetchDevices();
        } else {
            showToast(data.message || 'Gagal mengunci static lease', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

// ----------------- MODALS -----------------
function openCustomSpeedModal(ip, mac, alias) {
    document.getElementById('custom-modal-ip').value = ip;
    document.getElementById('custom-modal-mac').value = mac;
    document.getElementById('custom-modal-dev-info').textContent = `Perangkat: ${alias} (${ip})`;
    updateSliderLabels();
    openModal('modal-custom-speed');
}

function setSliderPreset(val) {
    document.getElementById('custom-down-slider').value = val;
    document.getElementById('custom-up-slider').value = Math.min(val, 30);
    updateSliderLabels();
}

function updateSliderLabels() {
    const downVal = document.getElementById('custom-down-slider').value;
    const upVal = document.getElementById('custom-up-slider').value;
    document.getElementById('custom-down-val').textContent = downVal === "0" ? "0M (Blokir Total)" : `${downVal}M (${downVal} Mbps)`;
    document.getElementById('custom-up-val').textContent = upVal === "0" ? "0M (Blokir Total)" : `${upVal}M (${upVal} Mbps)`;
}

async function submitCustomSpeed() {
    const ip = document.getElementById('custom-modal-ip').value;
    const mac = document.getElementById('custom-modal-mac').value;
    const downVal = `${document.getElementById('custom-down-slider').value}M`;
    const upVal = `${document.getElementById('custom-up-slider').value}M`;
    const prio = parseInt(document.getElementById('custom-prio-select').value);

    closeModal('modal-custom-speed');
    showToast(`Menerapkan limit kustom ${upVal}/${downVal} untuk ${ip}...`, 'info');

    try {
        const res = await fetch(`/api/devices/${ip}/speed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ip,
                mac,
                mode: 'custom',
                upload_limit: upVal,
                download_limit: downVal,
                priority: prio
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            await fetchDevices();
        } else {
            showToast(data.message || 'Gagal menerapkan limit kustom', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

function openEditDeviceModal(ip, mac, alias, type, notes, groupName = 'Default') {
    document.getElementById('edit-dev-ip').value = ip;
    document.getElementById('edit-dev-mac').value = mac;
    document.getElementById('edit-dev-alias').value = alias || '';
    document.getElementById('edit-dev-type').value = type || 'phone';
    document.getElementById('edit-dev-group').value = groupName || 'Default';
    document.getElementById('edit-dev-notes').value = notes || '';
    openModal('modal-edit-device');
}

async function submitDeviceAlias() {
    const ip = document.getElementById('edit-dev-ip').value;
    const mac = document.getElementById('edit-dev-mac').value;
    const alias_name = document.getElementById('edit-dev-alias').value.trim();
    const device_type = document.getElementById('edit-dev-type').value;
    const group_name = document.getElementById('edit-dev-group').value.trim() || 'Default';
    const notes = document.getElementById('edit-dev-notes').value.trim();

    if (!alias_name) {
        alert('Nama alias tidak boleh kosong');
        return;
    }

    closeModal('modal-edit-device');
    showToast(`Menyimpan alias dan sinkron DHCP comment MikroTik untuk ${ip}...`, 'info');
    try {
        const res = await fetch(`/api/devices/${ip}/alias`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, mac, alias_name, device_type, group_name, notes })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            await fetchDevices();
        } else {
            showToast(data.message || 'Gagal menyimpan alias', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

// ----------------- SCHEDULE MODAL & LOGIC -----------------
function openAddScheduleModal() {
    const devSelect = document.getElementById('sched-dev-select');
    if (devSelect && allDevices.length > 0) {
        devSelect.innerHTML = allDevices.map(d => `
            <option value="${d.ip}" data-mac="${d.mac}" data-alias="${escapeHtml(d.alias_name)}">
                ${escapeHtml(d.alias_name)} (${d.ip})
            </option>
        `).join('');
    }
    openModal('modal-add-schedule');
}

async function submitSchedule() {
    const devSelect = document.getElementById('sched-dev-select');
    const selectedOption = devSelect.options[devSelect.selectedIndex];
    const device_ip = selectedOption.value;
    const device_mac = selectedOption.getAttribute('data-mac') || '';
    const device_alias = selectedOption.getAttribute('data-alias') || '';
    const name = document.getElementById('sched-name').value.trim();
    const start_time = document.getElementById('sched-start').value;
    const end_time = document.getElementById('sched-end').value;
    const action_mode = document.getElementById('sched-action').value;

    if (!name) {
        alert('Nama jadwal harus diisi');
        return;
    }

    closeModal('modal-add-schedule');
    showToast(`Menyimpan jadwal '${name}'...`, 'info');

    try {
        const res = await fetch('/api/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_ip,
                device_mac,
                device_alias,
                name,
                start_time,
                end_time,
                action_mode
            })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            fetchSchedules();
        } else {
            showToast(data.message || 'Gagal menambahkan jadwal', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function deleteSchedule(id) {
    if (!confirm('Hapus jadwal otomatis ini?')) return;
    try {
        const res = await fetch(`/api/schedules/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            fetchSchedules();
        } else {
            showToast(data.message || 'Gagal menghapus jadwal', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function toggleSchedule(id, isEnabled) {
    try {
        const res = await fetch(`/api/schedules/${id}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_enabled: isEnabled })
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.message || 'Gagal mengubah status jadwal');
        showToast(data.message, 'success');
        await fetchSchedules();
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

// ----------------- DIAGNOSTIC TOOLS -----------------
async function runToolPing() {
    const target = document.getElementById('tool-ping-target').value.trim();
    const outputEl = document.getElementById('tool-ping-output');
    const btn = document.getElementById('btn-tool-ping');

    if (!target) return;
    outputEl.textContent = `Menjalankan ping ke ${target} dari MikroTik...`;
    btn.disabled = true;

    try {
        const res = await fetch('/api/tools/ping', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target, count: 4 })
        });
        const data = await res.json();
        outputEl.textContent = data.output || 'Tidak ada respons.';
    } catch (e) {
        outputEl.textContent = `Error: ${e.message}`;
    } finally {
        btn.disabled = false;
    }
}

async function runToolTraceroute() {
    const target = document.getElementById('tool-trace-target').value.trim();
    const outputEl = document.getElementById('tool-trace-output');
    const btn = document.getElementById('btn-tool-trace');

    if (!target) return;
    outputEl.textContent = `Menjalankan traceroute ke ${target}...`;
    btn.disabled = true;

    try {
        const res = await fetch('/api/tools/traceroute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target })
        });
        const data = await res.json();
        outputEl.textContent = data.output || 'Traceroute selesai tanpa output.';
    } catch (e) {
        outputEl.textContent = `Error: ${e.message}`;
    } finally {
        btn.disabled = false;
    }
}

async function runToolDns() {
    const domain = document.getElementById('tool-dns-target').value.trim();
    const outputEl = document.getElementById('tool-dns-output');
    const btn = document.getElementById('btn-tool-dns');

    if (!domain) return;
    outputEl.textContent = `Melakukan DNS lookup untuk ${domain}...`;
    btn.disabled = true;

    try {
        const res = await fetch('/api/tools/dns', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain })
        });
        const data = await res.json();
        outputEl.textContent = data.output ? `IP Resolved: ${data.output.trim()}` : 'Domain tidak dapat di-resolve.';
    } catch (e) {
        outputEl.textContent = `Error: ${e.message}`;
    } finally {
        btn.disabled = false;
    }
}

async function fetchArpTable() {
    const tbody = document.getElementById('arp-tbody');
    try {
        const res = await fetch('/api/tools/arp');
        if (!res.ok) return;
        const result = await res.json();
        const entries = result.data || [];
        if (entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-3 text-center text-slate-500">Tabel ARP kosong.</td></tr>';
            return;
        }
        tbody.innerHTML = entries.map(e => `
            <tr class="hover:bg-slate-800/40">
                <td class="px-4 py-2 text-cyan-300 font-bold">${escapeHtml(e.ip || '-')}</td>
                <td class="px-4 py-2 text-slate-200">${escapeHtml(e.mac || '-')}</td>
                <td class="px-4 py-2 text-slate-400">${escapeHtml(e.interface || '-')}</td>
                <td class="px-4 py-2">${e.dynamic ? '<span class="text-emerald-400 text-[10px]">DYNAMIC</span>' : '<span class="text-cyan-400 text-[10px]">STATIC</span>'}</td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Failed to fetch ARP table:", e);
    }
}

// ----------------- FIREWALL VIEWER -----------------
async function fetchFirewallRules() {
    const container = document.getElementById('firewall-content');
    container.innerHTML = '<div class="py-12 text-center text-slate-500"><i class="fa-solid fa-circle-notch fa-spin text-2xl mb-2 text-indigo-500"></i><p class="text-xs">Memuat aturan firewall dari MikroTik...</p></div>';
    try {
        const res = await fetch('/api/firewall');
        if (!res.ok) return;
        const result = await res.json();
        cachedFirewallData = result.data || {};
        renderFirewallSubTab();
    } catch (e) {
        container.innerHTML = `<p class="text-xs text-rose-400">Gagal memuat aturan firewall: ${e.message}</p>`;
    }
}

function switchFirewallSubTab(subtab) {
    activeFwSubTab = subtab;
    document.querySelectorAll('.fw-subtab-btn').forEach(btn => {
        btn.classList.remove('bg-indigo-600', 'text-white');
        btn.classList.add('bg-slate-800', 'text-slate-300');
    });
    const activeBtn = document.getElementById(`fw-subtab-${subtab}`);
    if (activeBtn) {
        activeBtn.classList.remove('bg-slate-800', 'text-slate-300');
        activeBtn.classList.add('bg-indigo-600', 'text-white');
    }
    renderFirewallSubTab();
}

function renderFirewallSubTab() {
    const container = document.getElementById('firewall-content');
    if (!cachedFirewallData) return;
    const rules = cachedFirewallData[activeFwSubTab] || [];

    if (rules.length === 0) {
        container.innerHTML = `<div class="py-8 text-center text-slate-500 text-xs">Tidak ada aturan aktif di bagian ini.</div>`;
        return;
    }

    container.innerHTML = `
        <table class="w-full text-left text-xs text-slate-300">
            <thead class="bg-slate-800/50 text-slate-400 uppercase font-mono text-[11px]">
                <tr>
                    <th class="px-4 py-2.5">Chain</th>
                    <th class="px-4 py-2.5">Action</th>
                    <th class="px-4 py-2.5">Protokol / Port</th>
                    <th class="px-4 py-2.5">Src / Dst Address</th>
                    <th class="px-4 py-2.5">Comment</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-800 font-mono text-[11px]">
                ${rules.map(r => {
                    const action = r.action || 'accept';
                    let actionBadge = 'bg-slate-800 text-slate-300';
                    if (action === 'accept') actionBadge = 'bg-emerald-500/20 text-emerald-300';
                    else if (action === 'drop') actionBadge = 'bg-rose-500/20 text-rose-300';
                    else if (action === 'masquerade') actionBadge = 'bg-cyan-500/20 text-cyan-300';
                    else if (action === 'dst-nat') actionBadge = 'bg-amber-500/20 text-amber-300';

                    return `
                        <tr class="hover:bg-slate-800/40">
                            <td class="px-4 py-2 text-indigo-300 font-bold">${r.chain || '-'}</td>
                            <td class="px-4 py-2"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${actionBadge}">${action.toUpperCase()}</span></td>
                            <td class="px-4 py-2 text-slate-400">${r.protocol || 'all'} ${r['dst-port'] ? ':' + r['dst-port'] : ''}</td>
                            <td class="px-4 py-2 text-slate-300">${r['src-address'] || r['dst-address'] || (r['out-interface'] ? 'out:' + r['out-interface'] : 'any')}</td>
                            <td class="px-4 py-2 text-slate-400 italic">${r.comment || '-'}</td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;
}

// ----------------- SECURITY AUDIT & BACKUP -----------------
async function fetchSecurityAudit() {
    const checklistContainer = document.getElementById('security-checklist-container');
    checklistContainer.innerHTML = '<div class="py-8 text-center text-slate-500 text-xs"><i class="fa-solid fa-circle-notch fa-spin text-xl mb-2 text-indigo-500"></i><p>Menganalisis konfigurasi router...</p></div>';

    try {
        const res = await fetch('/api/security/audit');
        if (!res.ok) return;
        const result = await res.json();
        const data = result.data;

        // Update Score Circular Display
        setText('security-score-val', `${data.score}%`);
        const labelEl = document.getElementById('security-score-label');
        if (data.score >= 80) {
            labelEl.textContent = 'Sistem Sangat Aman (Hardened)';
            labelEl.className = 'mt-4 text-xs font-semibold text-emerald-400';
        } else if (data.score >= 60) {
            labelEl.textContent = 'Cukup Aman (Ada Peringatan)';
            labelEl.className = 'mt-4 text-xs font-semibold text-amber-400';
        } else {
            labelEl.textContent = 'Perlu Peningkatan Keamanan';
            labelEl.className = 'mt-4 text-xs font-semibold text-rose-400';
        }

        // Render Checklist
        checklistContainer.innerHTML = data.checks.map(c => `
            <div class="p-3 rounded-xl border ${c.status === 'pass' ? 'bg-emerald-950/20 border-emerald-900/40' : 'bg-amber-950/20 border-amber-900/40'} flex items-start gap-3">
                <i class="fa-solid ${c.status === 'pass' ? 'fa-circle-check text-emerald-400' : 'fa-triangle-exclamation text-amber-400'} text-base mt-0.5 shrink-0"></i>
                <div>
                    <h4 class="text-xs font-semibold ${c.status === 'pass' ? 'text-emerald-300' : 'text-amber-300'}">${escapeHtml(c.name)}</h4>
                    <p class="text-[11px] text-slate-400 mt-0.5">${escapeHtml(c.desc)}</p>
                </div>
            </div>
        `).join('');
    } catch (e) {
        checklistContainer.innerHTML = `<p class="text-xs text-rose-400">Gagal menjalankan audit keamanan: ${e.message}</p>`;
    }
}

async function exportConfig() {
    const previewEl = document.getElementById('backup-export-preview');
    previewEl.textContent = 'Mengambil file export konfigurasi dari MikroTik (/export)...';
    try {
        const res = await fetch('/api/backup/export');
        const data = await res.json();
        previewEl.textContent = data.config || 'Gagal mengambil konfigurasi.';
    } catch (e) {
        previewEl.textContent = `Error: ${e.message}`;
    }
}

// ----------------- ROUTER POWER ACTION -----------------
async function triggerReboot() {
    if (!confirm("⚠️ PERINGATAN: Apakah Anda yakin ingin ME-REBOOT router MikroTik sekarang?\n\nKoneksi internet dan dashboard akan terputus selama ±30 detik hingga router menyala kembali.")) return;
    
    closeModal('modal-settings');
    showToast("Mengirim perintah reboot ke router...", "info");

    try {
        const res = await fetch('/api/router/reboot', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "Router sedang reboot...", "success");
    } catch (e) {
        showToast(`Error: ${e.message}`, "error");
    }
}

// ----------------- IN-BROWSER SSH TERMINAL (xterm.js) -----------------
function openTerminal() {
    openModal('modal-terminal');
    const container = document.getElementById('terminal-container');
    container.innerHTML = '';

    if (terminal) {
        try { terminal.dispose(); } catch (e) {}
    }

    terminal = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        fontFamily: 'JetBrains Mono, monospace',
        theme: {
            background: '#0f172a',
            foreground: '#e2e8f0',
            cursor: '#10b981',
            selectionBackground: '#4338ca'
        }
    });

    if (window.FitAddon && window.FitAddon.FitAddon) {
        terminalFitAddon = new window.FitAddon.FitAddon();
        terminal.loadAddon(terminalFitAddon);
    }

    terminal.open(container);
    if (terminalFitAddon) {
        setTimeout(() => terminalFitAddon.fit(), 100);
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;
    terminalWs = new WebSocket(wsUrl);

    terminalWs.onopen = () => {
        terminal.focus();
    };

    terminalWs.onmessage = (event) => {
        terminal.write(event.data);
    };

    terminal.onData((data) => {
        if (terminalWs && terminalWs.readyState === WebSocket.OPEN) {
            terminalWs.send(data);
        }
    });

    terminalWs.onclose = () => {
        terminal.write('\r\n\x1b[31m[Koneksi SSH Terminal ditutup]\x1b[0m\r\n');
    };

    terminalWs.onerror = () => {
        terminal.write('\r\n\x1b[31m[Error menghubungkan ke SSH Terminal]\x1b[0m\r\n');
    };
}

function closeTerminal() {
    if (terminalWs) {
        try { terminalWs.close(); } catch (e) {}
        terminalWs = null;
    }
    if (terminal) {
        try { terminal.dispose(); } catch (e) {}
        terminal = null;
    }
    closeModal('modal-terminal');
}

async function checkSetupStatus() {
    try {
        const res = await fetch('/api/setup/status');
        const data = await res.json();
        if (data.success && !data.configured) {
            openModal('modal-wizard');
        }
    } catch (e) {
        console.debug('Setup status check error:', e);
    }
}

async function probeRouterConnection() {
    const btn = document.getElementById('btn-wizard-probe');
    const host = document.getElementById('wizard-ip')?.value?.trim() || '192.168.88.1';
    const port = parseInt(document.getElementById('wizard-port')?.value?.trim() || '22');
    const user = document.getElementById('wizard-user')?.value?.trim() || 'admin';
    const password = document.getElementById('wizard-pass')?.value || '';

    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menghubungi Router...';

    try {
        const res = await fetch('/api/setup/probe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port, user, password })
        });
        const data = await res.json();
        if (!data.success) {
            showToast(data.error || 'Gagal terhubung ke router', 'error');
            return;
        }

        // Populate discovery box
        setText('wizard-res-model', data.model || 'MikroTik');
        setText('wizard-res-version', data.version || 'RouterOS');
        setText('wizard-res-wan', data.wan_interface || 'ether1');
        setText('wizard-res-lan', data.lan_bridge || 'bridge');

        const box = document.getElementById('wizard-discovery-box');
        if (box) box.classList.remove('hidden');

        showToast(`Terhubung: ${data.model} (${data.version})`, 'success');
    } catch (e) {
        showToast(`Koneksi error: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHtml;
    }
}

async function applyRouterSetup() {
    const host = document.getElementById('wizard-ip')?.value?.trim() || '192.168.88.1';
    const port = parseInt(document.getElementById('wizard-port')?.value?.trim() || '22');
    const user = document.getElementById('wizard-user')?.value?.trim() || 'admin';
    const password = document.getElementById('wizard-pass')?.value || '';
    const wan = document.getElementById('wizard-res-wan')?.textContent?.trim() || 'ether1';
    const lan = document.getElementById('wizard-res-lan')?.textContent?.trim() || 'bridge';
    const disable_fasttrack = document.getElementById('wizard-disable-fasttrack')?.checked ?? true;

    try {
        const res = await fetch('/api/setup/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port, user, password, wan_interface: wan, lan_bridge: lan, disable_fasttrack })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || 'Setup selesai! Dashboard siap digunakan.', 'success');
            closeModal('modal-wizard');
            refreshAllData();
        } else {
            showToast(data.message || 'Gagal menyimpan konfigurasi', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function toggleFastTrack() {
    try {
        const statusRes = await fetch('/api/fasttrack/status');
        const statusData = await statusRes.json();
        const isCurrentlyActive = statusData?.data?.is_active ?? true;
        const newTarget = !isCurrentlyActive;

        showToast(newTarget ? "Mengaktifkan FastTrack..." : "Menonaktifkan FastTrack untuk QoS...", "info");
        const res = await fetch('/api/fasttrack/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: newTarget })
        });
        const data = await res.json();
        showToast(data.message || "Status FastTrack berhasil diubah", data.success ? "success" : "error");
        await updateFastTrackBadge();
    } catch (e) {
        showToast(`Error toggle FastTrack: ${e.message}`, 'error');
    }
}

async function updateFastTrackBadge() {
    try {
        const res = await fetch('/api/fasttrack/status');
        const data = await res.json();
        const badge = document.getElementById('settings-fasttrack-status');
        const btn = document.getElementById('btn-toggle-fasttrack');
        if (!badge || !data?.data) return;

        if (data.data.is_active) {
            badge.className = "font-mono px-2 py-0.5 rounded text-[11px] bg-rose-500/10 text-rose-400 border border-rose-500/20";
            badge.textContent = "Enabled (Bypass QoS)";
            if (btn) btn.textContent = "Nonaktifkan untuk QoS";
        } else {
            badge.className = "font-mono px-2 py-0.5 rounded text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
            badge.textContent = "Disabled (QoS Ready)";
            if (btn) btn.textContent = "Aktifkan Bawaan";
        }
    } catch (e) {
        console.debug('FastTrack status error:', e);
    }
}

async function triggerCleanDetach() {
    if (!confirm("⚠️ PERINGATAN CLEAN DETACH:\n\nApakah Anda yakin ingin membersihkan konfigurasi MikroTik?\n\n• Seluruh antrean Simple Queue BWM akan dihapus.\n• Aturan FastTrack firewall akan dipulihkan ke bawaan pabrik.\n• Router kembali bersih tanpa sisa setting aplikasi.")) {
        return;
    }

    closeModal('modal-settings');
    showToast("Membersihkan konfigurasi antrean dan firewall router...", "info");

    try {
        const res = await fetch('/api/maintenance/clean-detach', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "Clean Detach selesai!", data.success ? "success" : "error");
        refreshAllData();
    } catch (e) {
        showToast(`Error clean detach: ${e.message}`, "error");
    }
}

async function openSettingsModal() {
    openModal('modal-settings');
    try {
        const statsRes = await fetch('/api/stats');
        const stats = await statsRes.json();
        if (stats) {
            setText('settings-router-model', `${stats.board_name || 'MikroTik'} (${stats.version || 'RouterOS'})`);
        }
    } catch (e) {}

    try {
        const setupRes = await fetch('/api/setup/status');
        const setup = await setupRes.json();
        if (setup?.configured) {
            setText('settings-target-router', `${setup.host}:${setup.port}`);
        }
    } catch (e) {}

    await updateFastTrackBadge();
}

function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

function closeTopmostModal() {
    const openModals = [...document.querySelectorAll('[id^="modal-"]')]
        .filter(modal => !modal.classList.contains('hidden'));
    const topmost = openModals.at(-1);
    if (!topmost) return;
    if (topmost.id === 'modal-terminal') closeTerminal();
    else closeModal(topmost.id);
}

// ----------------- AUDIT LOGS & ROUTEROS HISTORY -----------------
let rosLogsState = {
    page: 1,
    limit: 50,
    severity: 'all',
    topic: 'all',
    search: '',
    searchTimeout: null,
    total: 0
};
let activeLogSubTab = 'ros';

function switchLogSubTab(subtab) {
    activeLogSubTab = subtab;
    const rosView = document.getElementById('subview-ros-logs');
    const auditView = document.getElementById('subview-audit-logs');
    const rosBtn = document.getElementById('log-subtab-ros');
    const auditBtn = document.getElementById('log-subtab-audit');

    if (subtab === 'ros') {
        if (rosView) rosView.classList.remove('hidden');
        if (auditView) auditView.classList.add('hidden');
        if (rosBtn) {
            rosBtn.className = "log-subtab-btn px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white flex items-center gap-2 transition";
        }
        if (auditBtn) {
            auditBtn.className = "log-subtab-btn px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white flex items-center gap-2 transition";
        }
        fetchRouterOSLogs();
    } else {
        if (rosView) rosView.classList.add('hidden');
        if (auditView) auditView.classList.remove('hidden');
        if (rosBtn) {
            rosBtn.className = "log-subtab-btn px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white flex items-center gap-2 transition";
        }
        if (auditBtn) {
            auditBtn.className = "log-subtab-btn px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white flex items-center gap-2 transition";
        }
        fetchAuditLogs();
    }
}

async function fetchRouterOSLogs(sync = false) {
    const tbody = document.getElementById('ros-logs-tbody');
    const counterEl = document.getElementById('ros-logs-counter');
    const footerInfo = document.getElementById('ros-logs-footer-info');
    const pageNumEl = document.getElementById('ros-page-num');
    const prevBtn = document.getElementById('ros-prev-btn');
    const nextBtn = document.getElementById('ros-next-btn');

    try {
        const offset = (rosLogsState.page - 1) * rosLogsState.limit;
        let url = `/api/routeros/logs?limit=${rosLogsState.limit}&offset=${offset}`;
        if (rosLogsState.severity && rosLogsState.severity !== 'all') {
            url += `&severity=${encodeURIComponent(rosLogsState.severity)}`;
        }
        if (rosLogsState.topic && rosLogsState.topic !== 'all') {
            url += `&topic=${encodeURIComponent(rosLogsState.topic)}`;
        }
        if (rosLogsState.search) {
            url += `&search=${encodeURIComponent(rosLogsState.search)}`;
        }
        if (sync) {
            url += `&sync=true`;
        }

        const res = await fetch(url);
        if (!res.ok) throw new Error("Gagal mengambil log RouterOS");
        const json = await res.json();
        const logs = json.data || [];
        rosLogsState.total = json.total || 0;

        if (counterEl) {
            counterEl.textContent = `${rosLogsState.total.toLocaleString()} log diarsipkan`;
        }

        if (!logs || logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-8 text-center text-slate-500">Tidak ada log sistem yang cocok dengan kriteria pencarian.</td></tr>';
            if (footerInfo) footerInfo.textContent = '0 log ditemukan';
            if (prevBtn) prevBtn.disabled = true;
            if (nextBtn) nextBtn.disabled = true;
            return;
        }

        tbody.innerHTML = logs.map(l => {
            let badgeClass = "bg-cyan-900/50 text-cyan-300 border-cyan-700/40";
            let badgeText = (l.severity || "INFO").toUpperCase();
            if (l.severity === "error" || l.severity === "critical") {
                badgeClass = "bg-rose-900/60 text-rose-300 border-rose-700/50";
                badgeText = "ERROR";
            } else if (l.severity === "warning") {
                badgeClass = "bg-amber-900/60 text-amber-300 border-amber-700/50";
                badgeText = "WARN";
            } else if (l.severity === "account") {
                badgeClass = "bg-emerald-900/60 text-emerald-300 border-emerald-700/50";
                badgeText = "AUTH";
            }

            return `
                <tr class="hover:bg-slate-800/40 transition-colors">
                    <td class="px-5 py-2.5 text-slate-300 font-mono text-[11px] whitespace-nowrap">${escapeHtml(l.log_time || '-')}</td>
                    <td class="px-4 py-2.5 whitespace-nowrap">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${badgeClass}">${badgeText}</span>
                    </td>
                    <td class="px-5 py-2.5 text-slate-400 text-[11px] max-w-[140px] truncate" title="${escapeHtml(l.topics || '')}">${escapeHtml(l.topics || '-')}</td>
                    <td class="px-5 py-2.5 text-slate-200 text-xs font-mono break-all">${escapeHtml(l.message || '')}</td>
                    <td class="px-5 py-2.5 text-slate-500 text-[11px] text-right whitespace-nowrap font-mono">${escapeHtml(l.timestamp || '-')}</td>
                </tr>
            `;
        }).join('');

        const startIdx = offset + 1;
        const endIdx = offset + logs.length;
        if (footerInfo) {
            footerInfo.textContent = `Menampilkan ${startIdx}–${endIdx} dari ${rosLogsState.total} log`;
        }
        if (pageNumEl) pageNumEl.textContent = rosLogsState.page;
        if (prevBtn) prevBtn.disabled = rosLogsState.page <= 1;
        if (nextBtn) nextBtn.disabled = endIdx >= rosLogsState.total;

    } catch (e) {
        console.error("fetchRouterOSLogs error:", e);
        tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-6 text-center text-rose-400">Gagal memuat log: ${escapeHtml(e.message)}</td></tr>`;
    }
}

async function syncRouterOSLogs() {
    const btn = document.getElementById('btn-sync-ros-logs');
    const originalHtml = btn.innerHTML;
    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Menghubungi MikroTik...';
        const res = await fetch('/api/routeros/logs/sync', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || "Log MikroTik berhasil disinkronkan!", "success");
            await fetchRouterOSLogs();
        } else {
            showToast(data.message || "Gagal sinkron log", "error");
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

async function clearLocalRosLogs() {
    if (!confirm("Hapus seluruh riwayat log RouterOS yang tersimpan di database lokal Debian 13?")) {
        return;
    }
    try {
        const res = await fetch('/api/routeros/logs', { method: 'DELETE' });
        const data = await res.json();
        showToast(data.message || "Log lokal dibersihkan", "info");
        rosLogsState.page = 1;
        await fetchRouterOSLogs();
    } catch (e) {
        showToast(`Gagal: ${e.message}`, "error");
    }
}

function setRosSeverityFilter(sev) {
    rosLogsState.severity = sev;
    rosLogsState.page = 1;
    document.querySelectorAll('.ros-sev-btn').forEach(btn => {
        btn.className = "ros-sev-btn px-2.5 py-1 rounded-lg font-medium text-slate-400 hover:text-slate-200";
    });
    const activeBtn = document.getElementById(`sev-btn-${sev}`);
    if (activeBtn) {
        activeBtn.className = "ros-sev-btn px-2.5 py-1 rounded-lg font-medium text-white bg-indigo-600";
    }
    fetchRouterOSLogs();
}

function filterRosLogs() {
    const sel = document.getElementById('ros-log-topic-filter');
    rosLogsState.topic = sel ? sel.value : 'all';
    rosLogsState.page = 1;
    fetchRouterOSLogs();
}

function debounceRosSearch() {
    clearTimeout(rosLogsState.searchTimeout);
    rosLogsState.searchTimeout = setTimeout(() => {
        const inp = document.getElementById('ros-log-search');
        rosLogsState.search = inp ? inp.value.trim() : '';
        rosLogsState.page = 1;
        fetchRouterOSLogs();
    }, 300);
}

function changeRosLogsPage(delta) {
    const newPage = rosLogsState.page + delta;
    if (newPage >= 1) {
        rosLogsState.page = newPage;
        fetchRouterOSLogs();
    }
}

// ----------------- AUDIT LOGS (BANDWIDTH MANAGER) -----------------
async function fetchAuditLogs() {
    const tbody = document.getElementById('logs-tbody');
    try {
        const res = await fetch('/api/logs');
        if (!res.ok) return;
        const logs = await res.json();
        if (!logs || logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="px-6 py-4 text-center text-slate-500">Belum ada riwayat aktivitas.</td></tr>';
            return;
        }
        tbody.innerHTML = logs.map(l => `
            <tr class="hover:bg-slate-800/40">
                <td class="px-6 py-2.5 text-slate-400">${escapeHtml(l.timestamp || '-')}</td>
                <td class="px-6 py-2.5 font-bold text-indigo-300">${escapeHtml(l.action || '-')}</td>
                <td class="px-6 py-2.5 text-slate-200">${escapeHtml(l.target_ip || '-')}</td>
                <td class="px-6 py-2.5 text-slate-300">${escapeHtml(l.detail || '-')}</td>
                <td class="px-6 py-2.5 text-slate-500 uppercase">${escapeHtml(l.source || '-')}</td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Failed to fetch logs:", e);
    }
}

async function fetchSchedules() {
    const container = document.getElementById('schedule-list-container');
    try {
        const res = await fetch('/api/schedules');
        if (!res.ok) return;
        const schedules = await res.json();
        if (!schedules || schedules.length === 0) {
            container.innerHTML = `
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500">
                    <i class="fa-solid fa-calendar-xmark text-3xl mb-2 text-slate-600"></i>
                    <p class="text-sm">Belum ada jadwal otomatis yang dibuat.</p>
                </div>
            `;
            return;
        }
        container.innerHTML = schedules.map(s => {
            const isEnabled = Boolean(s.is_enabled);
            return `
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4 ${isEnabled ? '' : 'opacity-65'}">
                    <div class="min-w-0">
                        <div class="flex items-center gap-2">
                            <h4 class="text-sm font-semibold text-white">${escapeHtml(s.name)}</h4>
                            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isEnabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-500'}">${isEnabled ? 'AKTIF' : 'NONAKTIF'}</span>
                        </div>
                        <p class="text-xs text-slate-400 font-mono mt-1">Target: ${escapeHtml(s.device_alias || s.device_ip)} (${escapeHtml(s.device_ip)}) • Jam: ${escapeHtml(s.start_time)} s/d ${escapeHtml(s.end_time)} • Aksi: ${escapeHtml(s.action_mode)}</p>
                    </div>
                    <div class="flex items-center space-x-2 shrink-0">
                        <button onclick="toggleSchedule(${Number(s.id)}, ${!isEnabled})" class="px-3 py-1 rounded-lg bg-slate-800 text-indigo-400 text-xs font-semibold transition">${isEnabled ? 'Nonaktifkan' : 'Aktifkan'}</button>
                        <button onclick="deleteSchedule(${Number(s.id)})" class="px-3 py-1 rounded-lg bg-rose-900/30 hover:bg-rose-900/60 text-rose-400 text-xs font-semibold transition">Hapus</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.error("Failed to fetch schedules:", e);
    }
}

// ----------------- WEBSOCKET & CHARTS -----------------
function initChart() {
    const ctx = document.getElementById('trafficChart')?.getContext('2d');
    if (!ctx) return;

    trafficChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: 'Download (Mbps)',
                    data: chartRxData,
                    borderColor: '#188038',
                    backgroundColor: 'rgba(24, 128, 56, 0.08)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 0
                },
                {
                    label: 'Upload (Mbps)',
                    data: chartTxData,
                    borderColor: '#0b57d0',
                    backgroundColor: 'rgba(11, 87, 208, 0.08)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: {
                    grid: { color: 'rgba(95, 99, 104, 0.12)' },
                    ticks: { color: '#5f6368', font: { family: 'Roboto Mono', size: 10 } }
                },
                y: {
                    grid: { color: 'rgba(95, 99, 104, 0.12)' },
                    ticks: { color: '#5f6368', font: { family: 'Roboto Mono', size: 10 } },
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#3c4043', font: { family: 'Roboto', size: 11 } }
                }
            }
        }
    });
}

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/traffic`;
    let ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'traffic_update') {
                const nowStr = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                
                // Update graph labels
                document.getElementById('graph-rx-label').textContent = data.rx_str;
                document.getElementById('graph-tx-label').textContent = data.tx_str;
                setText('nav-rx', data.rx_str);
                setText('nav-tx', data.tx_str);
                setText('nav-cpu', `${data.cpu_load}%`);

                if (trafficChart) {
                    const rxMbps = (data.rx_bps / 1_000_000).toFixed(2);
                    const txMbps = (data.tx_bps / 1_000_000).toFixed(2);

                    chartLabels.push(nowStr);
                    chartRxData.push(rxMbps);
                    chartTxData.push(txMbps);

                    if (chartLabels.length > MAX_CHART_POINTS) {
                        chartLabels.shift();
                        chartRxData.shift();
                        chartTxData.shift();
                    }
                    trafficChart.update();
                }
            }
        } catch (e) {
            console.error("WS Parse error:", e);
        }
    };

    ws.onclose = () => {
        setTimeout(initWebSocket, 2500);
    };
}

// ----------------- TOAST UTILITY -----------------
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const colors = {
        success: 'bg-emerald-600 text-white border-emerald-500',
        error: 'bg-rose-600 text-white border-rose-500',
        info: 'bg-slate-800 text-slate-100 border-slate-700'
    };

    const toast = document.createElement('div');
    toast.className = `px-4 py-3 rounded-xl border shadow-2xl text-xs font-medium flex items-center gap-2 pointer-events-auto animate-scale-up ${colors[type] || colors.info}`;
    toast.innerHTML = `
        <i class="fa-solid ${type === 'success' ? 'fa-circle-check text-emerald-300' : (type === 'error' ? 'fa-circle-exclamation text-rose-300' : 'fa-circle-info text-cyan-300')}"></i>
        <span>${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ----------------- HELPERS -----------------
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
