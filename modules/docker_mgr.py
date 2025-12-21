import subprocess
import json

class DockerManager:
    def _run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return '', 'Command timeout', 1
    
    def list_containers(self):
        cmd = "docker ps -a --format '{{json .}}'"
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            if 'permission denied' in stderr.lower():
                return {'error': 'Permission denied. User needs to be in docker group.'}
            return {'error': f'Docker command failed: {stderr}'}
        
        if not stdout:
            return {'containers': []}
        
        containers = []
        for line in stdout.split('\n'):
            if line.strip():
                try:
                    container = json.loads(line)
                    containers.append({
                        'id': container.get('ID', ''),
                        'name': container.get('Names', ''),
                        'image': container.get('Image', ''),
                        'status': container.get('Status', ''),
                        'state': container.get('State', ''),
                        'ports': container.get('Ports', '')
                    })
                except json.JSONDecodeError:
                    pass
        
        return {'containers': containers}
    
    def container_action(self, container_id, action):
        valid_actions = ['start', 'stop', 'restart', 'pause', 'unpause']
        
        if action not in valid_actions:
            return {'success': False, 'error': f'Invalid action. Valid: {", ".join(valid_actions)}'}
        
        cmd = f"docker {action} {container_id}"
        _, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {'success': False, 'error': f'Action failed: {stderr}'}
        
        return {'success': True, 'message': f'Container {action}ed successfully'}


# Standalone test
if __name__ == '__main__':
    print("Testing DockerManager...")
    dm = DockerManager()
    
    data = dm.list_containers()
    if 'error' in data:
        print(f"Error: {data['error']}")
    else:
        print(f"Found {len(data['containers'])} containers:")
        for c in data['containers']:
            print(f"  - {c['name']} ({c['state']}): {c['image']}")