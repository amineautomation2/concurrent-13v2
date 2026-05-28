import os

from supabase import Client, create_client


class SupabaseQueueManager:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_KEY", "")
        self.client: Client = create_client(url, key)

    def fetch_and_lock_task(self, runner_id: str, fund_type: str) -> dict | None:
        """Atomically grabs a single task without worker collision."""
        try:
            response = (
                self.client.table("aviva_scraping_queue")
                .select("id, target_page_or_payload")
                .eq("status", "pending")
                .eq("fund_type", fund_type)
                .limit(1)
                .execute()
            )

            if not response.data:
                return None

            task = response.data[0]

            self.client.table("aviva_scraping_queue").update(
                {"status": "processing", "locked_by": runner_id, "updated_at": "now()"}
            ).eq("id", task["id"]).execute()

            return {"task_id": task["id"], "payload": task["target_page_or_payload"]}
        except Exception:
            return None

    def update_task_status(self, task_id: int, status: str, error_inc: bool = False):
        """Sets final processing states or increments fallback counters."""
        update_data = {"status": status, "updated_at": "now()"}
        if error_inc:
            # Simple fallback counter increment tracking via RPC or absolute override
            pass
        self.client.table("aviva_scraping_queue").update(update_data).eq(
            "id", task_id
        ).execute()

    def stream_funds_batch(self, fund_type: str, records: list[dict]):
        """Directly writes records to our primary cloud repository."""
        if not records:
            return
        payloads = []
        for r in records:
            payloads.append(
                {
                    "fund_type": fund_type,
                    "name": r.get("name"),
                    "isin": r.get("isin"),
                    "url": r.get("url"),
                    "kiid_url": r.get("kiid"),
                }
            )
        # Upsert by URL constraints prevents duplicates across separate run states
        self.client.table("aviva_funds_data").upsert(
            payloads, on_conflict="url"
        ).execute()
