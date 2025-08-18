import subprocess
import os
import time
import requests

# Path to Python inside venv
venv_python = os.path.join("venv", "Scripts", "python.exe")

# Step 1: Start ngrok silently
print("Starting ngrok...")
ngrok_process = subprocess.Popen(
    ["ngrok", "http", "5050"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# Step 2: Wait for ngrok to start and fetch URL
time.sleep(3)  # wait for ngrok to initialize
try:
    tunnels = requests.get("http://127.0.0.1:4040/api/tunnels").json()
    public_url = tunnels['tunnels'][0]['public_url']
    print(f"Ngrok public URL: {public_url}")

    # Save URL to file so make_call.py can read it
    with open("ngrok_url.txt", "w") as f:
        f.write(public_url)

except Exception as e:
    ngrok_process.kill()
    raise SystemExit(f"Error fetching ngrok URL: {e}")

# Step 3: Run main.py with venv
subprocess.run([venv_python, "main.py"])
