import subprocess
import psutil
import os

class SystemManager:
    def _run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return '', 'Command timeout', 1
    
    def get_stats(self):
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1, percpu=False)
        
        # CPU temperature
        temp = self._get_cpu_temperature()
        
        # Memory usage
        mem = psutil.virtual_memory()
        
        return {
            'cpu_percent': cpu_percent,
            'cpu_temp': temp,
            'memory': {
                'total': self._bytes_to_gb(mem.total),
                'used': self._bytes_to_gb(mem.used),
                'available': self._bytes_to_gb(mem.available),
                'percent': mem.percent
            }
        }
    
    def _get_cpu_temperature(self):
        # Try different methods to get CPU temperature
        
        # Method 1: thermal zone (most common)
        thermal_files = [
            '/sys/class/thermal/thermal_zone0/temp',
            '/sys/class/thermal/thermal_zone1/temp'
        ]
        
        for thermal_file in thermal_files:
            if os.path.exists(thermal_file):
                try:
                    with open(thermal_file, 'r') as f:
                        temp = float(f.read().strip()) / 1000.0
                        if 0 < temp < 150:  # Sanity check
                            return round(temp, 1)
                except:
                    pass
        
        # Method 2: sensors command
        stdout, _, code = self._run_command("sensors -u 2>/dev/null | grep '_input' | head -1")
        if code == 0 and stdout:
            try:
                temp = float(stdout.split(':')[1].strip())
                if 0 < temp < 150:
                    return round(temp, 1)
            except:
                pass
        
        # Method 3: acpi
        stdout, _, code = self._run_command("acpi -t 2>/dev/null")
        if code == 0 and stdout:
            try:
                temp = float(stdout.split(',')[1].strip().split()[0])
                if 0 < temp < 150:
                    return round(temp, 1)
            except:
                pass
        
        return None
    
    def _bytes_to_gb(self, bytes_val):
        return round(bytes_val / (1024 ** 3), 2)
    
    def power_action(self, action):
        if action == 'shutdown':
            cmd = "sudo shutdown -h now"
        elif action == 'reboot':
            cmd = "sudo reboot"
        else:
            return {'success': False, 'error': 'Invalid action'}
        
        # Schedule the action
        subprocess.Popen(cmd, shell=True)
        return {'success': True, 'message': f'{action} initiated'}


# Standalone test
if __name__ == '__main__':
    print("Testing SystemManager...")
    sm = SystemManager()
    
    stats = sm.get_stats()
    print(f"CPU: {stats['cpu_percent']}%")
    print(f"Temperature: {stats['cpu_temp']}°C" if stats['cpu_temp'] else "Temperature: N/A")
    print(f"Memory: {stats['memory']['used']}GB / {stats['memory']['total']}GB ({stats['memory']['percent']}%)")