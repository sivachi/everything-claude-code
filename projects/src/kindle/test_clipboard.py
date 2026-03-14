
import subprocess
import time

def run_osascript(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

def get_clipboard():
    return subprocess.check_output(['pbpaste']).decode('utf-8')

def main():
    print("Activating Kindle...")
    run_osascript('tell application "Amazon Kindle" to activate')
    time.sleep(1)

    print("Sending Cmd+C...")
    run_osascript('tell application "System Events" to keystroke "c" using command down')
    time.sleep(1)
    
    content = get_clipboard()
    print(f"Clipboard Content: '{content}'")

if __name__ == "__main__":
    main()
