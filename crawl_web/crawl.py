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
# from crawl4ai.extraction_strategy import CosineStrategy
from huggingface_hub import login
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import boto3
import os
import numpy as np 
from selenium.common.exceptions import NoSuchElementException
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

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
OPENAI_SECRET_KEY = os.getenv("OPENAI_API_KEY")
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless=new")  # newer headless mode
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--log-level=3")

logger = logging.getLogger(__name__)
google_news = GNews(language='vi', 
                    country='VN',
                    max_results=5,
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

async def _fetch_company_info(company_name: str):
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

@tool
def fetch_company_info(company_name: str):
    return asyncio.run(_fetch_company_info(company_name))

async def crawl_company_person_app(company_name, url):
    js_click_tab = ["document.querySelector('#lsTab3CT')?.click();"]

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
        
    if not is_matching_company(crawl_company_name, company_name):
        return None

    # Step 2: Click and extract people info
    config2 = CrawlerRunConfig(
        js_code=js_click_tab,
        extraction_strategy=company_person_extractor,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result2 = await crawler.arun(url=url, config=config2)
        data = json.loads(result2.extracted_content)
    

    return data


async def _fetch_company_person(company_name):
    results = search_web(f"{company_name} cafef", 1, domain='cafef.vn')
    for result in results:
        try:
            output = await crawl_company_person_app(company_name, result)
            return output
        except Exception as e:
            print(f"Error crawling {result}: {e}")
    return None

@tool
def fetch_company_person(company_name: str):
    return asyncio.run(_fetch_company_person(company_name))

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
def get_news(news):
    results = google_news.get_news(news)
    links = []

    # Setup Chrome only once
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        for article in results:
            url = article.get('url')
            description = article.get('description')
            if not url:
                continue

            try:
                driver.get(url)

                # Wait for potential redirection or anchor element
                WebDriverWait(driver, 10).until(
                    lambda d: d.current_url != url or d.find_elements(By.TAG_NAME, "a")
                )

                # Handle redirection
                final_url = driver.current_url
                if final_url != url:
                    links.append(final_url)
                    continue

                # Try to extract external link
                try:
                    link_element = driver.find_element(By.CSS_SELECTOR, 'a[rel="noopener noreferrer"]')
                    href = link_element.get_attribute("href")
                    if href:
                        links.append(
                            {
                                "url": href,
                                "description": description
                            }
                        )
                except Exception as e:
                    print(f"No external link found for {url}: {e}")
                    continue

            except Exception as e:
                print(f"Error processing URL {url}: {e}")
                continue

    finally:
        driver.quit()

    return links

if __name__ == "__main__":
    company_name = "Công ty Cổ phần Nhựa An Phát Xanh"
    output = fetch_news(company_name)
    print(output)

