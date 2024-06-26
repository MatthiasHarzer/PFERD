from configparser import SectionProxy
from typing import Callable, Dict

from ..auth import Authenticator
from ..config import Config
from .crawler import Crawler, CrawlError, CrawlerSection  # noqa: F401
from .hka_ilias import HkaIliasWebCrawler, HkaIliasWebCrawlerSection
from .ilias import KitIliasWebCrawler, KitIliasWebCrawlerSection
from .kit_ipd_crawler import KitIpdCrawler, KitIpdCrawlerSection
from .local_crawler import LocalCrawler, LocalCrawlerSection

CrawlerConstructor = Callable[[
    str,                       # Name (without the "crawl:" prefix)
    SectionProxy,              # Crawler's section of global config
    Config,                    # Global config
    Dict[str, Authenticator],  # Loaded authenticators by name
], Crawler]

CRAWLERS: Dict[str, CrawlerConstructor] = {
    "local": lambda n, s, c, a:
        LocalCrawler(n, LocalCrawlerSection(s), c),
    "kit-ilias-web": lambda n, s, c, a:
        KitIliasWebCrawler(n, KitIliasWebCrawlerSection(s), c, a),
    "kit-ipd": lambda n, s, c, a:
        KitIpdCrawler(n, KitIpdCrawlerSection(s), c),
    "hka-ilias-web": lambda n, s, c, a:
        HkaIliasWebCrawler(n, HkaIliasWebCrawlerSection(s), c, a),
}
