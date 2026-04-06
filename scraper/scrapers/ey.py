"""
ey.py – Scraper für EY (Ernst & Young) DACH Praktika.

Strategie:
1. EY Karriere-API (häufig über Taleo oder eigenes CMS)
2. Fallback: HTML-Scraping
"""

import logging
import re
from datetime import date

from .base import BaseScraper

logger = logging.getLogger(__name__)


class EYScraper(BaseScraper):
    company_name = "EY"

    API_URLS = [
        "https://careers.ey.com/api/jobs?q=Praktikum&country=DE",
        "https://eygbl.referrals.selectminds.com/api/jobs?q=Praktikum+intern&location=Germany",
    ]

    CAREER_URLS = [
        "https://careers.ey.com/ey/search/?q=Praktikum&locationsearch=Germany",
        "https://eygbl.referrals.selectminds.com/experienced/search/?q=Praktikum",
        "https://www.ey.com/de_de/careers/search?query=Praktikum&location=Deutschland",
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
        """Versuche EY Careers API."""
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
                title = item.get("title", item.get("name", item.get("jobTitle", "")))
                location = item.get("location", item.get("city", item.get("primaryLocation", "")))
                url = item.get("url", item.get("link", item.get("applyUrl", "")))
                description = item.get("description", item.get("shortDescription", ""))
                posted = item.get("postedDate", item.get("datePosted", str(date.today())))

                if not title:
                    continue
                if not is_praktikum(title, description):
                    continue
                if location and not is_dach_location(location):
                    continue

                if url and not url.startswith("http"):
                    url = f"https://careers.ey.com{url}"

                jobs.append(self._build_job(
                    title=title,
                    url=url or "https://careers.ey.com",
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
                soup.select(".job-listing, .job-card, .search-result") or
                soup.select("[class*='job'], [class*='position'], [class*='vacancy']") or
                soup.select("article, li.result, .result-item")
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
                    link = f"https://careers.ey.com{link}"

                jobs.append(self._build_job(
                    title=title,
                    url=link or url,
                    location=normalize_location(location.split(",")[0]) if location else "Unbekannt",
                    description=description,
                ))

            if jobs:
                break

        return jobs
