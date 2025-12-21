import subprocess
import configparser
import os

class TerminalManager:
    def __init__(self, config_file='config/settings.ini'):
        self.config_file = config_file
        self.max_sessions = self._load_max_sessions()
    
    def _load_max_sessions(self):
        if not os.path.exists(self.config_file):
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            config = configparser.ConfigParser()
            config['terminal'] = {'max_sessions_per_user': '3'}
            with open(self.config_file, 'w') as f:
                config.write(f)
            return 3
        
        config = configparser.ConfigParser()
        config.read(self.config_file)
        return int(config.get('terminal', 'max_sessions_per_user', fallback='3'))
    
    def _run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return '', 'Command timeout', 1
    
    def _get_session_name(self, username, index):
        return f"cockpit_{username}_{index}"
    
    def list_sessions(self, username):
        # Check which tmux sessions exist for this user
        sessions = []
        
        # Get all tmux sessions
        stdout, _, code = self._run_command("tmux list-sessions -F '#{session_name}' 2>/dev/null")
        
        if code == 0 and stdout:
            all_sessions = stdout.split('\n')
            prefix = f"cockpit_{username}_"
            
            for session in all_sessions:
                if session.startswith(prefix):
                    sessions.append({
                        'name': session,
                        'index': int(session.replace(prefix, ''))
                    })
        
        sessions.sort(key=lambda x: x['index'])
        
        return {
            'sessions': sessions,
            'count': len(sessions),
            'max_sessions': self.max_sessions
        }
    
    def create_session(self, username):
        current = self.list_sessions(username)
        
        if current['count'] >= self.max_sessions:
            return {
                'success': False,
                'error': f'Maximum {self.max_sessions} sessions allowed per user'
            }
        
        # Find next available index
        used_indices = [s['index'] for s in current['sessions']]
        next_index = 0
        while next_index in used_indices:
            next_index += 1
        
        session_name = self._get_session_name(username, next_index)
        
        # Create tmux session in detached mode
        cmd = f"tmux new-session -d -s {session_name}"
        _, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {'success': False, 'error': f'Failed to create session: {stderr}'}
        
        return {
            'success': True,
            'session_name': session_name,
            'message': f'Session {session_name} created'
        }
    
    def delete_session(self, username, session_name):
        # Verify session belongs to user
        prefix = f"cockpit_{username}_"
        if not session_name.startswith(prefix):
            return {'success': False, 'error': 'Invalid session name'}
        
        # Kill tmux session
        cmd = f"tmux kill-session -t {session_name}"
        _, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {'success': False, 'error': f'Failed to delete session: {stderr}'}
        
        return {'success': True, 'message': f'Session {session_name} deleted'}
    
    def get_attach_command(self, session_name):
        # Check if session exists
        cmd = f"tmux has-session -t {session_name} 2>/dev/null"
        _, _, code = self._run_command(cmd)
        
        if code != 0:
            return {'success': False, 'error': 'Session does not exist'}
        
        attach_cmd = f"tmux attach-session -t {session_name}"
        
        return {
            'success': True,
            'command': attach_cmd,
            'message': f'Use SSH to connect and run: {attach_cmd}'
        }


# Standalone test
if __name__ == '__main__':
    print("Testing TerminalManager...")
    tm = TerminalManager('test_settings.ini')
    
    username = 'testuser'
    
    # List sessions
    print("Current sessions:")
    print(tm.list_sessions(username))
    
    # Create session
    print("\nCreating session:")
    print(tm.create_session(username))
    
    # List again
    print("\nSessions after creation:")
    sessions = tm.list_sessions(username)
    print(sessions)
    
    # Get attach command
    if sessions['sessions']:
        print("\nAttach command:")
        print(tm.get_attach_command(sessions['sessions'][0]['name']))
        
        # Delete session
        print("\nDeleting session:")
        print(tm.delete_session(username, sessions['sessions'][0]['name']))
    
    # Clean up
    if os.path.exists('test_settings.ini'):
        os.remove('test_settings.ini')