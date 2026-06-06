# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['video_encoder.py'],
    pathex=['.'],
    binaries=[
        ('ffmpeg/ffmpeg.exe', '.'),
        ('ffmpeg/ffprobe.exe', '.'),
    ],
    datas=collect_data_files('customtkinter') + collect_data_files('tkinterdnd2'),
    hiddenimports=[
        'customtkinter',
        'tkinterdnd2',
        'PIL',
        'PIL._tkinter_finder',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SimpleEncoder',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=None,
)
