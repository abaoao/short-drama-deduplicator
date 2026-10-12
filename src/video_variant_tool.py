#!/usr/bin/env python3
import argparse
from pathlib import Path

from src.video_variant_tool import VideoVariantTool


def main():
    parser = argparse.ArgumentParser(
        description="Generate multiple edited variants of a short drama video to improve originality and pre-upload diversity."
    )
    parser.add_argument("--input", type=str, required=True, help="Folder that contains source videos")
    parser.add_argument("--output", type=str, required=True, help="Folder for generated variants")
    parser.add_argument(
        "--mode",
        type=str,
        default="auto",
        choices=["auto", "color", "subtitle", "speed", "music", "reframe"],
        help="Variant generation mode",
    )
    parser.add_argument("--count", type=int, default=4, help="Number of variants to generate per source video")
    parser.add_argument("--title", type=str, default="Original Short Drama", help="Title for subtitle variants")
    parser.add_argument("--speed", type=float, default=0.9, help="Speed multiplier for speed variants")
    parser.add_argument("--music", type=str, default=None, help="Optional music file to layer into generated outputs")
    args = parser.parse_args()

    tool = VideoVariantTool()
    report = tool.process_directory(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        mode=args.mode,
        per_video_count=args.count,
        title=args.title,
        speed=args.speed,
        music_path=args.music,
    )

    print(f"[OK] Generated {len(report['generated'])} variants under: {args.output}")


if __name__ == "__main__":
    main()
