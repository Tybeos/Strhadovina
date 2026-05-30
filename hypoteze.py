"""Scratchpad for testing random ideas about how the cipher is built.

Each hypothesis transforms the cipher text some way and is scored with the same
yardsticks the other tools use: index of coincidence, the best-fitting scheme's
chi-squared, and how many common English words the decryption contains. New
ideas are added as functions and registered in HYPOTHESES; this file grows over
time. A hypothesis looks promising when IoC moves toward English (0.0667),
chi-squared drops well below the random baseline, and word hits jump.
"""

from pathlib import Path

from solve import (
    COMMON_WORDS,
    SCHEMES,
    chi_squared,
    count_word_hits,
    decrypt_scheme,
    detect_key_length,
    recover_key,
)
from statistic import index_of_coincidence, split_into_columns

HERE = Path(__file__).resolve().parent
ONELINE = HERE / "cipher_oneline.txt"

ORD_A = ord("A")
ORD_Z = ord("Z")


def best_decryption(text):
    """Returns the (scheme, chi-squared, plaintext) with the best English fit."""
    key_length = detect_key_length(text)
    results = []
    for scheme in SCHEMES:
        plaintext = decrypt_scheme(text, recover_key(text, key_length, scheme), scheme)
        results.append((scheme, chi_squared(plaintext), plaintext))
    return min(results, key=lambda result: result[1])


def evaluate(label, text):
    """Scores one transformed text and prints a one-line verdict."""
    ioc = index_of_coincidence(text)
    scheme, chi, plaintext = best_decryption(text)
    hits = count_word_hits(plaintext, COMMON_WORDS)
    print(f"{label:<28} IoC={ioc:.4f}  best={scheme:<8} chi2={chi:7.1f}  words={hits}")


def atbash(text):
    """Mirrors the alphabet, A<->Z, B<->Y and so on."""
    return "".join(chr(ORD_Z - (ord(character) - ORD_A)) for character in text)


def hypothesis_as_is(text):
    """Baseline: the cipher unchanged."""
    evaluate("as-is", text)


def hypothesis_reversed(text):
    """Idea: the plaintext was written backwards before enciphering."""
    evaluate("reversed", text[::-1])


def hypothesis_atbash(text):
    """Idea: an Atbash pass sits on top of the cipher."""
    evaluate("atbash", atbash(text))


MOON_KEYS = [
    "THIRTEENMOONS", "FULLMOON", "FULLMOONS", "NEWMOON", "HARVESTMOON",
    "BLOODMOON", "MOONLIGHT", "MOONPHASE", "CRESCENT", "MOONLIT", "MOON",
    "MOONS", "LUNAR", "LUNA", "MESIC", "UPLNEK", "MOONCHILD", "WANINGMOON",
]


def try_keyword(text, keyword):
    """Decrypts with a fixed keyword across all schemes, returns the best fit."""
    results = [(scheme, chi_squared(decrypt_scheme(text, keyword, scheme)),
                decrypt_scheme(text, keyword, scheme)) for scheme in SCHEMES]
    return min(results, key=lambda result: result[1])


def hypothesis_moon_keywords(text):
    """Idea: the key is a moon or full-moon themed word (13 moons in a year)."""
    print("  moon-themed keys (sorted by chi-squared, lower is better):")
    scored = []
    for keyword in MOON_KEYS:
        scheme, chi, plaintext = try_keyword(text, keyword)
        scored.append((keyword, scheme, chi, count_word_hits(plaintext, COMMON_WORDS)))
    for keyword, scheme, chi, hits in sorted(scored, key=lambda row: row[2]):
        print(f"    {keyword:<14} {scheme:<8} chi2={chi:7.1f}  words={hits}")


def score_plaintext(label, plaintext):
    """Scores an already-decrypted plaintext directly, no scheme solving."""
    ioc = index_of_coincidence(plaintext)
    chi = chi_squared(plaintext)
    hits = count_word_hits(plaintext, COMMON_WORDS)
    print(f"{label:<28} IoC={ioc:.4f}  chi2={chi:7.1f}  words={hits}")


def reassemble_columns(columns, length, key_length):
    """Interleaves decrypted columns back into the original character order."""
    return "".join(columns[j % key_length][j // key_length] for j in range(length))


def hypothesis_keylength_sweep(text):
    """Idea: 13 is only a harmonic; the true period might be longer."""
    print("  key-length sweep (best chi-squared over all schemes, top 8):")
    rows = []
    for key_length in range(2, 41):
        best = min(chi_squared(decrypt_scheme(text, recover_key(text, key_length, s), s))
                   for s in SCHEMES)
        rows.append((key_length, best))
    for key_length, chi in sorted(rows, key=lambda row: row[1])[:8]:
        print(f"    len={key_length:<3} chi2={chi:7.1f}")


COPRIME = [1, 3, 5, 7, 9, 11, 15, 17, 19, 21, 23, 25]
INVERSE = {a: pow(a, -1, 26) for a in COPRIME}


def decrypt_affine_column(column, a, b):
    """Decrypts a column with an affine map: plaintext = a_inv * (cipher - b)."""
    inverse = INVERSE[a]
    return "".join(chr(inverse * ((ord(character) - ORD_A) - b) % 26 + ORD_A)
                   for character in column)


def best_affine_column(column):
    """Finds the affine (a, b) whose decryption best fits English."""
    return min(((chi_squared(decrypt_affine_column(column, a, b)), a, b)
                for a in COPRIME for b in range(26)), key=lambda row: row[0])


def hypothesis_affine_columns(text):
    """Idea: each column is an affine cipher (multiply and shift), not a pure shift."""
    key_length = detect_key_length(text)
    columns = split_into_columns(text, key_length)
    decrypted = [decrypt_affine_column(column, *best_affine_column(column)[1:])
                 for column in columns]
    plaintext = reassemble_columns(decrypted, len(text), key_length)
    score_plaintext("affine-columns", plaintext)


def porta_decrypt(text, key):
    """Decrypts with the reciprocal Porta tableau using a repeating key."""
    out = []
    for i, character in enumerate(text):
        row = (ord(key[i % len(key)]) - ORD_A) // 2
        value = ord(character) - ORD_A
        if value < 13:
            out.append(chr((value + row) % 13 + 13 + ORD_A))
        else:
            out.append(chr((value - 13 - row) % 13 + ORD_A))
    return "".join(out)


def best_porta_letter(column):
    """Finds the Porta key letter whose decryption best fits English."""
    return min(range(26),
               key=lambda k: chi_squared(porta_decrypt(column, chr(k + ORD_A))))


def hypothesis_porta(text):
    """Idea: it is a Porta cipher, not a Vigenere-family one."""
    key_length = detect_key_length(text)
    columns = split_into_columns(text, key_length)
    key = "".join(chr(best_porta_letter(column) + ORD_A) for column in columns)
    score_plaintext("porta", porta_decrypt(text, key))


def solve_autokey_chain(indices, text, primer):
    """Decrypts one plaintext-autokey chain given its primer letter."""
    out = []
    previous = primer
    for position in indices:
        plain = (ord(text[position]) - ORD_A - previous) % 26
        out.append(plain)
        previous = plain
    return out


def hypothesis_autokey_plaintext(text, m=None):
    """Idea: plaintext-autokey, key = short primer then the plaintext itself."""
    m = m or detect_key_length(text)
    plain = [""] * len(text)
    for start in range(m):
        indices = list(range(start, len(text), m))
        best = min(
            ((chi_squared("".join(chr(v + ORD_A)
                                  for v in solve_autokey_chain(indices, text, primer))),
              primer) for primer in range(26)), key=lambda row: row[0])
        for position, value in zip(indices, solve_autokey_chain(indices, text, best[1])):
            plain[position] = chr(value + ORD_A)
    score_plaintext(f"autokey-plain(m={m})", "".join(plain))


def hypothesis_autokey_ciphertext(text, m=None):
    """Idea: ciphertext-autokey; most letters decrypt as cipher[i] - cipher[i-m]."""
    m = m or detect_key_length(text)
    plain = []
    for i, character in enumerate(text):
        if i < m:
            plain.append(character)
        else:
            value = (ord(character) - ord(text[i - m])) % 26
            plain.append(chr(value + ORD_A))
    score_plaintext(f"autokey-cipher(m={m})", "".join(plain[m:]))


HYPOTHESES = [
    hypothesis_as_is,
    hypothesis_reversed,
    hypothesis_atbash,
    hypothesis_moon_keywords,
    hypothesis_keylength_sweep,
    hypothesis_affine_columns,
    hypothesis_porta,
    hypothesis_autokey_plaintext,
    hypothesis_autokey_ciphertext,
]


def main():
    """Runs every registered hypothesis against the cipher."""
    text = ONELINE.read_text(encoding="utf-8").strip()
    print(f"Testing {len(HYPOTHESES)} hypotheses on {len(text)} chars")
    print("(IoC English=0.0667 random=0.0385; lower chi2 and more words are better)")
    print()
    for hypothesis in HYPOTHESES:
        hypothesis(text)


if __name__ == "__main__":
    main()
