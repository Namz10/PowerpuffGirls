"""Canonical record assembly and batch transformation pipeline."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from src.represent.country_rules import normalize_country
from src.represent.normalize_address import normalize_address
from src.represent.normalize_name import normalize_name
from src.represent.config import NORMALIZER_VERSION


@dataclass
class CanonicalRecord:
    entity_id: str
    source: str
    country: str
    normalized_name: str
    romanized_name: str
    accent_folded_name: str
    normalized_address: str
    source_script: str
    postal_code: Optional[str]
    is_empty_address: bool
    has_landmark_ref: bool
    is_cedex: bool
    name_tokens: List[str]
    address_tokens: List[str]
    normalizer_version: str = NORMALIZER_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def transform_single_record(
    entity_id: str,
    raw_name: str,
    raw_address: Optional[str],
    raw_country: Optional[str],
    source: str = "",
) -> CanonicalRecord:
    """Transform raw record inputs into a standardized CanonicalRecord."""
    country = normalize_country(raw_country)
    norm_name, rom_name, fold_name, script, name_toks = normalize_name(raw_name)
    norm_addr, addr_toks, is_empty_addr, has_landmark, is_cedex, postal = normalize_address(
        raw_address, country=country
    )
    
    if not source and entity_id:
        if entity_id.startswith("S1-") or entity_id.startswith("1-"):
            source = "source1"
        elif entity_id.startswith("S2-") or entity_id.startswith("2-"):
            source = "source2"
        elif entity_id.startswith("S3-") or entity_id.startswith("3-"):
            source = "source3"

    return CanonicalRecord(
        entity_id=str(entity_id),
        source=source,
        country=country,
        normalized_name=norm_name,
        romanized_name=rom_name,
        accent_folded_name=fold_name,
        normalized_address=norm_addr,
        source_script=script,
        postal_code=postal,
        is_empty_address=is_empty_addr,
        has_landmark_ref=has_landmark,
        is_cedex=is_cedex,
        name_tokens=name_toks,
        address_tokens=addr_toks,
        normalizer_version=NORMALIZER_VERSION,
    )


def transform_dataframe(df: pd.DataFrame, source_name: str = "") -> pd.DataFrame:
    """Transform a pandas DataFrame of raw entity records into canonical schema."""
    id_col = next((c for c in ["entity_id", "id", "record_id"] if c in df.columns), df.columns[0])
    name_col = next((c for c in ["business_name", "name", "name_1", "name_2"] if c in df.columns), df.columns[1])
    addr_col = next((c for c in ["business_address", "address", "address_1", "address_2"] if c in df.columns), None)
    country_col = next((c for c in ["country", "country_code"] if c in df.columns), None)

    records = []
    for _, row in df.iterrows():
        eid = str(row[id_col])
        r_name = str(row[name_col]) if pd.notna(row[name_col]) else ""
        r_addr = str(row[addr_col]) if addr_col and pd.notna(row[addr_col]) else None
        r_country = str(row[country_col]) if country_col and pd.notna(row[country_col]) else None

        rec = transform_single_record(
            entity_id=eid,
            raw_name=r_name,
            raw_address=r_addr,
            raw_country=r_country,
            source=source_name,
        )
        records.append(rec.to_dict())

    return pd.DataFrame.from_records(records)
