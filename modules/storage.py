import subprocess
import json
import os

class StorageManager:
    def __init__(self):
        # User must configure internal UUIDs in config/internal_uuids.txt
        self.internal_config_file = 'config/internal_uuids.txt'
        self.mount_base = '/mnt/drive'
        self.mount_base_private = '/mnt/pvt_drive'
        self.mount_base_public = '/mnt/shared'
    
    def _load_internal_config(self):
        """
        Load internal UUIDs with show flag
        Format: UUID,show_flag
        Example:
        12345678-90ab-cdef-1234-567890abcdef,true
        abcdef12-3456-7890-abcd-ef1234567890,false
        """
        config = {}
        if not os.path.exists(self.internal_config_file):
            return config
        
        with open(self.internal_config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) == 2:
                        uuid = parts[0].strip()
                        show_flag = parts[1].strip().lower() == 'true'
                        config[uuid] = show_flag
        return config
    
    def _run_command(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return '', 'Command timeout', 1
    
    def _parse_size_mb(self, size_str):
        """Convert size string to MB for comparison"""
        size_str = size_str.upper().replace(' ', '')
        
        if 'T' in size_str:
            return float(size_str.replace('T', '')) * 1024 * 1024
        elif 'G' in size_str:
            return float(size_str.replace('G', '')) * 1024
        elif 'M' in size_str:
            return float(size_str.replace('M', ''))
        elif 'K' in size_str:
            return float(size_str.replace('K', '')) / 1024
        else:
            # Assume bytes
            try:
                return float(size_str) / (1024 * 1024)
            except:
                return 0
    
    def get_storage_info(self):
        # Get all block devices
        cmd = "lsblk -J -o NAME,SIZE,MOUNTPOINT,FSTYPE,UUID,TYPE"
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            raise Exception(f"Failed to get storage info: {stderr}")
        
        devices_data = json.loads(stdout)
        internal_config = self._load_internal_config()
        
        # Get disk usage for mounted partitions
        df_cmd = "df -h --output=source,size,used,avail,pcent,target"
        df_out, _, _ = self._run_command(df_cmd)
        
        df_map = {}
        for line in df_out.split('\n')[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 6:
                source = parts[0]
                df_map[source] = {
                    'size': parts[1],
                    'used': parts[2],
                    'available': parts[3],
                    'percent': parts[4],
                    'mountpoint': parts[5]
                }
        
        result = []
        for device in devices_data.get('blockdevices', []):
            if device['type'] == 'disk':
                disk_info = self._process_disk(device, df_map, internal_config)
                if disk_info:
                    result.append(disk_info)
        
        return {'disks': result}
    
    def _process_disk(self, device, df_map, internal_config):
        disk = {
            'name': device['name'],
            'size': device['size'],
            'partitions': []
        }
        
        for child in device.get('children', []):
            if child['type'] == 'part':
                uuid = child.get('uuid', '')
                device_path = f"/dev/{child['name']}"
                
                # Check size - skip if less than 100MB
                size_mb = self._parse_size_mb(child['size'])
                if size_mb < 100:
                    continue
                
                # Check if internal and should be shown
                is_internal = uuid in internal_config
                if is_internal:
                    show_internal = internal_config[uuid]
                    if not show_internal:
                        continue  # Skip this partition
                
                usage = df_map.get(device_path, {})
                
                partition = {
                    'name': child['name'],
                    'device': device_path,
                    'size': child['size'],
                    'mountpoint': child.get('mountpoint', ''),
                    'fstype': child.get('fstype', ''),
                    'uuid': uuid,
                    'is_internal': is_internal,
                    'is_mounted': bool(child.get('mountpoint')),
                    'usage': usage
                }
                disk['partitions'].append(partition)
        
        return disk if disk['partitions'] else None
    
    def mount(self, device, mount_type='normal'):
        # Check if already mounted
        check_cmd = f"mount | grep {device}"
        stdout, _, _ = self._run_command(check_cmd)
        if stdout:
            return {'success': False, 'error': f'{device} is already mounted'}
        
        # Get device info
        cmd = f"lsblk -J -o NAME,UUID {device}"
        stdout, stderr, code = self._run_command(cmd)
        if code != 0:
            return {'success': False, 'error': f'Device not found: {stderr}'}
        
        data = json.loads(stdout)
        uuid = data['blockdevices'][0].get('uuid', '')
        device_name = device.split('/')[-1]
        
        # Determine mount point based on type
        if mount_type == 'public':
            mount_point = f"{self.mount_base_public}/{device_name}"
        elif mount_type == 'private':
            mount_point = f"{self.mount_base_private}/{device_name}"
        else:  # normal
            mount_point = f"{self.mount_base}/{device_name}"
        
        os.makedirs(mount_point, exist_ok=True)
        
        # Mount
        mount_cmd = f"sudo mount {device} {mount_point}"
        _, stderr, code = self._run_command(mount_cmd)
        
        if code != 0:
            return {'success': False, 'error': f'Mount failed: {stderr}'}
        
        # Set permissions for public mounts
        if mount_type == 'public':
            self._run_command(f"sudo chmod 777 {mount_point}")
        
        return {'success': True, 'mountpoint': mount_point}
    
    def unmount(self, device):
        # Get mountpoint
        check_cmd = f"mount | grep {device}"
        stdout, _, _ = self._run_command(check_cmd)
        if not stdout:
            return {'success': False, 'error': f'{device} is not mounted'}
        
        # Extract mountpoint
        mountpoint = stdout.split()[2]
        
        # Unmount
        unmount_cmd = f"sudo umount {device}"
        _, stderr, code = self._run_command(unmount_cmd)
        
        if code != 0:
            return {'success': False, 'error': f'Unmount failed: {stderr}'}
        
        # Clean up: Remove the mount directory if it's in our managed paths
        managed_paths = [self.mount_base, self.mount_base_private, self.mount_base_public]
        should_cleanup = any(mountpoint.startswith(path) for path in managed_paths)
        
        if should_cleanup:
            try:
                # Check if directory is empty before removing
                if os.path.exists(mountpoint) and os.path.isdir(mountpoint):
                    # Try to remove the directory
                    if not os.listdir(mountpoint):  # Directory is empty
                        os.rmdir(mountpoint)
                    else:
                        # Directory not empty, try with sudo
                        self._run_command(f"sudo rmdir {mountpoint}")
            except Exception as e:
                # Log but don't fail the unmount operation
                print(f"Warning: Could not remove mount directory {mountpoint}: {e}")
        
        return {'success': True, 'message': f'Unmounted and cleaned up {mountpoint}'}


# Standalone test
if __name__ == '__main__':
    print("Testing StorageManager...")
    sm = StorageManager()
    
    try:
        info = sm.get_storage_info()
        print(json.dumps(info, indent=2))
    except Exception as e:
        print(f"Error: {e}")