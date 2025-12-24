from flask import Flask, render_template, request, jsonify, session, Response
from flask_cors import CORS
import os
import secrets
from functools import wraps
from datetime import timedelta
import subprocess
import time
import json
import pty
import select
import struct
import fcntl
import termios

# Import modules
from modules.auth import AuthManager
from modules.storage import StorageManager
from modules.system import SystemManager
from modules.process import ProcessManager
from modules.terminal import TerminalManager
from modules.docker_mgr import DockerManager
from modules.app_control import AppController

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
CORS(app)

# Initialize managers
auth_mgr = AuthManager('config/users.csv')
storage_mgr = StorageManager()
system_mgr = SystemManager()
process_mgr = ProcessManager()
terminal_mgr = TerminalManager('config/settings.ini')
docker_mgr = DockerManager()
app_ctrl = AppController()

# Active terminal connections
active_terminals = {}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        if not session.get('is_admin', False):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = auth_mgr.authenticate(username, password)
    if user:
        session.permanent = True
        session['username'] = username
        session['is_admin'] = user['is_admin']
        return jsonify({'success': True, 'is_admin': user['is_admin']})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/session/check', methods=['GET'])
def check_session():
    if 'username' in session:
        return jsonify({
            'authenticated': True,
            'username': session['username'],
            'is_admin': session.get('is_admin', False)
        })
    return jsonify({'authenticated': False}), 401

@app.route('/api/storage', methods=['GET'])
@login_required
def get_storage():
    try:
        data = storage_mgr.get_storage_info()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/storage/mount', methods=['POST'])
@admin_required
def mount_partition():
    data = request.json
    device = data.get('device')
    mount_type = data.get('type', 'private')
    try:
        result = storage_mgr.mount(device, mount_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/storage/unmount', methods=['POST'])
@admin_required
def unmount_partition():
    data = request.json
    device = data.get('device')
    try:
        result = storage_mgr.unmount(device)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/power', methods=['POST'])
@admin_required
def system_power():
    action = request.json.get('action')
    try:
        result = system_mgr.power_action(action)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/stats', methods=['GET'])
@login_required
def system_stats():
    try:
        data = system_mgr.get_stats()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/processes', methods=['GET'])
@login_required
def get_processes():
    try:
        data = process_mgr.get_processes()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add this near the top with other active tracking
active_htop_sessions = {}

@app.route('/api/htop/start', methods=['POST'])
@login_required
def start_htop():
    username = session['username']
    
    # Create unique htop session name
    htop_session = f"htop_{username}"
    
    # Kill existing htop session if any
    subprocess.run(f"tmux kill-session -t {htop_session} 2>/dev/null", shell=True)
    
    # Create new tmux session running htop
    create_cmd = f"tmux new-session -d -s {htop_session} htop"
    result = subprocess.run(create_cmd, shell=True, capture_output=True)
    
    if result.returncode != 0:
        return jsonify({'error': 'Failed to start htop'}), 500
    
    # Create terminal connection ID
    terminal_id = f"htop_{username}_{secrets.token_hex(8)}"
    
    # Fork PTY and attach to tmux session
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process - attach to htop tmux session
        os.execvp('tmux', ['tmux', 'attach-session', '-t', htop_session])
    
    # Parent process
    active_htop_sessions[terminal_id] = {
        'pid': pid,
        'fd': fd,
        'username': username,
        'session_name': htop_session
    }
    
    return jsonify({'terminal_id': terminal_id, 'success': True})

@app.route('/api/htop/read/<terminal_id>')
@login_required
def htop_read(terminal_id):
    if terminal_id not in active_htop_sessions:
        return Response('Terminal not found', status=404)
    
    def generate():
        term_data = active_htop_sessions.get(terminal_id)
        if not term_data:
            return
        
        fd = term_data['fd']
        
        try:
            while terminal_id in active_htop_sessions:
                r, _, _ = select.select([fd], [], [], 0.1)
                
                if r:
                    try:
                        data = os.read(fd, 4096)
                        if data:
                            yield f"data: {json.dumps({'output': data.decode('utf-8', errors='ignore')})}\n\n"
                        else:
                            break
                    except OSError:
                        break
                else:
                    yield f"data: {json.dumps({'keepalive': True})}\n\n"
        except:
            pass
        finally:
            if terminal_id in active_htop_sessions:
                cleanup_htop(terminal_id)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/htop/write/<terminal_id>', methods=['POST'])
@login_required
def htop_write(terminal_id):
    if terminal_id not in active_htop_sessions:
        return jsonify({'error': 'Terminal not found'}), 404
    
    data = request.json.get('data', '')
    term_data = active_htop_sessions[terminal_id]
    fd = term_data['fd']
    
    try:
        os.write(fd, data.encode('utf-8'))
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Write failed'}), 500

@app.route('/api/htop/resize/<terminal_id>', methods=['POST'])
@login_required
def htop_resize(terminal_id):
    if terminal_id not in active_htop_sessions:
        return jsonify({'error': 'Terminal not found'}), 404
    
    rows = request.json.get('rows', 24)
    cols = request.json.get('cols', 80)
    
    term_data = active_htop_sessions[terminal_id]
    fd = term_data['fd']
    
    try:
        size = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Resize failed'}), 500

@app.route('/api/htop/stop/<terminal_id>', methods=['POST'])
@login_required
def stop_htop(terminal_id):
    cleanup_htop(terminal_id)
    return jsonify({'success': True})

def cleanup_htop(terminal_id):
    if terminal_id in active_htop_sessions:
        term_data = active_htop_sessions[terminal_id]
        session_name = term_data['session_name']
        
        try:
            os.close(term_data['fd'])
            os.kill(term_data['pid'], 15)
        except:
            pass
        
        # Kill the tmux session
        subprocess.run(f"tmux kill-session -t {session_name} 2>/dev/null", shell=True)
        
        del active_htop_sessions[terminal_id]

# ==================== TERMINAL SESSION MANAGEMENT ====================

@app.route('/api/terminal/sessions', methods=['GET'])
@login_required
def list_sessions():
    username = session['username']
    try:
        sessions = terminal_mgr.list_sessions(username)
        return jsonify(sessions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminal/create', methods=['POST'])
@login_required
def create_session():
    username = session['username']
    try:
        result = terminal_mgr.create_session(username)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminal/delete', methods=['POST'])
@login_required
def delete_session():
    username = session['username']
    session_name = request.json.get('session_name')
    try:
        result = terminal_mgr.delete_session(username, session_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== PERSISTENT TERMINAL CONNECTION ====================

@app.route('/api/terminal/connect', methods=['POST'])
@login_required
def connect_terminal():
    """Connect to an existing tmux session"""
    username = session['username']
    session_name = request.json.get('session_name')
    
    # Verify session belongs to user
    prefix = f"cockpit_{username}_"
    if not session_name.startswith(prefix):
        return jsonify({'error': 'Invalid session name'}), 403
    
    # Check if tmux session exists
    check_cmd = f"tmux has-session -t {session_name} 2>/dev/null"
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    
    if result.returncode != 0:
        return jsonify({'error': 'Session does not exist'}), 404
    
    # Create a unique terminal connection ID
    terminal_id = f"{session_name}_{secrets.token_hex(8)}"
    
    # Fork a PTY and attach to tmux session
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process - attach to tmux session
        os.execvp('tmux', ['tmux', 'attach-session', '-t', session_name])
    
    # Parent process - store terminal info
    active_terminals[terminal_id] = {
        'pid': pid,
        'fd': fd,
        'username': username,
        'session_name': session_name
    }
    
    return jsonify({'terminal_id': terminal_id, 'success': True})

@app.route('/api/terminal/read/<terminal_id>')
@login_required
def terminal_read(terminal_id):
    """Read output from terminal"""
    if terminal_id not in active_terminals:
        return Response('Terminal not found', status=404)
    
    def generate():
        term_data = active_terminals.get(terminal_id)
        if not term_data:
            return
        
        fd = term_data['fd']
        
        try:
            while terminal_id in active_terminals:
                # Use select to wait for data
                r, _, _ = select.select([fd], [], [], 0.1)
                
                if r:
                    try:
                        data = os.read(fd, 4096)
                        if data:
                            yield f"data: {json.dumps({'output': data.decode('utf-8', errors='ignore')})}\n\n"
                        else:
                            break
                    except OSError:
                        break
                else:
                    # Send keepalive
                    yield f"data: {json.dumps({'keepalive': True})}\n\n"
        except:
            pass
        finally:
            if terminal_id in active_terminals:
                cleanup_terminal(terminal_id)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/terminal/write/<terminal_id>', methods=['POST'])
@login_required
def terminal_write(terminal_id):
    """Write input to terminal"""
    if terminal_id not in active_terminals:
        return jsonify({'error': 'Terminal not found'}), 404
    
    data = request.json.get('data', '')
    term_data = active_terminals[terminal_id]
    fd = term_data['fd']
    
    try:
        os.write(fd, data.encode('utf-8'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Write failed: {str(e)}'}), 500

@app.route('/api/terminal/resize/<terminal_id>', methods=['POST'])
@login_required
def terminal_resize(terminal_id):
    """Resize terminal window"""
    if terminal_id not in active_terminals:
        return jsonify({'error': 'Terminal not found'}), 404
    
    rows = request.json.get('rows', 24)
    cols = request.json.get('cols', 80)
    
    term_data = active_terminals[terminal_id]
    fd = term_data['fd']
    
    try:
        size = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Resize failed: {str(e)}'}), 500

@app.route('/api/terminal/disconnect/<terminal_id>', methods=['POST'])
@login_required
def disconnect_terminal(terminal_id):
    """Disconnect from terminal (tmux session keeps running)"""
    cleanup_terminal(terminal_id)
    return jsonify({'success': True, 'message': 'Disconnected (session still running)'})

def cleanup_terminal(terminal_id):
    """Clean up terminal connection (doesn't kill tmux session)"""
    if terminal_id in active_terminals:
        term_data = active_terminals[terminal_id]
        try:
            os.close(term_data['fd'])
            # Send Ctrl+B then D to detach from tmux
            try:
                os.kill(term_data['pid'], 15)  # SIGTERM to gracefully exit
            except:
                pass
        except:
            pass
        del active_terminals[terminal_id]

# ==================== DOCKER MANAGEMENT ====================

@app.route('/api/docker/containers', methods=['GET'])
@login_required
def list_containers():
    try:
        data = docker_mgr.list_containers()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/docker/action', methods=['POST'])
@admin_required
def docker_action():
    data = request.json
    container = data.get('container')
    action = data.get('action')
    try:
        result = docker_mgr.container_action(container, action)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== APP CONTROL ====================

@app.route('/api/apps', methods=['GET'])
@login_required
def list_apps():
    try:
        data = app_ctrl.list_apps()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/apps/action', methods=['POST'])
@admin_required
def app_action():
    data = request.json
    app_name = data.get('app')
    action = data.get('action')
    try:
        result = app_ctrl.app_action(app_name, action)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs('config', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)