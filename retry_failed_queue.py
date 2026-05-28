import logging
import os
import sys

from supabase import Client, create_client

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class SupabaseQueueRecovery:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_KEY", "")

        if not url or not key:
            logging.error(
                "SUPABASE_URL and SUPABASE_KEY environment variables are required."
            )
            sys.exit(1)

        self.client: Client = create_client(url, key)

    def re_queue_failed_tasks(self, fund_type: str, max_retries: int = 3):
        """
        Finds failed tasks for a fund type, filters out dead tasks that exceeded
        the maximum allowed error limit, and restores the rest to 'pending'.
        """
        logging.info(
            f"🔄 Scanning queue for failed tasks belonging to stage: [{fund_type}]"
        )

        try:
            # 1. Check how many items are currently failed for this stage
            response = (
                self.client.table("aviva_scraping_queue")
                .select("id, retry_count")
                .eq("fund_type", fund_type)
                .eq("status", "failed")
                .execute()
            )

            failed_tasks = response.data
            if not failed_tasks:
                logging.info(
                    f"✅ Clean Slate! Zero failed tasks found for stage: [{fund_type}]."
                )
                return

            logging.info(f"⚠️ Discovered {len(failed_tasks)} failed tasks.")

            re_queued_count = 0
            dropped_count = 0

            # 2. Iterate and selectively reset tasks based on historical retry threshold counters
            for task in failed_tasks:
                task_id = task["id"]
                current_retries = task.get("retry_count", 0)

                if current_retries >= max_retries:
                    logging.warning(
                        f"🚫 Task ID {task_id} has crashed {current_retries} times. Abandoning to prevent infinite loops."
                    )
                    dropped_count += 1
                    continue

                # Reset status to pending, strip the crash identifier, and increment retry count
                self.client.table("aviva_scraping_queue").update(
                    {
                        "status": "pending",
                        "locked_by": None,
                        "retry_count": current_retries + 1,
                        "updated_at": "now()",
                    }
                ).eq("id", task_id).execute()

                re_queued_count += 1

            logging.info(
                f"📊 Recovery run complete: {re_queued_count} tasks restored to pending. {dropped_count} tasks abandoned."
            )

        except Exception as e:
            logging.error(f"❌ Failed to run queue recovery optimization pipeline: {e}")


if __name__ == "__main__":
    # Allows fast execution straight from the terminal layout:
    # python retry_failed_queue.py MF_Discovery
    target_stage = sys.argv[1] if len(sys.argv) > 1 else "MF_KIID"

    recovery = SupabaseQueueRecovery()
    recovery.re_queue_failed_tasks(fund_type=target_stage)
