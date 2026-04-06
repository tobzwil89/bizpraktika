"""
kpmg.py – Scraper für KPMG DACH Praktika.

Strategie:
1. KPMG Karriere-API
2. Fallback: HTML-Scraping
"""

import logging
import re
from datetime import date

from .base import BaseScraper

logger = logging.getLogger(__name__)


class KPMGScraper(BaseScraper):
    company_name = "KPMG"

    # KPMG nutzt verschiedene ATS-Systeme je nach Region
    API_URLS = [
        "https://careers.kpmg.de/api/jobs?q=Praktikum&location=Deutschland",
        "https://ehyp.kpmg.de/api/v1/jobs?category=Praktikum",
    ]

    CAREER_URLS = [
        "https://careers.kpmg.de/stellenangebote?q=Praktikum",
        "https://jobs.kpmg.de/search/?q=Praktikum&locationsearch=Deutschland",
        "https://www.kpmg.de/karriere/stellenangebote.html?search=Praktikum",
    ]

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.company_name}] Starte Scraping...")
        jobs = []

        # Strategie 1: API
        jobs = self._try_api()
        if jobs:
            logger.info(f"[{self.company_name}] {len(jobs)} Jobs via API gefunden")
            return jobs

        # Strategie 2: HTML
        jobs = self._try_html()
        if jobs:
            logger.info(f"[{self.company_name}] {len(jobs)} Jobs via HTML gefunden")
            return jobs

        logger.warning(f"[{self.company_name}] Keine Jobs gefunden")
        return []

    def _try_api(self) -> list[dict]:
        """Versuche KPMG API."""
        from categorizer import is_praktikum, is_dach_location, normalize_location

        for api_url in self.API_URLS:
            data = self.fetch_json(api_url, timeout=20)
            if data is None:
                continue

            jobs = []
            results = data if isinstance(data, list) else data.get("jobs", data.get("results", data.get("data", [])))
            if not isinstance(results, list):
                continue

            for item in results:
                title = item.get("title", item.get("name", ""))
                location = item.get("location", item.get("city", ""))
                url = item.get("url", item.get("link", item.get("applyUrl", "")))
                description = item.get("description", item.get("shortDescription", ""))
                posted = item.get("postedDate", item.get("createdAt", str(date.today())))

                if not title:
                    continue
                if not is_praktikum(title, description):
                    continue
                if location and not is_dach_location(location):
                    continue

                if url and not url.startswith("http"):
                    url = f"https://careers.kpmg.de{url}"

                jobs.append(self._build_job(
                    title=title,
                    url=url or "https://careers.kpmg.de",
                    location=normalize_location(location.split(",")[0]) if location else "Unbekannt",
                    description=re.sub(r"<[^>]+>", " ", description or "").strip(),
                    posted=posted[:10] if posted else str(date.today()),
                ))

            if jobs:
                return jobs

        return []

    def _try_html(self) -> list[dict]:
        """Fallback: HTML Scraping."""
        from categorizer import is_praktikum, is_dach_location, normalize_location

        jobs = []
        for url in self.CAREER_URLS:
            soup = self.fetch_soup(url, timeout=20)
            if soup is None:
                continue

            job_elements = (
                soup.select(".job-listing, .job-card, .job-item, .vacancy") or
                soup.select("[class*='job'], [class*='position']") or
                soup.select("article, li.result")
            )

            for elem in job_elements:
                title_el = elem.select_one("h2 a, h3 a, .job-title a, .title a, a.title")
                if not title_el:
                    title_el = elem.select_one("h2, h3, .job-title, .title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                link = ""
                if title_el.name == "a":
                    link = title_el.get("href", "")
                else:
                    link_el = elem.select_one("a[href]")
                    link = link_el.get("href", "") if link_el else ""

                location_el = elem.select_one("[class*='location'], .location")
                location = location_el.get_text(strip=True) if location_el else ""

                desc_el = elem.select_one("[class*='desc'], .description")
                description = desc_el.get_text(strip=True) if desc_el else ""

                if not is_praktikum(title, description):
                    continue
                if location and not is_dach_location(location):
                    continue

                if link and not link.startswith("http"):
                    link = f"https://careers.kpmg.de{link}"

                jobs.append(self._build_job(
                    title=title,
                    url=link or url,
                    location=normalize_location(location.split(",")[0]) if location else "Unbekannt",
                    description=description,
                ))

            if jobs:
                break

        return jobs
