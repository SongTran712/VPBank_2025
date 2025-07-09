import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from duckduckgo_search import DDGS
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from pprint import pprint
import json
from rapidfuzz.fuzz import partial_ratio
import logging
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from gnews import GNews
from crawl4ai.extraction_strategy import CosineStrategy
from huggingface_hub import login
import os
from dotenv import load_dotenv
# Load the .env file
load_dotenv()

login(os.getenv("HF_ACCESS_TOKEN"))

logger = logging.getLogger(__name__)
google_news = GNews(language='vi', 
                    country='VN',
                    max_results= 10,
                    period = '1y'
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
company_info_schema ={
    "name": "company_info",
    "baseSelector": "tr", 
    "fields":[
        {
            "name": "company_name",
            "selector": 'th[itemprop="name"] span.copy',
            "type": "text"
        },
        {
            "name": "masothue",
            "selector": 'td[itemprop="taxID"] span.copy',
            "type": "text"
        },
        {
            "name": "diachi",
            "selector": 'td[itemprop="address"] span.copy',
            "type": "text"
        },
    ]
}
company_info_extraction = JsonCssExtractionStrategy(company_info_schema) 
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


async def crawl_company_info_app(url: str):
    """
    Crawl company information from a given URL using AsyncWebCrawler.

    Args:
        url (str): The target webpage URL.

    Returns:
        result: The crawler result if successful, otherwise None.
    """
    run_config = CrawlerRunConfig(
        extraction_strategy=company_info_extraction,
        cache_mode=CacheMode.BYPASS
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            return result

    except Exception as e:
        logger.error("Failed to crawl URL '%s': %s", url, str(e))
        return None


async def fetch_company_info(company_name: str):
    """
    Fetch and return company info by searching and crawling masothue.com.
    
    Args:
        company_name (str): The name of the company to search for.
        
    Returns:
        dict or None: Flattened company info if matched, else None.
    """
    results = search_web(f"{company_name} mã số thuế", 5, domain='masothue.com')

    for result in results:
        try:
            output = await crawl_company_info_app(result)
            if not output or not output.extracted_content:
                continue

            data = json.loads(output.extracted_content)

            flat_data = {}
            for entry in data:
                flat_data.update(entry)

            extracted_name = flat_data.get('company_name', '').strip()
            if extracted_name and is_matching_company(company_name, extracted_name):
                return flat_data

        except Exception as e:
            logger.error(f"Error crawling {result}: {e}", exc_info=True)
            # Continue to the next result instead of returning None immediately
            continue
    return None


async def crawl_company_person_app(company_name, url):
    js_click_tab = ["document.querySelector('#lsTab3CT')?.click();"]

    # Step 1: Extract general company info
    config1 = CrawlerRunConfig(
        extraction_strategy=company_name_extractor,
        wait_until="networkidle"
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result1 = await crawler.arun(url=url, config=config1)
        data = json.loads(result1.extracted_content)
        flat_data = {}
        for entry in data:
            flat_data.update(entry)
        crawl_company_name = flat_data.get('company_name', '')
        
    if not is_matching_company(crawl_company_name, company_name):
        return None

    # Step 2: Click and extract people info
    config2 = CrawlerRunConfig(
        js_code=js_click_tab,
        extraction_strategy=company_person_extractor,
        wait_until="networkidle"
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result2 = await crawler.arun(url=url, config=config2)
        data = json.loads(result2.extracted_content)
    

    return data

async def fetch_company_person(company_name):
    results = search_web(f"{company_name} cafef", 5, domain='cafef.vn')
    for result in results:
        try:
            output = await crawl_company_person_app(company_name, result)
            return output
        except Exception as e:
            print(f"Error crawling {result}: {e}")
    return None


company_news_schema = {
    "name": "article_content",
    "baseSelector": "div.post_content",
    "type":"group",
    "fields": [
        {
            "name": "text_content",
            "selector": "p",
            "type": "text"
        }
    ]
}

company_news_extractor = JsonCssExtractionStrategy(company_news_schema)

async def fetch_company_news(company_name):
    
    strategy = CosineStrategy(
        semantic_filter=company_name,    # Target content type
        word_count_threshold=100,             # Minimum words per cluster
        sim_threshold=0,                    # Similarity threshold
        top_k = 3
    )
    urls = google_news.get_news(company_name)

    config = CrawlerRunConfig(
        # extraction_strategy = company_news_extractor,
        # css_selector = "#post_content"
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url = urls[0]['url'], config = config
        )
        print(result.extracted_content)
        
    return result

if __name__ == "__main__":
    company_name = "Công ty Cổ phần Nhựa An Phát Xanh"
    output = asyncio.run(fetch_company_news(company_name))


