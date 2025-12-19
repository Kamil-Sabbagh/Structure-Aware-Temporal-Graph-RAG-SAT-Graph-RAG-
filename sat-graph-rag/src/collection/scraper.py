"""Base scraper with rate limiting and error handling."""

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PlanaltoScraper:
    """Scraper for Planalto government website."""
    
    BASE_URL = "https://www.planalto.gov.br/ccivil_03/constituicao"
    
    def __init__(
        self,
        delay_seconds: float = 2.0,
        user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        output_dir: str = "data/raw",
        max_retries: int = 3
    ):
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        
        # Configure retries
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        })
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_time = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_time = time.time()
    
    def fetch(self, url: str, timeout: int = 60) -> Optional[str]:
        """Fetch a URL with rate limiting and error handling."""
        self._rate_limit()
        
        for attempt in range(3):
            try:
                logger.info(f"Fetching: {url} (attempt {attempt + 1})")
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                
                # Handle encoding (Planalto uses ISO-8859-1 / Latin-1)
                response.encoding = response.apparent_encoding or 'iso-8859-1'
                return response.text
                
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))  # Wait before retry
                else:
                    logger.error(f"Failed to fetch {url} after 3 attempts: {e}")
                    return None
        
        return None
    
    def save_html(self, content: str, filename: str, subdir: str = "") -> Path:
        """Save HTML content to file."""
        if subdir:
            save_dir = self.output_dir / subdir
            save_dir.mkdir(parents=True, exist_ok=True)
        else:
            save_dir = self.output_dir
        
        filepath = save_dir / filename
        filepath.write_text(content, encoding='utf-8')
        logger.info(f"Saved: {filepath}")
        return filepath

