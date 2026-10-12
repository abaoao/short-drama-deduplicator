#!/usr/bin/env python3
import argparse
from pathlib import Path

from src.video_variant_tool import VideoVariantTool


def main():
    parser = argparse.ArgumentParser(description="Generate alternative versions of short drama videos.")
    parser.add_argument("--input", type=str, required=True, help="Input directory containing source videos")
    parser.add_argument("--output", type=str, required=True, help="Output directory for generated variants")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "color", "subtitle", "speed", "music", "reframe"], help="Variant generation mode")
    parser.add_argument("--count", type=int, default=4, help="How many variants to generate per source video")
    parser.add_argument("--title", type=str, default="Original Drama", help="Title to overlay in subtitle variants")
    parser.add_argument("--speed", type=float, default=0.9, help="Speed multiplier for speed variants")
    parser.add_argument("--music", type=str, default=None, help="Optional background music path")
    args = parser.parse_args()

    tool = VideoVariantTool()
    tool.process_directory(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        mode=args.mode,
        per_video_count=args.count,
        title=args.title,
        speed=args.speed,
        music_path=args.music,
    )

    print(f"[OK] Generated variants in: {args.output}")


if __name__ == "__main__":
    main()
