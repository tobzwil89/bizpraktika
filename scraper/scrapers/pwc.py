"""
pwc.py – Scraper für PwC DACH Praktika.

Strategie:
1. PwC Karriere-API (JSON, oft über Workday oder eigenes CMS)
2. Fallback: HTML-Scraping
"""

import logging
import re
from datetime import date

from .base import BaseScraper

logger = logging.getLogger(__name__)


class PwCScraper(BaseScraper):
    company_name = "PwC"

    # PwC nutzt häufig Workday als ATS
    API_URLS = [
        "https://pwc.wd3.myworkdayjobs.com/wday/cxs/pwc/Global_Experienced_Careers/jobs",
        "https://www.pwc.de/de/karriere/stellensuche.html",
    ]

    # Suchparameter für Workday API
    WORKDAY_SEARCH = {
        "appliedFacets": {
            "locations": [],  # DACH locations
            "jobFamilyGroup": [],
        },
        "searchText": "Praktikum intern internship",
        "limit": 50,
        "offset": 0,
    }

    CAREER_URLS = [
        "https://pwc.wd3.myworkdayjobs.com/Global_Experienced_Careers?q=Praktikum&locations=Deutschland",
        "https://www.pwc.de/de/karriere/stellensuche.html?jobType=Praktikum",
        "https://jobs.pwc.de/search/?q=Praktikum&locationsearch=",
    ]

    def scrape(self) -> list[dict]:
        logger.info(f"[{self.company_name}] Starte Scraping...")
        jobs = []

        # Strategie 1: Workday API
        jobs = self._try_workday_api()
        if jobs:
            logger.info(f"[{self.company_name}] {len(jobs)} Jobs via Workday API gefunden")
            return jobs

        # Strategie 2: HTML
        jobs = self._try_html()
        if jobs:
            logger.info(f"[{self.company_name}] {len(jobs)} Jobs via HTML gefunden")
            return jobs

        logger.warning(f"[{self.company_name}] Keine Jobs gefunden")
        return []

    def _try_workday_api(self) -> list[dict]:
        """Versuche PwC Workday API."""
        try:
            import json
            for api_url in self.API_URLS:
                if "workday" not in api_url.lower():
                    continue
                response = self.fetch_url(api_url, timeout=20)
                if response is None:
                    continue
                try:
                    data = response.json()
                except ValueError:
                    continue
                return self._parse_workday(data)
        except Exception as e:
            logger.debug(f"[{self.company_name}] Workday API fehlgeschlagen: {e}")
        return []

    def _parse_workday(self, data: dict) -> list[dict]:
        """Parse Workday API Response."""
        from categorizer import is_praktikum, is_dach_location

        jobs = []
        job_postings = data.get("jobPostings", data.get("results", []))

        for item in job_postings:
            title = item.get("title", item.get("bulletFields", [None])[0] or "")
            location = ""
            if "locationsText" in item:
                location = item["locationsText"]
            elif "bulletFields" in item and len(item["bulletFields"]) > 1:
                location = item["bulletFields"][1]

            external_path = item.get("externalPath", "")
            url = f"https://pwc.wd3.myworkdayjobs.com/Global_Experienced_Careers{external_path}" if external_path else ""

            posted = item.get("postedOn", str(date.today()))

            if not title:
                continue
            if not is_praktikum(title):
                continue
            if location and not is_dach_location(location):
                continue

            from categorizer import normalize_location
            jobs.append(self._build_job(
                title=title,
                url=url or "https://careers.pwc.de",
                location=normalize_location(location.split(",")[0]) if location else "Unbekannt",
                posted=posted[:10] if posted else str(date.today()),
            ))

        return jobs

    def _try_html(self) -> list[dict]:
        """Fallback: HTML Scraping."""
        from categorizer import is_praktikum, is_dach_location, normalize_location

        jobs = []
        for url in self.CAREER_URLS:
            soup = self.fetch_soup(url, timeout=20)
            if soup is None:
                continue

            job_elements = (
                soup.select("[data-automation-id='jobTitle'], .job-listing, .job-card") or
                soup.select("[class*='job'], [class*='vacancy']") or
                soup.select("li.result, article")
            )

            for elem in job_elements:
                title_el = elem.select_one("a, h2, h3, .title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                link = title_el.get("href", "") if title_el.name == "a" else ""
                if not link:
                    link_el = elem.select_one("a[href]")
                    link = link_el.get("href", "") if link_el else ""

                location_el = elem.select_one("[class*='location'], .location")
                location = location_el.get_text(strip=True) if location_el else ""

                if not is_praktikum(title):
                    continue
                if location and not is_dach_location(location):
                    continue

                if link and not link.startswith("http"):
                    link = f"https://pwc.wd3.myworkdayjobs.com{link}"

                jobs.append(self._build_job(
                    title=title,
                    url=link or url,
                    location=normalize_location(location.split(",")[0]) if location else "Unbekannt",
                ))

            if jobs:
                break

        return jobs
