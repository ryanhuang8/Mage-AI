#!/usr/bin/env python3
"""
Generate formatted output from a transcript file.
Usage: python generate_test.py <path_to_transcript.txt> --mode twitter|medical_case [--output out.txt]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate import generate
from prompts import PROMPTS


def main():
    parser = argparse.ArgumentParser(description="Generate formatted output from a transcript")
    parser.add_argument("transcript_file", help="Path to the transcript .txt file")
    parser.add_argument("--mode", "-m", required=True, choices=list(PROMPTS), help="Output mode")
    parser.add_argument("--output", "-o", help="Output file (default: prints to stdout only)")
    args = parser.parse_args()

    if not os.path.exists(args.transcript_file):
        print(f"ERROR: File not found → '{args.transcript_file}'")
        sys.exit(1)

    with open(args.transcript_file, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    print(f"Generating '{args.mode}' output...")
    result = generate(transcript_text, args.mode)

    print("\n" + "─" * 60)
    print(result)
    print("─" * 60)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"\nSaved to '{args.output}'")


if __name__ == "__main__":
    main()
