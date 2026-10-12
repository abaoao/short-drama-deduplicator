#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


class VideoVariantTool:
    """Generate multiple alternative versions of a source video using FFmpeg filters."""

    def __init__(self):
        self.required_tools = ["ffmpeg"]
        self._ensure_tools()

    def _ensure_tools(self):
        missing = []
        for tool in self.required_tools:
            if shutil.which(tool) is None:
                missing.append(tool)
        if missing:
            raise RuntimeError(f"Missing required CLI tools: {', '.join(missing)}. Please install FFmpeg.")

    def _find_videos(self, input_dir: Path) -> List[Path]:
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {input_dir}")
        videos = []
        for p in sorted(input_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
                videos.append(p)
        return videos

    def _run_ffmpeg(self, args: List[str], description: str):
        print(f"[RUN] {description}")
        subprocess.run(["ffmpeg", *args], check=True)

    def _build_filter_string(self, variant_type: str, title: str, speed: float = 1.0) -> str:
        if variant_type == "color":
            return (
                "scale=1280:720,"
                "eq=contrast=1.25:saturation=1.6:brightness=0.05,"
                "format=yuv420p"
            )
        if variant_type == "subtitle":
            safe_title = title.replace(':', '\\:').replace("'", "\\'")
            return (
                "scale=1280:720,"
                "drawtext=text='" + safe_title + "':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.4:boxborderw=12:x=(w-text_w)/2:y=h*0.82,"
                "format=yuv420p"
            )
        if variant_type == "speed":
            return "scale=1280:720,format=yuv420p"
        if variant_type == "music":
            return "scale=1280:720,eq=contrast=1.15:saturation=1.3,format=yuv420p"
        if variant_type == "reframe":
            return "crop=iw*0.88:ih*0.9:iw*0.06:ih*0.05,scale=1280:720,format=yuv420p"
        return "scale=1280:720,format=yuv420p"

    def _build_audio_args(self, source_video: Path, music_path: str | None = None, speed: float = 1.0):
        if music_path is None:
            return []
        music = Path(music_path)
        if not music.exists():
            print(f"[WARN] Music file not found: {music_path}; skipping audio layer")
            return []
        return [
            "-i", str(music),
            "-filter_complex",
            "[0:a]volume=1.0[a0];[1:a]volume=0.20[a1];[a0][a1]amix=inputs=2:duration=longest",
            "-map", "0:v:0",
            "-map", "[aout]",
        ]

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

        filters = self._build_filter_string(variant_type, title, speed)

        base_cmd = [
            "-y",
            "-i", str(source_video),
        ]

        if music_path:
            base_cmd += ["-i", music_path]

        if variant_type == "speed":
            # Use a slightly lower speed to create a new rhythm and pacing feel.
            filter_chain = f"setpts=PTS/{speed}," + filters
        elif variant_type == "subtitle":
            filter_chain = filters
        else:
            filter_chain = filters

        cmd = base_cmd + [
            "-vf", filter_chain,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "24",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
        ]

        self._run_ffmpeg(cmd, f"Generate {variant_type} variant for {source_video.name}")
        return output_path

    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        mode: str = "auto",
        per_video_count: int = 4,
        title: str = "Original Drama",
        speed: float = 0.9,
        music_path: str | None = None,
    ) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        videos = self._find_videos(input_dir)
        report = {"mode": mode, "generated": []}

        if not videos:
            print(f"[WARN] No video files found in {input_dir}")
            return report

        variant_order = {
            "auto": ["color", "subtitle", "speed", "reframe"],
            "color": ["color"],
            "subtitle": ["subtitle"],
            "speed": ["speed"],
            "music": ["music"],
            "reframe": ["reframe"],
        }

        selected = variant_order.get(mode, ["color"])

        for video in videos:
            for variant_type in selected[:max(1, min(per_video_count, len(selected)))]:
                if mode == "auto" and variant_type == "speed":
                    current_speed = speed
                else:
                    current_speed = 1.0

                out_path = self.generate_variant(
                    source_video=video,
                    output_dir=output_dir,
                    variant_type=variant_type,
                    title=title,
                    speed=current_speed,
                    music_path=music_path,
                )
                report["generated"].append({
                    "source": str(video),
                    "output": str(out_path),
                    "variant_type": variant_type,
                })

        report_path = output_dir / "report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report


if __name__ == "__main__":
    print("This module is intended to be used via main.py")
    sys.exit(1)
