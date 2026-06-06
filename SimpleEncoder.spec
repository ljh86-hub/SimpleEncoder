# -*- mode: python ; coding: utf-8 -*-
# SimpleEncoder.spec
# FFmpeg (ffmpeg.exe + ffprobe.exe) 를 함께 패키징합니다.
# ffmpeg 폴더가 이 spec 파일과 같은 위치에 있어야 합니다.

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ffmpeg 바이너리 경로 (build.bat 이 자동으로 다운로드해서 여기에 놓음)
ffmpeg_binaries = [
    ('ffmpeg\\ffmpeg.exe',  'ffmpeg'),
    ('ffmpeg\\ffprobe.exe', 'ffmpeg'),
]

a = Analysis(
    ['video_encoder.py'],
    pathex=['.'],
    binaries=ffmpeg_binaries,
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
    name='SimpleEncoder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 콘솔창 숨김 (GUI 전용)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 아이콘 파일 있으면 'icon.ico' 로 교체
)
