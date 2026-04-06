"""
json_manager.py – Verwaltet jobs.json: lesen, mergen, archivieren, schreiben.

- Archiviert alte Version bevor sie überschrieben wird
- Dedupliziert Jobs via URL oder Titel+Firma
- Aktualisiert Meta-Daten und Filter automatisch
"""

import json
import os
import shutil
from datetime import date
from pathlib import Path


# ─── Pfade ────────────────────────────────────────────────────────────
# Alles relativ zum Projekt-Root (Elternverzeichnis von /scraper)
def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def jobs_json_path() -> Path:
    return _project_root() / "jobs.json"


def archive_dir() -> Path:
    return _project_root() / "archive"


# ─── Lesen ────────────────────────────────────────────────────────────
def load_jobs(path: Path | None = None) -> dict:
    """Lade bestehende jobs.json. Gibt leere Struktur zurück wenn nicht vorhanden."""
    path = path or jobs_json_path()
    if not path.exists():
        return _empty_structure()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _empty_structure() -> dict:
    return {
        "meta": {
            "last_updated": str(date.today()),
            "total_jobs": 0,
            "version": "1.0",
        },
        "filters": {
            "specializations": [],
            "tracks": [],
            "locations": [],
            "durations": [],
            "start_dates": [],
            "company_sizes": [],
        },
        "jobs": [],
    }


# ─── Archivieren ──────────────────────────────────────────────────────
def archive_current(path: Path | None = None) -> str | None:
    """Archiviere aktuelle jobs.json → archive/jobs_YYYY-MM-DD.json."""
    path = path or jobs_json_path()
    if not path.exists():
        return None

    arch = archive_dir()
    arch.mkdir(exist_ok=True)

    today = date.today().isoformat()
    dest = arch / f"jobs_{today}.json"

    # Falls heute schon archiviert: Suffix anhängen
    counter = 1
    while dest.exists():
        dest = arch / f"jobs_{today}_{counter}.json"
        counter += 1

    shutil.copy2(path, dest)
    return str(dest)


# ─── Duplikat-Check ───────────────────────────────────────────────────
def _job_key(job: dict) -> str:
    """Eindeutiger Schlüssel für Duplikat-Erkennung: URL bevorzugt, sonst Titel+Firma."""
    url = job.get("url", "").strip().rstrip("/").lower()
    if url:
        return url
    title = job.get("title", "").strip().lower()
    company = job.get("company", "").strip().lower()
    return f"{title}|{company}"


def merge_jobs(existing_data: dict, new_jobs: list[dict]) -> dict:
    """
    Merge neue Jobs in bestehende Daten.

    Returns dict mit:
      - data: aktualisierte Datenstruktur
      - added: Anzahl neu hinzugefügter Jobs
      - duplicates: Anzahl übersprungener Duplikate
    """
    existing_jobs = existing_data.get("jobs", [])
    existing_keys = {_job_key(j) for j in existing_jobs}

    added = 0
    duplicates = 0

    # Nächste freie ID bestimmen
    max_id = max((j.get("id", 0) for j in existing_jobs), default=0)

    for job in new_jobs:
        key = _job_key(job)
        if key in existing_keys:
            duplicates += 1
            continue

        max_id += 1
        job["id"] = max_id
        existing_jobs.append(job)
        existing_keys.add(key)
        added += 1

    existing_data["jobs"] = existing_jobs
    return {"data": existing_data, "added": added, "duplicates": duplicates}


def remove_stale_jobs(
    existing_data: dict, active_urls: set[str], companies: list[str]
) -> dict:
    """
    Entferne Jobs die nicht mehr auf den Websites existieren.

    Nur Jobs von den gescrapten Companies werden geprüft.
    Jobs von anderen Companies bleiben erhalten.

    Returns dict mit:
      - data: aktualisierte Datenstruktur
      - removed: Anzahl entfernter Jobs
    """
    jobs = existing_data.get("jobs", [])
    companies_lower = {c.lower() for c in companies}
    active_urls_lower = {u.strip().rstrip("/").lower() for u in active_urls}

    kept = []
    removed = 0

    for job in jobs:
        company = job.get("company", "").lower()
        url = job.get("url", "").strip().rstrip("/").lower()

        # Job gehört nicht zu einer gescrapten Company → behalten
        if company not in companies_lower:
            kept.append(job)
            continue

        # Job existiert noch → behalten
        if url in active_urls_lower:
            kept.append(job)
            continue

        # Job existiert nicht mehr → entfernen
        removed += 1

    existing_data["jobs"] = kept
    return {"data": existing_data, "removed": removed}


# ─── Filter aktualisieren ────────────────────────────────────────────
def rebuild_filters(data: dict) -> dict:
    """Aktualisiere Filter und Meta basierend auf aktuellen Jobs."""
    jobs = data.get("jobs", [])

    specializations = sorted(set(j.get("specialization", "") for j in jobs if j.get("specialization")))
    tracks = sorted(set(j.get("track", "") for j in jobs if j.get("track")))
    locations = sorted(set(j.get("location", "") for j in jobs if j.get("location")))
    durations = sorted(set(j.get("duration", "") for j in jobs if j.get("duration")))
    start_dates = sorted(set(j.get("start_date", "") for j in jobs if j.get("start_date")))
    company_sizes = sorted(set(j.get("company_size", "") for j in jobs if j.get("company_size")))

    data["filters"] = {
        "specializations": specializations,
        "tracks": tracks,
        "locations": locations,
        "durations": durations,
        "start_dates": start_dates,
        "company_sizes": company_sizes,
    }
    data["meta"]["last_updated"] = str(date.today())
    data["meta"]["total_jobs"] = len(jobs)

    return data


# ─── Schreiben ────────────────────────────────────────────────────────
def save_jobs(data: dict, path: Path | None = None) -> None:
    """Schreibe jobs.json mit hübscher Formatierung."""
    path = path or jobs_json_path()
    data = rebuild_filters(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
