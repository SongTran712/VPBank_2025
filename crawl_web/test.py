import asyncio
import os
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig, LLMContentFilter, DefaultMarkdownGenerator
from crawl4ai.extraction_strategy import LLMExtractionStrategy
import os
import asyncio
import json
from pydantic import BaseModel, Field
from typing import List
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

class Crawler(BaseModel):
    title: str
    content: str

async def main():
    # 1. Define the LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config = LLMConfig(provider="openai/gpt-4o-mini", api_token=""),
        schema=Crawler.schema_json(), # Or use model_json_schema()
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
            url="https://thanhnien.vn/hang-gia-la-su-lua-doi-trang-tron-xoi-mon-dao-duc-kinh-doanh-185250710155406862.htm",
            config=crawl_config
        )

        if result.success:
            # 5. The extracted content is presumably JSON
            data = json.loads(result.extracted_content)
            print("Extracted items:", data)

        else:
            print("Error:", result.error_message)

if __name__ == "__main__":
    asyncio.run(main())

