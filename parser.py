from bs4 import BeautifulSoup
from utils import isin_from_text

class AvivaDomParser:
    @staticmethod
    def extract_pagination_rows(html_content: str) -> list[dict]:
        """Parses active targets out of the standard paginated UI table grid."""
        soup = BeautifulSoup(html_content, "html.parser")
        collected_funds = []
        
        row_elements = soup.select("#paginatedResults > fieldset > div")
        for row in row_elements:
            try:
                name_el = row.select_one("div:nth-child(2) > label > span > span")
                anchor_el = row.select_one("div:nth-child(2) > div > div > a")
                if not name_el or not anchor_el:
                    continue
                    
                absolute_url = anchor_el.get("href", "")
                collected_funds.append({
                    "name": name_el.get_text(strip=True),
                    "url": absolute_url,
                    "isin": isin_from_text(absolute_url)
                })
            except Exception:
                continue
        return collected_funds

    @staticmethod
    def locate_kiid_anchor(html_content: str) -> str | None:
        """Checks for active key documentation asset anchors."""
        soup = BeautifulSoup(html_content, "html.parser")
        anchor = soup.find("a", title="Link to KIID")
        return anchor.get("href") if anchor else None