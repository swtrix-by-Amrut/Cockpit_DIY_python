let currentUser = null;
let isAdmin = false;

// Toast notification
function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show' + (isError ? ' error' : '');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 5000);
}

// Login
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = username;
            isAdmin = data.is_admin;
            document.getElementById('loginContainer').style.display = 'none';
            document.getElementById('mainContainer').style.display = 'flex';
            document.getElementById('userDisplay').textContent = `${username} ${isAdmin ? '(Admin)' : ''}`;
            
            // Load first page
            refreshStorage();
        } else {
            showToast(data.error || 'Login failed', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
});

// Logout
async function logout() {
    try {
        await fetch('/api/logout', {method: 'POST'});
    } catch (e) {}
    
    location.reload();
}

// Page navigation
function showPage(pageName) {
    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Show selected page
    const page = document.getElementById(pageName + 'Page');
    if (page) {
        page.classList.add('active');
        
        // Load data for the page
        switch(pageName) {
            case 'storage':
                refreshStorage();
                break;
            case 'system':
                refreshSystemStats();
                break;
            case 'processes':
                refreshProcesses();
                break;
            case 'terminal':
                refreshSessions();
                break;
            case 'docker':
                refreshDocker();
                break;
            case 'apps':
                refreshApps();
                break;
        }
    }
}

// Storage Management
async function refreshStorage() {
    const content = document.getElementById('storageContent');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading...</p></div>';
    
    try {
        const response = await fetch('/api/storage');
        const data = await response.json();
        
        if (!response.ok) {
            content.innerHTML = `<p style="color: #f44336;">${data.error || 'Failed to load storage'}</p>`;
            return;
        }
        
        let html = '<div class="storage-grid">';
        
        if (data.disks.length === 0) {
            html = '<p>No disks found</p>';
        }
        
        for (const disk of data.disks) {
            html += `<div class="disk-item">
                <h4>💾 ${disk.name} (${disk.size})</h4>`;
            
            for (const part of disk.partitions) {
                const mounted = part.is_mounted;
                const usage = part.usage;
                
                html += `<div class="partition-item">
                    <div class="partition-header">
                        <div>
                            <strong>${part.name}</strong>
                            ${part.is_internal ? '<span style="color: #4CAF50;"> (Internal)</span>' : ''}
                            <br>
                            <small>${part.fstype || 'Unknown'} • ${part.size}</small>
                        </div>
                        <div class="partition-actions">`;
                
                // Show mount buttons based on conditions
				if (isAdmin) {
					if (!part.is_internal) {
						// External drives: show all 3 mount options or unmount
						if (mounted) {
							html += `<button class="btn btn-danger btn-sm" onclick="unmountPartition('${part.device}')">Unmount</button>`;
						} else {
							html += `
								<button class="btn btn-primary btn-sm" onclick="mountPartition('${part.device}', 'normal')">Mount</button>
								<button class="btn btn-secondary btn-sm" onclick="mountPartition('${part.device}', 'private')">Mount Private</button>
								<button class="btn btn-secondary btn-sm" onclick="mountPartition('${part.device}', 'public')">Mount Public</button>`;
						}
					}
					// Internal drives: no buttons at all (removed unmount option)
				}
                
                html += `</div></div>`;
                
                if (mounted && usage.size) {
                    const percent = parseInt(usage.percent) || 0;
                    html += `
                        <div style="margin-top: 10px;">
                            <small>Mounted: ${part.mountpoint}</small><br>
                            <small>${usage.used} / ${usage.size} (${usage.percent}) • ${usage.available} free</small>
                            <div class="usage-bar">
                                <div class="usage-fill" style="width: ${percent}%"></div>
                            </div>
                        </div>`;
                }
                
                html += `</div>`;
            }
            
            html += `</div>`;
        }
        
        html += '</div>';  // Close storage-grid
        content.innerHTML = html;
    } catch (error) {
        content.innerHTML = `<p style="color: #f44336;">Error: ${error.message}</p>`;
        showToast('Failed to load storage: ' + error.message, true);
    }
}

async function mountPartition(device, type) {
    try {
        const response = await fetch('/api/storage/mount', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({device, type})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(`Mounted ${device} at ${data.mountpoint}`);
            refreshStorage();
        } else {
            showToast(data.error || 'Mount failed', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
}

async function unmountPartition(device) {
    if (!confirm(`Unmount ${device}?`)) return;
    
    try {
        const response = await fetch('/api/storage/unmount', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({device})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(`Unmounted ${device}`);
            refreshStorage();
        } else {
            showToast(data.error || 'Unmount failed', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
}

// Power Management
async function powerAction(action) {
    const confirmMsg = action === 'shutdown' ? 
        'Are you sure you want to SHUTDOWN the server?' : 
        'Are you sure you want to REBOOT the server?';
    
    if (!confirm(confirmMsg)) return;
    
    try {
        const response = await fetch('/api/system/power', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
        } else {
            showToast(data.error || 'Action failed', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
}

// System Stats
async function refreshSystemStats() {
    const content = document.getElementById('systemStatsContent');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/api/system/stats');
        const data = await response.json();
        
        if (!response.ok) {
            content.innerHTML = `<p style="color: #f44336;">${data.error || 'Failed to load stats'}</p>`;
            return;
        }
        
        const html = `
            <div class="stat-grid">
                <div class="stat-card">
                    <div class="stat-label">CPU Usage</div>
                    <div class="stat-value">${data.cpu_percent}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">CPU Temperature</div>
                    <div class="stat-value">${data.cpu_temp !== null ? data.cpu_temp + '°C' : 'N/A'}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Memory Usage</div>
                    <div class="stat-value">${data.memory.percent}%</div>
                    <small style="color: #b0b0b0;">${data.memory.used}GB / ${data.memory.total}GB</small>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Memory Available</div>
                    <div class="stat-value">${data.memory.available}GB</div>
                </div>
            </div>`;
        
        content.innerHTML = html;
    } catch (error) {
        content.innerHTML = `<p style="color: #f44336;">Error: ${error.message}</p>`;
        showToast('Failed to load stats: ' + error.message, true);
    }
}

// Processes
let htopEventSource = null;
let htopRunning = false;

function toggleHtop() {
    if (htopRunning) {
        stopHtop();
    } else {
        startHtop();
    }
}

function startHtop() {
    const container = document.getElementById('htopContainer');
    const toggleText = document.getElementById('htopToggleText');
    
    container.style.display = 'block';
    container.textContent = 'Starting process monitor...';
    
    htopEventSource = new EventSource('/api/htop/stream');
    
    htopEventSource.onmessage = function(event) {
        // Clear and update with new data
        container.textContent = event.data;
    };
    
    htopEventSource.onerror = function(error) {
        console.error('EventSource error:', error);
        container.textContent += '\n\nConnection lost. Click Start to reconnect.';
        stopHtop();
    };
    
    htopRunning = true;
    toggleText.textContent = '⏸ Stop';
}

function stopHtop() {
    const toggleText = document.getElementById('htopToggleText');
    
    if (htopEventSource) {
        htopEventSource.close();
        htopEventSource = null;
    }
    
    htopRunning = false;
    toggleText.textContent = '▶ Start';
    
    const container = document.getElementById('htopContainer');
    container.style.display = 'none';
}

// Keep old function for compatibility but make it use htop
function refreshProcesses() {
    // Auto-start htop when page loads
    if (!htopRunning) {
        startHtop();
    }
}

// Clean up on page change
const originalShowPage = showPage;
showPage = function(pageName) {
    // Stop htop when leaving processes page
    if (htopRunning && pageName !== 'processes') {
        stopHtop();
    }
    originalShowPage(pageName);
};

// Terminal Sessions
async function refreshSessions() {
    const content = document.getElementById('sessionContent');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/api/terminal/sessions');
        const data = await response.json();
        
        if (!response.ok) {
            content.innerHTML = `<p style="color: #f44336;">${data.error || 'Failed to load sessions'}</p>`;
            return;
        }
        
        let html = `<p style="margin-bottom: 15px; color: #b0b0b0;">
            Sessions: ${data.count} / ${data.max_sessions}</p>`;
        
        if (data.sessions.length === 0) {
            html += '<p>No active sessions. Create one to get started.</p>';
        } else {
            html += '<div class="session-list">';
            for (const session of data.sessions) {
                html += `
                    <div class="session-item">
                        <div>
                            <strong>${session.name}</strong>
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <button class="btn btn-secondary btn-sm" onclick="useSession('${session.name}')">Use</button>
                            <button class="btn btn-danger btn-sm" onclick="deleteSession('${session.name}')">Delete</button>
                        </div>
                    </div>`;
            }
            html += '</div>';
        }
        
        content.innerHTML = html;
    } catch (error) {
        content.innerHTML = `<p style="color: #f44336;">Error: ${error.message}</p>`;
        showToast('Failed to load sessions: ' + error.message, true);
    }
}

async function createSession() {
    try {
        const response = await fetch('/api/terminal/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            refreshSessions();
        } else {
            showToast(data.error || 'Failed to create session', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
}


let currentTerminal = null;
let currentTerminalId = null;
let terminalEventSource = null;

async function useSession(sessionName) {
    try {
        // Close existing terminal
        if (currentTerminal) {
            await closeTerminal();
        }
        
        // Show terminal card
        document.getElementById('terminalCard').style.display = 'block';
        document.getElementById('activeSessionName').textContent = sessionName;
        
        // Clear container
        const container = document.getElementById('terminalContainer');
        container.innerHTML = '';
        
        // Create xterm terminal
        currentTerminal = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: '"Cascadia Code", Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#000000',
                foreground: '#ffffff',
                cursor: '#ffffff',
                black: '#000000',
                red: '#ff0000',
                green: '#00ff00',
                yellow: '#ffff00',
                blue: '#0000ff',
                magenta: '#ff00ff',
                cyan: '#00ffff',
                white: '#ffffff',
                brightBlack: '#808080',
                brightRed: '#ff0000',
                brightGreen: '#00ff00',
                brightYellow: '#ffff00',
                brightBlue: '#0000ff',
                brightMagenta: '#ff00ff',
                brightCyan: '#00ffff',
                brightWhite: '#ffffff'
            },
            rows: 30,
            cols: 100
        });
        
        currentTerminal.open(container);
        
        // Connect to tmux session
        const response = await fetch('/api/terminal/connect', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_name: sessionName})
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showToast(data.error || 'Failed to connect', true);
            return;
        }
        
        currentTerminalId = data.terminal_id;
        
        // Handle terminal input
        currentTerminal.onData(function(data) {
            fetch(`/api/terminal/write/${currentTerminalId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({data: data})
            });
        });
        
        // Handle terminal resize
        currentTerminal.onResize(function(size) {
            fetch(`/api/terminal/resize/${currentTerminalId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({rows: size.rows, cols: size.cols})
            });
        });
        
        // Connect to output stream
        terminalEventSource = new EventSource(`/api/terminal/read/${currentTerminalId}`);
        
        terminalEventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.output) {
                currentTerminal.write(data.output);
            }
        };
        
        terminalEventSource.onerror = function() {
            showToast('Terminal connection lost', true);
            closeTerminal();
        };
        
        // Focus terminal
        currentTerminal.focus();
        
    } catch (error) {
        showToast('Error: ' + error.message, true);
    }
}

async function closeTerminal() {
    // Close event source
    if (terminalEventSource) {
        terminalEventSource.close();
        terminalEventSource = null;
    }
    
    // Disconnect from terminal (tmux session stays alive)
    if (currentTerminalId) {
        await fetch(`/api/terminal/disconnect/${currentTerminalId}`, {
            method: 'POST'
        }).catch(() => {});
        currentTerminalId = null;
    }
    
    // Dispose xterm
    if (currentTerminal) {
        currentTerminal.dispose();
        currentTerminal = null;
    }
    
    // Hide card
    document.getElementById('terminalCard').style.display = 'none';
    
    showToast('Disconnected from terminal (session still running)');
}

async function deleteSession(sessionName) {
    if (!confirm(`Delete session ${sessionName}?`)) return;
    
    try {
        const response = await fetch('/api/terminal/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_name: sessionName})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            refreshSessions();
        } else {
            showToast(data.error || 'Failed to delete session', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
}

// Docker Management
async function refreshDocker() {
    const content = document.getElementById('dockerContent');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/api/docker/containers');
        const data = await response.json();
        
        if (data.error) {
            content.innerHTML = `<p style="color: #f44336;">${data.error}</p>`;
            return;
        }
        
        if (!response.ok) {
            content.innerHTML = `<p style="color: #f44336;">Failed to load containers</p>`;
            return;
        }
        
        if (data.containers.length === 0) {
            content.innerHTML = '<p>No containers found</p>';
            return;
        }
        
        let html = '';
        for (const container of data.containers) {
            const isRunning = container.state.toLowerCase() === 'running';
            
            html += `
                <div class="container-item">
                    <div class="container-info">
                        <div>
                            <strong>${container.name}</strong>
                            <span class="status-badge ${isRunning ? 'status-running' : 'status-stopped'}">
                                ${container.state}
                            </span>
                        </div>
                        <small style="color: #b0b0b0;">${container.image}</small><br>
                        <small style="color: #888;">${container.status}</small>
                    </div>
                    ${isAdmin ? `
                    <div class="container-actions">
                        ${!isRunning ? `<button class="btn btn-primary btn-sm" onclick="dockerAction('${container.id}', 'start')">Start</button>` : ''}
                        ${isRunning ? `<button class="btn btn-danger btn-sm" onclick="dockerAction('${container.id}', 'stop')">Stop</button>` : ''}
                        <button class="btn btn-secondary btn-sm" onclick="dockerAction('${container.id}', 'restart')">Restart</button>
                    </div>` : ''}
                </div>`;
        }
        
        content.innerHTML = html;
    } catch (error) {
        content.innerHTML = `<p style="color: #f44336;">Error: ${error.message}</p>`;
        showToast('Failed to load containers: ' + error.message, true);
    }
}

async function dockerAction(containerId, action) {
    try {
        const response = await fetch('/api/docker/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({container: containerId, action})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            setTimeout(refreshDocker, 1000);
        } else {
            showToast(data.error || 'Action failed', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
}

// App Control
async function refreshApps() {
    const content = document.getElementById('appsContent');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const response = await fetch('/api/apps');
        const data = await response.json();
        
        if (!response.ok) {
            content.innerHTML = `<p style="color: #f44336;">${data.error || 'Failed to load apps'}</p>`;
            return;
        }
        
        if (data.apps.length === 0) {
            content.innerHTML = '<p>No apps configured. Edit config/apps.json to add apps.</p>';
            return;
        }
        
        let html = '';
        for (const app of data.apps) {
            const isRunning = app.status === 'running';
            
            html += `
                <div class="app-item">
                    <div>
                        <strong>${app.display_name}</strong>
                        <span class="status-badge ${isRunning ? 'status-running' : 'status-stopped'}">
                            ${app.status}
                        </span>
                    </div>
                    ${isAdmin ? `
                    <div style="display: flex; gap: 10px;">
                        ${!isRunning ? `<button class="btn btn-primary btn-sm" onclick="appAction('${app.name}', 'start')">Start</button>` : ''}
                        ${isRunning ? `<button class="btn btn-danger btn-sm" onclick="appAction('${app.name}', 'stop')">Stop</button>` : ''}
                    </div>` : ''}
                </div>`;
        }
        
        content.innerHTML = html;
    } catch (error) {
        content.innerHTML = `<p style="color: #f44336;">Error: ${error.message}</p>`;
        showToast('Failed to load apps: ' + error.message, true);
    }
}

async function appAction(appName, action) {
    try {
        const response = await fetch('/api/apps/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({app: appName, action})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            setTimeout(refreshApps, 1000);
        } else {
            showToast(data.error || 'Action failed', true);
        }
    } catch (error) {
        showToast('Network error: ' + error.message, true);
    }
}

// Check if user is already logged in on page load
async function checkSession() {
    try {
        const response = await fetch('/api/session/check');
        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                currentUser = data.username;
                isAdmin = data.is_admin;
                document.getElementById('loginContainer').style.display = 'none';
                document.getElementById('mainContainer').style.display = 'flex';
                document.getElementById('userDisplay').textContent = `${data.username} ${data.is_admin ? '(Admin)' : ''}`;
                refreshStorage();
            }
        }
    } catch (error) {
        // Not logged in, show login page
    }
}

// Run session check on page load
checkSession();