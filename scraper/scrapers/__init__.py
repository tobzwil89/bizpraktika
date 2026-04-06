from .deloitte import DeloitteScraper
from .pwc import PwCScraper
from .kpmg import KPMGScraper
from .ey import EYScraper

ALL_SCRAPERS = [DeloitteScraper, PwCScraper, KPMGScraper, EYScraper]

__all__ = ["DeloitteScraper", "PwCScraper", "KPMGScraper", "EYScraper", "ALL_SCRAPERS"]
