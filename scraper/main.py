#!/usr/bin/env python3
"""
main.py – Hauptskript des BizPraktika Scrapers.

Ausführung:
    python scraper/main.py

Was passiert:
1. Alle Big4-Scraper laufen durch
2. Ergebnisse werden kategorisiert (Keyword-Matching)
3. Bestehende jobs.json wird archiviert
4. Neue Jobs werden gemerged, Duplikate entfernt
5. Veraltete Jobs (nicht mehr online) werden entfernt
6. Aktualisierte jobs.json wird geschrieben
7. Log-Output zeigt Zusammenfassung
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Scraper-Verzeichnis zum Python-Path hinzufügen
SCRAPER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRAPER_DIR))

from scrapers import ALL_SCRAPERS
from json_manager import (
    archive_current,
    load_jobs,
    merge_jobs,
    rebuild_filters,
    remove_stale_jobs,
    save_jobs,
)

# ─── Logging Setup ────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


# ─── Banner ───────────────────────────────────────────────────────────
BANNER = """
╔══════════════════════════════════════════════════╗
║       BizPraktika – Scraper v1.0                 ║
║       Big4 Praktika für DACH Business-Studenten  ║
╚══════════════════════════════════════════════════╝
"""


def main():
    setup_logging(verbose="--verbose" in sys.argv or "-v" in sys.argv)
    logger = logging.getLogger(__name__)

    print(BANNER)
    start_time = time.time()

    # ── 1. Bestehende Daten laden ──
    logger.info("Lade bestehende jobs.json...")
    existing_data = load_jobs()
    existing_count = len(existing_data.get("jobs", []))
    logger.info(f"  → {existing_count} bestehende Jobs geladen")

    # ── 2. Archivieren ──
    logger.info("Archiviere aktuelle jobs.json...")
    archive_path = archive_current()
    if archive_path:
        logger.info(f"  → Archiviert: {archive_path}")
    else:
        logger.info("  → Keine bestehende Datei zum Archivieren")

    # ── 3. Scraper laufen lassen ──
    all_new_jobs: list[dict] = []
    all_active_urls: set[str] = set()
    scraped_companies: list[str] = []
    scraper_results: dict[str, dict] = {}

    for ScraperClass in ALL_SCRAPERS:
        scraper = ScraperClass()
        company = scraper.company_name
        logger.info(f"{'─' * 50}")
        logger.info(f"Scrape: {company}")

        try:
            jobs = scraper.scrape()
            scraper_results[company] = {
                "status": "OK",
                "found": len(jobs),
            }
            all_new_jobs.extend(jobs)
            all_active_urls.update(j.get("url", "").strip().rstrip("/").lower() for j in jobs if j.get("url"))
            scraped_companies.append(company)
            logger.info(f"  ✓ {len(jobs)} Praktika gefunden")

        except Exception as e:
            scraper_results[company] = {
                "status": "FEHLER",
                "found": 0,
                "error": str(e),
            }
            logger.error(f"  ✗ Fehler bei {company}: {e}")
            # Script bricht NICHT ab
            continue

    logger.info(f"{'─' * 50}")

    # ── 4. Merge neue Jobs ──
    logger.info("Merge neue Jobs mit bestehenden Daten...")
    merge_result = merge_jobs(existing_data, all_new_jobs)
    data = merge_result["data"]
    added = merge_result["added"]
    duplicates = merge_result["duplicates"]
    logger.info(f"  → {added} neue Jobs hinzugefügt, {duplicates} Duplikate übersprungen")

    # ── 5. Veraltete Jobs entfernen ──
    # Nur wenn wir tatsächlich aktive URLs von den Scrapern bekommen haben
    if all_active_urls and scraped_companies:
        logger.info("Entferne veraltete Jobs...")
        stale_result = remove_stale_jobs(data, all_active_urls, scraped_companies)
        data = stale_result["data"]
        removed = stale_result["removed"]
        logger.info(f"  → {removed} veraltete Jobs entfernt")
    else:
        removed = 0
        logger.info("Überspringe Entfernung veralteter Jobs (keine aktiven URLs von Scrapern)")

    # ── 6. Speichern ──
    logger.info("Speichere aktualisierte jobs.json...")
    data = rebuild_filters(data)
    save_jobs(data)
    final_count = len(data.get("jobs", []))
    logger.info(f"  → {final_count} Jobs gespeichert")

    # ── 7. Zusammenfassung ──
    elapsed = time.time() - start_time
    print(f"""
{'═' * 50}
  ZUSAMMENFASSUNG
{'═' * 50}
  Laufzeit:       {elapsed:.1f}s
  Vorher:         {existing_count} Jobs
  Neu hinzugefügt:{added:>4} Jobs
  Duplikate:      {duplicates:>4} übersprungen
  Entfernt:       {removed:>4} veraltete Jobs
  Nachher:        {final_count} Jobs
{'═' * 50}
  SCRAPER-STATUS:
""")

    for company, result in scraper_results.items():
        status = result["status"]
        found = result["found"]
        icon = "✓" if status == "OK" else "✗"
        error = f" – {result.get('error', '')}" if status != "OK" else ""
        print(f"  {icon} {company:<12} {status:<8} {found} Jobs{error}")

    print(f"\n{'═' * 50}")
    print(f"  jobs.json aktualisiert: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
