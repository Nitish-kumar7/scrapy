from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Request, BackgroundTasks
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import os
from datetime import datetime
import json
from dotenv import load_dotenv
import aiohttp
import asyncio
from github_extractor import fetch_github_profile, GitHubAPIError
from portfolio_scraper import fetch_with_selenium, parse_portfolio
from resume_parser import parse_resume, ResumeParserError
from instagram_scraper import InstagramScraper
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

app = FastAPI(
    title="Social Media Scraping API",
    description="API for scraping social media, portfolios, and analyzing candidate data."
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key validation
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.warning("API_KEY not found in environment variables")

# Initialize Instagram scraper
instagram_scraper = None
try:
    instagram_scraper = InstagramScraper(rate_limit=3)
    logger.info("Instagram scraper initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Instagram scraper: {str(e)}")

async def get_api_key(api_key: str = Depends(api_key_header)):
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

# Models
class CandidateData(BaseModel):
    portfolio_url: Optional[str] = None
    github_username: Optional[str] = None
    instagram_username: Optional[str] = None
    resume_file: Optional[UploadFile] = None

# Routes
@app.post("/collect-candidate-data", dependencies=[Depends(get_api_key)])
async def collect_candidate_data(
    resume_file: UploadFile = File(...)
):
    """Collect and analyze candidate data from multiple sources."""
    try:
        candidate_data = {}
        errors = {}
        warnings = {}
        
        # Initialize variables
        portfolio_url = None
        github_username = None
        instagram_username = None

        # --- Process resume first to extract URLs and usernames ---
        parsed_resume_data = None
        if resume_file:
            try:
                if not resume_file.filename:
                    errors["resume"] = "No resume file provided"
                elif not resume_file.filename.lower().endswith(('.pdf', '.docx')):
                    errors["resume"] = "Only PDF and DOCX resume files are supported"
                else:
                    content = await resume_file.read()
                    parsed_resume_data = parse_resume(content, resume_file.filename)
                    candidate_data["resume"] = parsed_resume_data

                    # Extract URLs and usernames from resume
                    if parsed_resume_data:
                        if parsed_resume_data.get("portfolio_url"):
                            portfolio_url = parsed_resume_data["portfolio_url"]
                        if parsed_resume_data.get("github_url"):
                            github_username = parsed_resume_data["github_url"].split('/')[-1]  # Extract username from URL
                        if parsed_resume_data.get("instagram_username"):
                            instagram_username = parsed_resume_data["instagram_username"]

            except Exception as e:
                errors["resume"] = str(e)

        # Process portfolio data if URL was found
        if portfolio_url:
            try:
                html_content = await fetch_with_selenium(portfolio_url)
                if html_content:
                    candidate_data["portfolio"] = parse_portfolio(html_content, portfolio_url)
                else:
                    errors["portfolio"] = "Could not fetch portfolio content"
            except Exception as e:
                errors["portfolio"] = str(e)

        # Process GitHub data if username was found
        if github_username:
            try:
                candidate_data["github"] = await fetch_github_profile(github_username)
            except GitHubAPIError as e:
                errors["github"] = str(e)
            except Exception as e:
                errors["github"] = str(e)

        # Process Instagram data if username was found
        if instagram_username:
            global instagram_scraper
            if not instagram_scraper:
                try:
                    instagram_scraper = InstagramScraper(rate_limit=3)
                    logger.info("Instagram scraper initialized successfully")
                except Exception as e:
                    errors["instagram"] = f"Failed to initialize Instagram scraper: {str(e)}"
            else:
                try:
                    profile_data = instagram_scraper.scrape_profile(instagram_username)
                    if "error" in profile_data:
                        errors["instagram"] = profile_data["error"]
                    else:
                        candidate_data["instagram"] = {
                            "bio": profile_data.get("bio") or "No bio available",
                            "followers": profile_data.get("followers") or 0,
                            "posts_count": profile_data.get("posts_count") or 0,
                            "username": instagram_username
                        }
                except Exception as e:
                    errors["instagram"] = str(e)

        # Add any errors or warnings to the response
        if errors:
            candidate_data["errors"] = errors
        if warnings:
            candidate_data["warnings"] = warnings

        return candidate_data

    except Exception as e:
        logger.error(f"Error in collect_candidate_data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/scrape-portfolio-direct", dependencies=[Depends(get_api_key)])
async def scrape_portfolio_direct(url: str):
    """Scrape portfolio data from a given URL directly."""
    if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', url):
        raise HTTPException(status_code=400, detail="Invalid URL format")

    try:
        logger.info(f"Starting direct portfolio scrape for URL: {url}")
        html_content = await fetch_with_selenium(url)
        portfolio_data = parse_portfolio(html_content, url)

        if not any([
            portfolio_data["name"],
            portfolio_data["about"],
            portfolio_data["skills"],
            portfolio_data["experience"],
            portfolio_data["projects"],
            portfolio_data["education"],
            portfolio_data["contact"]
        ]):
            raise HTTPException(status_code=500, detail="Failed to extract meaningful portfolio data")

        logger.info("Direct portfolio scraping completed successfully!")
        return portfolio_data

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error during direct portfolio scraping: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape portfolio: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)