import requests
import aiohttp
import json
import os
from typing import Dict, Any, Optional, List
import logging
from dotenv import load_dotenv
from datetime import datetime
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_API_BASE = "https://api.github.com"

class GitHubAPIError(Exception):
    pass

async def fetch_github_profile(username: str) -> Dict[str, Any]:
    """
    Fetch GitHub profile data using the GitHub API.
    
    Args:
        username: GitHub username
        
    Returns:
        Dict containing profile data
    """
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Candidate-Verification-System"
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        async with aiohttp.ClientSession() as session:
            # Fetch user profile
            async with session.get(f"{GITHUB_API_BASE}/users/{username}", headers=headers) as response:
                if response.status == 404:
                    raise ValueError(f"GitHub user {username} not found")
                if response.status == 403:
                    raise GitHubAPIError("Rate limit exceeded. Please try again later.")
                response.raise_for_status()
                profile_data = await response.json()

            # Fetch repositories with pagination
            repos = []
            page = 1
            while True:
                async with session.get(
                    f"{GITHUB_API_BASE}/users/{username}/repos",
                    headers=headers,
                    params={"page": page, "per_page": 100, "sort": "updated"}
                ) as response:
                    if response.status == 403:
                        raise GitHubAPIError("Rate limit exceeded. Please try again later.")
                    response.raise_for_status()
                    page_repos = await response.json()
                    
                    if not page_repos:
                        break
                        
                    for repo in page_repos:
                        # Fetch additional repository details
                        try:
                            async with session.get(
                                f"{GITHUB_API_BASE}/repos/{username}/{repo['name']}",
                                headers=headers
                            ) as repo_response:
                                if repo_response.status == 200:
                                    repo_details = await repo_response.json()
                                    repos.append({
                                        "name": repo_details["name"],
                                        "description": repo_details["description"],
                                        "language": repo_details["language"],
                                        "stars": repo_details["stargazers_count"],
                                        "forks": repo_details["forks_count"],
                                        "open_issues": repo_details["open_issues_count"],
                                        "watchers": repo_details["watchers_count"],
                                        "size": repo_details["size"],
                                        "created_at": repo_details["created_at"],
                                        "updated_at": repo_details["updated_at"],
                                        "pushed_at": repo_details["pushed_at"],
                                        "url": repo_details["html_url"],
                                        "homepage": repo_details["homepage"],
                                        "topics": repo_details["topics"],
                                        "license": repo_details["license"]["name"] if repo_details["license"] else None,
                                        "default_branch": repo_details["default_branch"],
                                        "is_fork": repo_details["fork"],
                                        "archived": repo_details["archived"]
                                    })
                        except Exception as e:
                            logger.warning(f"Error fetching details for repo {repo['name']}: {str(e)}")
                            # Add basic repo info if detailed fetch fails
                            repos.append({
                                "name": repo["name"],
                                "description": repo["description"],
                                "language": repo["language"],
                                "stars": repo["stargazers_count"],
                                "forks": repo["forks_count"],
                                "url": repo["html_url"]
                            })
                    
                    if len(page_repos) < 100:
                        break
                    page += 1
                    time.sleep(1)  # Rate limiting

            # Fetch contribution statistics
            try:
                async with session.get(
                    f"{GITHUB_API_BASE}/users/{username}/events/public",
                    headers=headers,
                    params={"per_page": 100}
                ) as response:
                    if response.status == 200:
                        events = await response.json()
                        contributions = {
                            "commits": 0,
                            "pull_requests": 0,
                            "issues": 0,
                            "repositories_contributed_to": set()
                        }
                        
                        for event in events:
                            if event["type"] == "PushEvent":
                                contributions["commits"] += len(event["payload"]["commits"])
                                contributions["repositories_contributed_to"].add(event["repo"]["name"])
                            elif event["type"] == "PullRequestEvent":
                                contributions["pull_requests"] += 1
                                contributions["repositories_contributed_to"].add(event["repo"]["name"])
                            elif event["type"] == "IssuesEvent":
                                contributions["issues"] += 1
                                contributions["repositories_contributed_to"].add(event["repo"]["name"])
                        
                        contributions["repositories_contributed_to"] = list(contributions["repositories_contributed_to"])
            except Exception as e:
                logger.warning(f"Error fetching contribution statistics: {str(e)}")
                contributions = None

            # Compile profile data
            profile = {
                "username": profile_data["login"],
                "name": profile_data["name"],
                "bio": profile_data["bio"],
                "location": profile_data["location"],
                "company": profile_data["company"],
                "blog": profile_data["blog"],
                "email": profile_data["email"],
                "twitter_username": profile_data["twitter_username"],
                "public_repos": profile_data["public_repos"],
                "public_gists": profile_data["public_gists"],
                "followers": profile_data["followers"],
                "following": profile_data["following"],
                "created_at": profile_data["created_at"],
                "updated_at": profile_data["updated_at"],
                "avatar_url": profile_data["avatar_url"],
                "hireable": profile_data["hireable"],
                "repositories": repos,
                "contributions": contributions
            }

            return profile

    except aiohttp.ClientError as e:
        logger.error(f"Error fetching GitHub profile: {str(e)}")
        raise Exception(f"Failed to fetch GitHub profile: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise Exception(f"An unexpected error occurred: {str(e)}")

def get_repository_details(username: str, repo_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific repository.
    
    Args:
        username (str): GitHub username
        repo_name (str): Repository name
        
    Returns:
        Dict containing repository details
    """
    base_url = "https://api.github.com"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Candidate-Verification-System"
    }
    
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {token}"
    
    try:
        # Get basic repository info
        repo_url = f"{base_url}/repos/{username}/{repo_name}"
        response = requests.get(repo_url, headers=headers)
        response.raise_for_status()
        repo_data = response.json()
        
        # Get repository languages
        languages_url = f"{repo_url}/languages"
        languages_response = requests.get(languages_url, headers=headers)
        languages = languages_response.json() if languages_response.status_code == 200 else {}
        
        # Get repository contributors
        contributors_url = f"{repo_url}/contributors"
        contributors_response = requests.get(contributors_url, headers=headers)
        contributors = contributors_response.json() if contributors_response.status_code == 200 else []
        
        # Get repository topics
        topics_url = f"{repo_url}/topics"
        topics_response = requests.get(topics_url, headers=headers)
        topics = topics_response.json().get("names", []) if topics_response.status_code == 200 else []
        
        return {
            "name": repo_data.get("name"),
            "description": repo_data.get("description"),
            "language": repo_data.get("language"),
            "languages": languages,
            "stars": repo_data.get("stargazers_count"),
            "forks": repo_data.get("forks_count"),
            "open_issues": repo_data.get("open_issues_count"),
            "watchers": repo_data.get("watchers_count"),
            "size": repo_data.get("size"),
            "created_at": repo_data.get("created_at"),
            "updated_at": repo_data.get("updated_at"),
            "pushed_at": repo_data.get("pushed_at"),
            "url": repo_data.get("html_url"),
            "homepage": repo_data.get("homepage"),
            "topics": topics,
            "license": repo_data.get("license", {}).get("name"),
            "default_branch": repo_data.get("default_branch"),
            "is_fork": repo_data.get("fork"),
            "archived": repo_data.get("archived"),
            "contributors": [
                {
                    "username": c.get("login"),
                    "contributions": c.get("contributions"),
                    "avatar_url": c.get("avatar_url")
                }
                for c in contributors[:10]  # Limit to top 10 contributors
            ]
        }
        
    except requests.exceptions.RequestException as e:
        raise GitHubAPIError(f"Error fetching repository data: {str(e)}")
    except Exception as e:
        raise GitHubAPIError(f"Unexpected error: {str(e)}") 