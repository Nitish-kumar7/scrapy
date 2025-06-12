
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
import re

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
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-javascript')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.managed_default_content_settings.images": 2
            })
            
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
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
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

    def _extract_from_page_source(self, page_source: str, username: str) -> Dict[str, Any]:
        """Extract data from page source using regex patterns."""
        profile_data = {
            "bio": None,
            "followers": None,
            "posts_count": None,
            "username": username,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            # Multiple patterns for biography extraction
            bio_patterns = [
                r'"biography":"([^"]*)"',
                r'"biography":\s*"([^"]*)"',
                r'<meta property="og:description" content="([^"]*)"',
                r'content="([^"]*)" property="og:description"'
            ]
            
            for pattern in bio_patterns:
                bio_match = re.search(pattern, page_source, re.IGNORECASE)
                if bio_match:
                    bio_text = bio_match.group(1)
                    if bio_text and len(bio_text.strip()) > 0:
                        try:
                            profile_data["bio"] = bio_text.encode().decode('unicode_escape')
                        except:
                            profile_data["bio"] = bio_text
                        break

            # Enhanced followers count extraction
            followers_patterns = [
                r'"edge_followed_by":{"count":(\d+)}',
                r'"followers_count":(\d+)',
                r',"c":(\d+),"r":\d+},"followed_by"',
                r'"follower_count":(\d+)',
                r'(\d+) followers',
                r'followers.*?(\d+)',
                r'"userInteractionStatistic".*?"value":"(\d+)".*?"name":"follows"'
            ]
            
            for pattern in followers_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    try:
                        profile_data["followers"] = int(match.group(1))
                        break
                    except:
                        continue

            # Enhanced posts count extraction
            posts_patterns = [
                r'"edge_owner_to_timeline_media":{"count":(\d+)}',
                r'"posts_count":(\d+)',
                r'"media_count":(\d+)',
                r'(\d+) posts',
                r'posts.*?(\d+)',
                r'"interactionStatistic".*?"value":"(\d+)".*?"name":"posts"'
            ]
            
            for pattern in posts_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    try:
                        profile_data["posts_count"] = int(match.group(1))
                        break
                    except:
                        continue

            # Try to extract structured data
            structured_data_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            structured_matches = re.findall(structured_data_pattern, page_source, re.DOTALL)
            
            for structured_data in structured_matches:
                try:
                    data = json.loads(structured_data)
                    if isinstance(data, dict):
                        if "interactionStatistic" in data:
                            for stat in data["interactionStatistic"]:
                                if stat.get("interactionType", {}).get("name") == "follows":
                                    profile_data["followers"] = int(stat.get("userInteractionCount", 0))
                                elif "posts" in str(stat.get("interactionType", {})).lower():
                                    profile_data["posts_count"] = int(stat.get("userInteractionCount", 0))
                        
                        if "description" in data and not profile_data["bio"]:
                            profile_data["bio"] = data["description"]
                except:
                    continue

        except Exception as e:
            logger.warning(f"Error extracting data from page source: {str(e)}")

        return profile_data

    def _extract_from_elements(self, username: str) -> Dict[str, Any]:
        """Extract data using Selenium element selectors."""
        profile_data = {
            "bio": None,
            "followers": None,
            "posts_count": None,
            "username": username,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            # Wait for profile elements to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )

            # Try to extract bio with expanded selectors
            bio_selectors = [
                "h1 + div span",
                "header section div span",
                "[data-testid='user-bio'] span",
                "section > div span",
                "article div span",
                "main section div span",
                "div[dir='auto'] span",
                "header div div span",
                "span[dir='auto']"
            ]
            for selector in bio_selectors:
                try:
                    bio_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in bio_elements:
                        text = element.text.strip()
                        if text and len(text) > 5 and not text.isdigit() and "follow" not in text.lower():
                            profile_data["bio"] = text
                            break
                    if profile_data["bio"]:
                        break
                except:
                    continue

            # Try to extract followers and posts count from meta elements or visible text
            meta_selectors = [
                "header section ul li span",
                "header section div span", 
                "section div span",
                "main section ul li span",
                "header div span",
                "a[href*='followers'] span",
                "a[href*='following'] span"
            ]
            
            numbers_found = []
            for selector in meta_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        # Look for numbers with commas or 'K', 'M' suffixes
                        if re.match(r'^\d{1,3}(,\d{3})*$|^\d+(\.\d+)?[KM]?$', text):
                            numbers_found.append(text)
                except:
                    continue

            # Process found numbers (typically posts, followers, following in that order)
            if len(numbers_found) >= 2:
                try:
                    # First number is usually posts
                    posts_text = numbers_found[0].replace(',', '')
                    if 'K' in posts_text:
                        profile_data["posts_count"] = int(float(posts_text.replace('K', '')) * 1000)
                    elif 'M' in posts_text:
                        profile_data["posts_count"] = int(float(posts_text.replace('M', '')) * 1000000)
                    else:
                        profile_data["posts_count"] = int(posts_text)

                    # Second number is usually followers
                    followers_text = numbers_found[1].replace(',', '')
                    if 'K' in followers_text:
                        profile_data["followers"] = int(float(followers_text.replace('K', '')) * 1000)
                    elif 'M' in followers_text:
                        profile_data["followers"] = int(float(followers_text.replace('M', '')) * 1000000)
                    else:
                        profile_data["followers"] = int(followers_text)
                except:
                    pass

        except Exception as e:
            logger.warning(f"Error extracting data from elements: {str(e)}")

        return profile_data

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
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)

            # Wait for page to load
            time.sleep(3)

            # Check if profile exists - be more lenient with detection
            page_source = self.driver.page_source.lower()
            
            # Check for definitive "not found" indicators
            not_found_indicators = [
                "sorry, this page isn't available",
                "the link you followed may be broken",
                "user not found",
                "page not found"
            ]
            
            if any(indicator in page_source for indicator in not_found_indicators):
                return {
                    "error": "Profile not found",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }

            # Only return "private" if we're very sure - try to extract data first
            # Many profiles show some public data even if marked "private"

            # Try multiple extraction methods with retries
            attempts = 0
            max_attempts = 3
            profile_data = None
            
            while attempts < max_attempts:
                # Try page source extraction
                profile_data = self._extract_from_page_source(self.driver.page_source, username)
                
                # If page source extraction didn't work well, try element extraction
                if not all([profile_data["bio"], profile_data["followers"], profile_data["posts_count"]]):
                    element_data = self._extract_from_elements(username)
                    # Merge the data, preferring non-None values
                    for key in ["bio", "followers", "posts_count"]:
                        if profile_data[key] is None and element_data[key] is not None:
                            profile_data[key] = element_data[key]

                # If we got some meaningful data, break
                if any([profile_data["bio"], profile_data["followers"], profile_data["posts_count"]]):
                    break
                
                attempts += 1
                if attempts < max_attempts:
                    logger.info(f"Retry {attempts} for {username}")
                    time.sleep(2)
                    self.driver.refresh()
                    time.sleep(3)

            # Check if profile is actually private after trying to extract data
            page_source_lower = self.driver.page_source.lower()
            if ("this account is private" in page_source_lower and 
                not any([profile_data["bio"], profile_data["followers"], profile_data["posts_count"]])):
                return {
                    "error": "Profile is private",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }

            # If still no data, provide a more informative error
            if not any([profile_data["bio"], profile_data["followers"], profile_data["posts_count"]]):
                return {
                    "error": "Could not extract profile data - Instagram may be blocking automated access",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }

            logger.info(f"Successfully extracted data for {username}")
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
