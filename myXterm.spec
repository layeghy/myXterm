# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('secret.key', '.'),
        ('sessions.json', '.'),
        ('settings.json', '.'),
        ('ui/*.qss', 'ui'),
        ('resources/*', 'resources'),
        ('.venv/Lib/site-packages/winpty/*.dll', 'winpty'),
        ('.venv/Lib/site-packages/winpty/*.exe', 'winpty'),
        ('.venv/Lib/site-packages/winpty/*.dll', '.'),
        ('.venv/Lib/site-packages/winpty/*.exe', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineCore',
        'paramiko',
        'pyte',
        'pywinpty',
        'winpty',
        'cryptography.fernet',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='myXterm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    console=False,
    icon=['resources\\icon.ico'] if os.path.exists('resources\\icon.ico') else None,
)
