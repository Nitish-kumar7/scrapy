from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Body
from fastapi.security import APIKeyHeader
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, HttpUrl
import logging
from datetime import datetime
import json
import os
from dotenv import load_dotenv

from portfolio_scraper import fetch_with_selenium, parse_portfolio
from github_extractor import fetch_github_profile
from instagram_scraper import InstagramScraper
from resume_parser import parse_resume, ResumeParserError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Instagram scraper
instagram_scraper = InstagramScraper(rate_limit=5)

class CandidateData(BaseModel):
    portfolio_url: Optional[HttpUrl] = None
    github_username: Optional[str] = None
    instagram_username: Optional[str] = None
    resume_file: Optional[UploadFile] = None

async def collect_candidate_data(data: CandidateData) -> Dict[str, Any]:
    """
    Collect candidate data from multiple sources (portfolio, GitHub, Instagram, resume).
    """
    try:
        candidate_data = {}
        
        # 1. Portfolio Analysis
        if data.portfolio_url:
            try:
                logger.info(f"Scraping portfolio from: {data.portfolio_url}")
                html_content = fetch_with_selenium(str(data.portfolio_url))
                portfolio_data = parse_portfolio(html_content, str(data.portfolio_url))
                candidate_data["portfolio"] = portfolio_data
            except Exception as e:
                logger.error(f"Error scraping portfolio: {str(e)}")
                candidate_data["portfolio_error"] = str(e)

        # 2. GitHub Analysis
        if data.github_username:
            try:
                logger.info(f"Fetching GitHub profile for: {data.github_username}")
                github_data = await fetch_github_profile(data.github_username)
                candidate_data["github"] = github_data
            except Exception as e:
                logger.error(f"Error fetching GitHub data: {str(e)}")
                candidate_data["github_error"] = str(e)

        # 3. Instagram Analysis
        if data.instagram_username:
            try:
                logger.info(f"Scraping Instagram profile for: {data.instagram_username}")
                instagram_data = instagram_scraper.scrape_profile(data.instagram_username)
                candidate_data["instagram"] = instagram_data
            except Exception as e:
                logger.error(f"Error scraping Instagram: {str(e)}")
                candidate_data["instagram_error"] = str(e)

        # 4. Resume Analysis
        if data.resume_file:
            try:
                logger.info(f"Parsing resume: {data.resume_file.filename}")
                content = await data.resume_file.read()
                resume_data = parse_resume(content, data.resume_file.filename)
                candidate_data["resume"] = resume_data
            except Exception as e:
                logger.error(f"Error parsing resume: {str(e)}")
                candidate_data["resume_error"] = str(e)

        # Save combined data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"candidate_data_{timestamp}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(candidate_data, f, indent=2)
        logger.info(f"Saved combined candidate data to {filename}")

        return candidate_data

    except Exception as e:
        logger.error(f"Error in collect_candidate_data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error collecting candidate data: {str(e)}"
        )

def cross_reference_data(candidate_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cross-reference data from different sources to find correlations and inconsistencies.
    """
    analysis = {
        "skills_match": [],
        "experience_verification": [],
        "education_verification": [],
        "contact_consistency": [],
        "project_verification": []
    }

    # Extract skills from different sources
    portfolio_skills = set(candidate_data.get("portfolio", {}).get("skills", []))
    github_skills = set()
    resume_skills = set(candidate_data.get("resume", {}).get("skills", []))

    # Extract skills from GitHub repositories
    for repo in candidate_data.get("github", {}).get("repositories", []):
        if repo.get("language"):
            github_skills.add(repo["language"])

    # Compare skills across sources
    all_skills = portfolio_skills.union(github_skills, resume_skills)
    for skill in all_skills:
        sources = []
        if skill in portfolio_skills:
            sources.append("portfolio")
        if skill in github_skills:
            sources.append("github")
        if skill in resume_skills:
            sources.append("resume")
        analysis["skills_match"].append({
            "skill": skill,
            "sources": sources,
            "confidence": len(sources) / 3.0
        })

    # Verify experience
    portfolio_exp = candidate_data.get("portfolio", {}).get("experience", [])
    resume_exp = candidate_data.get("resume", {}).get("experience", [])
    for exp in portfolio_exp:
        analysis["experience_verification"].append({
            "title": exp.get("title"),
            "date": exp.get("date"),
            "verified_in_resume": any(
                e.get("title", "").lower() in exp.get("title", "").lower()
                for e in resume_exp
            )
        })

    # Verify education
    portfolio_edu = candidate_data.get("portfolio", {}).get("education", [])
    resume_edu = candidate_data.get("resume", {}).get("education", [])
    for edu in portfolio_edu:
        analysis["education_verification"].append({
            "institution": edu.get("institution"),
            "degree": edu.get("degree"),
            "verified_in_resume": any(
                e.get("institution", "").lower() in edu.get("institution", "").lower()
                for e in resume_edu
            )
        })

    # Check contact information consistency
    portfolio_contact = candidate_data.get("portfolio", {}).get("contact", {})
    github_contact = candidate_data.get("github", {}).get("blog", "")
    resume_contact = {
        "email": candidate_data.get("resume", {}).get("email", ""),
        "phone": candidate_data.get("resume", {}).get("phone", "")
    }

    analysis["contact_consistency"] = {
        "email": {
            "portfolio": portfolio_contact.get("email"),
            "resume": resume_contact.get("email"),
            "consistent": portfolio_contact.get("email") == resume_contact.get("email")
        },
        "website": {
            "portfolio": portfolio_contact.get("website"),
            "github": github_contact,
            "consistent": portfolio_contact.get("website") == github_contact
        }
    }

    # Verify projects
    portfolio_projects = candidate_data.get("portfolio", {}).get("projects", [])
    github_repos = candidate_data.get("github", {}).get("repositories", [])
    for project in portfolio_projects:
        analysis["project_verification"].append({
            "title": project.get("title"),
            "verified_in_github": any(
                repo.get("name", "").lower() in project.get("title", "").lower()
                for repo in github_repos
            )
        })

    return analysis 