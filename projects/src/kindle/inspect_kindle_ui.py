
import subprocess
import time

def run_osascript(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

def inspect_ui():
    print("Activating Kindle...")
    run_osascript('tell application "Amazon Kindle" to activate')
    time.sleep(1)
    
    print("Sending Cmd+L to go to Library...")
    run_osascript('''
        tell application "System Events" to keystroke "l" using command down
    ''')
    time.sleep(2)

    print("Inspecting UI elements of front window...")
    script = '''
    tell application "System Events"
        tell process "Amazon Kindle"
            if exists front window then
                set w to front window
                set ui_summary to ""
                
                -- Function to get basic info of an element
                try
                    set ui_elems to UI elements of w
                    repeat with elem in ui_elems
                        set role_name to role of elem
                        set role_desc to role description of elem
                        set elem_name to name of elem
                        set ui_summary to ui_summary & "Role: " & role_name & ", Desc: " & role_desc & ", Name: " & elem_name & "\n"
                        
                        -- Try to go one level deeper if it is a group/scroll area
                        if role_name is "AXScrollArea" or role_name is "AXGroup" then
                            try
                                set sub_elems to UI elements of elem
                                repeat with sub in sub_elems
                                    set sub_role to role of sub
                                    set sub_name to name of sub
                                    set ui_summary to ui_summary & "    SubRole: " & sub_role & ", Name: " & sub_name & "\n"
                                end repeat
                            end try
                        end if
                    end repeat
                on error errMsg
                    set ui_summary to "Error: " & errMsg
                end try
                
                return ui_summary
            else
                return "No front window found"
            end if
        end tell
    end tell
    '''
    res = run_osascript(script)
    print("--- UI Dump ---")
    print(res.stdout)
    if res.stderr:
        print("--- Error ---")
        print(res.stderr)

if __name__ == "__main__":
    inspect_ui()
