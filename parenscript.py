# parent_script.py
import subprocess
import json

def run_child_script():
    result = subprocess.run(
        ["python", "shelly-plug-data.py"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

if __name__ == "__main__":
    data = run_child_script()
    print("Data from child script:", data['result'])