"""Interactive inspection tool for Person 2 representation outputs."""

import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.represent.canonical_record import transform_single_record
from src.represent.token_resource import TokenResource
from src.represent.config import resource_dir


def main():
    print("=" * 80)
    print(" PERSON 2 (SHRIYA) — REPRESENTATION TRANSFORMATION DEMO")
    print("=" * 80)

    test_records = [
        # (ID, Name, Address, Country)
        ("S1-001", "M/S Reliance Industries Pvt. Ltd.", "Near MG Road, Bangalore 560001", "India"),
        ("S1-002", "टाटा कंसल्टेंसी सर्विसेज लिमिटेड", "मुंबई महाराष्ट्र 400001", "India"),
        ("S1-003", "ಕರ್ನಾಟಕ ಎಂಟರ್ಪ್ರೈಸಸ್", "ಬೆಂಗಳೂರು", "India"),
        ("S1-004", "தமிழ்நாடு நிறுவனம்", "சென்னை 600001", "India"),
        ("S1-005", "భారత్ ఎలక్ట్రానిక్స్ లిమిటెడ్", "హైదరాబాద్ 500001", "India"),
        ("S1-006", "বাংলা ট্রেডার্স", "কলকাতা 700001", "India"),
        ("S1-007", "ગુજરાત ટેક્સટાઈલ્સ", "અમદાવાદ 380001", "India"),
        ("S1-008", "കേരള ആയുർവേദ", "കൊച്ചി 682001", "India"),
        ("S1-009", "L'Oréal S.A.S.", "15 Boulevard Haussmann, 75440 CEDEX 09, Paris", "France"),
        ("S1-010", "Boulangerie Moderne E.U.R.L.", "12 1er étage, Boîte Postale 45, Lyon", "France"),
        ("S1-011", "Immobilier Parisien S.C.I.", "8 3ème Avenue, 75008 Paris", "France"),
        ("S1-012", "Google LLC & Co.", "1600 Amphitheatre Pkwy, Mountain View, CA 94043", "US"),
        ("S1-013", "Ghost Company Inc", "", "US"),
    ]

    for eid, r_name, r_addr, r_country in test_records:
        rec = transform_single_record(eid, r_name, r_addr, r_country)
        print(f"\n[Record ID: {eid}] ({rec.country} | Script: {rec.source_script})")
        print(f"  Raw Name:            {r_name}")
        print(f"  Normalized Name:     {rec.normalized_name}")
        print(f"  Romanized Name:      {rec.romanized_name}")
        print(f"  Accent-Folded Name:  {rec.accent_folded_name}")
        print(f"  Raw Address:         {r_addr if r_addr else '(empty)'}")
        print(f"  Normalized Address:  {rec.normalized_address if rec.normalized_address else '(empty)'}")
        print(f"  Postal Code:         {rec.postal_code}")
        print(f"  Flags:               empty_addr={rec.is_empty_address}, landmark={rec.has_landmark_ref}, cedex={rec.is_cedex}")
        print(f"  Name Tokens:         {rec.name_tokens}")
        print(f"  Address Tokens:      {rec.address_tokens}")

    # Load and inspect token resources
    res_path = resource_dir()
    if (res_path / "boilerplate_tokens.json").exists():
        print("\n" + "=" * 80)
        print(" MINED BOILERPLATE TOKENS (artifacts/resources/boilerplate_tokens.json)")
        print("=" * 80)
        with (res_path / "boilerplate_tokens.json").open("r", encoding="utf-8") as f:
            bp = json.load(f)
        for country, tokens in bp.items():
            print(f"  [{country}] (Top 15 tokens): {tokens[:15]}")

    if (res_path / "name_idf.json").exists():
        print("\n" + "=" * 80)
        print(" SAMPLE TOKEN IDFs (artifacts/resources/name_idf.json)")
        print("=" * 80)
        token_res = TokenResource.load(res_path)
        sample_words = ["limited", "private", "road", "reliance", "technologies", "danone", "apple"]
        for w in sample_words:
            idf_in = token_res.get_name_idf(w, "India")
            idf_us = token_res.get_name_idf(w, "US")
            idf_fr = token_res.get_name_idf(w, "France")
            print(f"  Token '{w:12s}': India IDF={idf_in:<6.2f} | US IDF={idf_us:<6.2f} | France IDF={idf_fr:<6.2f}")


if __name__ == "__main__":
    main()
