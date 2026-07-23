#!/usr/bin/env python3
"""
Download all Ausonius works from Pedecerto.

Source: https://www.pedecerto.eu/pagine/autori/idautori/183

Downloads all works by Ausonius as XML files into cento/stylometry/ausonius_raw/.
Some works may contain a mix of meters; a separate filtering script can be used
to extract only hexameter lines.

Usage:
    python download_ausonius.py
"""

import urllib.request
import urllib.error
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUTHOR_URL = "https://www.pedecerto.eu/pagine/autori/idautori/183"
DOWNLOAD_BASE = "https://www.pedecerto.eu/pagine/download/idopere"

OUTPUT_DIR = Path(__file__).parent / "ausonius_raw"

# All works by Ausonius on Pedecerto.
# These are the download IDs from the pedecerto author page.
#
# Key: download ID
# Value: (filename, description)
#
# Note: Some works may contain a mix of meters. The hexameter works are:
#   401 (praefationes), 402 (ephemeris), 404 (uersus Paschales),
#   405 (epicedion in patrem), 410 (Parentalia), 413 (epigrammata),
#   416 (Mosella), 417 (Bissula), 421 (fasti), 422 (Caesares),
#   424 (technopaegnion)
#
# Other works may have some hexameter lines mixed with other meters.
ALL_WORKS = {
    401: ("praefationes", "Praefationes"),
    402: ("ephemeris", "Ephemeris"),
    403: ("ad_patrem_de_suscepto_filio", "ad patrem de suscepto filio"),
    404: ("uersus_paschales", "Uersus Paschales"),
    405: ("epicedion_in_patrem", "Epicedion in patrem"),
    406: ("de_herediolo", "de herediolo"),
    407: ("pater_ad_filium", "pater ad filium"),
    408: ("protrepticus_ad_nepotem", "protrepticus ad nepotem"),
    409: ("genethliacos", "genethliacos"),
    410: ("parentalia", "Parentalia"),
    411: ("commemoratio_professorum_burdigalensium", "commemoratio professorum Burdigalensium"),
    412: ("epitaphia_heroum", "epitaphia heroum"),
    413: ("epigrammata", "Epigrammata"),
    414: ("eclogae", "eclogae"),
    415: ("griphus_ternarii_numeri", "griphus ternarii numeri"),
    416: ("mosella", "Mosella"),
    417: ("bissula", "Bissula"),
    418: ("cento_nuptialis", "cento nuptialis"),
    419: ("cupido_cruciatus", "Cupido cruciatus"),
    420: ("precationes_variae", "precationes variae"),
    421: ("fasti", "Fasti"),
    422: ("caesares", "Caesares"),
    423: ("ordo_urbium_nobilium", "ordo urbium nobilium"),
    424: ("technopaegnion", "Technopaegnion"),
    425: ("ludus_septem_sapientium", "ludus septem sapientium"),
    426: ("epistulae", "epistulae"),
    427: ("appendix_ausoniana", "appendix Ausoniana"),
    428: ("oratio_consulis_ausonii_versibus_rhopalicis", "oratio consulis Ausonii versibus rhopalicis"),
    429: ("periochae_iliados", "periochae Iliados"),
    430: ("periochae_odyssiae", "periochae Odyssiae"),
    431: ("appendix_ausoniana_2", "*appendix Ausoniana"),
}

# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------


def fetch_author_page(url: str) -> str:
    """Fetch the HTML of the author page."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def parse_download_ids(html: str) -> dict[int, str]:
    """
    Parse the author page HTML to extract download IDs and their titles.

    Returns a mapping of download_id -> title.
    """
    pattern = r"javascript:download\((\d+)\)[^>]*>([^<]*)"
    matches = re.findall(pattern, html)
    result = {}
    for id_str, title in matches:
        id_val = int(id_str)
        title = title.strip()
        if title:
            result[id_val] = title
    return result


def download_xml(download_id: int, output_path: Path) -> bool:
    """
    Download a single XML file from Pedecerto.

    Returns True on success, False on failure.
    """
    url = f"{DOWNLOAD_BASE}/{download_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
        output_path.write_bytes(content)
        print(f"  ✓ {output_path.name} ({len(content)} bytes)")
        return True
    except urllib.error.HTTPError as e:
        print(f"  ✗ {output_path.name} — HTTP {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"  ✗ {output_path.name} — {e.reason}")
        return False


def main():
    print(f"Output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch the author page and parse download IDs
    print(f"\nFetching author page: {AUTHOR_URL}")
    html = fetch_author_page(AUTHOR_URL)
    page_works = parse_download_ids(html)
    print(f"Found {len(page_works)} works by Ausonius on Pedecerto:")
    for id_val, title in sorted(page_works.items()):
        print(f"  {id_val}: {title}")

    # Step 2: Download all works
    print(f"\nDownloading {len(ALL_WORKS)} works:")
    success = 0
    for download_id, (filename, description) in sorted(ALL_WORKS.items()):
        output_path = OUTPUT_DIR / f"{filename}.xml"
        if download_xml(download_id, output_path):
            success += 1

    print(f"\nDone: {success}/{len(ALL_WORKS)} files downloaded.")
    if success < len(ALL_WORKS):
        print("Some downloads failed. Check the output above.")
        sys.exit(1)

    print("\nNote: Some works may contain non-hexameter lines.")
    print("A filtering script can be used to extract only hexameter lines.")


if __name__ == "__main__":
    main()
