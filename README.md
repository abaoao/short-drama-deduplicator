#!/usr/bin/env python3
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict


class VideoVariantTool:
    """Generate alternative versions of source videos using FFmpeg filtering."""

    def __init__(self):
        self._ensure_ffmpeg()

    def _ensure_ffmpeg(self):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg not found in PATH. Please install FFmpeg first: https://ffmpeg.org/")

    def _find_videos(self, input_dir: Path) -> List[Path]:
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

        video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
        return sorted(
            [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in video_exts],
            key=lambda p: p.name.lower(),
        )

    def _run_ffmpeg(self, command: List[str], description: str):
        print(f"[RUN] {description}")
        subprocess.run(command, check=True)

    def _build_filter(self, variant_type: str, title: str, speed: float = 1.0) -> str:
        if variant_type == "color":
            return "scale=1280:720,eq=contrast=1.25:saturation=1.6:brightness=0.05,format=yuv420p"

        if variant_type == "subtitle":
            text = title.replace("'", "\\'").replace(":", "\\:")
            return (
                "scale=1280:720,"
                f"drawtext=text='{text}':fontcolor=white:fontsize=30:box=1:boxcolor=black@0.45:boxborderw=12:x=(w-text_w)/2:y=h*0.82,"
                "format=yuv420p"
            )

        if variant_type == "speed":
            return f"setpts=PTS/{speed},scale=1280:720,format=yuv420p"

        if variant_type == "reframe":
            return "crop=iw*0.88:ih*0.9:iw*0.06:ih*0.05,scale=1280:720,format=yuv420p"

        if variant_type == "music":
            return "scale=1280:720,eq=contrast=1.15:saturation=1.3,format=yuv420p"

        return "scale=1280:720,format=yuv420p"

    def _generate_with_audio_mix(self, source: Path, output: Path, filter_expr: str, music_path: str | None = None):
        if not music_path:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(source),
                "-vf", filter_expr,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "24",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-movflags", "+faststart",
                str(output),
            ]
            self._run_ffmpeg(cmd, f"Generate variant from {source.name}")
            return

        music = Path(music_path)
        if not music.exists():
            print(f"[WARN] Music file not found: {music_path}; falling back to no music")
            self._generate_with_audio_mix(source, output, filter_expr, None)
            return

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-i", str(music),
            "-filter_complex",
            f"[0:v]{filter_expr}[v];[0:a]volume=1.0[a0];[1:a]volume=0.18[a1];[a0][a1]amix=inputs=2:duration=longest[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "24",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output),
        ]
        self._run_ffmpeg(cmd, f"Generate music variant from {source.name}")

    def generate_variant(
        self,
        source_video: Path,
        output_dir: Path,
        variant_type: str,
        title: str,
        speed: float = 1.0,
        music_path: str | None = None,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"{source_video.stem}_{variant_type}.mp4"
        output_path = output_dir / out_name

        filter_expr = self._build_filter(variant_type, title=title, speed=speed)

        if variant_type == "music":
            self._generate_with_audio_mix(source_video, output_path, filter_expr, music_path)
        else:
            self._generate_with_audio_mix(source_video, output_path, filter_expr, None)

        return output_path

    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        mode: str = "auto",
        per_video_count: int = 4,
        title: str = "Original Short Drama",
        speed: float = 0.9,
        music_path: str | None = None,
    ) -> Dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        videos = self._find_videos(input_dir)

        report = {"mode": mode, "generated": []}
        if not videos:
            print(f"[WARN] No video files found in {input_dir}")
            return report

        mode_map = {
            "auto": ["color", "subtitle", "speed", "reframe"],
            "color": ["color"],
            "subtitle": ["subtitle"],
            "speed": ["speed"],
            "music": ["music"],
            "reframe": ["reframe"],
        }

        variant_types = mode_map.get(mode, ["color"])
        limit = max(1, min(per_video_count, len(variant_types)))

        for video in videos:
            for variant_type in variant_types[:limit]:
                current_speed = speed if variant_type == "speed" else 1.0
                output_path = self.generate_variant(
                    source_video=video,
                    output_dir=output_dir,
                    variant_type=variant_type,
                    title=title,
                    speed=current_speed,
                    music_path=music_path if variant_type == "music" else None,
                )
                report["generated"].append(
                    {
                        "source": str(video),
                        "output": str(output_path),
                        "variant_type": variant_type,
                    }
                )

        report_path = output_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report


if __name__ == "__main__":
    print("This module is intended to be used via main.py")
