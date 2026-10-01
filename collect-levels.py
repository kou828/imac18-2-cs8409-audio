#!/usr/bin/env python3
"""Measure an ALSA S32_LE stream in memory and print level statistics only."""

import argparse
import json
import math
import shutil
import struct
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="ALSA device, e.g. hw:CARD=PCH,DEV=0")
    parser.add_argument("--seconds", type=int, default=5, metavar="1..600")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error("--seconds must be between 1 and 600")

    arecord = shutil.which("arecord")
    if not arecord:
        parser.error("arecord is not installed")

    command = [
        arecord,
        "--quiet",
        "--device", args.device,
        "--file-type", "raw",
        "--format=S32_LE",
        "--rate=44100",
        "--channels=2",
        "--duration", str(args.seconds),
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    assert process.stdout is not None

    byte_tail = b""
    frames = 0
    scale = 2147483648.0
    channel_stats = [
        {"sum": 0, "sum_squares": 0, "peak": 0, "zeros": 0, "clipped": 0}
        for _ in range(2)
    ]
    window_frames = 0
    window_stats = [
        {"sum": 0, "sum_squares": 0, "peak": 0} for _ in range(2)
    ]
    windows = []

    def finish_window() -> None:
        nonlocal window_frames, window_stats
        if not window_frames:
            return
        levels = []
        for stats in window_stats:
            mean = stats["sum"] / window_frames
            ac_rms = math.sqrt(max(0.0, stats["sum_squares"] / window_frames - mean * mean))
            levels.append({
                "ac_rms_dbfs": round(20.0 * math.log10(ac_rms / scale), 2) if ac_rms else None,
                "peak_dbfs": round(20.0 * math.log10(stats["peak"] / scale), 2) if stats["peak"] else None,
            })
        windows.append({"start_seconds": len(windows), "channels": levels})
        window_frames = 0
        window_stats = [{"sum": 0, "sum_squares": 0, "peak": 0} for _ in range(2)]

    try:
        while True:
            block = process.stdout.read(16384)
            if not block:
                break
            block = byte_tail + block
            complete = len(block) - (len(block) % 8)
            byte_tail = block[complete:]
            for left, right in struct.iter_unpack("<ii", block[:complete]):
                for index, sample in enumerate((left, right)):
                    magnitude = abs(sample)
                    stats = channel_stats[index]
                    stats["sum"] += sample
                    stats["sum_squares"] += sample * sample
                    stats["zeros"] += sample == 0
                    stats["clipped"] += magnitude >= 2147483000
                    stats["peak"] = max(stats["peak"], magnitude)
                    current_window = window_stats[index]
                    current_window["sum"] += sample
                    current_window["sum_squares"] += sample * sample
                    current_window["peak"] = max(current_window["peak"], magnitude)
                frames += 1
                window_frames += 1
                if window_frames == 44100:
                    finish_window()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        print("capture interrupted; no audio was saved", file=sys.stderr)
        return 130
    finally:
        process.stdout.close()

    result = process.wait()
    if result != 0:
        print(f"arecord exited with status {result}; no audio was saved", file=sys.stderr)
        return 1
    if byte_tail:
        print("incomplete stereo PCM frame; no audio was saved", file=sys.stderr)
        return 1
    finish_window()
    if not frames:
        print("no PCM samples received; no audio was saved", file=sys.stderr)
        return 1

    channels = []
    for stats in channel_stats:
        mean = stats["sum"] / frames
        rms = math.sqrt(stats["sum_squares"] / frames)
        ac_rms = math.sqrt(max(0.0, stats["sum_squares"] / frames - mean * mean))
        channels.append({
            "mean_dbfs": round(20.0 * math.log10(abs(mean) / scale), 2) if mean else None,
            "rms_dbfs": round(20.0 * math.log10(rms / scale), 2) if rms else None,
            "ac_rms_dbfs": round(20.0 * math.log10(ac_rms / scale), 2) if ac_rms else None,
            "peak_dbfs": round(20.0 * math.log10(stats["peak"] / scale), 2) if stats["peak"] else None,
            "zero_fraction": round(stats["zeros"] / frames, 6),
            "clipped_fraction": round(stats["clipped"] / frames, 6),
        })
    result_data = {
        "device": args.device,
        "requested_seconds": args.seconds,
        "format": "S32_LE/44100/2ch",
        "frames": frames,
        "channels": channels,
        "one_second_windows": windows,
        "audio_saved": False,
    }
    print(json.dumps(result_data, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
