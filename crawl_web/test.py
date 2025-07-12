import asyncio
import nest_asyncio
nest_asyncio.apply()

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def get_external_link_selenium(url):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")  # newer headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--log-level=3")

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        driver.get(url)
        
        # Wait for redirection or anchor element (fallback)
        WebDriverWait(driver, 10).until(
            lambda d: d.current_url != url or d.find_elements(By.TAG_NAME, "a")
        )

        # If redirected, return final URL
        if driver.current_url != url:
            return driver.current_url

        # Fallback: find external link
        try:
            link = driver.find_element(By.CSS_SELECTOR, 'a[rel="noopener noreferrer"]')
            return link.get_attribute('href')
        except:
            return None

    except Exception as e:
        print("Selenium error:", e)
        return None
    finally:
        try:
            driver.quit()
        except:
            pass

async def resolve_actual_url(url):
    return await asyncio.to_thread(get_external_link_selenium, url)

async def test():
    url = "https://news.google.com/rss/articles/CBMivwFBVV95cUxORFhjX25IeWtMb1dlOVNIM0R4dzl6dHJDQlJXTkoxOTZncUdRX3dXc05FOWc0b1NybzFzbkE5UlJ6dnlROTVVX0M0ZXlsaDY0Q2FOOGswYzN2cFB3ckY1a2R4M3ZKZ0JXZWJ6MkVFTWR5Q0NXV2R6MHNubXJxMGJTTTFXdnpQdFg1TTVPWFZjYzhvTFZEcFZabnJhRmlLd01VN2ZNU0dyOXcwRF9jVGVVc0FLdUQzU24zMVVoXzNUQQ?oc=5&hl=en-US&gl=US&ceid=US:en"
    real_url = await resolve_actual_url(url)
    print("Resolved:", real_url)

if __name__ == "__main__":
    asyncio.run(test())
