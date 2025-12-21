# Server Cockpit - Setup Guide

A web-based Linux server management interface with Flask backend and vanilla JavaScript frontend.

## Features

- 🔐 Secure login (admin/non-admin users)
- 💾 Storage management with mount/unmount
- ⚡ System power control
- 📊 CPU/Memory/Temperature monitoring
- 🔍 Process monitoring
- 💻 Persistent terminal sessions (tmux)
- 🐳 Docker container management
- 🎮 Application control (systemd services)

## Installation

### 1. Install Dependencies

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Install system dependencies
sudo apt-get update
sudo apt-get install tmux lm-sensors

# Optional: Initialize sensors
sudo sensors-detect
```

### 2. Set Up Permissions

The app needs sudo privileges for certain operations. Add to sudoers:

```bash
sudo visudo
```

Add these lines (replace `yourusername`):

```
yourusername ALL=(ALL) NOPASSWD: /bin/mount
yourusername ALL=(ALL) NOPASSWD: /bin/umount
yourusername ALL=(ALL) NOPASSWD: /sbin/shutdown
yourusername ALL=(ALL) NOPASSWD: /sbin/reboot
yourusername ALL=(ALL) NOPASSWD: /bin/systemctl
yourusername ALL=(ALL) NOPASSWD: /usr/bin/chmod
```

### 3. Add User to Docker Group (Optional)

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 4. Project Structure

Create the following structure:

```
server-cockpit/
├── app.py
├── requirements.txt
├── modules/
│   ├── __init__.py
│   ├── auth.py
│   ├── storage.py
│   ├── system.py
│   ├── process.py
│   ├── terminal.py
│   ├── docker_mgr.py
│   └── app_control.py
├── templates/
│   └── index.html
├── static/
│   └── app.js
└── config/
    ├── users.csv (auto-created)
    ├── settings.ini (auto-created)
    ├── internal_uuids.txt (YOU MUST CREATE)
    └── apps.json (auto-created)
```

Create the `modules/__init__.py` file (empty is fine):

```bash
touch modules/__init__.py
```

### 5. Configure Internal UUIDs

List UUIDs of internal drives (to prevent accidental unmounting):

```bash
# Get UUIDs
lsblk -o NAME,UUID

# Create config file
nano config/internal_uuids.txt
```

Add one UUID per line:

```
12345678-90ab-cdef-1234-567890abcdef
abcdef12-3456-7890-abcd-ef1234567890
```

### 6. Configure Applications (Optional)

Edit `config/apps.json` to add your applications:

```json
{
  "apps": [
    {
      "name": "qbittorrent",
      "display_name": "qBittorrent",
      "start_command": "sudo systemctl start qbittorrent",
      "stop_command": "sudo systemctl stop qbittorrent",
      "status_command": "systemctl is-active qbittorrent",
      "type": "systemd"
    },
    {
      "name": "jellyfin",
      "display_name": "Jellyfin",
      "start_command": "docker start jellyfin",
      "stop_command": "docker stop jellyfin",
      "status_command": "docker inspect -f '{{.State.Status}}' jellyfin",
      "type": "docker"
    }
  ]
}
```

## Running the Application

### Development Mode

```bash
python3 app.py
```

Access at: `http://localhost:5000`

### Production Mode (with systemd)

Create `/etc/systemd/system/server-cockpit.service`:

```ini
[Unit]
Description=Server Cockpit
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/server-cockpit
ExecStart=/usr/bin/python3 /path/to/server-cockpit/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable server-cockpit
sudo systemctl start server-cockpit
```

### Production with Gunicorn

```bash
pip3 install gunicorn

# Run
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Default Credentials

- **Admin**: `admin` / `admin123`
- **User**: `user` / `user123`

⚠️ **Change these immediately!**

Edit `config/users.csv` after first run. Passwords are SHA-256 hashed.

## Configuration Files

### `config/users.csv`
```csv
username,password_hash,is_admin
admin,<sha256_hash>,true
user,<sha256_hash>,false
```

### `config/settings.ini`
```ini
[terminal]
max_sessions_per_user = 3
```

### `config/internal_uuids.txt`
```
uuid-of-internal-drive-1
uuid-of-internal-drive-2
```

### `config/apps.json`
See example above.

## Testing Individual Modules

Each module is independently testable:

```bash
# Test authentication
python3 modules/auth.py

# Test storage
python3 modules/storage.py

# Test system stats
python3 modules/system.py

# Test processes
python3 modules/process.py

# Test terminal sessions
python3 modules/terminal.py

# Test Docker
python3 modules/docker_mgr.py

# Test app control
python3 modules/app_control.py
```

## Features by Page

### Page 1: Storage
- View all disks and partitions
- Mount/unmount external drives
- See storage usage statistics
- Quick links to web services

### Page 2: Power
- Shutdown server
- Reboot server

### Page 3: System Stats
- CPU usage percentage
- CPU temperature
- Memory usage and availability

### Page 4: Processes
- Top 50 processes by memory
- Shows PID, name, user, memory, CPU

### Page 5: Terminal Sessions
- Create persistent tmux sessions
- Maximum 3 sessions per user (configurable)
- Sessions persist after logout
- Attach to sessions via SSH

### Page 6: Docker
- View all containers
- Start/stop/restart containers
- See container status and ports

### Page 7: App Control
- Start/stop systemd services
- Custom application management
- Status indicators

## Security Notes

1. **HTTPS**: Use a reverse proxy (nginx/Apache) with SSL in production
2. **Firewall**: Restrict access to trusted IPs
3. **Passwords**: Change default passwords immediately
4. **Sudo**: Limit sudo permissions to only required commands
5. **Sessions**: Flask sessions use a random secret key (regenerated on restart)

## Troubleshooting

### Permission Denied Errors
- Check sudoers configuration
- Ensure user is in docker group (for Docker features)
- Verify file permissions on config directory

### Temperature Not Showing
- Install lm-sensors: `sudo apt-get install lm-sensors`
- Run: `sudo sensors-detect`
- Check if thermal zones exist: `ls /sys/class/thermal/`

### Docker Not Working
- Ensure Docker is installed and running
- Add user to docker group: `sudo usermod -aG docker $USER`
- Restart session or run: `newgrp docker`

### Sessions Not Persisting
- Ensure tmux is installed: `sudo apt-get install tmux`
- Check tmux is running: `tmux list-sessions`

## Customization

### Change Important Links (Page 1)
Edit `templates/index.html`, find the links section:

```html
<div class="links-grid">
    <a href="http://localhost:2283" target="_blank" class="link-card">Immich</a>
    <!-- Add/modify links here -->
</div>
```

### Adjust Max Sessions
Edit `config/settings.ini`:

```ini
[terminal]
max_sessions_per_user = 5
```

### Add More Apps
Edit `config/apps.json` and add new entries.

## Future Migration to C

All modules are designed as standalone Python files with minimal dependencies, making it easy to rewrite them in C one by one:

1. Each module has a single class
2. Clear input/output interfaces
3. No complex Python-specific features
4. Can test each module independently

To migrate:
1. Rewrite module in C
2. Create Python bindings (ctypes/cffi)
3. Replace import in app.py
4. Test

## License

MIT License - Feel free to modify and use as needed.

## Support

For issues or questions, check:
1. System logs: `journalctl -u server-cockpit -f`
2. Flask logs in terminal
3. Browser console (F12) for frontend errors