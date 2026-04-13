import os
import sys
import subprocess
import shutil
from pathlib import Path

def convert_logo():
    try:
        from PIL import Image
        if os.path.exists("logo.png"):
            print("Converting logo.png to logo.ico...")
            img = Image.open("logo.png")
            img.save("logo.ico", format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
            return True
    except ImportError:
        print("Pillow not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow"])
        return convert_logo()
    except Exception as e:
        print(f"Logo conversion failed: {e}")
    return False

def cleanup_build():
    print("Cleaning up old build artifacts...")
    # Remove old spec, build, and dist folders to ensure a clean slate
    dirs_to_remove = [Path("build"), Path("dist")]
    for d in dirs_to_remove:
        if d.exists():
            try:
                shutil.rmtree(d, ignore_errors=True)
                print(f"Removed {d}")
            except Exception as e:
                print(f"Warning: Could not remove {d}: {e}")
    
    spec_file = Path("FlatSync.spec")
    if spec_file.exists():
        spec_file.unlink()

def run_build():
    print("Starting Robust FlatSync EXE Build Process...")
    
    # 1. Install/Update PyInstaller within current environment
    print("Ensuring PyInstaller is installed in the active environment...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # 2. Cleanup old attempts
    cleanup_build()
    
    # 3. Handle Icon
    icon_success = convert_logo()
    
    # 4. Comprehensive PyInstaller Command
    # --collect-all forces PyInstaller to grab everything from a package
    # We remove 'routes' from add-data so it's compiled as modules
    
    print("\nExecuting PyInstaller (this may take 1-2 minutes)...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--clean",
        "--name", "FlatSync",
        "--add-data", "templates;templates",
        "--add-data", "static;static",
        "--collect-all", "flask",
        "--collect-all", "flask_sqlalchemy",
        "--collect-all", "flask_migrate",
        "--collect-all", "flask_login",
        "--collect-all", "sqlalchemy",
        "--collect-all", "webview",
        "--collect-all", "reportlab",
        "--collect-all", "xhtml2pdf",
        "--collect-all", "num2words",
        "app.py"
    ]
    
    if icon_success:
        cmd.extend(["--icon", "logo.ico"])
        
    try:
        subprocess.run(cmd, check=True)
        print("\n" + "="*40)
        print("BUILD SUCCESSFUL!")
        print("Your application is now bundled at:")
        print(os.path.abspath("dist/FlatSync.exe"))
        print("\nPlease test this EXE to verify all modules are included.")
        print("="*40)
    except subprocess.CalledProcessError:
        print("\nBuild failed. Please check the logs above for missing libraries.")

if __name__ == "__main__":
    run_build()
