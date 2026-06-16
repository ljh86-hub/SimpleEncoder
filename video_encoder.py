"""
SimpleEncoder - FFmpeg 기반 동영상 인코더
"""

from tkinterdnd2 import TkinterDnD, DND_FILES
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import re
import json
import sys
import tempfile
import traceback
from pathlib import Path

# ── FFmpeg 경로 ──────────────────────────────────────────────────
def _ffmpeg_bin(name):
    base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, name)
    return p if os.path.exists(p) else name

FFMPEG  = _ffmpeg_bin('ffmpeg.exe')
FFPROBE = _ffmpeg_bin('ffprobe.exe')

# subprocess 콘솔 숨김 옵션
SI = subprocess.STARTUPINFO()
SI.dwFlags |= subprocess.STARTF_USESHOWWINDOW
SI.wShowWindow = 0
HIDE_KWARGS = {"startupinfo": SI, "creationflags": subprocess.CREATE_NO_WINDOW}

# ── 테마 ─────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── 프리셋 ───────────────────────────────────────────────────────
PRESETS = {
    "고화질 (H.265 | 저용량 권장)": {
        "vcodec": "libx265", "crf": "22", "preset": "medium",
        "acodec": "aac", "ab": "192k", "ext": ".mp4",
        "desc": "파일 크기 down  화질 up  (H.264 대비 ~40% 절감)"
    },
    "일반 (H.264 | 호환성 최고)": {
        "vcodec": "libx264", "crf": "23", "preset": "medium",
        "acodec": "aac", "ab": "192k", "ext": ".mp4",
        "desc": "모든 기기 플레이어 호환 / 무난한 균형"
    },
    "웹 최적화 (H.264 FastStart)": {
        "vcodec": "libx264", "crf": "24", "preset": "fast",
        "acodec": "aac", "ab": "128k", "ext": ".mp4",
        "desc": "웹 스트리밍 최적화 / 빠른 인코딩"
    },
    "초저용량 (H.265 | SNS용)": {
        "vcodec": "libx265", "crf": "28", "preset": "medium",
        "acodec": "aac", "ab": "128k", "ext": ".mp4",
        "desc": "SNS 업로드 / 용량 최소화"
    },
    "무손실 (FFV1 | 편집용)": {
        "vcodec": "ffv1", "crf": None, "preset": None,
        "acodec": "flac", "ab": None, "ext": ".mkv",
        "desc": "화질 손실 없음 / 파일 크기 매우 큼"
    },
}

RESOLUTIONS = ["원본 유지", "3840x2160 (4K)", "2560x1440 (2K)", "1920x1080 (FHD)", "1280x720 (HD)", "854x480 (SD)"]
FRAMERATES  = ["원본 유지", "60", "30", "25", "24"]
VIDEO_EXTS  = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts", ".m2ts"}


# ── 유틸 ─────────────────────────────────────────────────────────
def get_video_info(path):
    try:
        out = subprocess.check_output(
            [FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
            stderr=subprocess.DEVNULL, **HIDE_KWARGS)
        data = json.loads(out)
        info = {"size_mb": int(data.get("format", {}).get("size", 0)) / 1024 / 1024}
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                info["width"]  = s.get("width", "?")
                info["height"] = s.get("height", "?")
        return info
    except Exception:
        return {}


def fmt_size(mb):
    """MB 숫자를 보기 좋은 단위로"""
    if mb >= 1024:
        return f"{mb/1024:.2f} GB"
    return f"{mb:.1f} MB"


def parse_drop_paths(data):
    paths, data = [], data.strip()
    while data:
        if data.startswith('{'):
            end = data.index('}')
            paths.append(data[1:end])
            data = data[end+1:].strip()
        else:
            parts = data.split(' ', 1)
            paths.append(parts[0])
            data = parts[1].strip() if len(parts) > 1 else ''
    return paths


def collect_videos_from_path(p):
    """파일 경로 or 폴더 경로에서 비디오 파일들 수집"""
    if os.path.isfile(p) and Path(p).suffix.lower() in VIDEO_EXTS:
        return [p]
    if os.path.isdir(p):
        return [str(f) for f in sorted(Path(p).rglob("*")) if f.suffix.lower() in VIDEO_EXTS]
    return []


# ── 파일 행 ──────────────────────────────────────────────────────
class FileRow(ctk.CTkFrame):
    def __init__(self, master, path, on_remove, on_drag_start, on_drag_motion, on_drag_end, **kw):
        super().__init__(master, fg_color=("#2b2b2b", "#1e1e1e"), corner_radius=8, **kw)
        self.path = path
        self.grid_columnconfigure(2, weight=1)

        # 드래그 핸들
        handle = ctk.CTkLabel(self, text="=", font=("Consolas", 18),
                              text_color="#666", cursor="fleur", width=24)
        handle.grid(row=0, column=0, padx=(6, 0), pady=6)
        handle.bind("<ButtonPress-1>",   lambda e: on_drag_start(e, self))
        handle.bind("<B1-Motion>",       lambda e: on_drag_motion(e, self))
        handle.bind("<ButtonRelease-1>", lambda e: on_drag_end(e, self))

        # 체크박스
        self.var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="", variable=self.var, width=28).grid(
            row=0, column=1, padx=(4, 0), pady=6)

        # 파일명
        ctk.CTkLabel(self, text=os.path.basename(path), anchor="w",
                     font=("Consolas", 12)).grid(row=0, column=2, sticky="ew", padx=8)

        # 정보
        info = get_video_info(path)
        self.size_mb = info.get("size_mb", 0)
        meta = " . ".join(filter(None, [
            f"{info.get('width','?')}x{info.get('height','?')}" if "width" in info else "",
            f"{info['size_mb']:.1f} MB" if "size_mb" in info else "",
        ]))
        if meta:
            ctk.CTkLabel(self, text=meta, text_color="#666",
                         font=("Consolas", 11)).grid(row=0, column=3, padx=8)

        # 삭제 버튼
        ctk.CTkButton(self, text="X", width=28, height=28,
                      fg_color="transparent", hover_color="#c0392b",
                      command=lambda: on_remove(self)).grid(row=0, column=4, padx=(0, 6))


# ── 메인 앱 ──────────────────────────────────────────────────────
class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("SimpleEncoder")
        self.geometry("860x740")
        self.minsize(700, 600)

        self._file_rows = []
        self._proc = None
        self._cancel_flag = False
        self._drag_row = None
        self._drag_start_y = 0
        self._repeat_count = 1

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 헤더
        hdr = ctk.CTkFrame(self, fg_color=("#1a1a2e", "#0f0f1a"), corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="SimpleEncoder",
                     font=("Segoe UI", 22, "bold"),
                     text_color="#4fc3f7").pack(side="left", padx=20, pady=14)
        ctk.CTkLabel(hdr, text="FFmpeg 기반 고화질 저용량 인코더",
                     font=("Segoe UI", 11),
                     text_color="#90a4ae").pack(side="left", pady=14)

        # 파일 추가 버튼 행
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 0))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(top, text="+ 파일 추가", width=120,
                      command=self._add_files).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(top, text="폴더 추가", width=100,
                      fg_color="#37474f", hover_color="#546e7a",
                      command=self._add_folder).grid(row=0, column=1, sticky="w")
        ctk.CTkButton(top, text="목록 초기화", width=100,
                      fg_color="#37474f", hover_color="#c0392b",
                      command=self._clear_list).grid(row=0, column=2)

        # 파일 목록
        list_outer = ctk.CTkFrame(self, fg_color=("#1c1c1c", "#161616"))
        list_outer.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        list_outer.grid_rowconfigure(0, weight=1)
        list_outer.grid_columnconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(list_outer, fg_color="transparent", label_text="")
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._empty_lbl = ctk.CTkLabel(
            self._scroll,
            text="동영상 파일을 여기에 드래그하거나 버튼으로 추가하세요\n(MP4, MKV, AVI, MOV, WMV 등 지원)",
            text_color="#555", font=("Segoe UI", 13))
        self._empty_lbl.grid(row=0, column=0, pady=40)

        list_outer.drop_target_register(DND_FILES)
        list_outer.dnd_bind('<<Drop>>', self._on_drop)

        # 설정 패널
        cfg = ctk.CTkFrame(self, fg_color=("#1e1e2e", "#12121f"))
        cfg.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6))
        cfg.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 프리셋
        ctk.CTkLabel(cfg, text="인코딩 프리셋", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, padx=12, pady=(10, 2), sticky="w")
        self._preset_var = ctk.StringVar(value=list(PRESETS.keys())[0])
        ctk.CTkOptionMenu(cfg, variable=self._preset_var,
                          values=list(PRESETS.keys()),
                          command=self._on_preset_change, width=220).grid(
            row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

        # 해상도
        ctk.CTkLabel(cfg, text="해상도", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=1, padx=8, pady=(10, 2), sticky="w")
        self._res_var = ctk.StringVar(value=RESOLUTIONS[0])
        ctk.CTkOptionMenu(cfg, variable=self._res_var, values=RESOLUTIONS, width=180).grid(
            row=1, column=1, padx=8, pady=(0, 10), sticky="ew")

        # 프레임레이트
        ctk.CTkLabel(cfg, text="프레임레이트", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=2, padx=8, pady=(10, 2), sticky="w")
        self._fps_var = ctk.StringVar(value=FRAMERATES[0])
        ctk.CTkOptionMenu(cfg, variable=self._fps_var, values=FRAMERATES, width=130).grid(
            row=1, column=2, padx=8, pady=(0, 10), sticky="ew")

        # 옵션
        ctk.CTkLabel(cfg, text="옵션", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=3, padx=12, pady=(10, 2), sticky="w")
        self._merge_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(cfg, text="파일 합치기", variable=self._merge_var).grid(
            row=1, column=3, padx=12, pady=(0, 4), sticky="w")
        self._open_folder_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(cfg, text="완료 후 폴더 열기", variable=self._open_folder_var,
                        font=("Segoe UI", 11)).grid(
            row=2, column=3, padx=12, pady=(0, 10), sticky="w")

        # 프리셋 설명
        self._desc_lbl = ctk.CTkLabel(cfg, text="", text_color="#90a4ae",
                                      font=("Segoe UI", 11), wraplength=800)
        self._desc_lbl.grid(row=3, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="w")
        self._on_preset_change(self._preset_var.get())

        # ── 반복 횟수 (-, 숫자, + 딱 붙게) ─────────────────────
        repeat_row = ctk.CTkFrame(self, fg_color=("#1e1e2e", "#12121f"))
        repeat_row.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 6))

        ctk.CTkLabel(repeat_row, text="각 파일 반복 횟수:",
                     font=("Segoe UI", 11, "bold")).pack(side="left", padx=(12, 12), pady=10)

        spinner = ctk.CTkFrame(repeat_row, fg_color="transparent")
        spinner.pack(side="left", pady=10)

        ctk.CTkButton(spinner, text="−", width=32, height=32,
                      font=("Segoe UI", 16, "bold"),
                      fg_color="#37474f", hover_color="#546e7a",
                      corner_radius=6,
                      command=self._decrease_repeat).pack(side="left")

        self._repeat_lbl = ctk.CTkLabel(spinner, text="1",
                                         font=("Segoe UI", 14, "bold"),
                                         width=44, height=32,
                                         fg_color="#0f0f1a", corner_radius=6)
        self._repeat_lbl.pack(side="left", padx=2)

        ctk.CTkButton(spinner, text="+", width=32, height=32,
                      font=("Segoe UI", 16, "bold"),
                      fg_color="#37474f", hover_color="#546e7a",
                      corner_radius=6,
                      command=self._increase_repeat).pack(side="left")

        ctk.CTkLabel(repeat_row,
                     text="회   (예: 2회 → 1,1,2,2,3,3 / '파일 합치기'와 함께 사용)",
                     text_color="#90a4ae",
                     font=("Segoe UI", 11)).pack(side="left", padx=(12, 12), pady=10)

        # ── 출력 파일명 접미사 ────────────────────────────────────
        suffix_row = ctk.CTkFrame(self, fg_color="transparent")
        suffix_row.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 2))
        suffix_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(suffix_row, text="파일명 접미사:",
                     font=("Segoe UI", 11)).grid(row=0, column=0, padx=(0, 8))
        self._suffix_var = ctk.StringVar(value="_encoded")
        ctk.CTkEntry(suffix_row, textvariable=self._suffix_var,
                     placeholder_text="예: _encoded, _h265").grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(suffix_row, text="원본명 + 접미사 (같은 이름 있으면 _1, _2 자동)",
                     text_color="#666", font=("Segoe UI", 10)).grid(row=0, column=2, padx=(8, 0))

        # 저장 위치
        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.grid(row=6, column=0, sticky="ew", padx=16, pady=2)
        out_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(out_row, text="저장 위치:", font=("Segoe UI", 11)).grid(row=0, column=0, padx=(0, 8))
        self._out_var = ctk.StringVar(value="원본 파일과 같은 폴더")
        ctk.CTkEntry(out_row, textvariable=self._out_var).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(out_row, text="찾기", width=60,
                      command=self._choose_outdir).grid(row=0, column=2, padx=(6, 0))

        # 진행바
        self._progress = ctk.CTkProgressBar(self, height=14)
        self._progress.grid(row=7, column=0, sticky="ew", padx=16, pady=(8, 2))
        self._progress.set(0)

        # 상태 표시
        self._status_lbl = ctk.CTkLabel(self, text="준비", text_color="#90a4ae",
                                        font=("Segoe UI", 14, "bold"))
        self._status_lbl.grid(row=8, column=0, padx=16, pady=4, sticky="w")

        # 인코딩 버튼
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=9, column=0, padx=16, pady=10, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        self._encode_btn = ctk.CTkButton(
            btn_row, text="인코딩 시작", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color="#1565c0", hover_color="#1976d2",
            command=self._start_encode)
        self._encode_btn.grid(row=0, column=0, sticky="ew")

        self._cancel_btn = ctk.CTkButton(
            btn_row, text="취소", height=42, width=100,
            font=("Segoe UI", 14),
            fg_color="#b71c1c", hover_color="#c62828",
            command=self._cancel_encode, state="disabled")
        self._cancel_btn.grid(row=0, column=1, padx=(8, 0))

    # ── 반복 +/- ─────────────────────────────────────────────────
    def _increase_repeat(self):
        self._repeat_count = min(99, self._repeat_count + 1)
        self._repeat_lbl.configure(text=str(self._repeat_count))

    def _decrease_repeat(self):
        self._repeat_count = max(1, self._repeat_count - 1)
        self._repeat_lbl.configure(text=str(self._repeat_count))

    # ── 드롭 처리 ────────────────────────────────────────────────
    def _on_drop(self, event):
        for p in parse_drop_paths(event.data):
            for v in collect_videos_from_path(p):
                self._add_row(v)

    # ── 행 순서 드래그 ────────────────────────────────────────────
    def _drag_start(self, event, row):
        self._drag_row = row
        self._drag_start_y = event.y_root
        row.configure(fg_color=("#3a3a5c", "#2a2a4a"))

    def _drag_motion(self, event, row):
        if not self._drag_row:
            return
        y = event.y_root
        idx = self._file_rows.index(self._drag_row)
        if y < self._drag_start_y - 20 and idx > 0:
            self._file_rows[idx], self._file_rows[idx-1] = self._file_rows[idx-1], self._file_rows[idx]
            self._refresh_grid()
            self._drag_start_y = y
        elif y > self._drag_start_y + 20 and idx < len(self._file_rows) - 1:
            self._file_rows[idx], self._file_rows[idx+1] = self._file_rows[idx+1], self._file_rows[idx]
            self._refresh_grid()
            self._drag_start_y = y

    def _drag_end(self, event, row):
        if self._drag_row:
            self._drag_row.configure(fg_color=("#2b2b2b", "#1e1e1e"))
            self._drag_row = None

    def _refresh_grid(self):
        for i, r in enumerate(self._file_rows):
            r.grid(row=i, column=0, sticky="ew", pady=2, padx=4)

    # ── 파일 관리 ─────────────────────────────────────────────────
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="동영상 파일 선택",
            filetypes=[("동영상 파일", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.ts *.m2ts"),
                       ("모든 파일", "*.*")])
        for p in paths:
            self._add_row(p)

    def _add_folder(self):
        d = filedialog.askdirectory(title="폴더 선택")
        if d:
            for v in collect_videos_from_path(d):
                self._add_row(v)

    def _add_row(self, path):
        if path in [r.path for r in self._file_rows]:
            return
        self._empty_lbl.grid_remove()
        row = FileRow(self._scroll, path,
                      on_remove=self._remove_row,
                      on_drag_start=self._drag_start,
                      on_drag_motion=self._drag_motion,
                      on_drag_end=self._drag_end)
        row.grid(row=len(self._file_rows), column=0, sticky="ew", pady=2, padx=4)
        self._file_rows.append(row)

    def _remove_row(self, row):
        row.destroy()
        self._file_rows.remove(row)
        self._refresh_grid()
        if not self._file_rows:
            self._empty_lbl.grid()

    def _clear_list(self):
        for r in self._file_rows:
            r.destroy()
        self._file_rows.clear()
        self._empty_lbl.grid()

    def _choose_outdir(self):
        d = filedialog.askdirectory(title="저장 폴더 선택")
        if d:
            self._out_var.set(d)

    def _on_preset_change(self, val):
        self._desc_lbl.configure(text=f"  {PRESETS.get(val, {}).get('desc', '')}")

    # ── 네이밍 ────────────────────────────────────────────────────
    def _build_stem(self, src_path, extra=""):
        """원본명 + 접미사(+extra). 금지문자 정리."""
        suffix = self._suffix_var.get().strip()
        stem = Path(src_path).stem + suffix + extra
        stem = re.sub(r'[\\/:*?"<>|]', "_", stem)
        return stem or "output"

    def _unique_path(self, out_dir, stem, ext):
        """덮어쓰기 방지: 같은 이름 있으면 _1, _2... 자동 증가"""
        candidate = os.path.join(out_dir, stem + ext)
        if not os.path.exists(candidate):
            return candidate
        i = 1
        while True:
            candidate = os.path.join(out_dir, f"{stem}_{i}{ext}")
            if not os.path.exists(candidate):
                return candidate
            i += 1

    # ── 인코딩 ───────────────────────────────────────────────────
    def _get_output_dir(self, src_path):
        val = self._out_var.get().strip()
        if val == "원본 파일과 같은 폴더" or not val:
            return os.path.dirname(src_path)
        return val

    def _make_filelist(self, paths, repeat):
        """임시 폴더(시스템 temp)에 concat 리스트 파일 생성 — 원본 폴더 오염 방지"""
        fd, path = tempfile.mkstemp(suffix='.txt', prefix='se_concat_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            for fp in paths:
                for _ in range(repeat):
                    f.write(f"file '{fp}'\n")
        return path

    def _apply_encode_args(self, cmd, preset_key):
        """공통 인코딩 옵션 적용"""
        p = PRESETS[preset_key]
        cmd += ["-c:v", p["vcodec"]]
        if p["crf"] is not None:
            cmd += ["-crf", p["crf"]]
        if p["preset"] is not None:
            cmd += ["-preset", p["preset"]]
        if self._res_var.get() != "원본 유지":
            cmd += ["-vf", f"scale={self._res_var.get().split()[0]}"]
        if self._fps_var.get() != "원본 유지":
            cmd += ["-r", self._fps_var.get()]
        cmd += ["-c:a", p["acodec"]]
        if p["ab"]:
            cmd += ["-b:a", p["ab"]]
        if "FastStart" in preset_key:
            cmd += ["-movflags", "+faststart"]
        return cmd

    def _start_encode(self):
        active = [r for r in self._file_rows if r.var.get()]
        if not active:
            messagebox.showwarning("파일 없음", "인코딩할 파일을 추가하세요.")
            return
        try:
            subprocess.check_output([FFMPEG, "-version"], stderr=subprocess.DEVNULL, **HIDE_KWARGS)
        except (FileNotFoundError, OSError):
            messagebox.showerror("오류", f"FFmpeg을 찾을 수 없습니다.\n경로: {FFMPEG}")
            return

        self._encode_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._cancel_flag = False
        self._progress.set(0)
        threading.Thread(target=self._encode_thread, args=(active,), daemon=True).start()

    def _encode_thread(self, rows):
        preset_key = self._preset_var.get()
        ext = PRESETS[preset_key]["ext"]
        merge = self._merge_var.get() and len(rows) > 1
        repeat = self._repeat_count
        temp_files = []
        last_out_dir = ""
        src_total = 0.0   # 원본 합계(MB)
        out_total = 0.0   # 결과 합계(MB)

        try:
            if merge:
                base = rows[0].path
                last_out_dir = self._get_output_dir(base)
                stem = self._build_stem(base, extra="_merged")
                output = self._unique_path(last_out_dir, stem, ext)

                list_file = self._make_filelist([r.path for r in rows], repeat)
                temp_files.append(list_file)

                cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_file]
                self._apply_encode_args(cmd, preset_key)
                cmd.append(output)
                self._run_ffmpeg(cmd, 0, 1, output)

                src_total = sum(r.size_mb for r in rows) * repeat
                out_total = self._file_size_mb(output)
            else:
                for i, row in enumerate(rows):
                    if self._cancel_flag:
                        break
                    last_out_dir = self._get_output_dir(row.path)
                    stem = self._build_stem(row.path)
                    output = self._unique_path(last_out_dir, stem, ext)

                    if repeat > 1:
                        list_file = self._make_filelist([row.path], repeat)
                        temp_files.append(list_file)
                        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_file]
                    else:
                        cmd = [FFMPEG, "-y", "-i", row.path]

                    self._apply_encode_args(cmd, preset_key)
                    cmd.append(output)
                    self._run_ffmpeg(cmd, i, len(rows), output)

                    src_total += row.size_mb * (repeat if repeat > 1 else 1)
                    out_total += self._file_size_mb(output)

            if not self._cancel_flag:
                self.after(0, self._on_encode_done, last_out_dir, src_total, out_total)
        except Exception as e:
            self._set_status(f"오류: {e}", "#ef5350")
            self.after(0, self._reset_buttons)
        finally:
            for tf in temp_files:
                try:
                    os.remove(tf)
                except Exception:
                    pass

    def _file_size_mb(self, path):
        try:
            return os.path.getsize(path) / 1024 / 1024
        except Exception:
            return 0.0

    def _on_encode_done(self, out_dir, src_total, out_total):
        self._reset_buttons()
        self._progress.set(1.0)

        # 실제 절감 결과 표시
        if src_total > 0 and out_total > 0:
            saved = (1 - out_total / src_total) * 100
            self._status_lbl.configure(
                text=f"✓ 완료!  {fmt_size(src_total)} → {fmt_size(out_total)}  ({saved:.0f}% 절감)",
                text_color="#4caf50")
        else:
            self._status_lbl.configure(text="✓ 인코딩 완료!", text_color="#4caf50")

        if self._open_folder_var.get() and out_dir and os.path.isdir(out_dir):
            try:
                os.startfile(out_dir)
            except Exception:
                pass

    def _reset_buttons(self):
        self._encode_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")

    def _run_ffmpeg(self, cmd, idx, total, output):
        duration = None
        self._set_status(f"[{idx+1}/{total}] 인코딩 중: {os.path.basename(output)}", "#90a4ae")
        self._proc = subprocess.Popen(
            cmd, stderr=subprocess.PIPE,
            universal_newlines=True, encoding="utf-8", errors="replace",
            **HIDE_KWARGS)
        time_pat = re.compile(r"time=(\d+):(\d+):([\d.]+)")
        dur_pat  = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")

        for line in self._proc.stderr:
            if self._cancel_flag:
                self._proc.terminate()
                break
            if duration is None:
                m = dur_pat.search(line)
                if m:
                    h, mi, s = m.groups()
                    duration = int(h)*3600 + int(mi)*60 + float(s)
            m = time_pat.search(line)
            if m and duration:
                h, mi, s = m.groups()
                cur = int(h)*3600 + int(mi)*60 + float(s)
                fp = min(cur / duration, 1.0)
                self.after(0, self._progress.set, (idx + fp) / total)
                self._set_status(f"[{idx+1}/{total}] {os.path.basename(output)} - {fp*100:.0f}%", "#90a4ae")

        self._proc.wait()

    def _cancel_encode(self):
        self._cancel_flag = True
        if self._proc:
            self._proc.terminate()
        self._set_status("취소됨", "#ffa726")
        self._progress.set(0)
        self._reset_buttons()

    def _set_status(self, text, color="#90a4ae"):
        self.after(0, self._status_lbl.configure, {"text": text, "text_color": color})


# ── 메인 ─────────────────────────────────────────────────────────
try:
    app = App()
    app.mainloop()
except Exception:
    err = traceback.format_exc()
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("오류", f"실행 오류:\n\n{err[:800]}")
        root.destroy()
    except Exception:
        pass
