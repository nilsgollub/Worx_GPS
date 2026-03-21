import paramiko
import sys

def check_jetson(host, user, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password)
        
        commands = {
            "System Stats": "uptime; free -m; nproc; df -h /",
            "Top Processes": "top -b -n 1 | head -n 30",
            "Tegrastats (GPU/System)": "head -n 2 /var/log/syslog | grep -v 'tegrastats' | tail -n 0; timeout 2s tegrastats | head -n 1",
            "Docker Stats (Frigate)": "docker stats --no-stream",
            "Python/Envs": "python3 --version; pip3 --version; ls -la /usr/local/bin/python*"
        }
        
        for name, cmd in commands.items():
            print(f"\n{'='*20} {name} {'='*20}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            print(stdout.read().decode())
            err = stderr.read().decode()
            if err:
                print(f"Error ({name}): {err}")
                
        ssh.close()
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    check_jetson("192.168.1.157", "nilsgollub", "JhiswenP3003!")
