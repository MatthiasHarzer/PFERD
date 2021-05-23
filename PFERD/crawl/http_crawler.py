import asyncio
from pathlib import PurePath
from typing import Optional

import aiohttp
from aiohttp.client import ClientTimeout

from ..config import Config
from ..logging import log
from ..utils import fmt_real_path
from ..version import NAME, VERSION
from .crawler import Crawler, CrawlerSection


class HttpCrawlerSection(CrawlerSection):
    def http_timeout(self) -> float:
        return self.s.getfloat("http_timeout", fallback=20)


class HttpCrawler(Crawler):
    COOKIE_FILE = PurePath(".cookies")

    def __init__(
            self,
            name: str,
            section: HttpCrawlerSection,
            config: Config,
    ) -> None:
        super().__init__(name, section, config)

        self._cookie_jar_path = self._output_dir.resolve(self.COOKIE_FILE)
        self._output_dir.register_reserved(self.COOKIE_FILE)
        self._authentication_id = 0
        self._authentication_lock = asyncio.Lock()
        self._current_cookie_jar: Optional[aiohttp.CookieJar] = None
        self._request_count = 0
        self._http_timeout = section.http_timeout()

    async def _current_auth_id(self) -> int:
        """
        Returns the id for the current authentication, i.e. an identifier for the last
        successful call to [authenticate].

        This method must be called before any request that might authenticate is made, so the
        HttpCrawler can properly track when [authenticate] can return early and when actual
        authentication is necessary.
        """
        # We acquire the lock here to ensure we wait for any concurrent authenticate to finish.
        # This should reduce the amount of requests we make: If an authentication is in progress
        # all future requests wait for authentication to complete.
        async with self._authentication_lock:
            self._request_count += 1
            return self._authentication_id

    async def authenticate(self, caller_auth_id: int) -> None:
        """
        Starts the authentication process. The main work is offloaded to _authenticate, which
        you should overwrite in a subclass if needed. This method should *NOT* be overwritten.

        The [caller_auth_id] should be the result of a [_current_auth_id] call made *before*
        the request was made. This ensures that authentication is not performed needlessly.
        """
        async with self._authentication_lock:
            # Another thread successfully called authenticate in-between
            # We do not want to perform auth again, so we return here. We can
            # assume the other thread suceeded as authenticate will throw an error
            # if it failed and aborts the crawl process.
            if caller_auth_id != self._authentication_id:
                return
            await self._authenticate()
            self._authentication_id += 1
            # Saving the cookies after the first auth ensures we won't need to re-authenticate
            # on the next run, should this one be aborted or crash
            await self._save_cookies()

    async def _authenticate(self) -> None:
        """
        Performs authentication. This method must only return normally if authentication suceeded.
        In all other cases it must either retry internally or throw a terminal exception.
        """
        raise RuntimeError("_authenticate() was called but crawler doesn't provide an implementation")

    async def _save_cookies(self) -> None:
        log.explain_topic("Saving cookies")
        if not self._current_cookie_jar:
            log.explain("No cookie jar, save aborted")
            return

        try:
            self._current_cookie_jar.save(self._cookie_jar_path)
            log.explain(f"Cookies saved to {fmt_real_path(self._cookie_jar_path)}")
        except Exception:
            log.warn(f"Failed to save cookies to {fmt_real_path(self._cookie_jar_path)}")

    async def run(self) -> None:
        self._current_cookie_jar = aiohttp.CookieJar()
        self._request_count = 0

        try:
            self._current_cookie_jar.load(self._cookie_jar_path)
        except Exception:
            pass

        async with aiohttp.ClientSession(
                headers={"User-Agent": f"{NAME}/{VERSION}"},
                cookie_jar=self._current_cookie_jar,
                timeout=ClientTimeout(total=self._http_timeout)
        ) as session:
            self.session = session
            try:
                await super().run()
            finally:
                del self.session
        log.explain_topic(f"Total amount of HTTP requests: {self._request_count}")

        # They are saved in authenticate, but a final save won't hurt
        await self._save_cookies()
