import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from duckduckgo_search import DDGS
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from pprint import pprint
import json

from rapidfuzz import fuzz

def is_matching_company(expected_name, extracted_name, threshold=85):
    """
    Compare two names using fuzzy matching.
    Returns True if similarity is above threshold.
    """
    if not extracted_name:
        return False
    score = fuzz.partial_ratio(expected_name.lower(), extracted_name.lower())
    print(f"Fuzzy score: {score} for '{expected_name}' vs '{extracted_name}'")
    return score >= threshold


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


def search_web(text, limit, domain=None):
    filtered_results = []
    with DDGS() as ddgs:
        raw_results = ddgs.text(keywords=text, max_results=limit)
        for result in raw_results:
            href = result['href']
            if (domain is None or domain in href ):
                filtered_results.append(href)
    return filtered_results


async def crawl_app(url):
    browser_config = BrowserConfig(headless = True, viewport_width = 1280, viewport_height = 720)
    run_config = CrawlerRunConfig(extraction_strategy = company_info_extraction, cache_mode = CacheMode.BYPASS)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)
        return result


async def fetch_company_info(company_name):
    results = search_web(f"{company_name} mã số thuế", 5, domain='masothue.com')
    # results = list(filter(lambda x: is_matching_company(x.title, company_name)))
    for result in results:
        try:
            output = await crawl_app(result)
            data = json.loads(output.extracted_content)

            flat_data = {}
            for entry in data:
                flat_data.update(entry)

            if flat_data['company_name'] and is_matching_company(company_name, flat_data['company_name']):
                return flat_data
    
        except Exception as e:
            print(f"Error crawling {result}: {e}")
            return None
    return None

async def fetch_company_person(company_name):
    

if __name__ == "__main__":
    company = "CTCP Nhựa An Phát Xanh"
    output = asyncio.run(fetch_company_info(company))

