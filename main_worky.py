import os
import sys
import asyncio
import random
import logging
from db_manager import SupabaseQueueManager
from browser_client import CloakedBrowserClient
from parser import AvivaDomParser
from curl_cffi import requests as cloaked_requests
from utils import get_proxy_endpoint, extract_isin_from_pdf_bytes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def human_pacing_sequence(page, run_cooldown=False):
    """Encapsulates telemetry-breaking interactive steps."""
    if run_cooldown:
        cooldown = random.uniform(25.0, 45.0)
        logging.info(f"🧘 Akamai Cadence Break activated — pausing for {cooldown:.1f}s...")
        await asyncio.sleep(cooldown)
        return
    
    await page.mouse.move(random.randint(200, 700), random.randint(200, 600))
    await asyncio.sleep(random.uniform(0.5, 1.2))
    
    for _ in range(random.randint(1, 2)):
        scroll_delta = random.randint(280, 480)
        await page.evaluate(f"window.scrollBy(0, {scroll_delta})")
        await asyncio.sleep(random.uniform(1.0, 1.5))


async def process_task(fund_type: str, payload: dict, page) -> list[dict] | dict | None:
    """Executes target routing based on the locked queue item sub-type context."""
    
    # ========================================================================
    # STAGE 1 & 2: Browser Actions (Requires CloakBrowser Instance)
    # ========================================================================
    if fund_type in ["Investment", "ETF", "MF_Pagination"]:
        url = payload["target_url"]
        await page.goto(url, wait_until="commit", timeout=120000)
        await human_pacing_sequence(page)
        
        cookie_btn = page.locator("#onetrust-accept-btn-handler")
        if await cookie_btn.is_visible():
            await cookie_btn.click()
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        html = await page.content()
        return AvivaDomParser.extract_pagination_rows(html)
        
    elif fund_type == "MF_KIID":
        url = payload["fund_url"]
        await page.goto(url, wait_until="commit", timeout=120000)
        await human_pacing_sequence(page)
        
        html = await page.content()
        kiid_link = AvivaDomParser.locate_kiid_anchor(html)
        
        payload.update(kiid=kiid_link)
        return [payload]

    # ========================================================================
    # STAGE 3: High-Speed Stream Actions (No Browser, Just Network Sockets)
    # ========================================================================
    elif fund_type == "MF_ISIN":
        kiid_url = payload["kiid_url"]
        
        # Pull a proxy to keep your network profile cloaked from Akamai
        proxy_dict = get_proxy_endpoint()
        session_proxy = proxy_dict["proxy"]
        
        # Issue a direct binary request using curl_cffi requests framework
        # We run it inside asyncio.to_thread so it doesn't freeze your event loop
        response = await asyncio.to_thread(
            cloaked_requests.get,
            kiid_url,
            proxies={"http": session_proxy, "https": session_proxy},
            timeout=30
        )
        
        if response.status_code == 200:
            # Send the binary data stream directly to your regex extractors
            isin = extract_isin_from_pdf_bytes(response.content)
            
            # Map the clean validated data payload back
            return [{
                "name": payload["name"],
                "url": payload["url"],
                "isin": isin,
                "kiid": kiid_url
            }]
        else:
            raise Exception(f"Failed to stream PDF chunk. Status code: {response.status_code}")
    return None

async def main():
    runner_id = os.environ.get("RUNNER_IDENTIFIER", "local-dev-worker")
    fund_type_job = os.environ.get("TARGET_FUND_TYPE", "Investment")
    
    db = SupabaseQueueManager()
    browser_manager = CloakedBrowserClient()
    
    await browser_manager.init_browser()
    success_count = 0
    
    try:
        while True:
            task_wrapper = db.fetch_and_lock_task(runner_id, fund_type_job)
            if not task_wrapper:
                logging.info("Distributed processing queue dry. Exiting worker loop safely.")
                break
                
            task_id = task_wrapper["task_id"]
            payload = task_wrapper["payload"]
            
            # Periodically force deep cooldown steps before hitting the network limits
            if success_count > 0 and success_count % random.randint(7, 11) == 0:
                # Use a dummy context or handle cadence pauses directly via manager
                pass 
                
            context, page = await browser_manager.get_page_context()
            
            try:
                # Execute automated scraping steps 
                results = await process_task(fund_type_job, payload, page)
                
                # Stream the newly mined items into our production table right away
                if results:
                    db.stream_funds_batch(fund_type_job, results)
                    
                db.update_task_status(task_id, "completed")
                success_count += 1
                logging.info(f"✅ Processed task ID: {task_id} successfully.")
                
            except Exception as e:
                logging.error(f"❌ Failure handling Task ID {task_id}: {e}")
                db.update_task_status(task_id, "failed", error_inc=True)
            finally:
                await context.close()
                # Variable padding pause to keep access profiles natural
                await asyncio.sleep(random.uniform(2.0, 3.5))
                
    finally:
        await browser_manager.close()

if __name__ == "__main__":
    asyncio.run(main())