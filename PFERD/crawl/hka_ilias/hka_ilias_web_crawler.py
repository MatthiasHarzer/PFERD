import re
from configparser import SectionProxy
from typing import Dict

import aiohttp

from ...auth import Authenticator
from ...config import Config
from ...utils import soupify
from ..crawler import CrawlError
from ..ilias.kit_ilias_web_crawler import KitIliasWebCrawler, KitIliasWebCrawlerSection

_ILIAS_URL = "https://ilias.h-ka.de"


class HkaIliasWebCrawlerSection(KitIliasWebCrawlerSection):
    def __init__(self, section: SectionProxy):
        super().__init__(section, ilias_url=_ILIAS_URL)


class HkaIliasWebCrawler(KitIliasWebCrawler):
    """
    An HKA ILIAS web crawler, based on the KitIliasWebCrawler
    """

    def __init__(
            self,
            name: str,
            section: KitIliasWebCrawlerSection,
            config: Config,
            authenticators: Dict[str, Authenticator]
    ):
        # Setting a main authenticator for cookie sharing
        auth = section.auth(authenticators)
        login_service = HkaLoginService(auth)
        super().__init__(name, section, config, authenticators,
                         login_service=login_service, ilias_url=_ILIAS_URL)


class HkaLoginService:
    # idk why the HKA ILIAS requires these stupid query params to handle requests,
    # but without it won't authenticate
    _LOGIN_URL = (f"{_ILIAS_URL}/ilias.php?lang=de&cmd=post&cmdClass=ilstartupgui&cmdNode=11h"
                  f"&baseClass=ilStartUpGUI&rtoken=")
    _LOGIN_CHECK_SUCCESS_URL = f"{_ILIAS_URL}/ilias.php?baseClass=ilDashboardGUI&cmd=jumpToSelectedItems"
    _LOGOUT_HREF_REGEX = re.compile("^https://ilias.h-ka.de/logout.php.*")

    def __init__(self, authenticator: Authenticator, ) -> None:
        self._auth = authenticator

    async def login(self, sess: aiohttp.ClientSession) -> None:
        """
        Performs the login process for the HKA ILIAS
        """

        username, password = await self._auth.credentials()

        data = {
            "username": username,
            "password": password,
            "cmd[doStandardAuthentication]": "Anmelden",
        }
        await sess.post(self._LOGIN_URL, data=data)

        if not await self._login_successful(sess):
            raise CrawlError("Login failed")

    async def _login_successful(self, sess: aiohttp.ClientSession) -> bool:
        async with sess.get(HkaLoginService._LOGIN_CHECK_SUCCESS_URL) as request:
            soup = soupify(await request.read())
            # This can be improved
            logout_element = soup.find("a", href=self._LOGOUT_HREF_REGEX)
            return logout_element is not None
