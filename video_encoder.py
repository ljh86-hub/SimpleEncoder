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
import traceback
from pathlib import Path

# ── FFmpeg 경로 ───────────────────────────────────────────────────
def _ffmpeg_bin(name):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(base, name)
    if os.path.exists(bundled):
        return bundled
    return name

FFMPEG  = _ffmpeg_bin('ffmpeg.exe')
FFPROBE = _ffmpeg_bin('ffprobe.exe')

# ── 설정 ─────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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


def get_video_info(path):
    cmd = [FFPROBE, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        data = json.loads(out)
        info = {}
        fmt = data.get("format", {})
        info["duration"] = float(fmt.get("duration", 0))
        info["size_mb"]  = int(fmt.get("size", 0)) / 1024 / 1024
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                info["width"]  = s.get("width", "?")
                info["height"] = s.get("height", "?")
                info["vcodec"] = s.get("codec_name", "?")
            elif s.get("codec_type") == "audio":
                info["acodec"] = s.get("codec_name", "?")
        return info
    except Exception:
        return {}


def parse_drop_paths(data: str) -> list:
    """tkinterdnd2 드롭 데이터 파싱 (공백 포함 경로 처리)"""
    paths = []
    data = data.strip()
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


class FileRow(ctk.CTkFrame):
    def __init__(self, master, path, on_remove, on_drag_start, on_drag_motion, on_drag_end, **kw):
        super().__init__(master, fg_color=("#2b2b2b", "#1e1e1e"), corner_radius=8, **kw)
        self.path = path
        self.name = os.path.basename(path)
        self.grid_columnconfigure(2, weight=1)

        handle = ctk.CTkLabel(self, text="=", font=("Consolas", 18),
                               text_color="#666", cursor="fleur", width=24)
        handle.grid(row=0, column=0, padx=(6, 0), pady=6)
        handle.bind("<ButtonPress-1>",   lambda e: on_drag_start(e, self))
        handle.bind("<B1-Motion>",       lambda e: on_drag_motion(e, self))
        handle.bind("<ButtonRelease-1>", lambda e: on_drag_end(e, self))

        self.var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="", variable=self.var, width=28).grid(
            row=0, column=1, padx=(4, 0), pady=6)

        ctk.CTkLabel(self, text=self.name, anchor="w",
                     font=("Consolas", 12)).grid(row=0, column=2, sticky="ew", padx=8)

        info = get_video_info(path)
        size_txt = f"{info['size_mb']:.1f} MB" if "size_mb" in info else ""
        res_txt  = f"{info.get('width','?')}x{info.get('height','?')}" if "width" in info else ""
        meta = " . ".join(filter(None, [res_txt, size_txt]))
        if meta:
            ctk.CTkLabel(self, text=meta, text_color=("#888", "#666"),
                         font=("Consolas", 11)).grid(row=0, column=3, padx=8)

        ctk.CTkButton(self, text="X", width=28, height=28,
                      fg_color="transparent", hover_color="#c0392b",
                      command=lambda: on_remove(self)).grid(row=0, column=4, padx=(0, 6))


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("SimpleEncoder")
        self.geometry("860x700")
        self.minsize(700, 560)
        self.resizable(True, True)

        # customtkinter 테마를 TkinterDnD.Tk 에 적용
        ctk.set_appearance_mode("dark")

        self._file_rows = []
        self._proc = None
        self._cancel_flag = False
        self._drag_row = None
        self._drag_start_y = 0

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(self, fg_color=("#1a1a2e", "#0f0f1a"), corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="SimpleEncoder",
                     font=("Segoe UI", 22, "bold"),
                     text_color="#4fc3f7").pack(side="left", padx=20, pady=14)
        ctk.CTkLabel(hdr, text="FFmpeg 기반 고화질 저용량 인코더",
                     font=("Segoe UI", 11),
                     text_color="#90a4ae").pack(side="left", pady=14)

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

        self._list_outer = ctk.CTkFrame(self, fg_color=("#1c1c1c", "#161616"))
        self._list_outer.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        self._list_outer.grid_rowconfigure(0, weight=1)
        self._list_outer.grid_columnconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self._list_outer,
                                               fg_color="transparent", label_text="")
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._empty_lbl = ctk.CTkLabel(
            self._scroll,
            text="동영상 파일을 여기에 드래그하거나 버튼으로 추가하세요\n(MP4, MKV, AVI, MOV, WMV 등 지원)",
            text_color="#555", font=("Segoe UI", 13))
        self._empty_lbl.grid(row=0, column=0, pady=40)

        # 드롭 등록
        self._list_outer.drop_target_register(DND_FILES)
        self._list_outer.dnd_bind('<<Drop>>', self._on_drop)

        cfg = ctk.CTkFrame(self, fg_color=("#1e1e2e", "#12121f"))
        cfg.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6))
        cfg.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkLabel(cfg, text="인코딩 프리셋", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, padx=12, pady=(10, 2), sticky="w")
        self._preset_var = ctk.StringVar(value=list(PRESETS.keys())[0])
        ctk.CTkOptionMenu(cfg, variable=self._preset_var,
                          values=list(PRESETS.keys()),
                          command=self._on_preset_change, width=220).grid(
            row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(cfg, text="해상도", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=1, padx=8, pady=(10, 2), sticky="w")
        self._res_var = ctk.StringVar(value=RESOLUTIONS[0])
        ctk.CTkOptionMenu(cfg, variable=self._res_var,
                          values=RESOLUTIONS, width=180).grid(
            row=1, column=1, padx=8, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(cfg, text="프레임레이트", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=2, padx=8, pady=(10, 2), sticky="w")
        self._fps_var = ctk.StringVar(value=FRAMERATES[0])
        ctk.CTkOptionMenu(cfg, variable=self._fps_var,
                          values=FRAMERATES, width=130).grid(
            row=1, column=2, padx=8, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(cfg, text="병합 옵션", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=3, padx=12, pady=(10, 2), sticky="w")
        self._merge_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(cfg, text="파일 합치기", variable=self._merge_var).grid(
            row=1, column=3, padx=12, pady=(0, 10), sticky="w")

        self._desc_lbl = ctk.CTkLabel(cfg, text="", text_color="#90a4ae",
                                      font=("Segoe UI", 11), wraplength=800)
        self._desc_lbl.grid(row=2, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="w")
        self._on_preset_change(self._preset_var.get())

        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.grid(row=4, column=0, sticky="ew", padx=16, pady=2)
        out_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(out_row, text="저장 위치:", font=("Segoe UI", 11)).grid(row=0, column=0, padx=(0, 8))
        self._out_var = ctk.StringVar(value="원본 파일과 같은 폴더")
        ctk.CTkEntry(out_row, textvariable=self._out_var).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(out_row, text="찾기", width=60,
                      command=self._choose_outdir).grid(row=0, column=2, padx=(6, 0))

        self._progress = ctk.CTkProgressBar(self, height=14)
        self._progress.grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 2))
        self._progress.set(0)

        self._status_lbl = ctk.CTkLabel(self, text="준비", text_color="#90a4ae",
                                        font=("Consolas", 11))
        self._status_lbl.grid(row=6, column=0, padx=16, sticky="w")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=7, column=0, padx=16, pady=10, sticky="ew")
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

    # ── 드롭 처리 ────────────────────────────────────────────────
    def _on_drop(self, event):
        for p in parse_drop_paths(event.data):
            if os.path.isfile(p) and Path(p).suffix.lower() in VIDEO_EXTS:
                self._add_row(p)
            elif os.path.isdir(p):
                for f in sorted(Path(p).rglob("*")):
                    if f.suffix.lower() in VIDEO_EXTS:
                        self._add_row(str(f))

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
        if not d:
            return
        for f in sorted(Path(d).rglob("*")):
            if f.suffix.lower() in VIDEO_EXTS:
                self._add_row(str(f))

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
        desc = PRESETS.get(val, {}).get("desc", "")
        self._desc_lbl.configure(text=f"  {desc}")

    # ── 인코딩 ───────────────────────────────────────────────────
    def _get_output_dir(self, src_path):
        val = self._out_var.get().strip()
        if val == "원본 파일과 같은 폴더" or not val:
            return os.path.dirname(src_path)
        return val

    def _build_ffmpeg_cmd(self, inputs, output, preset_key):
        p = PRESETS[preset_key]
        merge = self._merge_var.get() and len(inputs) > 1
        cmd = [FFMPEG, "-y"]
        if merge:
            list_file = output + "_filelist.txt"
            with open(list_file, "w", encoding="utf-8") as f:
                for fp in inputs:
                    f.write(f"file '{fp}'\n")
            cmd += ["-f", "concat", "-safe", "0", "-i", list_file]
        else:
            for fp in inputs:
                cmd += ["-i", fp]
        cmd += ["-c:v", p["vcodec"]]
        if p["crf"] is not None:
            cmd += ["-crf", p["crf"]]
        if p["preset"] is not None:
            cmd += ["-preset", p["preset"]]
        res = self._res_var.get()
        if res != "원본 유지":
            cmd += ["-vf", f"scale={res.split()[0]}"]
        fps = self._fps_var.get()
        if fps != "원본 유지":
            cmd += ["-r", fps]
        cmd += ["-c:a", p["acodec"]]
        if p["ab"]:
            cmd += ["-b:a", p["ab"]]
        if "FastStart" in preset_key:
            cmd += ["-movflags", "+faststart"]
        cmd.append(output)
        return cmd

    def _start_encode(self):
        active = [r for r in self._file_rows if r.var.get()]
        if not active:
            messagebox.showwarning("파일 없음", "인코딩할 파일을 추가하세요.")
            return
        try:
            subprocess.check_output([FFMPEG, "-version"], stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            messagebox.showerror("오류", f"FFmpeg을 찾을 수 없습니다.\n경로: {FFMPEG}")
            return

        self._encode_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._cancel_flag = False
        self._progress.set(0)
        threading.Thread(target=self._encode_thread, args=(active,), daemon=True).start()

    def _encode_thread(self, rows):
        preset_key = self._preset_var.get()
        p = PRESETS[preset_key]
        merge = self._merge_var.get() and len(rows) > 1
        total = 1 if merge else len(rows)
        last_out_dir = ""
        try:
            if merge:
                base = rows[0].path
                last_out_dir = self._get_output_dir(base)
                stem = Path(base).stem + "_merged"
                output = os.path.join(last_out_dir, stem + p["ext"])
                cmd = self._build_ffmpeg_cmd([r.path for r in rows], output, preset_key)
                self._run_ffmpeg(cmd, 0, 1, output)
            else:
                for i, row in enumerate(rows):
                    if self._cancel_flag:
                        break
                    last_out_dir = self._get_output_dir(row.path)
                    stem = Path(row.path).stem + "_encoded"
                    output = os.path.join(last_out_dir, stem + p["ext"])
                    cmd = self._build_ffmpeg_cmd([row.path], output, preset_key)
                    self._run_ffmpeg(cmd, i, total, output)

            if not self._cancel_flag:
                self._set_status("완료!", "#4caf50")
                self._progress.set(1.0)
                self.after(0, self._on_encode_done, last_out_dir)
        except Exception as e:
            self._set_status(f"오류: {e}", "#ef5350")
            self.after(0, self._reset_buttons)

    def _on_encode_done(self, out_dir):
        self._reset_buttons()
        if out_dir and os.path.isdir(out_dir):
            try:
                os.startfile(out_dir)
            except Exception:
                pass
        messagebox.showinfo("완료", "인코딩 완료!\n출력 폴더를 엽니다.")

    def _reset_buttons(self):
        self._encode_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")

    def _run_ffmpeg(self, cmd, idx, total, output):
        duration = None
        self._set_status(f"[{idx+1}/{total}] 인코딩 중: {os.path.basename(output)}")
        self._proc = subprocess.Popen(
            cmd, stderr=subprocess.PIPE,
            universal_newlines=True, encoding="utf-8", errors="replace")
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
                self._set_status(f"[{idx+1}/{total}] {os.path.basename(output)} - {fp*100:.0f}%")
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
