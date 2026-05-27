import os
import sys
import time
import io
import re
import random
import asyncio
import logging
from bs4 import BeautifulSoup
from pypdf import PdfReader
from curl_cffi import requests as cloaked_requests

# Structural Module Imports from your repository layout
from db_manager import SupabaseQueueManager  # Handles atomic state updates
from parser import AvivaDomParser            # Contains locate_kiid_anchor
# Fetches your target residential proxies
from utils import get_proxy_endpoint
# Your native working sync browser launcher
from cloakbrowser import launch

# Configure runtime execution logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ============================================================================
# THREAD-SAFE SYNCHRONOUS BROWSER PIPELINE (STAGE 2: MF_Discovery)
# ============================================================================


def run_sync_browser_discovery(url: str) -> str | None:
    """
    Executes entirely within an isolated background thread context.
    Uses native synchronous syntax so Playwright Sync API stays happy.
    """
    logging.info(f"🌐 Spawning CloakBrowser thread for URL: {url}")
    proxy_dict = get_proxy_endpoint()
    assigned_proxy = proxy_dict["proxy"]

    # Launch tracking instance matching your original repository settings
    browser = launch(headless=True, proxy=assigned_proxy,
                     geoip=True, humanize=True)
    page = browser.new_page()

    # Abort heavy assets inline to conserve proxy bandwidth allocation
    page.route("**/*", lambda route: route.abort()
               if route.request.resource_type in {"stylesheet", "font", "image", "media"}
               else route.continue_())

    try:
        page.goto(url, wait_until="commit", timeout=120000)

        # Apply standard interactive cadence masks to blend with human footprints
        page.mouse.move(random.randint(200, 700), random.randint(200, 600))
        time.sleep(random.uniform(1.5, 3.0))

        # Interact with the cookie management layer if visible
        cookie_btn = page.locator("#onetrust-accept-btn-handler")
        if cookie_btn.is_visible():
            cookie_btn.click()
            time.sleep(random.uniform(0.5, 1.5))

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        anchor = soup.find("a", title="Link to KIID")

        return anchor.get("href") if anchor else None

    finally:
        try:
            page.close()
            browser.close()
        except Exception:
            pass

# ============================================================================
# THREAD-SAFE HIGH-SPEED PDF STREAM ENGINE (STAGE 3: MF_KIID)
# ============================================================================


def run_sync_pdf_isin_extraction(kiid_url: str) -> str | None:
    """
    Bypasses the UI entirely. Uses curl_cffi to fetch binary data 
    and pypdf regex processing to extract validated ISIN codes.
    """
    logging.info(f"📥 Streaming target binary bytes from KIID: {kiid_url}")
    # proxy_dict = get_proxy_endpoint()
    # session_proxy = proxy_dict["proxy"]

    try:
        # Replicates the authenticated download stream headers from your kiid.py file
        cookies = {
            'ApplicationGatewayAffinityCORS': 'e1dd5c8d8f0aaac8dbef88daaa63d498',
            'ApplicationGatewayAffinity': 'e1dd5c8d8f0aaac8dbef88daaa63d498',
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,*/*'
        }

        response = cloaked_requests.get(
            kiid_url,
            headers=headers,
            cookies=cookies,
            # proxies={"http": session_proxy, "https": session_proxy},
            proxies=None,
            timeout=45
        )

        if response.status_code != 200:
            logging.error(
                f"Network request rejected with status code: {response.status_code}")
            return None

        # Parse text buffers in-memory
        pdf_file = io.BytesIO(response.content)
        reader = PdfReader(pdf_file)

        # Compile exact regex engine footprints used in your kiid.py file
        isin_extract_rx = re.compile(
            r"[A-Z]{2}(?:[?\s]*[A-Z0-9]){9}[?\\s]*[0-9]")
        isin_strict_rx = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

        for page in reader.pages:
            text = page.extract_text() or ""
            matches = isin_extract_rx.findall(text)

            for match in matches:
                cleaned_isin = match.replace(" ", "")
                if isin_strict_rx.match(cleaned_isin):
                    return cleaned_isin

    except Exception as e:
        logging.error(f"Error processing PDF stream content: {e}")

    return None

# ============================================================================
# ASYNC TASK DISPATCH ROUTER LAYER
# ============================================================================


async def process_task(fund_type: str, payload: dict) -> list[dict] | None:
    """
    Bridges your async orchestration runner to thread-isolated execution blocks
    to guarantee Playwright never triggers threading panic loops.
    """
    # --- STAGE 2: VISITING THE DETAILS PAGE VIA BROWSER TO EXTRACT PDF URL ---
    if fund_type == "MF_KIID":
        url = payload["fund_url"]

        # Run blocking sync browser functions completely off the event loop
        kiid_link = await asyncio.to_thread(run_sync_browser_discovery, url)

        if kiid_link:
            return [{
                "name": payload["name"],
                "url": url,
                "kiid": kiid_link,
                "isin": None
            }]

    # --- STAGE 3: DOWNLOADING CODES STRAIGHT FROM DISCOVERED PDF BINARIES ---
    elif fund_type == "MF_ISIN":
        kiid_url = payload["kiid_url"]

        # Stream binary files instantly over raw connection sockets
        isin_code = await asyncio.to_thread(run_sync_pdf_isin_extraction, kiid_url)

        return [{
            "name": payload["name"],
            "url": payload["url"],
            "kiid": kiid_url,
            "isin": isin_code
        }]

    return None

# ============================================================================
# RUNNABLE MAIN EXECUTION LOOP ENGINE
# ============================================================================


async def main():
    runner_id = os.environ.get("RUNNER_IDENTIFIER", "local-dev-node")
    # Toggles between 'MF_Discovery' (Browser) and 'MF_KIID' (Direct Network Stream)
    fund_type_job = os.environ.get("TARGET_FUND_TYPE", "MF_Pagination")

    db = SupabaseQueueManager()
    logging.info(
        f"🚀 Initializing Orchestration Runner Node: {runner_id} for operation: {fund_type_job}")

    while True:
        # Atomic transactional pulling sequence
        task_wrapper = db.fetch_and_lock_task(runner_id, fund_type_job)
        if not task_wrapper:
            logging.info(
                "🏁 Supabase task queue pool exhausted. Exiting worker loop safely.")
            break

        task_id = task_wrapper["task_id"]
        payload = task_wrapper["payload"]

        try:
            results = await process_task(fund_type_job, payload)

            if results:
                # Instantly stream row batches to your master cloud storage repository
                db.stream_funds_batch("MF", results)
                db.update_task_status(task_id, "completed")
                logging.info(f"✅ Successfully synchronized Task ID {task_id}")
            else:
                db.update_task_status(task_id, "failed")
                logging.warning(
                    f"⚠️ Task ID {task_id} completed execution but returned no data signatures.")

        except Exception as e:
            logging.error(
                f"❌ Structural crash handling Task ID {task_id}: {e}")
            db.update_task_status(task_id, "failed")

        # Variable sleep interval to stagger outgoing target hits
        await asyncio.sleep(random.uniform(2.0, 4.0))

if __name__ == "__main__":
    asyncio.run(main())
