import os


def get_server_status() -> dict:
    """Get server CPU, RAM, Disk usage."""
    status = {}
    try:
        import psutil
        status['cpu'] = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        status['ram_total'] = round(mem.total / (1024**3), 1)
        status['ram_used'] = round(mem.used / (1024**3), 1)
        status['ram_percent'] = mem.percent
        disk = psutil.disk_usage('/')
        status['disk_total'] = round(disk.total / (1024**3), 1)
        status['disk_used'] = round(disk.used / (1024**3), 1)
        status['disk_percent'] = round(disk.percent, 1)
    except ImportError:
        # Fallback without psutil
        try:
            import subprocess
            result = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                status['ram_total'] = round(int(parts[1]) / 1024, 1)
                status['ram_used'] = round(int(parts[2]) / 1024, 1)
                status['ram_percent'] = round(int(parts[2]) / int(parts[1]) * 100, 1)
        except Exception:
            pass
        try:
            import subprocess
            result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                status['disk_total'] = parts[1]
                status['disk_used'] = parts[2]
                status['disk_percent'] = float(parts[4].replace('%', ''))
        except Exception:
            pass
    return status


def format_server_status(status: dict) -> str:
    lines = ["🖥️ <b>وضعیت سرور</b>\n"]
    if 'cpu' in status:
        bar = _bar(status['cpu'])
        lines.append(f"💻 CPU: {bar} {status['cpu']}%")
    if 'ram_percent' in status:
        bar = _bar(status['ram_percent'])
        lines.append(f"🧠 RAM: {bar} {status['ram_percent']}% ({status.get('ram_used', '?')} / {status.get('ram_total', '?')} GB)")
    if 'disk_percent' in status:
        bar = _bar(status['disk_percent'])
        lines.append(f"💾 Disk: {bar} {status['disk_percent']}% ({status.get('disk_used', '?')} / {status.get('disk_total', '?')})")
    return "\n".join(lines)


def _bar(percent: float) -> str:
    filled = int(percent / 10)
    return "█" * filled + "░" * (10 - filled)
