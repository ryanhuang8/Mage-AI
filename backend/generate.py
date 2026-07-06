# generate.py
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from prompts import PROMPTS

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate(transcript_text: str, mode: str) -> str:
    """Generate formatted output (e.g. a twitter thread or medical case note) from a transcript."""
    if mode not in PROMPTS:
        raise ValueError(f"Unknown mode '{mode}'. Available modes: {list(PROMPTS)}")

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2048,
        system=PROMPTS[mode],
        messages=[{"role": "user", "content": transcript_text}],
    )
    text_blocks = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_blocks)
