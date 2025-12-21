import subprocess
import os
import json

class AppController:
    def __init__(self):
        # User must configure app control commands in config/apps.json
        self.config_file = 'config/apps.json'
        self._ensure_config_exists()
    
    def _ensure_config_exists(self):
        if not os.path.exists(self.config_file):
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Create example config
            example_config = {
                "apps": [
                    {
                        "name": "qbittorrent",
                        "display_name": "qBittorrent",
                        "start_command": "sudo systemctl start qbittorrent",
                        "stop_command": "sudo systemctl stop qbittorrent",
                        "status_command": "systemctl is-active qbittorrent",
                        "type": "systemd"
                    }
                ]
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(example_config, f, indent=2)
    
    def _run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return '', 'Command timeout', 1
    
    def _load_apps(self):
        with open(self.config_file, 'r') as f:
            config = json.load(f)
        return config.get('apps', [])
    
    def list_apps(self):
        apps = self._load_apps()
        result = []
        
        for app in apps:
            status = self._get_app_status(app)
            result.append({
                'name': app['name'],
                'display_name': app.get('display_name', app['name']),
                'status': status,
                'type': app.get('type', 'unknown')
            })
        
        return {'apps': result}
    
    def _get_app_status(self, app):
        if 'status_command' not in app:
            return 'unknown'
        
        stdout, _, code = self._run_command(app['status_command'])
        
        if app.get('type') == 'systemd':
            return 'running' if stdout == 'active' else 'stopped'
        elif app.get('type') == 'docker':
            return 'running' if 'Up' in stdout else 'stopped'
        else:
            return 'running' if code == 0 else 'stopped'
    
    def app_action(self, app_name, action):
        apps = self._load_apps()
        app = next((a for a in apps if a['name'] == app_name), None)
        
        if not app:
            return {'success': False, 'error': f'App {app_name} not found'}
        
        if action == 'start':
            cmd = app.get('start_command')
        elif action == 'stop':
            cmd = app.get('stop_command')
        else:
            return {'success': False, 'error': 'Invalid action'}
        
        if not cmd:
            return {'success': False, 'error': f'No {action} command configured for {app_name}'}
        
        _, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {'success': False, 'error': f'Action failed: {stderr}'}
        
        return {'success': True, 'message': f'{app_name} {action}ed successfully'}


# Standalone test
if __name__ == '__main__':
    print("Testing AppController...")
    ac = AppController()
    
    data = ac.list_apps()
    print(f"Configured apps:")
    for app in data['apps']:
        print(f"  - {app['display_name']}: {app['status']}")