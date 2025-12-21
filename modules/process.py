import psutil

class ProcessManager:
    def get_processes(self):
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'username']):
            try:
                pinfo = proc.info
                mem_mb = pinfo['memory_info'].rss / (1024 * 1024)
                
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'user': pinfo['username'],
                    'memory_mb': round(mem_mb, 1),
                    'cpu_percent': round(pinfo['cpu_percent'] or 0, 1)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by memory usage
        processes.sort(key=lambda x: x['memory_mb'], reverse=True)
        
        # Return top 50 processes
        return {'processes': processes[:50]}


# Standalone test
if __name__ == '__main__':
    print("Testing ProcessManager...")
    pm = ProcessManager()
    
    data = pm.get_processes()
    print(f"Top 10 processes by memory:")
    for i, proc in enumerate(data['processes'][:10], 1):
        print(f"{i}. {proc['name']}: {proc['memory_mb']}MB (CPU: {proc['cpu_percent']}%)")