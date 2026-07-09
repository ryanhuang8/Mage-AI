#!/usr/bin/env python3
"""
Generate formatted output from a transcript already stored in the database.
Usage: python generate_test.py <transcript_id> --mode twitter|medical_case [--output out.txt]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import get_session, init_db
from generate import generate
from models import Generation, Transcript
from prompts import PROMPTS


def main():
    parser = argparse.ArgumentParser(
        description="Generate formatted output from a stored transcript"
    )
    parser.add_argument("transcript_id", type=int, help="ID of the transcript row to generate from")
    parser.add_argument("--mode", "-m", required=True, choices=list(PROMPTS), help="Output mode")
    parser.add_argument("--output", "-o", help="Also save output to this file")
    args = parser.parse_args()

    init_db()
    db = get_session()
    transcript = db.get(Transcript, args.transcript_id)
    if not transcript:
        print(f"ERROR: No transcript found with id {args.transcript_id}")
        sys.exit(1)

    print(f"Generating '{args.mode}' output for transcript_id={args.transcript_id}...")
    result = generate(transcript.text, args.mode)

    generation = Generation(transcript_id=transcript.id, mode=args.mode, output_text=result)
    db.add(generation)
    db.commit()
    print(f"Saved to database → generation_id={generation.id}")
    db.close()

    print("\n" + "─" * 60)
    print(result)
    print("─" * 60)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"\nAlso saved to '{args.output}'")


if __name__ == "__main__":
    main()
