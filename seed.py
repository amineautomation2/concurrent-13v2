import logging
import os
import sys

from supabase import Client, create_client


class SupabaseSeeder:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_KEY", "")

        if not url or not key:
            print(
                "❌ Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set.",
                file=sys.stderr,
            )
            sys.exit(1)

        self.client: Client = create_client(url, key)

    def populate_kiid_tasks(self, discovered_funds: list[dict], batch_size: int = 200):
        """
        Takes raw Mutual Fund pagination entries and maps them cleanly into the transactional queue.
        Expected entry format: {"name": "Aviva Multi-Asset Fund", "url": "https://..."}
        """
        print(
            f"🔄 Preparing to seed {len(discovered_funds)} Mutual Fund entries into the cloud queue..."
        )

        payload_records = []
        for fund in discovered_funds:
            # We wrap the fund discovery details into the target_page_or_payload JSONB column
            payload_records.append(
                {
                    "fund_type": "MF_KIID",
                    "status": "pending",
                    "target_page_or_payload": {
                        "name": fund["name"],
                        "fund_url": fund["url"],
                    },
                }
            )

        # Bulk-insert in chunks to maintain network stability and optimize database transactions
        total_inserted = 0
        for i in range(0, len(payload_records), batch_size):
            chunk = payload_records[i : i + batch_size]
            try:
                self.client.table("aviva_scraping_queue").insert(chunk).execute()
                total_inserted += len(chunk)
                print(
                    f"✅ Successfully queued batch: {total_inserted}/{len(payload_records)} items synced."
                )
            except Exception as e:
                print(
                    f"❌ Failed to insert database batch starting at index {i}: {e}",
                    file=sys.stderr,
                )


# data = get_xlsx_data("aviva.xlsx", "MF")
# seeder = SupabaseSeeder()
# seeder.populate_kiid_tasks(data)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def transition_to_kiid_queue():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        logging.error("Missing Supabase credentials.")
        sys.exit(1)

    supabase: Client = create_client(url, key)

    logging.info("Searching for master entries with valid KIID URLs missing ISINs...")

    all_records = []
    page_size = 1000
    start_index = 0

    # 1. Paginate through the master database until all rows are fetched
    while True:
        end_index = start_index + page_size - 1
        logging.info(
            f"📥 Querying master rows in range indices: {start_index} to {end_index}"
        )

        response = (
            supabase.table("aviva_funds_data")
            .select("name, url, kiid_url")
            .eq("fund_type", "MF")
            .neq("kiid_url", None)
            .is_("isin", None)
            .range(start_index, end_index)
            .execute()
        )

        page_data = response.data
        if not page_data:
            break

        all_records.extend(page_data)

        # If the page returned is smaller than our page size, we hit the end
        if len(page_data) < page_size:
            break

        start_index += page_size

    if not all_records:
        logging.info("✅ Zero target rows need processing.")
        return

    logging.info(
        f"📊 Total matching records extracted across pages: {len(all_records)}"
    )
    logging.info(
        f"🔄 Mapping {len(all_records)} entries into the transactional task queue..."
    )

    # 2. Structure payloads for transaction queue ingestion
    queue_batch = []
    for row in all_records:
        queue_batch.append(
            {
                "fund_type": "MF_ISIN",
                "status": "pending",
                "target_page_or_payload": {
                    "name": row["name"],
                    "url": row["url"],
                    "kiid_url": row["kiid_url"],
                },
            }
        )

    # Chunk insertions back up to Supabase to maintain stable throughput
    insert_chunk_size = 200
    for i in range(0, len(queue_batch), insert_chunk_size):
        chunk = queue_batch[i : i + insert_chunk_size]
        supabase.table("aviva_scraping_queue").insert(chunk).execute()

    logging.info(
        f"🏁 Centralized queue successfully populated with all {len(queue_batch)} MF_KIID targets!"
    )


if __name__ == "__main__":
    transition_to_kiid_queue()

# Problem = MF need to manually feed funds data betwen runs (MF_Pagination, KIID and ISIN)
