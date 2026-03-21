import paramiko

def check_jetson(host, user, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password)
    
    # 1. Check RAM usage precisely
    print("--- MEMORY (MB) ---")
    stdin, stdout, stderr = ssh.exec_command("free -m")
    print(stdout.read().decode())
    
    # 2. Check Load
    print("--- LOAD ---")
    stdin, stdout, stderr = ssh.exec_command("uptime")
    print(stdout.read().decode())

    # 3. Check Docker (Frigate)
    print("--- DOCKER STATS ---")
    stdin, stdout, stderr = ssh.exec_command("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'")
    print(stdout.read().decode())
    
    # 4. Check NV Tegrastats
    print("--- TEGRA STATS (GPU/TEMP) ---")
    stdin, stdout, stderr = ssh.exec_command("timeout 1s tegrastats | head -n 1")
    print(stdout.read().decode())

    ssh.close()

if __name__ == "__main__":
    check_jetson("192.168.1.157", "nilsgollub", "JhiswenP3003!")
