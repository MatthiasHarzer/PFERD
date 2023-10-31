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
    A HKA ILIAS web crawler, based on the KitIliasWebCrawler
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
        login_service = HkaShibbolethLogin(auth)
        super().__init__(name, section, config, authenticators,
                         login_service=login_service, ilias_url=_ILIAS_URL)


class HkaShibbolethLogin:
    """
    Login via KIT's shibboleth system.
    """

    # idk why the HKA ILIAS requires these stupid query params to handle requests,
    # but without it won't authenticate
    _LOGIN_URL = (f"{_ILIAS_URL}/ilias.php?lang=de&target=root_1&cmd=post&cmdClass=ilstartupgui"
                  f"&cmdNode=11g&baseClass=ilStartUpGUI&rtoken")
    _LOGIN_CHECK_SUCCESS_URL = (f"{_ILIAS_URL}/ilias.php?cmdClass=ilmembershipoverviewgui&cmdNode=jq"
                                f"&baseClass=ilmembershipoverviewgui")

    def __init__(self, authenticator: Authenticator, ) -> None:
        self._auth = authenticator

    async def login(self, sess: aiohttp.ClientSession) -> None:
        """
        Performs the ILIAS Shibboleth authentication dance and saves the login
        cookies it receieves.

        This function should only be called whenever it is detected that you're
        not logged in. The cookies obtained should be good for a few minutes,
        maybe even an hour or two.
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

    @staticmethod
    async def _login_successful(sess: aiohttp.ClientSession) -> bool:
        async with sess.get(HkaShibbolethLogin._LOGIN_CHECK_SUCCESS_URL) as request:
            soup = soupify(await request.read())
            return soup.find("div", {"class": "custom-login-page"}) is None
