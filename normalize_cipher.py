"""Normalizes cipher_raw.txt into clean text variants.

Reads the spaced-out source cipher and produces:
  - cipher_nospaces.txt: each line stripped of whitespace, line structure kept
  - cipher_oneline.txt:  all non-empty lines joined into a single line
  - random_oneline.txt:  random baseline lines, each the same length as oneline
"""

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "cipher_raw.txt"
NOSPACES = HERE / "cipher_nospaces.txt"
ONELINE = HERE / "cipher_oneline.txt"
RANDOM_ONELINE = HERE / "random_oneline.txt"
RANDOM_LINES = 1000


def strip_whitespace_per_line(text):
    """Removes all whitespace from each line, keeping the line structure."""
    return ["".join(line.split()) for line in text.splitlines()]


def join_non_empty(lines):
    """Joins all non-empty lines into one continuous string."""
    return "".join(line for line in lines if line)


def random_lines(alphabet, length, count):
    """Builds count lines of random characters, each length long."""
    return ["".join(random.choice(alphabet) for _ in range(length))
            for _ in range(count)]


def main():
    """Reads the raw cipher and writes the nospaces and oneline variants."""
    raw = RAW.read_text(encoding="utf-8")
    raw_chars = sum(1 for char in raw if not char.isspace())
    print(f"raw      -> {RAW.name} ({raw_chars} chars)")

    nospaces_lines = strip_whitespace_per_line(raw)
    NOSPACES.write_text("\n".join(nospaces_lines) + "\n", encoding="utf-8")

    oneline = join_non_empty(nospaces_lines)
    ONELINE.write_text(oneline + "\n", encoding="utf-8")

    alphabet = sorted(set(oneline))
    randoms = random_lines(alphabet, len(oneline), RANDOM_LINES)
    RANDOM_ONELINE.write_text("\n".join(randoms) + "\n", encoding="utf-8")

    print(f"nospaces -> {NOSPACES.name} ({sum(len(l) for l in nospaces_lines)} chars)")
    print(f"oneline  -> {ONELINE.name} ({len(oneline)} chars)")
    print(f"random   -> {RANDOM_ONELINE.name} ({RANDOM_LINES} lines x {len(oneline)} chars)")


if __name__ == "__main__":
    main()
