"""
SimpleEncoder - FFmpeg 기반 동영상 인코더
의존성: pip install customtkinter
실행: python video_encoder.py
FFmpeg이 설치되어 있어야 합니다 (https://ffmpeg.org)
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import re
import json
from pathlib import Path

# ── 테마 설정 ──────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── 프리셋 정의 ──────────────────────────────────────────────────
PRESETS = {
    "고화질 (H.265 | 저용량 권장)": {
        "vcodec": "libx265", "crf": "22", "preset": "medium",
        "acodec": "aac", "ab": "192k", "ext": ".mp4",
        "desc": "파일 크기 ↓↓  화질 ↑↑  (H.264 대비 ~40% 절감)"
    },
    "일반 (H.264 | 호환성 최고)": {
        "vcodec": "libx264", "crf": "23", "preset": "medium",
        "acodec": "aac", "ab": "192k", "ext": ".mp4",
        "desc": "모든 기기·플레이어 호환 / 무난한 균형"
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


def get_video_info(path: str) -> dict:
    """FFprobe로 영상 정보 추출"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path
    ]
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
                info["fps"]    = eval(s.get("r_frame_rate", "0/1"))
                info["vcodec"] = s.get("codec_name", "?")
            elif s.get("codec_type") == "audio":
                info["acodec"] = s.get("codec_name", "?")
        return info
    except Exception:
        return {}


class FileRow(ctk.CTkFrame):
    """파일 목록의 단일 행"""
    def __init__(self, master, path: str, on_remove, **kw):
        super().__init__(master, fg_color=("#2b2b2b", "#1e1e1e"),
                         corner_radius=8, **kw)
        self.path = path
        self.name = os.path.basename(path)
        self.on_remove = on_remove

        self.grid_columnconfigure(1, weight=1)

        # 체크박스 (포함 여부)
        self.var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="", variable=self.var, width=28).grid(
            row=0, column=0, padx=(8, 0), pady=6)

        # 파일명
        ctk.CTkLabel(self, text=self.name, anchor="w",
                     font=("Consolas", 12)).grid(
            row=0, column=1, sticky="ew", padx=8)

        # 용량 정보
        info = get_video_info(path)
        size_txt = f"{info['size_mb']:.1f} MB" if "size_mb" in info else ""
        res_txt  = f"{info.get('width','?')}x{info.get('height','?')}" if "width" in info else ""
        meta = " · ".join(filter(None, [res_txt, size_txt]))
        if meta:
            ctk.CTkLabel(self, text=meta,
                         text_color=("#888", "#666"),
                         font=("Consolas", 11)).grid(
                row=0, column=2, padx=8)

        # 삭제 버튼
        ctk.CTkButton(self, text="✕", width=28, height=28,
                      fg_color="transparent", hover_color="#c0392b",
                      command=lambda: on_remove(self)).grid(
            row=0, column=3, padx=(0, 6))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SimpleEncoder")
        self.geometry("860x700")
        self.minsize(700, 560)
        self.resizable(True, True)

        self._file_rows: list[FileRow] = []
        self._proc = None
        self._cancel_flag = False

        self._build_ui()

    # ── UI 구성 ──────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── 헤더 ──
        hdr = ctk.CTkFrame(self, fg_color=("#1a1a2e", "#0f0f1a"), corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="⚡ SimpleEncoder",
                     font=("Segoe UI", 22, "bold"),
                     text_color="#4fc3f7").pack(side="left", padx=20, pady=14)
        ctk.CTkLabel(hdr, text="FFmpeg 기반 고화질 저용량 인코더",
                     font=("Segoe UI", 11),
                     text_color="#90a4ae").pack(side="left", pady=14)

        # ── 파일 추가 영역 ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 0))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(top, text="＋ 파일 추가", width=120,
                      command=self._add_files).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(top, text="폴더 추가", width=100,
                      fg_color="#37474f", hover_color="#546e7a",
                      command=self._add_folder).grid(row=0, column=1, sticky="w")
        ctk.CTkButton(top, text="목록 초기화", width=100,
                      fg_color="#37474f", hover_color="#c0392b",
                      command=self._clear_list).grid(row=0, column=2)

        # ── 파일 목록 ──
        list_outer = ctk.CTkFrame(self, fg_color=("#1c1c1c", "#161616"))
        list_outer.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        list_outer.grid_rowconfigure(0, weight=1)
        list_outer.grid_columnconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(list_outer,
                                               fg_color="transparent",
                                               label_text="")
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._scroll.grid_columnconfigure(0, weight=1)

        self._empty_lbl = ctk.CTkLabel(
            self._scroll,
            text="여기에 동영상 파일을 추가하세요\n(MP4, MKV, AVI, MOV, WMV 등 지원)",
            text_color="#555",
            font=("Segoe UI", 13))
        self._empty_lbl.grid(row=0, column=0, pady=40)

        # ── 설정 패널 ──
        cfg = ctk.CTkFrame(self, fg_color=("#1e1e2e", "#12121f"))
        cfg.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6))
        cfg.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 프리셋
        ctk.CTkLabel(cfg, text="인코딩 프리셋", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, padx=12, pady=(10, 2), sticky="w")
        self._preset_var = ctk.StringVar(value=list(PRESETS.keys())[0])
        self._preset_menu = ctk.CTkOptionMenu(
            cfg, variable=self._preset_var,
            values=list(PRESETS.keys()),
            command=self._on_preset_change,
            width=220)
        self._preset_menu.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

        # 해상도
        ctk.CTkLabel(cfg, text="해상도", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=1, padx=8, pady=(10, 2), sticky="w")
        self._res_var = ctk.StringVar(value=RESOLUTIONS[0])
        ctk.CTkOptionMenu(cfg, variable=self._res_var,
                          values=RESOLUTIONS, width=180).grid(
            row=1, column=1, padx=8, pady=(0, 10), sticky="ew")

        # 프레임레이트
        ctk.CTkLabel(cfg, text="프레임레이트", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=2, padx=8, pady=(10, 2), sticky="w")
        self._fps_var = ctk.StringVar(value=FRAMERATES[0])
        ctk.CTkOptionMenu(cfg, variable=self._fps_var,
                          values=FRAMERATES, width=130).grid(
            row=1, column=2, padx=8, pady=(0, 10), sticky="ew")

        # 합치기 옵션
        ctk.CTkLabel(cfg, text="병합 옵션", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=3, padx=12, pady=(10, 2), sticky="w")
        self._merge_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(cfg, text="파일 합치기", variable=self._merge_var).grid(
            row=1, column=3, padx=12, pady=(0, 10), sticky="w")

        # 프리셋 설명
        self._desc_lbl = ctk.CTkLabel(cfg, text="", text_color="#90a4ae",
                                      font=("Segoe UI", 11), wraplength=800)
        self._desc_lbl.grid(row=2, column=0, columnspan=4,
                            padx=12, pady=(0, 8), sticky="w")
        self._on_preset_change(self._preset_var.get())

        # ── 출력 경로 ──
        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.grid(row=4, column=0, sticky="ew", padx=16, pady=2)
        out_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(out_row, text="저장 위치:", font=("Segoe UI", 11)).grid(
            row=0, column=0, padx=(0, 8))
        self._out_var = ctk.StringVar(value="원본 파일과 같은 폴더")
        ctk.CTkEntry(out_row, textvariable=self._out_var).grid(
            row=0, column=1, sticky="ew")
        ctk.CTkButton(out_row, text="찾기", width=60,
                      command=self._choose_outdir).grid(row=0, column=2, padx=(6, 0))

        # ── 진행 상황 ──
        self._progress = ctk.CTkProgressBar(self, height=14)
        self._progress.grid(row=5, column=0, sticky="ew", padx=16, pady=(8, 2))
        self._progress.set(0)

        self._status_lbl = ctk.CTkLabel(self, text="준비", text_color="#90a4ae",
                                        font=("Consolas", 11))
        self._status_lbl.grid(row=6, column=0, padx=16, sticky="w")

        # ── 인코딩 버튼 ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=7, column=0, padx=16, pady=10, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        self._encode_btn = ctk.CTkButton(
            btn_row, text="⚡ 인코딩 시작", height=42,
            font=("Segoe UI", 14, "bold"),
            fg_color="#1565c0", hover_color="#1976d2",
            command=self._start_encode)
        self._encode_btn.grid(row=0, column=0, sticky="ew")

        self._cancel_btn = ctk.CTkButton(
            btn_row, text="■ 취소", height=42, width=100,
            font=("Segoe UI", 14),
            fg_color="#b71c1c", hover_color="#c62828",
            command=self._cancel_encode,
            state="disabled")
        self._cancel_btn.grid(row=0, column=1, padx=(8, 0))

    # ── 이벤트 ──────────────────────────────────────────────────
    def _on_preset_change(self, val):
        desc = PRESETS.get(val, {}).get("desc", "")
        self._desc_lbl.configure(text=f"  ℹ  {desc}")

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
        exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".ts", ".m2ts"}
        for f in sorted(Path(d).rglob("*")):
            if f.suffix.lower() in exts:
                self._add_row(str(f))

    def _add_row(self, path: str):
        existing = [r.path for r in self._file_rows]
        if path in existing:
            return
        self._empty_lbl.grid_remove()
        row = FileRow(self._scroll, path, on_remove=self._remove_row)
        row.grid(row=len(self._file_rows), column=0, sticky="ew",
                 pady=2, padx=4)
        self._file_rows.append(row)

    def _remove_row(self, row: FileRow):
        row.destroy()
        self._file_rows.remove(row)
        # 재배치
        for i, r in enumerate(self._file_rows):
            r.grid(row=i)
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

    # ── 인코딩 ──────────────────────────────────────────────────
    def _get_output_dir(self, src_path: str) -> str:
        val = self._out_var.get().strip()
        if val == "원본 파일과 같은 폴더" or not val:
            return os.path.dirname(src_path)
        return val

    def _build_ffmpeg_cmd(self, inputs: list[str], output: str, preset_key: str) -> list[str]:
        p = PRESETS[preset_key]
        merge = self._merge_var.get() and len(inputs) > 1

        cmd = ["ffmpeg", "-y"]

        if merge:
            # concat demuxer 사용
            list_file = output + "_filelist.txt"
            with open(list_file, "w", encoding="utf-8") as f:
                for fp in inputs:
                    f.write(f"file '{fp}'\n")
            cmd += ["-f", "concat", "-safe", "0", "-i", list_file]
        else:
            for fp in inputs:
                cmd += ["-i", fp]

        # 비디오 코덱
        cmd += ["-c:v", p["vcodec"]]
        if p["crf"] is not None:
            cmd += ["-crf", p["crf"]]
        if p["preset"] is not None:
            cmd += ["-preset", p["preset"]]

        # 해상도
        res = self._res_var.get()
        if res != "원본 유지":
            wh = res.split(" ")[0]
            cmd += ["-vf", f"scale={wh}"]

        # 프레임레이트
        fps = self._fps_var.get()
        if fps != "원본 유지":
            cmd += ["-r", fps]

        # 오디오 코덱
        cmd += ["-c:a", p["acodec"]]
        if p["ab"]:
            cmd += ["-b:a", p["ab"]]

        # FastStart (웹용)
        if "FastStart" in preset_key:
            cmd += ["-movflags", "+faststart"]

        # 다중 입력 비병합 시 map
        if not merge and len(inputs) > 1:
            pass  # 개별 출력 처리는 아래 루프에서

        cmd.append(output)
        return cmd

    def _start_encode(self):
        active = [r for r in self._file_rows if r.var.get()]
        if not active:
            messagebox.showwarning("파일 없음", "인코딩할 파일을 추가하세요.")
            return

        # FFmpeg 확인
        try:
            subprocess.check_output(["ffmpeg", "-version"], stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            messagebox.showerror(
                "FFmpeg 없음",
                "FFmpeg이 설치되지 않았습니다.\n\nhttps://ffmpeg.org 에서 다운로드 후\n시스템 PATH에 추가해 주세요.")
            return

        self._encode_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._cancel_flag = False
        self._progress.set(0)

        threading.Thread(target=self._encode_thread,
                         args=(active,), daemon=True).start()

    def _encode_thread(self, rows: list[FileRow]):
        preset_key = self._preset_var.get()
        p = PRESETS[preset_key]
        merge = self._merge_var.get() and len(rows) > 1
        total = 1 if merge else len(rows)

        try:
            if merge:
                # 파일 합치기 → 첫 번째 파일 기준 출력
                base = rows[0].path
                out_dir = self._get_output_dir(base)
                stem = Path(base).stem + "_merged"
                output = os.path.join(out_dir, stem + p["ext"])
                cmd = self._build_ffmpeg_cmd(
                    [r.path for r in rows], output, preset_key)
                self._run_ffmpeg(cmd, 0, 1, output)
            else:
                for i, row in enumerate(rows):
                    if self._cancel_flag:
                        break
                    out_dir = self._get_output_dir(row.path)
                    stem = Path(row.path).stem + "_encoded"
                    output = os.path.join(out_dir, stem + p["ext"])
                    cmd = self._build_ffmpeg_cmd([row.path], output, preset_key)
                    self._run_ffmpeg(cmd, i, total, output)

            if not self._cancel_flag:
                self._set_status("✅ 인코딩 완료!", "#4caf50")
                self._progress.set(1.0)
                self.after(0, lambda: messagebox.showinfo(
                    "완료", "인코딩이 완료되었습니다!"))
        except Exception as e:
            self._set_status(f"❌ 오류: {e}", "#ef5350")
        finally:
            self.after(0, self._encode_btn.configure, {"state": "normal"})
            self.after(0, self._cancel_btn.configure, {"state": "disabled"})

    def _run_ffmpeg(self, cmd: list[str], idx: int, total: int, output: str):
        """FFmpeg 프로세스 실행 + 진행률 파싱"""
        # 전체 길이 먼저 파악
        duration = None

        self._set_status(f"[{idx+1}/{total}] 인코딩 중: {os.path.basename(output)}")

        self._proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace"
        )

        time_pattern = re.compile(r"time=(\d+):(\d+):([\d.]+)")
        dur_pattern  = re.compile(r"Duration:\s*(\d+):(\d+):([\d.]+)")

        for line in self._proc.stderr:
            if self._cancel_flag:
                self._proc.terminate()
                break

            if duration is None:
                m = dur_pattern.search(line)
                if m:
                    h, mi, s = m.groups()
                    duration = int(h)*3600 + int(mi)*60 + float(s)

            m = time_pattern.search(line)
            if m and duration:
                h, mi, s = m.groups()
                cur = int(h)*3600 + int(mi)*60 + float(s)
                file_prog = min(cur / duration, 1.0)
                total_prog = (idx + file_prog) / total
                self.after(0, self._progress.set, total_prog)
                self._set_status(
                    f"[{idx+1}/{total}] {os.path.basename(output)} "
                    f"— {file_prog*100:.0f}%")

        self._proc.wait()

    def _cancel_encode(self):
        self._cancel_flag = True
        if self._proc:
            self._proc.terminate()
        self._set_status("⏹ 취소됨", "#ffa726")
        self._progress.set(0)
        self._encode_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")

    def _set_status(self, text: str, color: str = "#90a4ae"):
        self.after(0, self._status_lbl.configure,
                   {"text": text, "text_color": color})


if __name__ == "__main__":
    app = App()
    app.mainloop()
