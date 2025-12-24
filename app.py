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

from flask import Flask, render_template, request, jsonify, session, Response
from flask_cors import CORS
import os
import secrets
from functools import wraps
from datetime import timedelta
import subprocess
import time
import json
import threading
import queue


active_terminals = {}


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
    
@app.route('/api/terminal/connect/<session_name>')
@login_required
def connect_terminal(session_name):
    username = session['username']
    
    # Verify session belongs to user
    prefix = f"cockpit_{username}_"
    if not session_name.startswith(prefix):
        return jsonify({'error': 'Invalid session'}), 403
    
    # Check if session exists
    result = subprocess.run(
        f"tmux has-session -t {session_name} 2>/dev/null",
        shell=True,
        capture_output=True
    )
    
    if result.returncode != 0:
        return jsonify({'error': 'Session does not exist'}), 404
    
    # Create a unique terminal ID
    terminal_id = f"{session_name}_{secrets.token_hex(8)}"
    
    # Create bash process attached to tmux session
    cmd = f"tmux attach-session -t {session_name}"
    
    # Start the process
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0
    )
    
    output_queue = queue.Queue()
    
    def read_output():
        while True:
            try:
                char = proc.stdout.read(1)
                if char:
                    output_queue.put(char.decode('utf-8', errors='ignore'))
                else:
                    break
            except:
                break
    
    # Start output reading thread
    thread = threading.Thread(target=read_output, daemon=True)
    thread.start()
    
    active_terminals[terminal_id] = {
        'process': proc,
        'output_queue': output_queue,
        'thread': thread
    }
    
    return jsonify({'terminal_id': terminal_id, 'success': True})

@app.route('/api/terminal/output/<terminal_id>')
@login_required
def terminal_output(terminal_id):
    if terminal_id not in active_terminals:
        return jsonify({'error': 'Terminal not found'}), 404
    
    def generate():
        term_data = active_terminals[terminal_id]
        output_queue = term_data['output_queue']
        
        while terminal_id in active_terminals:
            try:
                # Get all available output
                output = ''
                try:
                    while True:
                        output += output_queue.get(timeout=0.1)
                except queue.Empty:
                    pass
                
                if output:
                    yield f"data: {json.dumps({'output': output})}\n\n"
                else:
                    yield f"data: {json.dumps({'ping': True})}\n\n"
                
                time.sleep(0.05)
            except:
                break
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/terminal/input/<terminal_id>', methods=['POST'])
@login_required
def terminal_input(terminal_id):
    if terminal_id not in active_terminals:
        return jsonify({'error': 'Terminal not found'}), 404
    
    data = request.json
    input_data = data.get('input', '')
    
    term_data = active_terminals[terminal_id]
    proc = term_data['process']
    
    try:
        proc.stdin.write(input_data.encode('utf-8'))
        proc.stdin.flush()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Failed to send input'}), 500

@app.route('/api/terminal/close/<terminal_id>', methods=['POST'])
@login_required
def close_terminal(terminal_id):
    if terminal_id in active_terminals:
        term_data = active_terminals[terminal_id]
        proc = term_data['process']
        
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except:
            proc.kill()
        
        del active_terminals[terminal_id]
    
    return jsonify({'success': True})

         
            
if __name__ == '__main__':
    os.makedirs('config', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)