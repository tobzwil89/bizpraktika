"""
base.py – Basis-Klasse für alle Scraper.

Stellt gemeinsame Funktionalität bereit:
- HTTP-Requests mit Retries, Timeouts, Rate Limiting
- User-Agent Rotation
- Logging
- Gemeinsame Hilfsmethoden
"""

import logging
import random
import time
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Realistische User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


class BaseScraper(ABC):
    """Abstrakte Basis-Klasse für alle Company-Scraper."""

    company_name: str = "Unknown"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        self._request_count = 0

    def _get_headers(self) -> dict:
        """Zufälligen User-Agent zurückgeben."""
        return {"User-Agent": random.choice(USER_AGENTS)}

    def _rate_limit(self):
        """Pause zwischen Requests (1-3 Sekunden)."""
        self._request_count += 1
        if self._request_count > 1:
            delay = random.uniform(1.0, 3.0)
            logger.debug(f"  Rate limit: {delay:.1f}s Pause")
            time.sleep(delay)

    def fetch_url(self, url: str, timeout: int = 30, retries: int = 2) -> requests.Response | None:
        """
        HTTP GET mit Retry-Logik und Fehlerbehandlung.

        Returns None bei Fehler (bricht nicht ab).
        """
        self._rate_limit()
        for attempt in range(retries + 1):
            try:
                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                logger.warning(f"  Timeout bei {url} (Versuch {attempt + 1}/{retries + 1})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"  Verbindungsfehler bei {url} (Versuch {attempt + 1}/{retries + 1})")
            except requests.exceptions.HTTPError as e:
                logger.warning(f"  HTTP-Fehler {e.response.status_code} bei {url}")
                if e.response.status_code == 429:
                    # Rate limited – längere Pause
                    time.sleep(random.uniform(5.0, 10.0))
                elif e.response.status_code >= 500:
                    time.sleep(random.uniform(2.0, 5.0))
                else:
                    return None  # 4xx Fehler – kein Retry
            except requests.exceptions.RequestException as e:
                logger.error(f"  Request-Fehler bei {url}: {e}")
                return None

            if attempt < retries:
                time.sleep(random.uniform(2.0, 5.0))

        logger.error(f"  Alle {retries + 1} Versuche fehlgeschlagen für {url}")
        return None

    def fetch_json(self, url: str, **kwargs) -> dict | list | None:
        """Fetch URL und parse als JSON."""
        response = self.fetch_url(url, **kwargs)
        if response is None:
            return None
        try:
            return response.json()
        except ValueError:
            logger.error(f"  Ungültiges JSON von {url}")
            return None

    def fetch_soup(self, url: str, parser: str = "lxml", **kwargs) -> BeautifulSoup | None:
        """Fetch URL und parse als BeautifulSoup."""
        response = self.fetch_url(url, **kwargs)
        if response is None:
            return None
        return BeautifulSoup(response.text, parser)

    @abstractmethod
    def scrape(self) -> list[dict]:
        """
        Scrape alle Praktika dieser Company.

        Returns: Liste von Job-Dicts mit mindestens:
          - title (str)
          - company (str)
          - location (str)
          - url (str)
          - description (str, kann leer sein)
          - duration (str, "Unbekannt" wenn nicht gefunden)
          - start_date (str, "Unbekannt" wenn nicht gefunden)
          - company_size (str)
          - salary (str)
          - posted (str, ISO-Datum oder "Unbekannt")
        """
        ...

    def _build_job(
        self,
        title: str,
        url: str,
        location: str = "Unbekannt",
        description: str = "",
        duration: str = "Unbekannt",
        start_date: str = "Unbekannt",
        company_size: str = "Konzern (10.000+ MA)",
        posted: str = "Unbekannt",
    ) -> dict:
        """Erstelle ein standardisiertes Job-Dict."""
        from categorizer import categorize_job

        cats = categorize_job(title, description, self.company_name)

        return {
            "title": title.strip(),
            "company": self.company_name,
            "specialization": cats["specialization"],
            "track": cats["track"],
            "location": location.strip(),
            "duration": duration,
            "start_date": start_date,
            "company_size": company_size,
            "salary": "Bezahlt",
            "posted": posted,
            "url": url.strip(),
            "description": description.strip(),
        }
