CIPHER = 'ABCDBDEAFGEHDIJAKLEGMNOCPQRDSBJTAPJOUIVILLCTPQWKRUXPQDSPKULAMCTNCVBSQVEPCKRKQOHPGYDCLAMEXHROQJYHCPJYFVMLSBSQEEYIMGEWLIGAONPQZMNTDMYSLCDILHFIJXJEGWOIMZSIEOSRREJHHHYSWRIXYWTJOZEJBWPJDOKSGKJOLQHYIXOFXVRSKXXFRKPOHSVAYNZPMRYXKOEPLNTTMAUBBYAAPOEELQOOXQMYLLCHIRRJWEJHWYCKYWSIHRTJCVIWOZOTIARYXDIYKHDFLAMSCPQKLMKYWSYMIDDKOLLCEPXPKOIIYIGJCSEXSFLOMHOSUCAUSJIHEACEIWMVWZEMRTNLVGOPHKQVMICMSOTAVAVSPMEHPCEGKEBETXHRMPCELMKYUQRIUNMSWTCLAPQRBPPBGPEJSHXEMJVPNMRDGDRKDMNOCARIQVPIQRYXVVPOOYIFRHXBSIRESMHVXXFLSACILLLSWZVMICPCEFLCVOLJNSRLLCUTUXLMTDSEIWVDCDXLODNRLYQCVBJTKKOXMRLSABESCIHEVRSLPRZPIXQONMJMJMPTSXIIWXLYPEJSHXLAMLOZKKXKYYEKMNOPSIWPVOBLXASEXGRDWMDCAPMUNMSOYOMKUPXORYXAWQHRAKZTAVBBYMZMHHHYTKIDQPLLLLSOTPMBBIKOGUSDGSS'

WORDS = [
    'ARGYNVOSTHOLT', 'BARONVALLAKOV', 'BAROVIAFOREVE',
    'BAROVIANMISTS', 'BLOODMOONRISE', 'CASTLERAVENLO',
    'CHILDOFBAROVI', 'COUNTOFBAROVI', 'CURSEOFSTRAHD',
    'DARKLORDOFRAV', 'DARKLORDSTRAH', 'DEVILOFBAROVI',
    'FULLMOONNIGHT', 'HEARTOFSORROW', 'HOLYRAVENKIND',
    'IREENAKOLYANA', 'KASIMIRVELIKO', 'LANDOFBAROVIA',
    'LORDOFBAROVIA', 'MADAMEVATAROK', 'MISTSOFBAROVI',
    'OLDBONEGRINDE', 'RAVENLOFTLAND', 'SAINTMARKOVIA',
    'SERGEIZAROVIC', 'STRAHDTHEDARK', 'STRAHDVONZARO',
    'STRAHDZAROVIC', 'SYMBOLRAVENKI', 'TATYANAREBORN',
    'THEAMBERTEMPL', 'THECOUNTSTRAH', 'THEDARKPOWERS',
    'THELANDOFMIST', 'THEMISTSOFBAR', 'THEMISTYLANDS',
    'THETAROKKADEC', 'THETHREEFANES', 'THETOMEOFSTRA',
    'THIRTEENMOONS', 'VAMPIRESTRAHD', 'VARGASVALLAKO',
    'VASILIVONHOLT', 'WIZARDOFWINES',
]


"""One-file Quagmire key tester for the Strahd cipher (console output only).

Everything is embedded: the cipher text and the 13-letter Curse-of-Strahd
keyword list. The ONLY external file needed is english_quadgrams.txt in the same
folder (the English quadgram table; too big to embed):
  https://raw.githubusercontent.com/jameslyons/python_cryptanalysis/master/quadgrams.txt

The cipher is a Quagmire: a Vigenere of period 13 over a scrambled 26-symbol
alphabet. For each 13-letter key this fixes the key, hill-climbs the alphabet to
fit English (quadgram score), and prints the result. A correct key scores around
-2800 (IoC ~0.066) and yields readable text; wrong keys sit near -4800.

Run:
  python3 strahd_onefile.py            test every embedded keyword, ranked
  python3 strahd_onefile.py MYKEYWORD  test one 13-letter keyword
"""

import math
import random
import sys
from collections import Counter
from pathlib import Path

QUADGRAM_FILE = Path(__file__).resolve().parent / "english_quadgrams.txt"
KEY_LENGTH = 13
RESTARTS = 12


def load_quadgrams(path):
    """Loads quadgram log10 probabilities and a floor for unseen quadgrams."""
    counts, total = {}, 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        quad, count = line.split()
        counts[quad] = int(count)
        total += int(count)
    log_probs = {q: math.log10(c / total) for q, c in counts.items()}
    return log_probs, math.log10(0.01 / total)


def quadgram_score(text, log_probs, floor):
    """Returns the English quadgram log-probability of the text."""
    return sum(log_probs.get(text[i:i + 4], floor) for i in range(len(text) - 3))


def decrypt(labels, perm, key):
    """Decrypts: plaintext = perm[label] - key (mod 26), key repeating."""
    klen = len(key)
    return "".join(chr((perm[labels[i]] - key[i % klen]) % 26 + 65)
                   for i in range(len(labels)))


def index_of_coincidence(text):
    """Returns the index of coincidence (a readability sanity check)."""
    total = len(text)
    if total < 2:
        return 0.0
    counts = Counter(text)
    return sum(n * (n - 1) for n in counts.values()) / (total * (total - 1))


def hill_climb(labels, key, log_probs, floor, rng):
    """Steepest-ascent hill-climb of the alphabet permutation from a random start."""
    perm = list(range(26))
    rng.shuffle(perm)
    current = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
    improved = True
    while improved:
        improved = False
        for a in range(25):
            for b in range(a + 1, 26):
                perm[a], perm[b] = perm[b], perm[a]
                score = quadgram_score(decrypt(labels, perm, key), log_probs, floor)
                if score > current:
                    current = score
                    improved = True
                else:
                    perm[a], perm[b] = perm[b], perm[a]
    return current, perm


def test_key(labels, keyword, log_probs, floor):
    """Tests one keyword, returns (best score, plaintext)."""
    key = [ord(c) - 65 for c in keyword]
    best = None
    for seed in range(RESTARTS):
        score, perm = hill_climb(labels, key, log_probs, floor, random.Random(seed))
        if best is None or score > best[0]:
            best = (score, decrypt(labels, perm, key))
    return best


def main():
    """Tests the given keyword, or every embedded keyword, printing to console."""
    log_probs, floor = load_quadgrams(QUADGRAM_FILE)
    labels = [ord(c) - 65 for c in CIPHER]

    keywords = [sys.argv[1].strip().upper()] if len(sys.argv) > 1 else WORDS
    bad = [k for k in keywords if len(k) != KEY_LENGTH or not k.isalpha()]
    if bad:
        print("Skipping non-13-letter keys:", bad)
    keywords = [k for k in keywords if len(k) == KEY_LENGTH and k.isalpha()]

    print(f"Testing {len(keywords)} key(s). Correct key ~ -2800 / IoC 0.066; "
          "wrong ~ -4800.\n")
    results = []
    for keyword in keywords:
        score, plaintext = test_key(labels, keyword, log_probs, floor)
        results.append((score, keyword, plaintext))
        print(f"{keyword}: score={score:.0f}  IoC={index_of_coincidence(plaintext):.4f}")

    results.sort(reverse=True)
    best = results[0]
    print("\nBEST:", best[1], f"(score {best[0]:.0f}, IoC {index_of_coincidence(best[2]):.4f})")
    print(best[2])
    if best[0] > -3500:
        print("\n>>> Looks promising, read the text above.")
    else:
        print("\n>>> Nothing cracked (all near random). Key is not in this list.")


if __name__ == "__main__":
    main()
