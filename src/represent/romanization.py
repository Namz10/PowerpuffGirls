"""Deterministic offline romanization for Indic scripts.

Supports 7 Indic scripts:
1. Devanagari (Hindi, Marathi, Sanskrit)
2. Bengali (Bengali, Assamese)
3. Gujarati
4. Tamil
5. Telugu
6. Kannada
7. Malayalam

Preserves unknown code points, Latin characters, numbers, and punctuation.
"""

from typing import Dict, Optional

# Vowel mappings (Independent vowels)
INDEPENDENT_VOWELS: Dict[int, str] = {
    # Devanagari
    0x0905: "a", 0x0906: "aa", 0x0907: "i", 0x0908: "ee", 0x0909: "u", 0x090A: "oo",
    0x090B: "ri", 0x090E: "e", 0x090F: "e", 0x0910: "ai", 0x0912: "o", 0x0913: "o", 0x0914: "au",
    # Bengali
    0x0985: "a", 0x0986: "aa", 0x0987: "i", 0x0988: "ee", 0x0989: "u", 0x098A: "oo",
    0x098B: "ri", 0x098F: "e", 0x0990: "ai", 0x0993: "o", 0x0994: "au",
    # Gujarati
    0x0A85: "a", 0x0A86: "aa", 0x0A87: "i", 0x0A88: "ee", 0x0A89: "u", 0x0A8A: "oo",
    0x0A8B: "ri", 0x0A8F: "e", 0x0A90: "ai", 0x0A93: "o", 0x0A94: "au",
    # Tamil
    0x0B85: "a", 0x0B86: "aa", 0x0B87: "i", 0x0B88: "ee", 0x0B89: "u", 0x0B8A: "oo",
    0x0B8E: "e", 0x0B8F: "ee", 0x0B90: "ai", 0x0B92: "o", 0x0B93: "oo", 0x0B94: "au",
    # Telugu
    0x0C05: "a", 0x0C06: "aa", 0x0C07: "i", 0x0C08: "ee", 0x0C09: "u", 0x0C0A: "oo",
    0x0C0B: "ri", 0x0C0E: "e", 0x0C0F: "ee", 0x0C10: "ai", 0x0C12: "o", 0x0C13: "oo", 0x0C14: "au",
    # Kannada
    0x0C85: "a", 0x0C86: "aa", 0x0C87: "i", 0x0C88: "ee", 0x0C89: "u", 0x0C8A: "oo",
    0x0C8B: "ri", 0x0C8E: "e", 0x0C8F: "ee", 0x0C90: "ai", 0x0C92: "o", 0x0C93: "oo", 0x0C94: "au",
    # Malayalam
    0x0D05: "a", 0x0D06: "aa", 0x0D07: "i", 0x0D08: "ee", 0x0D09: "u", 0x0D0A: "oo",
    0x0D0B: "ri", 0x0D0E: "e", 0x0D0F: "ee", 0x0D10: "ai", 0x0D12: "o", 0x0D13: "oo", 0x0D14: "au",
}

# Dependent vowel signs (Matras)
DEPENDENT_VOWELS: Dict[int, str] = {
    # Devanagari
    0x093E: "aa", 0x093F: "i", 0x0940: "ee", 0x0941: "u", 0x0942: "oo",
    0x0943: "ri", 0x0946: "e", 0x0947: "e", 0x0948: "ai", 0x094A: "o", 0x094B: "o", 0x094C: "au",
    # Bengali
    0x09BE: "aa", 0x09BF: "i", 0x09C0: "ee", 0x09C1: "u", 0x09C2: "oo",
    0x09C3: "ri", 0x09C7: "e", 0x09C8: "ai", 0x09CB: "o", 0x09CC: "au",
    # Gujarati
    0x0ABE: "aa", 0x0ABF: "i", 0x0AC0: "ee", 0x0AC1: "u", 0x0AC2: "oo",
    0x0AC3: "ri", 0x0AC7: "e", 0x0AC8: "ai", 0x0ACB: "o", 0x0ACC: "au",
    # Tamil
    0x0BBE: "aa", 0x0BBF: "i", 0x0BC0: "ee", 0x0BC1: "u", 0x0BC2: "oo",
    0x0BC6: "e", 0x0BC7: "ee", 0x0BC8: "ai", 0x0BCA: "o", 0x0BCB: "oo", 0x0BCC: "au",
    # Telugu
    0x0C3E: "aa", 0x0C3F: "i", 0x0C40: "ee", 0x0C41: "u", 0x0C42: "oo",
    0x0C43: "ri", 0x0C46: "e", 0x0C47: "ee", 0x0C48: "ai", 0x0C4A: "o", 0x0C4B: "oo", 0x0C4C: "au",
    # Kannada
    0x0CBE: "aa", 0x0CBF: "i", 0x0CC0: "ee", 0x0CC1: "u", 0x0CC2: "oo",
    0x0CC3: "ri", 0x0CC6: "e", 0x0CC7: "ee", 0x0CC8: "ai", 0x0CCA: "o", 0x0CCB: "oo", 0x0CCC: "au",
    # Malayalam
    0x0D3E: "aa", 0x0D3F: "i", 0x0D40: "ee", 0x0D41: "u", 0x0D42: "oo",
    0x0D43: "ri", 0x0D46: "e", 0x0D47: "ee", 0x0D48: "ai", 0x0D4A: "o", 0x0D4B: "oo", 0x0D4C: "au",
}

# Consonant base mappings (inherent 'a' is added dynamically)
CONSONANTS: Dict[int, str] = {
    # Devanagari
    0x0915: "k", 0x0916: "kh", 0x0917: "g", 0x0918: "gh", 0x0919: "ng",
    0x091A: "ch", 0x091B: "chh", 0x091C: "j", 0x091D: "jh", 0x091E: "ny",
    0x091F: "t", 0x0920: "th", 0x0921: "d", 0x0922: "dh", 0x0923: "n",
    0x0924: "t", 0x0925: "th", 0x0926: "d", 0x0927: "dh", 0x0928: "n",
    0x092A: "p", 0x092B: "ph", 0x092C: "b", 0x092D: "bh", 0x092E: "m",
    0x092F: "y", 0x0930: "r", 0x0931: "r", 0x0932: "l", 0x0933: "l",
    0x0935: "v", 0x0936: "sh", 0x0937: "sh", 0x0938: "s", 0x0939: "h",
    0x0958: "q", 0x0959: "kh", 0x095A: "gh", 0x095B: "z", 0x095C: "r",
    0x095D: "rh", 0x095E: "f",

    # Bengali
    0x0995: "k", 0x0996: "kh", 0x0997: "g", 0x0998: "gh", 0x0999: "ng",
    0x099A: "ch", 0x099B: "chh", 0x099C: "j", 0x099D: "jh", 0x099E: "ny",
    0x099F: "t", 0x09A0: "th", 0x09A1: "d", 0x09A2: "dh", 0x09A3: "n",
    0x09A4: "t", 0x09A5: "th", 0x09A6: "d", 0x09A7: "dh", 0x09A8: "n",
    0x09AA: "p", 0x09AB: "ph", 0x09AC: "b", 0x09AD: "bh", 0x09AE: "m",
    0x09AF: "y", 0x09B0: "r", 0x09B2: "l", 0x09B6: "sh", 0x09B7: "sh",
    0x09B8: "s", 0x09B9: "h", 0x09DC: "r", 0x09DD: "rh", 0x09DF: "y",

    # Gujarati
    0x0A95: "k", 0x0A96: "kh", 0x0A97: "g", 0x0A98: "gh", 0x0A99: "ng",
    0x0A9A: "ch", 0x0A9B: "chh", 0x0A9C: "j", 0x0A9D: "jh", 0x0A9E: "ny",
    0x0A9F: "t", 0x0AA0: "th", 0x0AA1: "d", 0x0AA2: "dh", 0x0AA3: "n",
    0x0AA4: "t", 0x0AA5: "th", 0x0AA6: "d", 0x0AA7: "dh", 0x0AA8: "n",
    0x0AAA: "p", 0x0AAB: "ph", 0x0AAC: "b", 0x0AAD: "bh", 0x0AAE: "m",
    0x0AAF: "y", 0x0AB0: "r", 0x0AB2: "l", 0x0AB3: "l", 0x0AB5: "v",
    0x0AB6: "sh", 0x0AB7: "sh", 0x0AB8: "s", 0x0AB9: "h",

    # Tamil
    0x0B95: "k", 0x0B99: "ng", 0x0B9A: "ch", 0x0B9C: "j", 0x0B9E: "ny",
    0x0B9F: "t", 0x0BA3: "n", 0x0BA4: "t", 0x0BA8: "n", 0x0BA9: "n",
    0x0BAA: "p", 0x0BAE: "m", 0x0BAF: "y", 0x0BB0: "r", 0x0BB1: "r",
    0x0BB2: "l", 0x0BB3: "l", 0x0BB4: "zh", 0x0BB5: "v", 0x0BB6: "sh",
    0x0BB7: "sh", 0x0BB8: "s", 0x0BB9: "h",

    # Telugu
    0x0C15: "k", 0x0C16: "kh", 0x0C17: "g", 0x0C18: "gh", 0x0C19: "ng",
    0x0C1A: "ch", 0x0C1B: "chh", 0x0C1C: "j", 0x0C1D: "jh", 0x0C1E: "ny",
    0x0C1F: "t", 0x0C20: "th", 0x0C21: "d", 0x0C22: "dh", 0x0C23: "n",
    0x0C24: "t", 0x0C25: "th", 0x0C26: "d", 0x0C27: "dh", 0x0C28: "n",
    0x0C2A: "p", 0x0C2B: "ph", 0x0C2C: "b", 0x0C2D: "bh", 0x0C2E: "m",
    0x0C2F: "y", 0x0C30: "r", 0x0C31: "r", 0x0C32: "l", 0x0C33: "l",
    0x0C35: "v", 0x0C36: "sh", 0x0C37: "sh", 0x0C38: "s", 0x0C39: "h",

    # Kannada
    0x0C95: "k", 0x0C96: "kh", 0x0C97: "g", 0x0C98: "gh", 0x0C99: "ng",
    0x0C9A: "ch", 0x0C9B: "chh", 0x0C9C: "j", 0x0C9D: "jh", 0x0C9E: "ny",
    0x0C9F: "t", 0x0CA0: "th", 0x0CA1: "d", 0x0CA2: "dh", 0x0CA3: "n",
    0x0CA4: "t", 0x0CA5: "th", 0x0CA6: "d", 0x0CA7: "dh", 0x0CA8: "n",
    0x0CAA: "p", 0x0CAB: "ph", 0x0CAC: "b", 0x0CAD: "bh", 0x0CAE: "m",
    0x0CAF: "y", 0x0CB0: "r", 0x0CB1: "r", 0x0CB2: "l", 0x0CB3: "l",
    0x0CB5: "v", 0x0CB6: "sh", 0x0CB7: "sh", 0x0CB8: "s", 0x0CB9: "h",

    # Malayalam
    0x0D15: "k", 0x0D16: "kh", 0x0D17: "g", 0x0D18: "gh", 0x0D19: "ng",
    0x0D1A: "ch", 0x0D1B: "chh", 0x0D1C: "j", 0x0D1D: "jh", 0x0D1E: "ny",
    0x0D1F: "t", 0x0D20: "th", 0x0D21: "d", 0x0D22: "dh", 0x0D23: "n",
    0x0D24: "t", 0x0D25: "th", 0x0D26: "d", 0x0D27: "dh", 0x0D28: "n",
    0x0D2A: "p", 0x0D2B: "ph", 0x0D2C: "b", 0x0D2D: "bh", 0x0D2E: "m",
    0x0D2F: "y", 0x0D30: "r", 0x0D31: "r", 0x0D32: "l", 0x0D33: "l",
    0x0D34: "zh", 0x0D35: "v", 0x0D36: "sh", 0x0D37: "sh", 0x0D38: "s",
    0x0D39: "h",
}

# Viramas / Halants (cancels inherent vowel 'a')
VIRAMAS = {
    0x094D,  # Devanagari
    0x09CD,  # Bengali
    0x0ACD,  # Gujarati
    0x0BCD,  # Tamil
    0x0C4D,  # Telugu
    0x0CCD,  # Kannada
    0x0D4D,  # Malayalam
}

# Modifiers (Anusvara, Chandrabindu, Visarga)
MODIFIERS: Dict[int, str] = {
    # Anusvara / Chandrabindu
    0x0901: "n", 0x0902: "m", 0x0981: "n", 0x0982: "ng", 0x0A81: "n", 0x0A82: "m",
    0x0B82: "m", 0x0C01: "n", 0x0C02: "m", 0x0C82: "m", 0x0D02: "m",
    # Visarga
    0x0903: "h", 0x0983: "h", 0x0A83: "h", 0x0B83: "h", 0x0C03: "h", 0x0C83: "h", 0x0D03: "h",
    # Nukta
    0x093C: "", 0x09BC: "", 0x0ABC: "",
}


def romanize_indic_text(text: str) -> str:
    """Deterministically romanize Indic script text to Latin phonetic representation.
    
    Preserves all non-Indic characters, digits, spaces, and unknown code points unchanged.
    """
    if not text:
        return ""

    chars = list(text)
    n = len(chars)
    out = []
    i = 0

    while i < n:
        cp = ord(chars[i])

        if cp in INDEPENDENT_VOWELS:
            out.append(INDEPENDENT_VOWELS[cp])
            i += 1
        elif cp in CONSONANTS:
            base = CONSONANTS[cp]
            # Check next character to decide on inherent vowel
            if i + 1 < n:
                next_cp = ord(chars[i + 1])
                if next_cp in VIRAMAS:
                    # Inherent vowel cancelled by halant/virama
                    out.append(base)
                    i += 2  # Skip virama
                elif next_cp in DEPENDENT_VOWELS:
                    # Replaced by dependent vowel
                    out.append(base + DEPENDENT_VOWELS[next_cp])
                    i += 2
                elif next_cp in MODIFIERS:
                    out.append(base + "a" + MODIFIERS[next_cp])
                    i += 2
                else:
                    # Inherent 'a'
                    out.append(base + "a")
                    i += 1
            else:
                # End of string consonant
                out.append(base + "a")
                i += 1
        elif cp in DEPENDENT_VOWELS:
            # Standalone dependent vowel (rare/fallback)
            out.append(DEPENDENT_VOWELS[cp])
            i += 1
        elif cp in MODIFIERS:
            out.append(MODIFIERS[cp])
            i += 1
        elif cp in VIRAMAS:
            # Standalone virama
            i += 1
        else:
            # Preserve unknown code point / ASCII / punctuation untouched
            out.append(chars[i])
            i += 1

    return "".join(out)
