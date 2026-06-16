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

# ── onedir 빌드: EXE(실행기) + COLLECT(폴더로 묶기) ──
# onefile과 달리 매 실행마다 압축 해제가 없어 시작 속도가 빠름
exe = EXE(
    pyz,
    a.scripts,
    [],                 # ← onefile과 달리 binaries/datas를 여기 넣지 않음
    exclude_binaries=True,
    name='SimpleEncoder',
    debug=False,
    strip=False,
    upx=False,          # 백신 오탐 완화
    console=False,
    icon='SimpleEncoder.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SimpleEncoder',   # → dist/SimpleEncoder/ 폴더 생성
)
