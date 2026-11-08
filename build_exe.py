"""Build standalone .exe. Run: python build_exe.py"""
import subprocess, sys, os

def main():
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
    d = os.path.dirname(os.path.abspath(__file__))

    # Regenerate icon if missing
    icon = os.path.join(d, 'icon.ico')
    if not os.path.exists(icon):
        subprocess.run([sys.executable, os.path.join(d, 'generate_icon.py')], check=True)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile', '--windowed', '--name', 'GCodeViewer',
        '--icon', icon,
        '--hidden-import', 'windnd',
        '--hidden-import', 'languages',
        '--hidden-import', 'themes',
        '--exclude-module', 'numpy',
        '--exclude-module', 'setuptools',
        '--exclude-module', 'pip',
        '--add-data', f'{os.path.join(d, "languages.py")};.',
        '--add-data', f'{os.path.join(d, "themes.py")};.',
        '--add-data', f'{icon};.',
        '--noconfirm',
        os.path.join(d, 'gcode_viewer.py')
    ]
    subprocess.run(cmd, check=True, cwd=d)
    print(f"\nDone! EXE: {os.path.join(d, 'dist', 'GCodeViewer.exe')}")

if __name__ == '__main__':
    main()
