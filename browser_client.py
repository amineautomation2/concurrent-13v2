import time
import random
from cloakbrowser import launch
from utils import get_proxy_endpoint

class CloakedBrowserClient:
    """Manages long-lived browser sessions and isolated short-lived contexts."""
    def __init__(self):
        self.browser = None
        self.current_proxy = None
        self.session_birth = 0
        self.MAX_BROWSER_LIFETIME_SEC = 10 * 60

    async def init_browser(self):
        if self.browser:
            await self.close()
        proxy_info = get_proxy_endpoint()
        self.current_proxy = proxy_info["proxy"]
        self.browser = await launch(headless=True, proxy=self.current_proxy, geoip=True, humanize=True)
        self.session_birth = time.time()

    def _block_assets(self, page):
        page.route("**/*", lambda r: r.abort() if r.request.resource_type in 
                   {"stylesheet", "font", "image", "media"} else r.continue_())

    async def get_page_context(self):
        """Enforces cyclic main browser rotations based on time drift parameters."""
        if not self.browser or (time.time() - self.session_birth > self.MAX_BROWSER_LIFETIME_SEC):
            await self.init_browser()
        
        # Open an isolated context per unique task transaction
        context = await self.browser.new_context()
        page = await context.new_page()
        self._block_assets(page)
        return context, page

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        self.browser = None