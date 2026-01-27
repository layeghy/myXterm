import os
import shutil
import subprocess
import time

def build_installer():
    print("Starting build process...")
    
    # Files
    sessions_file = "sessions.json"
    backup_file = "sessions.json.bak"
    pyinstaller_path = os.path.join("venv", "Scripts", "pyinstaller.exe")
    
    # Icon handling
    icon_png = os.path.join("build", "resources", "icon.png")
    icon_ico = os.path.join("build", "resources", "icon.ico")
    
    if os.path.exists(icon_png):
        print(f"Converting {icon_png} to .ico...")
        try:
            from PIL import Image
            img = Image.open(icon_png)
            img.save(icon_ico, format='ICO', sizes=[(256, 256)])
            print(f"Created {icon_ico}")
        except Exception as e:
            print(f"Failed to convert icon: {e}")
            if os.path.exists(icon_ico):
                 print(f"Using existing {icon_ico}")
            else:
                icon_ico = "NONE"
    elif os.path.exists(icon_ico):
        print(f"Using existing {icon_ico}")
    else:
        print(f"Warning: Icon file not found at {icon_png} or {icon_ico}")
        icon_ico = "NONE"

    # 1. Backup existing sessions
    has_sessions = False
    if os.path.exists(sessions_file):
        print(f"Backing up {sessions_file} to {backup_file}...")
        shutil.move(sessions_file, backup_file)
        has_sessions = True
    
    try:
        # 2. Create empty sessions file
        print("Creating empty sessions.json for build...")
        with open(sessions_file, "w") as f:
            f.write("[]")
            
        # 3. Build Main Application
        print("Building Main Application (myXterm.exe)...")
        # Use simple command to build from spec file
        # The spec file handles all data, hidden imports, and icon settings
        cmd_app = [
            pyinstaller_path,
            "--clean",
            "myXterm.spec" 
        ]
        subprocess.check_call(cmd_app)
        
        # Verify main app exists
        main_exe = os.path.join("dist", "myXterm.exe")
        if not os.path.exists(main_exe):
            raise FileNotFoundError("Main executable build failed")

        # 4. Build Installer
        print("\nBuilding Installer (Setup_myXterm.exe)...")
        # The installer needs the main executable as a data file
        # Format: source;dest
        # We want myXterm.exe to be available at runtime for the installer to extract
        cmd_installer = [
            pyinstaller_path,
            "--noconsole",
            "--name", "Setup_myXterm",
            "--add-data", f"{main_exe};.",  # Include the built exe
            "--clean",
            "--onefile",
            "--uac-admin", # Request admin privileges for installation
            f"--icon={icon_ico}",
            "installer.py"
        ]
        subprocess.check_call(cmd_installer)
        
        print("\nBuild successful!")
        print(f"Main App: {main_exe}")
        print(f"Installer: dist/Setup_myXterm.exe")
        
    except subprocess.CalledProcessError as e:
        print(f"\nError during build: {e}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        # 5. Cleanup and Restore
        print("Cleaning up...")
        if os.path.exists(sessions_file):
            os.remove(sessions_file)
            
        if has_sessions:
            print(f"Restoring {sessions_file}...")
            shutil.move(backup_file, sessions_file)
            
    print("Done.")

if __name__ == "__main__":
    build_installer()
