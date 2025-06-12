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
    instagram_scraper = InstagramScraper(rate_limit=5)
    logger.info("Instagram scraper initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Instagram scraper: {str(e)}")
    # Don't raise the error here, we'll handle it in the endpoints

async def get_api_key(api_key: str = Depends(api_key_header)):
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

# Models
class PortfolioRequest(BaseModel):
    url: str

class InstagramProfileRequest(BaseModel):
    username: str

class CandidateData(BaseModel):
    portfolio_url: Optional[str] = None
    github_username: Optional[str] = None
    instagram_username: Optional[str] = None
    resume_file: Optional[UploadFile] = None

class UsernameRequest(BaseModel):
    username: str

class BatchRequest(BaseModel):
    usernames: List[str]

# Routes
@app.get("/")
async def read_root():
    """Root endpoint to check if the API is running."""
    return {"status": "ok", "message": "Social Media Scraper API is running"}

@app.get("/github/{username}", dependencies=[Depends(get_api_key)])
async def get_github_profile(username: str):
    """Get GitHub profile data."""
    try:
        profile_data = await fetch_github_profile(username)
        return {
            "status": "success",
            "data": profile_data,
            "timestamp": datetime.now().isoformat()
        }
    except GitHubAPIError as e:
        logger.error(f"GitHub API error: {str(e)}")
        raise HTTPException(status_code=429 if "Rate limit" in str(e) else 500, detail=str(e))
    except ValueError as e:
        logger.error(f"Invalid GitHub username: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching GitHub profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/instagram/{username}", dependencies=[Depends(get_api_key)])
async def get_instagram_profile(username: str):
    """Get Instagram profile data."""
    global instagram_scraper
    
    # Try to initialize the scraper if it's not already initialized
    if not instagram_scraper:
        try:
            instagram_scraper = InstagramScraper(rate_limit=5)
            logger.info("Instagram scraper initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Instagram scraper: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Instagram scraper: {str(e)}"
            )

    try:
        profile_data = instagram_scraper.scrape_profile(username)
        if "error" in profile_data:
            status_code = 404 if "not found" in profile_data["error"].lower() else 500
            raise HTTPException(status_code=status_code, detail=profile_data["error"])
        
        # Extract only the required fields
        return {
            "status": "success",
            "data": {
                "bio": profile_data.get("bio"),
                "followers": profile_data.get("followers"),
                "posts_count": profile_data.get("posts_count")
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching Instagram profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resume/upload", dependencies=[Depends(get_api_key)])
async def upload_resume(
    file: UploadFile = File(...)
):
    """Upload and parse a resume."""
    try:
        if not file.filename.lower().endswith(('.pdf', '.docx')):
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

        # Save the uploaded file temporarily
        temp_file_path = f"temp_{file.filename}"
        try:
            with open(temp_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # Parse the resume
            resume_data = parse_resume(content, file.filename)
            return {
                "status": "success",
                "data": resume_data,
                "timestamp": datetime.now().isoformat()
            }
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    except ResumeParserError as e:
        logger.error(f"Resume parsing error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing resume: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio-scrape", dependencies=[Depends(get_api_key)])
async def scrape_portfolio(
    request: PortfolioRequest
):
    """Scrape portfolio website data."""
    try:
        # Fetch the page content
        html_content = await fetch_with_selenium(request.url)
        if not html_content:
            raise HTTPException(status_code=404, detail="Could not fetch portfolio content")

        # Parse the portfolio data
        portfolio_data = parse_portfolio(html_content, request.url)
        
        # Save the data to a file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"portfolio_data_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
        
        return {
            "status": "success",
            "data": portfolio_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error scraping portfolio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect-candidate-data", dependencies=[Depends(get_api_key)])
async def collect_candidate_data(
    portfolio_url: Optional[str] = Form(None),
    github_username: Optional[str] = Form(None),
    instagram_username: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None)
):
    """Collect and analyze candidate data from multiple sources."""
    try:
        candidate_data = {}
        errors = {}

        # Process portfolio data
        if portfolio_url:
            try:
                html_content = await fetch_with_selenium(portfolio_url)
                if html_content:
                    candidate_data["portfolio"] = parse_portfolio(html_content, portfolio_url)
                else:
                    errors["portfolio"] = "Could not fetch portfolio content"
            except Exception as e:
                errors["portfolio"] = str(e)

        # Process GitHub data
        if github_username:
            try:
                candidate_data["github"] = await fetch_github_profile(github_username)
            except GitHubAPIError as e:
                errors["github"] = str(e)
            except Exception as e:
                errors["github"] = str(e)

        # Process Instagram data
        if instagram_username:
            global instagram_scraper
            if not instagram_scraper:
                try:
                    instagram_scraper = InstagramScraper(rate_limit=5)
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
                            "bio": profile_data.get("bio"),
                            "followers": profile_data.get("followers"),
                            "posts_count": profile_data.get("posts_count")
                        }
                except Exception as e:
                    errors["instagram"] = str(e)

        # Process resume data
        if resume_file:
            try:
                if not resume_file.filename.lower().endswith(('.pdf', '.docx')):
                    errors["resume"] = "Only PDF and DOCX files are supported"
                else:
                    # Save the uploaded file temporarily
                    temp_file_path = f"temp_{resume_file.filename}"
                    try:
                        with open(temp_file_path, "wb") as buffer:
                            content = await resume_file.read()
                            buffer.write(content)

                        # Parse the resume
                        candidate_data["resume"] = parse_resume(content, resume_file.filename)
                    finally:
                        # Clean up the temporary file
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
            except ResumeParserError as e:
                errors["resume"] = str(e)
            except Exception as e:
                errors["resume"] = str(e)

        # Save the combined data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"candidate_data_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "candidate_data": candidate_data,
                "errors": errors,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "data": candidate_data,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error collecting candidate data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)