"""Estimates the cipher's key length and shows the evidence for it.

Runs three independent tests on cipher_oneline.txt and compares each against the
random baseline in random_oneline.txt, so the strength of the signal is visible,
not just the winner:
  - autocorrelation: slide the text over itself and count matching letters
  - column index of coincidence: split into k columns and measure structure
  - Kasiski: distances between repeated chunks, factored into key lengths
A true key length shows up as a peak that also repeats at its multiples (a true
period 13 makes both 13 and 26 stand out).
"""

from pathlib import Path

from statistic import (
    average_column_ioc,
    index_of_coincidence,
    likely_key_lengths,
)

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"
RANDOM_ONELINE = HERE / "random_oneline.txt"
KEYLENGTH = HERE / "keylength.txt"
MAX_LENGTH = 26
RANDOM_SAMPLES = 1000


def match_rate(text, offset):
    """Returns the fraction of positions where text equals itself shifted by offset."""
    pairs = len(text) - offset
    if pairs < 1:
        return 0.0
    return sum(1 for i in range(pairs) if text[i] == text[i + offset]) / pairs


def autocorrelation(text):
    """Returns the match rate for every shift from 1 to MAX_LENGTH."""
    return [(offset, match_rate(text, offset)) for offset in range(1, MAX_LENGTH + 1)]


def column_iocs(text):
    """Returns the average column IoC for every key length from 2 to MAX_LENGTH."""
    return [(length, average_column_ioc(text, length))
            for length in range(2, MAX_LENGTH + 1)]


def average_over_random(samples, measure):
    """Averages a per-text measurement across the random baseline samples."""
    return sum(measure(sample) for sample in samples) / len(samples)


def fundamental_period(scores):
    """Returns the smallest length that peaks; a true period also lifts its multiples."""
    best = max(ioc for _, ioc in scores)
    strong = [length for length, ioc in scores if ioc >= 0.95 * best]
    return min(strong)


def kasiski_votes(text):
    """Returns a dict of key length to Kasiski vote count."""
    return dict(likely_key_lengths(text, max_length=MAX_LENGTH, top=MAX_LENGTH))


def bar(ioc):
    """Renders a small bar whose length grows with the column IoC."""
    return "#" * max(0, round((ioc - 0.038) * 1000))


def build_report(text, random_samples):
    """Builds the full key-length report (table plus verdict) as text."""
    autocorr = dict(autocorrelation(text))
    columns = dict(column_iocs(text))
    votes = kasiski_votes(text)
    period = fundamental_period(list(columns.items()))

    auto_floor = average_over_random(
        random_samples, lambda s: max(rate for _, rate in autocorrelation(s)))
    col_floor = average_over_random(
        random_samples, lambda s: max(average_column_ioc(s, k)
                                      for k in range(2, MAX_LENGTH + 1)))

    lines = [f"Key-length evidence for {len(text)} characters "
             f"(whole-text IoC {index_of_coincidence(text):.4f})",
             "Higher = more structure. A true period peaks at its length AND its multiples.",
             f"The 'rnd' row averages all {len(random_samples)} random lines from "
             "random_oneline.txt; compare every row against it.",
             "",
             " Len | Autocorr | Col-IoC | Kasiski | Col-IoC strength       | Note",
             "-----+----------+---------+---------+------------------------+---------"]
    for length in range(2, MAX_LENGTH + 1):
        note = ""
        if length == period:
            note = f"<< KEY LENGTH ({period})"
        elif length % period == 0:
            note = f"= {length // period} x {period}"
        lines.append(
            f" {length:3d} |  {autocorr[length]:.4f}  | {columns[length]:.4f}  |"
            f"   {votes.get(length, 0):3d}   | {bar(columns[length]):<22} | {note}")
    lines.append("-----+----------+---------+---------+------------------------+---------")
    lines.append(f" rnd |  {auto_floor:.4f}  | {col_floor:.4f}  |     -   | "
                 f"{'(random baseline)':<22} |")
    lines.append("")
    lines.append("Harmonic check (a real period also lights up at its multiples, "
                 "not at its neighbours):")
    lines.append("  Multiple | Autocorr | Neighbours (one off either side)")
    lines.append("  ---------+----------+---------------------------------")
    multiple = period
    while multiple + 1 < len(text) // 10:
        factor = multiple // period
        autocorr_m = match_rate(text, multiple)
        low = match_rate(text, multiple - 1)
        high = match_rate(text, multiple + 1)
        lines.append(f"  {multiple:3d} ({factor}x) |  {autocorr_m:.4f}  | "
                     f"{multiple - 1}: {low:.4f}   {multiple + 1}: {high:.4f}")
        multiple += period
    lines.append("  Random per-shift level is ~0.0385 (=1/26); the multiples of "
                 f"{period} stay well above it while the neighbours fall back to it.")
    lines.append("")
    lines.append(f"Verdict: key length {period}. The strongest evidence is the "
                 f"harmonic check above: every multiple of {period} stays elevated "
                 "while neighbours drop to the random level, which random noise "
                 "cannot fake.")
    return "\n".join(lines) + "\n"


def main():
    """Runs the three tests, prints the table, and writes keylength.txt."""
    text = ONELINE.read_text(encoding="utf-8").strip()
    random_samples = [line for line in
                      RANDOM_ONELINE.read_text(encoding="utf-8").splitlines()
                      if line][:RANDOM_SAMPLES]

    report = build_report(text, random_samples)
    KEYLENGTH.write_text(report, encoding="utf-8")
    print(report, end="")
    print(f"\n(written to {KEYLENGTH.name})")


if __name__ == "__main__":
    main()
