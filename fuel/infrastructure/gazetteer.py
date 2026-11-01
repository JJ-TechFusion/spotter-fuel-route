"""Readers for the bundled source files: Census gazetteers and the fuel price CSV."""

import csv
import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from fuel.domain.places import normalize_place_name

# Census names carry a legal suffix ("Dallas city", "Big Cabin town") we strip off.
_LEGAL_SUFFIX = re.compile(
    r"\s+(city and borough|charter township|township|city|town|village|borough|cdp|plantation|municipality)$",
    re.IGNORECASE,
)
_GOVERNMENT_SUFFIX = re.compile(r"\s+(consolidated|unified|metropolitan|metro) government.*$", re.IGNORECASE)


@dataclass(frozen=True)
class GazetteerPlace:
    state: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class PriceRow:
    opis_id: int
    name: str
    address: str
    city: str
    state: str
    price: float


def lookup_keys(census_name: str) -> set[str]:
    """All normalized names a Census place should answer to.

    'Augusta-Richmond County consolidated government (balance)' -> {'augustarichmondcounty', 'augusta'}
    'Boise City city' -> {'boisecity', 'boise'}
    """
    name = re.sub(r"\s*\(.*\)$", "", census_name.strip())
    name = _GOVERNMENT_SUFFIX.sub("", name)
    base = _LEGAL_SUFFIX.sub("", name)
    names = {base, re.sub(r"\s+city$", "", base, flags=re.IGNORECASE)}
    if "-" in base:
        names.add(base.split("-")[0])
    return {normalize_place_name(n) for n in names}


def read_gazetteer(zip_path: Path) -> Iterator[GazetteerPlace]:
    with zipfile.ZipFile(zip_path) as archive:
        member = next(n for n in archive.namelist() if n.endswith(".txt"))
        with archive.open(member) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="latin-1"), delimiter="\t")
            header = [h.strip() for h in next(reader)]
            state_i, name_i = header.index("USPS"), header.index("NAME")
            lat_i, lon_i = header.index("INTPTLAT"), header.index("INTPTLONG")
            for row in reader:
                yield GazetteerPlace(row[state_i], row[name_i], float(row[lat_i]), float(row[lon_i].strip()))


def read_fuel_prices(csv_path: Path) -> Iterator[PriceRow]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yield PriceRow(
                opis_id=int(row["OPIS Truckstop ID"]),
                name=row["Truckstop Name"].strip(),
                address=row["Address"].strip(),
                city=row["City"].strip(),
                state=row["State"].strip(),
                price=float(row["Retail Price"]),
            )
