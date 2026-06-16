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
    # tkinterdnd2는 더 이상 사용하지 않으므로 제외 (DnD 바이너리는 오탐 유발 원인)
    datas=collect_data_files('customtkinter'),
    hiddenimports=[
        'customtkinter',
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
    upx=False,          # ★ UPX 비활성화: 백신 오탐(멀웨어 패킹 의심)의 주요 원인
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='SimpleEncoder.ico',
)
