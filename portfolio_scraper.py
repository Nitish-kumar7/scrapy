import re
import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import platform
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Rate limiting
last_request_time = 0
RATE_LIMIT_SECONDS = 2

def check_rate_limit():
    global last_request_time
    current_time = time.time()
    if current_time - last_request_time < RATE_LIMIT_SECONDS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before making another request.")
    last_request_time = current_time

class PortfolioData(BaseModel):
    name: Optional[str] = None
    about: Optional[str] = None
    skills: List[str] = []
    experience: List[Dict] = []
    projects: List[Dict] = []
    education: List[Dict] = []
    contact: Dict = {}

    class Config:
        schema_extra = {
            "example": {
                "name": "John Doe",
                "about": "Full-stack developer with 5 years of experience",
                "skills": ["Python", "JavaScript", "React"],
                "experience": [
                    {
                        "title": "Senior Developer",
                        "date": "2020-2023",
                        "responsibilities": ["Led team of 5 developers", "Implemented CI/CD pipeline"]
                    }
                ],
                "projects": [
                    {
                        "title": "E-commerce Platform",
                        "description": "Built with React and Node.js",
                        "link": "https://github.com/username/project"
                    }
                ],
                "education": [
                    {
                        "years": "2015-2019",
                        "institution": "University of Technology",
                        "degree": "Bachelor of Computer Science"
                    }
                ],
                "contact": {
                    "linkedin": "https://linkedin.com/in/johndoe",
                    "github": "https://github.com/johndoe",
                    "email": "john@example.com"
                }
            }
        }

@app.get("/")
async def root():
    return {"message": "Portfolio Scraper API"}

async def fetch_with_selenium(url: str) -> str:
    """Fetch webpage content using Selenium."""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Set environment variables for WebDriver Manager
        os.environ['WDM_SSL_VERIFY'] = '0'
        os.environ['WDM_LOCAL'] = '1'
        os.environ['WDM_LOG_LEVEL'] = '0'

        # Ensure 64-bit ChromeDriver is downloaded on Windows
        if platform.system() == 'Windows':
            os.environ['WDM_ARCHITECTURE'] = '64'
            os.environ['WDM_OS'] = 'win64'

        # Install ChromeDriver and get the path to the downloaded driver folder
        downloaded_driver_path = ChromeDriverManager().install()
        logger.info(f"WebDriverManager returned path for portfolio scraper: {downloaded_driver_path}")

        final_driver_executable_path = None

        # Determine the actual chromedriver.exe path
        if downloaded_driver_path and os.path.exists(downloaded_driver_path):
            if downloaded_driver_path.endswith('.exe'):
                final_driver_executable_path = downloaded_driver_path
            else:
                # Try common subdirectories
                possible_dirs = [downloaded_driver_path, os.path.dirname(downloaded_driver_path)]
                for p_dir in possible_dirs:
                    exe_in_dir = os.path.join(p_dir, 'chromedriver.exe')
                    if os.path.exists(exe_in_dir) and os.path.isfile(exe_in_dir):
                        final_driver_executable_path = exe_in_dir
                        break
                    win32_subdir = os.path.join(p_dir, 'chromedriver-win32')
                    exe_in_win32_subdir = os.path.join(win32_subdir, 'chromedriver.exe')
                    if os.path.exists(exe_in_win32_subdir) and os.path.isfile(exe_in_win32_subdir):
                        final_driver_executable_path = exe_in_win32_subdir
                        break

        if not final_driver_executable_path or not os.path.exists(final_driver_executable_path) or not final_driver_executable_path.endswith('.exe'):
            raise Exception(f"Could not find a valid chromedriver.exe executable for portfolio scraper. Last path checked: {final_driver_executable_path}")

        logger.info(f"Using ChromeDriver for portfolio scraper at: {final_driver_executable_path}")

        service = Service(executable_path=final_driver_executable_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get(url)
        time.sleep(2)  # Wait for JavaScript to load
        html_content = driver.page_source
        driver.quit()
        return html_content
    except Exception as e:
        logger.error(f"Error fetching URL with Selenium for portfolio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch URL for portfolio: {str(e)}")

def clean_text(text: str) -> Optional[str]:
    """Clean and normalize text."""
    if not text:
        return None
    return ' '.join(text.split())

def extract_text_from_tags(soup, selectors: List[str], max_length: int = 500, fallback_tags: List[str] = None, keywords: List[str] = None, exclude_keywords: List[str] = None) -> Optional[str]:
    """Extract clean text from HTML tags using CSS selectors."""
    if exclude_keywords is None:
        exclude_keywords = ['copyright', 'privacy', 'terms', 'cookie', 'all rights', 'responsibilities', 'experience', 'projects', 'skills', 'education', 'contact']
    extracted_texts = []

    for selector in selectors:
        tags = soup.select(selector)
        for tag in tags:
            text = clean_text(tag.get_text())
            if text and len(text) <= max_length and (not keywords or any(kw.lower() in text.lower() for kw in keywords)) and not any(ex_kw.lower() in text.lower() for ex_kw in exclude_keywords):
                extracted_texts.append(text)

    if not extracted_texts and fallback_tags:
        for tag_name in fallback_tags:
            tags = soup.find_all(tag_name)
            for tag in tags:
                text = clean_text(tag.get_text())
                if text and len(text) <= max_length and not any(ex_kw.lower() in text.lower() for ex_kw in exclude_keywords) and (not keywords or any(kw.lower() in text.lower() for kw in keywords)):
                    extracted_texts.append(text)

    return " ".join(list(dict.fromkeys(extracted_texts)))[:max_length] if extracted_texts else None

def extract_list_from_tags(soup, selectors: List[str], separator: str = ',') -> List[str]:
    """Extract unique, clean text items from a list or section."""
    items = []
    exclude_keywords = {'projects', 'skills', 'experience', 'education', 'contact', 'resume', 'certificates', 'terms', 'conditions', 'icon', 'hackathons', 'internships'}

    for selector in selectors:
        elements = soup.select(selector)
        for elem in elements:
            text = clean_text(elem.get_text() or elem.get('alt') or elem.get('title'))
            if not text or any(ex_kw.lower() in text.lower() for ex_kw in exclude_keywords):
                continue
            if separator in text:
                items.extend([clean_text(item) for item in text.split(separator) if clean_text(item) and not any(ex_kw.lower() in item.lower() for ex_kw in exclude_keywords)])
            elif len(text.split()) <= 5 and text not in items:
                items.append(text)

    return list(dict.fromkeys([item for item in items if item]))

def extract_link_from_tags(soup, selectors: List[str], base_url: str) -> Optional[str]:
    """Extract and resolve a URL from CSS selectors."""
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag and tag.get('href'):
            href = tag['href']
            if href.startswith('mailto:'):
                return href.replace('mailto:', '')
            return urljoin(base_url, href)
    return None

def parse_portfolio(html_content: str, url: str) -> Dict:
    """Parse comprehensive portfolio data from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    logger.info(f"Parsing HTML content, length: {len(html_content)}")
    
    portfolio_data = {
        "name": None,
        "about": None,
        "skills": [],
        "experience": [],
        "projects": [],
        "education": [],
        "contact": {}
    }
    
    # Extract name
    name_selectors = ['h1.text-5xl', 'h2.text-4xl', '.name', '.profile-name', '.hero h1']
    portfolio_data["name"] = extract_text_from_tags(
        soup, name_selectors, max_length=100, keywords=['developer', 'engineer', 'yuva'], exclude_keywords=['projects', 'skills', 'experience', 'responsibilities']
    ) or clean_text(soup.find('title').get_text().split('|')[0] if soup.find('title') else None)
    logger.info(f"Extracted name: {portfolio_data['name']}")

    # Extract about section
    about_selectors = ['#about p', '#hero p.text-lg', '.about p', '.bio p', '.intro p', '.max-w-prose']
    portfolio_data["about"] = extract_text_from_tags(
        soup, about_selectors, max_length=500, keywords=['about', 'developer', 'passionate', 'ai'], exclude_keywords=['contact', 'resume', 'projects', 'skills']
    )
    logger.info(f"Extracted about: {portfolio_data['about'][:100] if portfolio_data['about'] else None}")

    # Extract skills
    skills_selectors = ['#skills .skill-item', '#skills span.inline-block', '.skills li', '.technologies span.text-sm', '.flex-wrap span.rounded']
    skills_section = soup.select_one('#skills, .skills, .technologies')
    if skills_section:
        portfolio_data["skills"] = extract_list_from_tags(soup, skills_selectors)
    logger.info(f"Extracted {len(portfolio_data['skills'])} skills: {portfolio_data['skills'][:10]}")

    # Extract experience
    experience_selectors = ['#experience', '.experience', '.timeline', '[class*="experience"]']
    experience_section = soup.select_one(','.join(experience_selectors))
    if experience_section:
        entries = experience_section.select('.timeline-entry, .experience-item, .job, div.mb-8')
        for entry in entries:
            title = extract_text_from_tags(entry, ['h3.text-xl', 'h4.text-lg', '.job-title'], max_length=100, exclude_keywords=['responsibilities', 'date'])
            date_text = extract_text_from_tags(entry, ['.date-range', '.duration', '.text-sm'], max_length=50)
            # Clean date to extract only the range (e.g., "April 2024 - April 2025")
            date_match = re.search(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* \d{4} - (?:Present|\w+ \d{4})\b', date_text or '')
            date = date_match.group(0) if date_match else date_text
            experience = {
                "title": title,
                "date": date,
                "responsibilities": [
                    clean_text(r.get_text()) for r in entry.select('ul li, .description p') if clean_text(r.get_text())
                ]
            }
            if any(experience.values()):
                portfolio_data["experience"].append(experience)
    logger.info(f"Extracted {len(portfolio_data['experience'])} experience entries")

    # Extract projects
    project_selectors = ['#projects', '.projects', '.portfolio', '[class*="projects"]', '.grid']
    project_section = soup.select_one(','.join(project_selectors))
    if project_section:
        project_entries = project_section.select('.project-item, .portfolio-item, div.rounded-lg')
        for entry in project_entries:
            project = {
                "title": extract_text_from_tags(entry, ['h3.text-lg', 'h4', '.project-name'], max_length=100),
                "description": extract_text_from_tags(entry, ['p.description', '.summary'], max_length=500),
                "link": extract_link_from_tags(entry, ['a.project-link', 'a[href*="github.com"]'], url)
            }
            if any(project.values()):
                portfolio_data["projects"].append(project)
    logger.info(f"Extracted {len(portfolio_data['projects'])} projects")

    # Extract education
    education_selectors = ['#education', '.education', '[class*="education"]']
    education_section = soup.select_one(','.join(education_selectors))
    if education_section:
        education_entries = education_section.select('.education-item, div.mb-6')
        for entry in education_entries:
            education = {
                "years": extract_text_from_tags(entry, ['.years', '.duration', '.text-sm'], max_length=50),
                "institution": extract_text_from_tags(entry, ['h3.text-lg', '.institution'], max_length=100),
                "degree": extract_text_from_tags(entry, ['p.degree', '.qualification'], max_length=100)
            }
            if any(education.values()):
                portfolio_data["education"].append(education)
    logger.info(f"Extracted {len(portfolio_data['education'])} education entries")

    # Extract contact information
    contact_selectors = {
        "linkedin": "a[href*='linkedin.com']",
        "twitter": "a[href*='twitter.com'], a[href*='x.com']",
        "instagram": "a[href*='instagram.com']",
        "github": "a[href*='github.com']",
        "email": "a[href*='mailto:']",
        "website": "a[href*='http']:not([href*='linkedin.com'],[href*='twitter.com'],[href*='x.com'],[href*='instagram.com'],[href*='github.com'])"
    }
    contact_section = soup.select_one('#contact, .contact, .connect, footer, [class*="contact"], .social-links')
    if contact_section:
        for platform, selector in contact_selectors.items():
            link_elem = contact_section.select_one(selector)
            if link_elem and link_elem.get("href"):
                portfolio_data["contact"][platform] = link_elem["href"].replace('mailto:', '')
    else:
        for platform, selector in contact_selectors.items():
            link_elem = soup.select_one(selector)
            if link_elem and link_elem.get("href"):
                portfolio_data["contact"][platform] = link_elem["href"].replace('mailto:', '')
    logger.info(f"Extracted {len(portfolio_data['contact'])} contact links")

    # Save to JSON
    try:
        filename = f"portfolio_{url.replace('https://', '').replace('http://', '').replace('/', '_')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f, indent=2)
        logger.info(f"Saved portfolio data to {filename}")
    except Exception as e:
        logger.warning(f"Error saving JSON: {str(e)}")
    
    return portfolio_data

@app.get("/scrape-portfolio", response_model=PortfolioData, dependencies=[Depends(check_rate_limit)])
async def scrape_portfolio_endpoint(url: str):
    """Scrape portfolio data from a given URL."""
    if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', url):
        raise HTTPException(status_code=400, detail="Invalid URL format")

    try:
        logger.info(f"Starting portfolio scrape for URL: {url}")
        html_content = await fetch_with_selenium(url)
        portfolio_data = parse_portfolio(html_content, url)

        if not any([portfolio_data["name"], portfolio_data["about"], portfolio_data["skills"],
                    portfolio_data["experience"], portfolio_data["projects"], portfolio_data["education"],
                    portfolio_data["contact"]]):
            raise HTTPException(status_code=500, detail="Failed to extract meaningful portfolio data")

        logger.info("Scraping completed successfully!")
        return portfolio_data

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape portfolio: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 