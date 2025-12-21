from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import secrets
from functools import wraps
from datetime import timedelta
import subprocess

from flask_sock import Sock
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
# app.secret_key = secrets.token_hex(32)
sock = Sock(app)

app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Session lasts 1 day
CORS(app)



CORS(app)

# Initialize managers
auth_mgr = AuthManager('config/users.csv')
storage_mgr = StorageManager()
system_mgr = SystemManager()
process_mgr = ProcessManager()
terminal_mgr = TerminalManager('config/settings.ini')
docker_mgr = DockerManager()
app_ctrl = AppController()

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
        session.permanent = True  # Make session persistent
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

@app.route('/api/terminal/attach', methods=['POST'])
@login_required
def attach_session():
    session_name = request.json.get('session_name')
    username = session['username']
    
    # Verify session belongs to user
    prefix = f"cockpit_{username}_"
    if not session_name.startswith(prefix):
        return jsonify({'success': False, 'error': 'Invalid session name'}), 403
    
    # Check if session exists
    cmd = f"tmux has-session -t {session_name} 2>/dev/null"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    
    if result.returncode != 0:
        return jsonify({'success': False, 'error': 'Session does not exist'}), 404
    
    attach_cmd = f"tmux attach-session -t {session_name}"
    
    return jsonify({
        'success': True,
        'command': attach_cmd,
        'session_name': session_name,
        'message': f'To connect via SSH, run: {attach_cmd}'
    })

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

from flask import Response
import time

@app.route('/api/htop/stream')
@login_required
def htop_stream():
    def generate():
        while True:
            try:
                # Use top in batch mode with more lines
                result = subprocess.run(
                    ['top', '-b', '-n', '1', '-w', '200', '-o', '%MEM'],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env={'COLUMNS': '200', 'LINES': '50'}
                )
                
                if result.returncode == 0:
                    output = result.stdout
                    # Ensure we're sending the full output
                    yield f"data: {output}\n\n"
                else:
                    yield f"data: Error: {result.stderr}\n\n"
                
                time.sleep(2)
            except subprocess.TimeoutExpired:
                yield "data: Command timeout\n\n"
                time.sleep(2)
            except Exception as e:
                yield f"data: Error: {str(e)}\n\n"
                time.sleep(2)
    
    return Response(generate(), mimetype='text/event-stream')
    
@sock.route('/api/terminal/ws/<session_name>')
def terminal_websocket(ws, session_name):
    # Verify session belongs to user
    if 'username' not in session:
        ws.close()
        return
    
    username = session['username']
    if not session_name.startswith(f"cockpit_{username}_"):
        ws.close()
        return
    
    # Check if session exists
    result = subprocess.run(
        f"tmux has-session -t {session_name} 2>/dev/null",
        shell=True,
        capture_output=True
    )
    
    if result.returncode != 0:
        ws.send(json.dumps({'error': 'Session does not exist'}))
        ws.close()
        return
    
    # Attach to tmux session using pty
    cmd = f"tmux attach-session -t {session_name}"
    
    # Create pty
    pid, fd = pty.fork()
    
    if pid == 0:
        # Child process
        os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])
    
    # Parent process
    try:
        # Set non-blocking
        flag = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
        
        while True:
            # Check for data from tmux
            r, _, _ = select.select([fd], [], [], 0.01)
            if fd in r:
                try:
                    data = os.read(fd, 1024)
                    if data:
                        ws.send(data.decode('utf-8', errors='ignore'))
                    else:
                        break
                except OSError:
                    break
            
            # Check for data from websocket
            try:
                data = ws.receive(timeout=0.01)
                if data:
                    os.write(fd, data.encode('utf-8'))
            except:
                pass
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        os.close(fd)
        try:
            os.kill(pid, 9)
        except:
            pass
            
            
if __name__ == '__main__':
    os.makedirs('config', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)