import json
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from typing import Dict, Any, Optional
import platform
import requests
import zipfile
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class InstagramScraper:
    def __init__(self, rate_limit: int = 5):
        """Initialize the Instagram scraper with rate limiting."""
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.driver = None
        self._initialize_driver()

    def _download_chromedriver(self):
        """Download the correct ChromeDriver version for 64-bit Windows."""
        try:
            # Chrome version 137.0.7151.70
            url = "https://storage.googleapis.com/chrome-for-testing-public/137.0.7151.70/win64/chromedriver-win64.zip"
            response = requests.get(url)
            if response.status_code == 200:
                # Extract the zip file
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                    # Create a directory for the driver
                    driver_dir = os.path.join(os.path.expanduser('~'), '.wdm', 'drivers', 'chromedriver', 'win64', '137.0.7151.70')
                    os.makedirs(driver_dir, exist_ok=True)
                    # Extract to the directory
                    zip_ref.extractall(driver_dir)
                    # Return the path to the chromedriver.exe
                    return os.path.join(driver_dir, 'chromedriver-win64', 'chromedriver.exe')
            else:
                raise Exception(f"Failed to download ChromeDriver: {response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading ChromeDriver: {str(e)}")
            raise

    def _initialize_driver(self):
        """Initialize the Selenium WebDriver with appropriate options."""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36')
            
            # Clear WebDriver Manager cache
            cache_path = os.path.expanduser('~/.wdm')
            if os.path.exists(cache_path):
                import shutil
                shutil.rmtree(cache_path)
                logger.info("Cleared WebDriver Manager cache")

            # Download and use the correct ChromeDriver version
            driver_path = self._download_chromedriver()
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            raise RuntimeError(f"Failed to initialize Instagram scraper: {str(e)}")

    def _wait_for_rate_limit(self):
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.rate_limit:
            time.sleep(self.rate_limit - time_since_last_request)
        self.last_request_time = time.time()

    def scrape_profile(self, username: str) -> Dict[str, Any]:
        """Scrape Instagram profile data."""
        if not self.driver:
            try:
                self._initialize_driver()
            except Exception as e:
                logger.error(f"Failed to initialize driver: {str(e)}")
                return {
                    "error": f"Failed to initialize Instagram scraper: {str(e)}",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }

        try:
            self._wait_for_rate_limit()
            url = f"https://www.instagram.com/{username}/"
            self.driver.get(url)

            # Wait for the page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "main"))
                )
            except:
                logger.warning(f"Profile page not loaded for {username}. It may be private or not exist.")
                return {
                    "error": "Profile is private or not found",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }

            # Extract data from script tags
            profile_data = {
                "bio": None,
                "followers": None,
                "posts_count": None,
                "username": username,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            scripts = self.driver.find_elements(By.TAG_NAME, "script")
            for script in scripts:
                if script.get_attribute("innerHTML") and 'window._sharedData' in script.get_attribute("innerHTML"):
                    try:
                        data = json.loads(script.get_attribute("innerHTML").split('window._sharedData = ')[1].split(';</script>')[0])
                        if 'entry_data' in data and 'ProfilePage' in data['entry_data']:
                            profile = data['entry_data']['ProfilePage'][0]['graphql']['user']
                            profile_data.update({
                                "bio": profile.get('biography', ''),
                                "followers": profile.get('edge_followed_by', {}).get('count', 0),
                                "posts_count": profile.get('edge_owner_to_timeline_media', {}).get('count', 0)
                            })
                            break
                    except Exception as e:
                        logger.warning(f"Failed to parse script data: {str(e)}")
                        continue

            if not any([profile_data["bio"], profile_data["followers"], profile_data["posts_count"]]):
                return {
                    "error": "Could not extract profile data",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }

            return profile_data
        except Exception as e:
            logger.error(f"Error scraping profile: {str(e)}")
            return {
                "error": f"Error scraping profile: {str(e)}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }

    def __del__(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {str(e)}")

# Example usage
if __name__ == "__main__":
    try:
        scraper = InstagramScraper(rate_limit=5)
        profile_data = scraper.scrape_profile("nitish5300")
        print(json.dumps(profile_data, indent=2))
    except Exception as e:
        logger.error(f"Main execution failed: {str(e)}")