import time

from cloakbrowser import launch


class CloakedBrowserClient:
    """
    Manages long-lived synchronous browser sessions and isolated short-lived
    contexts safely inside dedicated synchronous worker threads.
    """

    def __init__(self):
        self.browser = None
        self.current_proxy = None
        self.session_birth = 0
        self.MAX_BROWSER_LIFETIME_SEC = 10 * 60

    def init_browser(self):
        """Synchronous initializer executed safely inside a thread layer."""
        if self.browser:
            self.close()

        # proxy_info = get_proxy_endpoint()
        # self.current_proxy = proxy_info["proxy"]
        self.current_proxy = None

        # Fire up your native sync cloakbrowser context
        self.browser = launch(
            headless=True, proxy=self.current_proxy, geoip=True, humanize=True
        )
        self.session_birth = time.time()

    def _block_assets(self, page):
        """Synchronous Playwright asset abort router."""
        page.route(
            "**/*",
            lambda r: (
                r.abort()
                if r.request.resource_type in {"stylesheet", "font", "image", "media"}
                else r.continue_()
            ),
        )

    def get_page_context(self):
        """Creates a clean tab context. Recycles browser process if expired."""
        if not self.browser or (
            time.time() - self.session_birth > self.MAX_BROWSER_LIFETIME_SEC
        ):
            self.init_browser()

        # Return sync page elements to the worker thread safely
        page = self.browser.new_page()
        self._block_assets(page)
        return page

    def close(self):
        """Ensures complete runtime memory cleanup."""
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        self.browser = None
