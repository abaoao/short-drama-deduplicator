#!/usr/bin/env python3
import argparse
from pathlib import Path

from src.video_variant_tool import VideoVariantTool
from src.advanced_variant_tool import AdvancedVariantTool


def main():
    parser = argparse.ArgumentParser(
        description="Short-drama variant generator (basic + aggressive modes)."
    )
    parser.add_argument("--input", type=str, required=True, help="Input folder with source videos")
    parser.add_argument("--output", type=str, required=True, help="Output folder for variants")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "color", "subtitle", "speed", "music", "reframe", "aggressive"], help="Variant mode")
    parser.add_argument("--count", type=int, default=4, help="Variants per source")
    parser.add_argument("--title", type=str, default="Original Short Drama", help="Title for subtitle variants")
    parser.add_argument("--speed", type=float, default=0.95, help="Speed multiplier for speed variants")
    parser.add_argument("--music", type=str, default=None, help="Optional music file path")
    parser.add_argument("--aggr", type=int, default=2, choices=[1,2,3], help="Aggressiveness for aggressive mode (1..3)")
    args = parser.parse_args()

    if args.mode == "aggressive":
        adv = AdvancedVariantTool()
        report = adv.process_directory(
            input_dir=Path(args.input),
            output_dir=Path(args.output),
            aggressiveness=args.aggr,
            per_video_count=args.count,
            title=args.title,
            speed=args.speed,
            music_path=args.music,
        )
    else:
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

    print(f"[OK] Generated {len(report.get('generated', []))} variants at {args.output}")


if __name__ == "__main__":
    main()
