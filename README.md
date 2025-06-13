# Portfolio Analyzer

A FastAPI-based application that analyzes candidate profiles by scraping data from multiple sources including portfolios, GitHub, and Instagram.

## Features

- Resume parsing (PDF/DOCX) with automatic extraction of:
  - Contact information
  - Skills
  - Education
  - Experience
  - Projects
  - Social media links (GitHub, Portfolio, Instagram)

- Portfolio website scraping:
  - Name and about section
  - Skills and technologies
  - Work experience
  - Projects
  - Education
  - Contact information

- GitHub profile analysis:
  - Basic profile information
  - Repository statistics
  - Contribution metrics

- Instagram profile analysis:
  - Bio
  - Follower/Following counts
  - Post count

## API Endpoints

1. `POST /collect-candidate-data`
   - Accepts a resume file (PDF/DOCX)
   - Automatically extracts and scrapes data from portfolio, GitHub, and Instagram
   - Returns comprehensive candidate data

2. `GET /scrape-portfolio-direct`
   - Direct portfolio URL scraping
   - Returns structured portfolio data

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```
API_KEY=your_api_key_here
```

3. Run the server:
```bash
uvicorn main:app --reload
```

## Dependencies

- FastAPI
- BeautifulSoup4
- Selenium
- PyPDF2
- python-docx
- python-dotenv
- requests
- uvicorn

## Security

- API key authentication required for all endpoints
- Rate limiting implemented for Instagram scraping
- Secure handling of sensitive data

## License

MIT License 