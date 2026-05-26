import os
import sys
import json
from supabase import create_client, Client
from utils import get_xlsx_data

class SupabaseSeeder:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_KEY", "")
        
        if not url or not key:
            print("❌ Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set.", file=sys.stderr)
            sys.exit(1)
            
        self.client: Client = create_client(url, key)

    def populate_kiid_tasks(self, discovered_funds: list[dict], batch_size: int = 200):
        """
        Takes raw Mutual Fund pagination entries and maps them cleanly into the transactional queue.
        Expected entry format: {"name": "Aviva Multi-Asset Fund", "url": "https://..."}
        """
        print(f"🔄 Preparing to seed {len(discovered_funds)} Mutual Fund entries into the cloud queue...")
        
        payload_records = []
        for fund in discovered_funds:
            # We wrap the fund discovery details into the target_page_or_payload JSONB column
            payload_records.append({
                "fund_type": "MF_KIID",
                "status": "pending",
                "target_page_or_payload": {
                    "name": fund["name"],
                    "fund_url": fund["url"]
                }
            })
            
        # Bulk-insert in chunks to maintain network stability and optimize database transactions
        total_inserted = 0
        for i in range(0, len(payload_records), batch_size):
            chunk = payload_records[i:i + batch_size]
            try:
                self.client.table("aviva_scraping_queue").insert(chunk).execute()
                total_inserted += len(chunk)
                print(f"✅ Successfully queued batch: {total_inserted}/{len(payload_records)} items synced.")
            except Exception as e:
                print(f"❌ Failed to insert database batch starting at index {i}: {e}", file=sys.stderr)
            

data = get_xlsx_data("aviva.xlsx", "MF")
seeder = SupabaseSeeder()
seeder.populate_kiid_tasks(data)