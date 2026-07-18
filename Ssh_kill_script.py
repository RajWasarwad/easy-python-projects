import time
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("your_remote_ip", username="user", password="password")

# Store the script name in a variable to avoid typos
SCRIPT_NAME = "my_multi_threaded_script.py"

# get_pty=True is required for the Ctrl+C characters to work
stdin, stdout, stderr = ssh.exec_command(f"python3 {SCRIPT_NAME}", get_pty=True)

try:
    while True:
        if stdout.channel.recv_ready():
            line = stdout.readline()
            print(f"Remote: {line.strip()}")
            
            # Condition check
            if "Target condition met" in line:
                print("\n[1/3] Condition hit! Sending first Ctrl+C...")
                stdin.write("\x03")
                stdin.flush()
                time.sleep(0.3)  # Wait for threads to respond
                
                print("[2/3] Sending second Ctrl+C...")
                stdin.write("\x03")
                stdin.flush()
                time.sleep(1.5)  # Give the script a moment to gracefully exit
                
                # Check if the process is still running
                if not stdout.channel.exit_status_ready():
                    print("[3/3] Script still active. Executing forceful pkill...")
                    
                    # -9 sends SIGKILL, which terminates the process instantly
                    # -f matches against the full command line argument (the script name)
                    ssh.exec_command(f"pkill -9 -f {SCRIPT_NAME}")
                else:
                    print("Script exited gracefully via Ctrl+C.")
                break

        time.sleep(0.1)
        if stdout.channel.exit_status_ready():
            print("Script finished naturally.")
            break

finally:
    ssh.close()
