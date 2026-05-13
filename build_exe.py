"""Build standalone .exe. Run: python build_exe.py"""
import subprocess, sys, os

def main():
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
    d = os.path.dirname(os.path.abspath(__file__))
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile', '--windowed', '--name', 'GCodeViewer',
        '--hidden-import', 'windnd',
        '--hidden-import', 'languages',
        '--hidden-import', 'themes',
        '--add-data', f'{os.path.join(d, "languages.py")};.',
        '--add-data', f'{os.path.join(d, "themes.py")};.',
        '--noconfirm',
        os.path.join(d, 'gcode_viewer.py')
    ]
    subprocess.run(cmd, check=True, cwd=d)
    print(f"\nDone! EXE: {os.path.join(d, 'dist', 'GCodeViewer.exe')}")

if __name__ == '__main__':
    main()
