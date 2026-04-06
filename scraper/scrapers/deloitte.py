"""
deloitte.py – Scraper für Deloitte DACH Praktika.

Strategie:
1. Versuche Deloitte Careers API (JSON)
2. Fallback: HTML-Scraping der Karriereseite
"""

import logging
import re
from datetime import date

from .base import BaseScraper

logger = logging.getLogger(__name__)


class DeloitteScraper(BaseScraper):
    company_name = "Deloitte"

    # Deloitte nutzt eine Karriereseite powered by SmartRecruiters / eigenes CMS
    # Die API-Endpoints ändern sich gelegentlich – daher mehrere Strategien

    # Strategie 1: Deloitte Karriere-API
    API_URL = "https://apply.deloitte.com/careers/SearchJobs"
    API_PARAMS = {
        "listFilterMode": "1",
        "jobRecordsPerPage": "50",
        "698": "3756",     # Country = Deutschland (Code kann sich ändern)
        "1138": "6184",    # Category = Praktikum/Intern
    }

    # Strategie 2: Direkte Karriereseiten-URLs
    CAREER_URLS = [
        "https://apply.deloitte.com/careers/SearchJobs?698=3756&1138=6184&listFilterMode=1&jobRecordsPerPage=50",
        "https://jobs.deloitte.de/search/?q=Praktikum&locationsearch=Deutschland",
        "https://jobsinvolvingx.deloitte.com/careers/SearchJobs?698=3756&1138=6184",
    ]

    # Suchbegriffe für Fallback
    SEARCH_TERMS = ["Praktikum", "Intern", "Internship"]
    LOCATIONS = ["Deutschland", "Germany", "Österreich", "Austria", "Schweiz", "Switzerland"]

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.company_name}] Starte Scraping...")
        jobs = []

        # Strategie 1: API
        jobs = self._try_api()
        if jobs:
            logger.info(f"[{self.company_name}] {len(jobs)} Jobs via API gefunden")
            return jobs

        # Strategie 2: HTML Scraping
        jobs = self._try_html()
        if jobs:
            logger.info(f"[{self.company_name}] {len(jobs)} Jobs via HTML gefunden")
            return jobs

        logger.warning(f"[{self.company_name}] Keine Jobs gefunden – alle Strategien fehlgeschlagen")
        return []

    def _try_api(self) -> list[dict]:
        """Versuche Jobs über die Deloitte Careers API zu laden."""
        try:
            data = self.fetch_json(
                self.API_URL,
                timeout=20,
            )
            if data and isinstance(data, dict):
                return self._parse_api_response(data)
        except Exception as e:
            logger.debug(f"[{self.company_name}] API fehlgeschlagen: {e}")
        return []

    def _parse_api_response(self, data: dict) -> list[dict]:
        """Parse API JSON Response."""
        jobs = []
        results = data.get("results", data.get("jobs", data.get("data", [])))
        if isinstance(results, dict):
            results = results.get("jobs", results.get("results", []))
        if not isinstance(results, list):
            return []

        from categorizer import is_praktikum, is_dach_location

        for item in results:
            title = item.get("title", item.get("jobTitle", ""))
            location = item.get("location", item.get("city", ""))
            url = item.get("url", item.get("applyUrl", ""))
            description = item.get("description", item.get("shortDescription", ""))

            if not title:
                continue
            if not is_praktikum(title, description):
                continue
            if location and not is_dach_location(location):
                continue

            # URL normalisieren
            if url and not url.startswith("http"):
                url = f"https://apply.deloitte.com{url}"

            posted = item.get("postedDate", item.get("dateCreated", str(date.today())))

            jobs.append(self._build_job(
                title=title,
                url=url or f"https://apply.deloitte.com/careers/SearchJobs?Keywords={title.replace(' ', '+')}",
                location=self._normalize_deloitte_location(location),
                description=self._clean_html(description),
                posted=self._normalize_date(posted),
            ))

        return jobs

    def _try_html(self) -> list[dict]:
        """Fallback: HTML-Scraping der Karriereseite."""
        jobs = []
        for url in self.CAREER_URLS:
            soup = self.fetch_soup(url, timeout=20)
            if soup is None:
                continue

            # Verschiedene HTML-Strukturen probieren
            job_elements = (
                soup.select(".job-listing, .job-card, .search-result-item") or
                soup.select("[class*='job'], [class*='vacancy'], [class*='opening']") or
                soup.select("article, .result, .listing")
            )

            if not job_elements:
                continue

            from categorizer import is_praktikum, is_dach_location

            for elem in job_elements:
                title_el = (
                    elem.select_one("h2 a, h3 a, .job-title a, .title a") or
                    elem.select_one("h2, h3, .job-title, .title")
                )
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                link = title_el.get("href", "") if title_el.name == "a" else ""
                if not link:
                    link_el = elem.select_one("a[href]")
                    link = link_el.get("href", "") if link_el else ""

                location_el = elem.select_one(".location, .job-location, [class*='location']")
                location = location_el.get_text(strip=True) if location_el else ""

                desc_el = elem.select_one(".description, .job-description, [class*='desc']")
                description = desc_el.get_text(strip=True) if desc_el else ""

                if not is_praktikum(title, description):
                    continue
                if location and not is_dach_location(location):
                    continue

                if link and not link.startswith("http"):
                    link = f"https://apply.deloitte.com{link}"

                jobs.append(self._build_job(
                    title=title,
                    url=link or url,
                    location=self._normalize_deloitte_location(location),
                    description=description,
                ))

            if jobs:
                break  # Genug gefunden

        return jobs

    @staticmethod
    def _normalize_deloitte_location(loc: str) -> str:
        from categorizer import normalize_location
        if not loc:
            return "Unbekannt"
        # Deloitte nutzt oft "München | Germany" Format
        loc = loc.split("|")[0].split(",")[0].strip()
        return normalize_location(loc)

    @staticmethod
    def _clean_html(text: str) -> str:
        """Entferne HTML-Tags aus Beschreibung."""
        if not text:
            return ""
        return re.sub(r"<[^>]+>", " ", text).strip()
        
    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Normalisiere Datumsformate auf ISO."""
        if not date_str:
            return str(date.today())
        # Versuche häufige Formate
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                from datetime import datetime
                return datetime.strptime(date_str[:10], fmt[:len(date_str[:10])]).strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                continue
        return str(date.today())
