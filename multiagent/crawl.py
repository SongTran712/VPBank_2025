import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from duckduckgo_search import DDGS
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
import json
from rapidfuzz.fuzz import partial_ratio
import logging
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from gnews import GNews
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from strands import Agent, tool
import asyncio
import json
from pydantic import BaseModel, Field
from typing import List
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from dotenv import load_dotenv
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from googlesearch import search


load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
OPENAI_SECRET_KEY = os.getenv("OPENAI_API_KEY")
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless=True")  # newer headless mode
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--log-level=3")

logger = logging.getLogger(__name__)
google_news = GNews(language='vi', 
                    country='VN',
                    max_results=3,
                    period='1y',
                    
                    )

def is_matching_company(expected_name, extracted_name, threshold=85):
    try:
        if not (expected_name and extracted_name):
            return False

        score = partial_ratio(expected_name.lower(), extracted_name.lower())
        
        logger.debug("Fuzzy score: %s for '%s' vs '%s'", score, expected_name, extracted_name)
        return score >= threshold

    except Exception as e:
        logger.error("Error comparing '%s' and '%s': %s", expected_name, extracted_name, str(e))
        return False

browser_config = BrowserConfig(headless = True, viewport_width = 1280, viewport_height = 720)

company_name_schema = {
    "name": "company_person",
    "baseSelector": "div.dulieu",
    "fields": [
        {
            "name": "company_name",
            "selector": "h1",  # Adjust this if needed
            "type": "text"
        }
    ]
}

company_name_extractor = JsonCssExtractionStrategy(company_name_schema)

company_person_schema = {
            "name": "company_person",
            "baseSelector": "tr[valign='top']",  # ✅ not baseSelector here
            "type": "group",  # ✅ REQUIRED to extract multiple rows
            "fields": [
                {
                    "name": "chuc_vu",
                    "selector": "td:nth-child(1)",
                    "type": "text"
                },
                {
                    "name": "ho_ten",
                    "selector": "td:nth-child(2) a",
                    "type": "text"
                }
            ]
        }
company_person_extractor = JsonCssExtractionStrategy(company_person_schema)
@tool
def get_gg_search(info, search_num=3):
    try:
        j = search(info, num_results=search_num, lang='vn', advanced=True)
        results = []
        for i in j:
            results.append({
                "url": i.url,
                "description": i.description
            })
        return {"status": "success", "data": results}
    except Exception as e:
        logger.exception("Lỗi trong get_gg_search:")
        return {"status": "error", "message": str(e)}

def search_web(text: str, limit: int, domain: str = None) -> list:
    """
    Perform a DuckDuckGo search and return a list of filtered result URLs.
    
    Args:
        text (str): The search query.
        limit (int): Maximum number of results.
        domain (str, optional): If provided, filter results to include only URLs containing this domain.
        
    Returns:
        list: Filtered list of result URLs.
    """
    
    filtered_results = []
    
    try:
        with DDGS() as ddgs:
            raw_results = ddgs.text(keywords=text, max_results=limit)
            for result in raw_results:
                href = result.get('href')
                if href and (domain is None or domain in href):
                    filtered_results.append(href)
                    
    except Exception as e:
        logger.error("Error during web search for '%s': %s", text, str(e))

    return filtered_results
async def wait_before_extract(page):
    await asyncio.sleep(1)  # wait 1 second

# base_wait = """js:() => new Promise(resolve => setTimeout(resolve, 3000))"""



class CongtY(BaseModel):
    name: str
    tax: str
    diachi: str
    email: str
    sdt: str
    tinhtrang: str
    
async def crawl_company_info_app(url: str, max_retries=3, retry_delay=2):
    llm_strategy = LLMExtractionStrategy(
        llm_config = LLMConfig(provider="openai/gpt-4o-mini", api_token=os.getenv("OPENAI_API_KEY")),
        schema=CongtY.model_json_schema(), # Or use model_json_schema()
        extraction_type="schema",
        instruction="""
Extract company name, tax, and address of company. If company name you crawl not meet the user input, just return empty json
"""
,
        # chunk_token_threshold=1000,
        # overlap_rate=0.0,
        apply_chunking=False,
        input_format="markdown",   # or "html", "fit_markdown"
        # extra_args={"temperature": 0.0, "max_tokens": 400}
    )
    run_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=True
    )

    for attempt in range(1, max_retries + 1):
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                return result
        except Exception as e:
            print(f"[Attempt {attempt}] Error: {e}")
            logger.error("Failed to crawl URL '%s' on attempt %d: %s", url, attempt, str(e))
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
            else:
                print("Max retries reached. Skipping.")
    return None

from collections import defaultdict
async def _fetch_company_info(company_name: str):
    """
    Fetch and return company info by searching and crawling masothue.com.
    
    Args:
        company_name (str): The name of the company to search for.
        
    Returns:
        dict or None: Flattened company info if matched, else None.
    """
    results = search_web(f"{company_name} mã số thuế", 3, domain='masothue.com')
    for result in results:
        try:
            output = await crawl_company_info_app(result)
            if not output or not output.extracted_content:
                continue
            
            data = json.loads(output.extracted_content)

            extracted_name = data[0].get('name', '').strip()
            if extracted_name:
                return str(output.extracted_content)

        except Exception as e:
            logger.error(f"Error crawling {result}: {e}", exc_info=True)
            # Continue to the next result instead of returning None immediately
            continue
    return None

class ThanhVien(BaseModel):
    name: str
    tax: str
    diachi: str

@tool
def fetch_company_info(company_name: str):
    try:
        result = asyncio.run(_fetch_company_info(company_name))
        if result is None:
            raise ValueError(f"Không tìm thấy thông tin cho '{company_name}'")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.exception("Lỗi trong fetch_company_info:")
        return {"status": "error", "message": str(e)}



async def crawl_company_person_app(company_name, url, max_retries=4, retry_delay=5):
    js_click_tab = ["document.querySelector('#lsTab3CT')?.click();"]

    for attempt in range(1, max_retries + 1):
        try:
            # Step 1: Extract general company info
            config1 = CrawlerRunConfig(
                extraction_strategy=company_name_extractor,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result1 = await crawler.arun(url=url, config=config1)

                data = json.loads(result1.extracted_content)

                flat_data = {}
                for entry in data:
                    flat_data.update(entry)

                crawl_company_name = flat_data.get('company_name', '')
                print(f"Crawled company name: {crawl_company_name}")

            config2 = CrawlerRunConfig(
                js_code=js_click_tab,
                extraction_strategy=company_person_extractor,
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result2 = await crawler.arun(url=url, config=config2)

                data = json.loads(result2.extracted_content)
                print(data)
                return data

        except Exception as e:
            print(f"[Attempt {attempt}] Error during crawling: {e}")
            if attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                print("Max retries reached. Giving up.")
                return None


async def _fetch_company_person(company_name):
    results = get_gg_search(f"{company_name} cafef", 1).get('data')
    for result in results:
        try:
            output = await crawl_company_person_app(company_name, result.get('url', ''))
            if output:
                return output
        except Exception as e:
            print(f"Error crawling {result}: {e}")
    return None

@tool
def fetch_company_person(company_name: str):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            result = asyncio.ensure_future(_fetch_company_person(company_name))
            # In some contexts (e.g. notebook or bot), await this outside
            raise RuntimeError("Cannot fetch_company_person inside running event loop without await.")
        else:
            result = loop.run_until_complete(_fetch_company_person(company_name))

        if result is None:
            raise ValueError(f"Không tìm thấy người đại diện cho '{company_name}'")
        return {"status": "success", "data": result}
    except Exception as e:
        logger.exception("Lỗi trong fetch_company_person:")
        return {"status": "error", "message": str(e)}

class Crawler(BaseModel):
    title: str
    content: str


async def _crawl_news(url):
    # 1. Define the LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config = LLMConfig(provider="openai/gpt-4o-mini", api_token=os.getenv("OPENAI_API_KEY")),
        schema=Crawler.model_json_schema(), # Or use model_json_schema()
        extraction_type="schema",
        instruction="""
Extract only the title and main content of the article in plain Markdown.

- title: The main title of the article.
- content: The full readable body of the article, excluding ads, navigation bars, and comments.

Exclude sidebars, ads, and any unrelated content. Return a clean JSON with only `title` and `content` fields.
"""
,
        # chunk_token_threshold=1000,
        # overlap_rate=0.0,
        apply_chunking=False,
        input_format="markdown",   # or "html", "fit_markdown"
        # extra_args={"temperature": 0.0, "max_tokens": 400}
    )

    # 2. Build the crawler config
    crawl_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS
    )

    # 3. Create a browser config if needed
    browser_cfg = BrowserConfig(headless=True)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        # 4. Let's say we want to crawl a single page
        result = await crawler.arun(
            url=url,
            config=crawl_config
        )

        if result.success:
            # 5. The extracted content is presumably JSON
            data = json.loads(result.extracted_content)
            return data

        else:
            print("Error:", result.error_message)
            return None
        
@tool
def crawl_news(url):
    return asyncio.run(_crawl_news(url))



@tool
def get_gg_news(news: str):
    try:
        results = google_news.get_news(news)
        if not results:
            raise ValueError("Không tìm thấy tin tức")
        
        # Bổ sung xử lý click để lấy link chi tiết như bạn đã làm
        links = []
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")  # Use new headless mode
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        try:
            for article in results:
                url = article.get("url")
                description = article.get("description")
                if not url:
                    continue
                try:
                    driver.get(url)
                    WebDriverWait(driver, 10).until(
                        lambda d: d.current_url != url or d.find_elements(By.TAG_NAME, "a")
                    )
                    final_url = driver.current_url
                    if final_url != url:
                        links.append(final_url)
                        continue

                    try:
                        link_element = driver.find_element(By.CSS_SELECTOR, 'a[rel="noopener noreferrer"]')
                        href = link_element.get_attribute("href")
                        if href:
                            links.append({"url": href, "description": description})
                    except Exception as e:
                        logger.warning(f"No external link for {url}: {e}")
                        continue
                except Exception as e:
                    logger.warning(f"Error processing URL {url}: {e}")
                    continue
        finally:
            driver.quit()

        return {"status": "success", "data": links}
    except Exception as e:
        logger.exception("Lỗi trong get_gg_news:")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    company_name = "CÔNG TY CP An Phát"
    print(fetch_company_info(company_name))

