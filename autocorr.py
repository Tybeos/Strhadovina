"""Full autocorrelation of the cipher across every shift.

For each shift from 1 to nearly the whole length, slides the text over itself
and counts matching letters. Multiples of the period 13 are marked so the
repeating pattern is visible across the entire text. Writes autocorr_full.txt.
High shifts compare few letters, so their rates are noisy; the 'pairs' column
shows how many letters were compared.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
AUTOCORR = HERE / "autocorr_full.txt"
PERIOD = 13
RELIABLE_MAX = 351


def match_rate(text, offset):
    """Returns (pairs, fraction matching) for the text shifted by offset."""
    pairs = len(text) - offset
    if pairs < 1:
        return 0, 0.0
    matches = sum(1 for i in range(pairs) if text[i] == text[i + offset])
    return pairs, matches / pairs


def bar(rate):
    """Renders a bar that grows with the match rate."""
    return "#" * max(0, round((rate - 0.030) * 400))


def build_report(text):
    """Builds the full autocorrelation table and a summary as text."""
    rows = [(offset, *match_rate(text, offset)) for offset in range(1, len(text) - 1)]

    reliable = [(o, r) for o, p, r in rows if o <= RELIABLE_MAX]
    multiples = [r for o, r in reliable if o % PERIOD == 0]
    others = [r for o, r in reliable if o % PERIOD != 0]
    avg_mult = sum(multiples) / len(multiples)
    avg_other = sum(others) / len(others)

    lines = ["Full autocorrelation (slide the text and count matching letters)",
             f"Multiples of {PERIOD} are marked. Random per-shift level ~0.0385 (=1/26).",
             "High shifts compare few letters (see 'pairs') and get noisy.",
             "",
             f"Average match rate over shifts 1-{RELIABLE_MAX}:",
             f"  at multiples of {PERIOD}: {avg_mult:.4f}",
             f"  at all other shifts   : {avg_other:.4f}",
             f"  -> multiples of {PERIOD} are {(avg_mult / avg_other - 1) * 100:+.0f}% higher",
             "",
             "shift | pairs | rate   | bar                          | mark",
             "------+-------+--------+------------------------------+------"]
    for offset, pairs, rate in rows:
        mark = f"<== {offset // PERIOD} x {PERIOD}" if offset % PERIOD == 0 else ""
        lines.append(f" {offset:4d} | {pairs:5d} | {rate:.4f} | {bar(rate):<28} | {mark}")
    return "\n".join(lines) + "\n"


def main():
    """Writes the full autocorrelation table and prints the summary."""
    text = ONELINE.read_text(encoding="utf-8").strip()
    report = build_report(text)
    AUTOCORR.write_text(report, encoding="utf-8")
    print("\n".join(report.splitlines()[:8]))
    print(f"...\n(full table of {len(text) - 2} shifts written to {AUTOCORR.name})")


if __name__ == "__main__":
    main()
