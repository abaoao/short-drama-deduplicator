"""
Advanced variant generator — scene-aware reordering, trimming, pitch & speed tweaks,
and other transformations that increase perceptual difference vs. original.

This module uses PySceneDetect (scenedetect) to split scenes and FFmpeg to re-encode.
"""
from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

try:
    from scenedetect import VideoManager, SceneManager
    from scenedetect.detectors import ContentDetector
except Exception:
    raise ImportError("scenedetect (PySceneDetect) is required for aggressive mode. Install with: pip install scenedetect")


@dataclass
class SceneRange:
    start: float
    end: float


class AdvancedVariantTool:
    """Scene-aware transformations to produce significantly different variants."""

    def __init__(self):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found in PATH — install ffmpeg before using this tool")

    def _detect_scenes(self, video_path: Path, downscale: int = 2) -> List[SceneRange]:
        vm = VideoManager([str(video_path)])
        sm = SceneManager()
        sm.add_detector(ContentDetector())
        vm.set_downscale_factor(downscale)
        try:
            vm.start()
            sm.detect_scenes(frame_source=vm)
            scene_list = sm.get_scene_list()
        finally:
            vm.release()

        ranges: List[SceneRange] = []
        for start, end in scene_list:
            ranges.append(SceneRange(start.get_seconds(), end.get_seconds()))
        # If no scenes detected, fallback to single full range
        if not ranges:
            duration = self._get_duration(video_path)
            ranges = [SceneRange(0.0, duration)]
        return ranges

    def _get_duration(self, path: Path) -> float:
        # use ffprobe
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        out = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(out.stdout.strip())
        except Exception:
            return 0.0

    def _extract_segment(self, src: Path, start: float, end: float, out_path: Path):
        duration = end - start
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-ss", f"{start:.3f}",
            "-t", f"{duration:.3f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)

    def _concat_segments(self, segs: List[Path], out_path: Path):
        # create concat list file
        with tempfile.NamedTemporaryFile('w', delete=False, encoding='utf-8') as f:
            for s in segs:
                f.write(f"file '{s.as_posix()}'\n")
            list_path = Path(f.name)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "24",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)
        try:
            list_path.unlink()
        except Exception:
            pass

    def _audio_pitch_shift(self, src: Path, out_path: Path, semitones: float):
        # Change pitch without changing duration by adjusting sample rate then resampling
        # factor = 2^(semitones/12)
        factor = 2 ** (semitones / 12.0)
        # asetrate needs integer; base sample rate 44100
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-c:v", "copy",
            "-af", f"asetrate=44100*{factor:.6f},aresample=44100,atempo=1/{factor:.6f}",
            "-c:a", "aac",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)

    def _speed_change(self, src: Path, out_path: Path, speed: float):
        # Adjust playback speed (video+audio)
        vf = f"setpts=PTS/{speed}"
        # atempo supports 0.5-2.0; chain if outside range
        atempo = speed
        if atempo <= 0:
            atempo = 1.0
        atempo_filters = []
        if atempo < 0.5:
            # chain multiples
            n = math.ceil(math.log(0.5 / atempo, 0.5))
            parts = [str(max(0.5, atempo ** (1/(n+1)))) for _ in range(n+1)]
            atempo_filters = ",".join([f"atempo={p}" for p in parts])
        elif atempo > 2.0:
            n = math.ceil(math.log(atempo / 2.0, 2.0))
            parts = [str(min(2.0, atempo ** (1/(n+1)))) for _ in range(n+1)]
            atempo_filters = ",".join([f"atempo={p}" for p in parts])
        else:
            atempo_filters = f"atempo={atempo:.6f}"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-filter:v", vf,
            "-af", atempo_filters,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "24",
            "-c:a", "aac",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)

    def _reframe_zoompan(self, src: Path, out_path: Path):
        # apply subtle zoom/pan using zoompan can be heavy; use crop+scale variation instead
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-vf", "crop=iw*0.92:ih*0.92:iw*0.04:ih*0.04,scale=1280:720,format=yuv420p",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "24",
            "-c:a", "aac",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)

    def _maybe_insert_broll(self, segs: List[Path], broll_dir: Path | None, insert_ratio: float = 0.15) -> List[Path]:
        if not broll_dir:
            return segs
        if not broll_dir.exists():
            return segs
        brolls = sorted([p for p in broll_dir.iterdir() if p.suffix.lower() in {'.mp4', '.mov', '.mkv'}])
        if not brolls:
            return segs
        out = []
        for s in segs:
            out.append(s)
            if random.random() < insert_ratio:
                # pick random b-roll and take a short subclip (first 3s)
                b = random.choice(brolls)
                # create temp subclip
                tmp = Path(tempfile.mkdtemp()) / f"broll_{b.name}"
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(b),
                    "-t", "3",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "28",
                    "-c:a", "aac",
                    str(tmp),
                ]
                subprocess.run(cmd, check=True)
                out.append(tmp)
        return out

    def generate_aggressive_variant(
        self,
        source: Path,
        output_dir: Path,
        aggressiveness: int = 2,
        title: str = "",
        speed: float = 0.95,
        music_path: str | None = None,
        broll_dir: Path | None = None,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        # 1) Detect scenes
        scenes = self._detect_scenes(source)
        # Limit scenes for performance
        if len(scenes) > 100:
            # merge into 100 ranges approx
            factor = math.ceil(len(scenes) / 100)
            merged = []
            i = 0
            while i < len(scenes):
                start = scenes[i].start
                j = min(i + factor - 1, len(scenes) - 1)
                end = scenes[j].end
                merged.append(SceneRange(start, end))
                i += factor
            scenes = merged

        tmpdir = Path(tempfile.mkdtemp(prefix="advseg_"))
        seg_files: List[Path] = []
        # Extract scene segments
        for idx, r in enumerate(scenes):
            seg = tmpdir / f"seg_{idx:03d}.mp4"
            try:
                self._extract_segment(source, r.start, r.end, seg)
                seg_files.append(seg)
            except Exception:
                continue

        # Decide reordering strategy by aggressiveness
        segs = seg_files.copy()
        if aggressiveness == 1:
            # swap some adjacent pairs
            for i in range(0, len(segs) - 1, 2):
                if random.random() < 0.25:
                    segs[i], segs[i + 1] = segs[i + 1], segs[i]
        elif aggressiveness == 2:
            # moderate shuffle: split into chunks and shuffle chunks
            chunk = max(1, len(segs) // 6)
            chunks = [segs[i:i+chunk] for i in range(0, len(segs), chunk)]
            random.shuffle(chunks)
            segs = [s for c in chunks for s in c]
        else:
            # aggressive: full shuffle of segments
            random.shuffle(segs)

        # Optionally insert b-roll
        segs = self._maybe_insert_broll(segs, broll_dir, insert_ratio=0.2 if aggressiveness>=2 else 0.08)

        # Concatenate
        concatenated = tmpdir / f"concat_{source.stem}.mp4"
        self._concat_segments(segs, concatenated)

        # Apply pitch shift and/or speed tweak to final file
        out_name = f"{source.stem}_aggr{aggressiveness}.mp4"
        out_path = output_dir / out_name

        # apply small pitch shift and speed adjustments depending on aggressiveness
        semitones = (aggressiveness - 2) * 1.5  # -1.5, 0, +1.5
        target_speed = 1.0 if aggressiveness == 1 else (0.95 if aggressiveness == 2 else 0.93)

        # First change speed if needed
        if abs(target_speed - 1.0) > 0.001:
            sped = tmpdir / f"sp_{source.stem}.mp4"
            self._speed_change(concatenated, sped, target_speed)
        else:
            sped = concatenated

        # Then pitch shift slightly
        if abs(semitones) > 0.001:
            pitched = tmpdir / f"pt_{source.stem}.mp4"
            self._audio_pitch_shift(sped, pitched, semitones)
        else:
            pitched = sped

        # final optional reframe zoom/pan
        final_temp = tmpdir / f"final_{source.stem}.mp4"
        self._reframe_zoompan(pitched, final_temp)

        # Optionally mix background music
        if music_path:
            # mix music softly
            final_with_music = output_dir / f"{source.stem}_aggr{aggressiveness}_music.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(final_temp),
                "-i", str(music_path),
                "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=0.12[a1];[a0][a1]amix=inputs=2:duration=first[a]",
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                str(final_with_music),
            ]
            subprocess.run(cmd, check=True)
            shutil.move(str(final_with_music), str(out_path))
        else:
            shutil.move(str(final_temp), str(out_path))

        # Cleanup tmpdir could be left for debugging; keep minimal
        # shutil.rmtree(tmpdir)

        return out_path

    def process_directory(
        self,
        input_dir: Path,
        output_dir: Path,
        aggressiveness: int = 2,
        per_video_count: int = 3,
        title: str = "",
        speed: float = 0.95,
        music_path: str | None = None,
        broll_dir: str | None = None,
    ) -> dict:
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        videos = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.mp4', '.mov', '.mkv'}])
        report = {"mode": "aggressive", "generated": []}
        for v in videos:
            for i in range(per_video_count):
                out = self.generate_aggressive_variant(
                    source=v,
                    output_dir=output_dir,
                    aggressiveness=aggressiveness,
                    title=title,
                    speed=speed,
                    music_path=music_path,
                    broll_dir=Path(broll_dir) if broll_dir else None,
                )
                report["generated"].append({"source": str(v), "output": str(out), "aggressiveness": aggressiveness})
        report_path = output_dir / "aggr_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
