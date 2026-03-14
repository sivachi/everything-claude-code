
import subprocess
import time

def run_osascript(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

def get_window_title():
    script = '''
    tell application "System Events"
        tell process "Amazon Kindle"
            if exists front window then
                return name of front window
            else
                return "No Window"
            end if
        end tell
    end tell
    '''
    return run_osascript(script).stdout.strip()

def main():
    print("Activating Kindle...")
    run_osascript('tell application "Amazon Kindle" to activate')
    time.sleep(1)

    print("State 1 (Library?): Title =", get_window_title())
    
    print("Attempting to open book (Press Enter)...")
    run_osascript('tell application "System Events" to key code 36') # Enter
    time.sleep(3)
    
    title_book = get_window_title()
    print("State 2 (Book Open?): Title =", title_book)
    
    print("Attempting to close book (Cmd+L)...")
    # Using Cmd+L (Library) is safer than Cmd+W (Close Window) which might close the app
    run_osascript('tell application "System Events" to keystroke "l" using command down')
    time.sleep(3)
    
    title_library = get_window_title()
    print("State 3 (Back to Library?): Title =", title_library)

if __name__ == "__main__":
    main()
