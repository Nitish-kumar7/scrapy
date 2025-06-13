import pdfplumber
import docx
import io
from typing import Dict, Any, List, Optional
import re
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Comprehensive list of technical skills to look for
common_skills = [
    # Programming Languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Ruby", "PHP",
    "Go", "Rust", "Swift", "Kotlin", "HTML", "CSS", "SQL", "NoSQL", "GraphQL",
    "R", "MATLAB", "Scala", "Perl", "Shell", "Bash", "PowerShell",
    
    # Web Technologies
    "React", "Angular", "Vue", "Node.js", "Express", "Django", "Flask", "Spring",
    "Laravel", "ASP.NET", "jQuery", "Bootstrap", "Tailwind CSS", "SASS", "LESS",
    "Webpack", "Babel", "npm", "Yarn", "REST", "SOAP", "WebSocket",
    
    # Databases
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "Oracle", "SQL Server", "DynamoDB", "Firebase", "CouchDB", "Neo4j",
    
    # Cloud Platforms
    "AWS", "Azure", "GCP", "Digital Ocean", "Heroku", "Vercel", "Netlify",
    "Lambda", "EC2", "S3", "RDS", "CloudFront", "Route 53", "CloudFormation",
    
    # DevOps & Tools
    "Docker", "Kubernetes", "Jenkins", "Git", "GitHub", "GitLab", "Bitbucket",
    "CI/CD", "Terraform", "Ansible", "Puppet", "Chef", "Prometheus", "Grafana",
    "ELK Stack", "Splunk", "Jira", "Confluence", "Trello", "Asana",
    
    # AI & ML
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Keras",
    "Scikit-learn", "Pandas", "NumPy", "SciPy", "NLTK", "SpaCy", "OpenCV",
    "Computer Vision", "NLP", "Natural Language Processing", "Data Science",
    
    # Mobile Development
    "iOS", "Android", "React Native", "Flutter", "Xamarin", "Swift", "Kotlin",
    "Mobile App Development", "App Store", "Google Play",
    
    # Security
    "Cybersecurity", "Network Security", "Application Security", "Cloud Security",
    "Penetration Testing", "Vulnerability Assessment", "SIEM", "Firewall",
    "IDS/IPS", "Cryptography", "SSL/TLS", "OAuth", "JWT", "SAML",
    
    # Other Technologies
    "Blockchain", "Smart Contracts", "Solidity", "Ethereum", "Bitcoin",
    "IoT", "Embedded Systems", "Arduino", "Raspberry Pi", "Microcontrollers",
    "Game Development", "Unity", "Unreal Engine", "3D Modeling", "CAD",
    "Virtual Reality", "Augmented Reality", "AR/VR"
]

class ResumeParserError(Exception):
    """Custom exception for resume parsing errors."""
    pass

def validate_file_size(content: bytes, max_size_mb: int = 10) -> None:
    """Validate file size."""
    if len(content) > max_size_mb * 1024 * 1024:
        raise ResumeParserError(f"File size exceeds maximum limit of {max_size_mb}MB")
    if len(content) < 100:
        raise ResumeParserError("File appears to be empty or corrupted")

def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF content."""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        raise ResumeParserError(f"Error extracting text from PDF: {str(e)}")

def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX content."""
    try:
        doc = docx.Document(io.BytesIO(content))
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text)
        return "\n".join(text)
    except Exception as e:
        logger.error(f"DOCX extraction error: {str(e)}")
        raise ResumeParserError(f"Error extracting text from DOCX: {str(e)}")

def extract_email(text: str) -> Optional[str]:
    """Extract email address from text."""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None

def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text."""
    # Enhanced phone pattern to match various formats
    phone_patterns = [
        r'\+?[\d\s\-\(\)]{10,}',  # Basic pattern
        r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # International format
        r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (XXX) XXX-XXXX format
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            # Clean up the phone number
            phone = re.sub(r'[^\d+]', '', match.group(0))
            if len(phone) >= 10:  # Ensure minimum length
                return phone
    return None

def extract_github_url(text: str) -> Optional[str]:
    """Extract GitHub profile URL from text."""
    github_pattern = r'(?i)(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+'
    match = re.search(github_pattern, text)
    return match.group(0) if match else None

def extract_portfolio_url(text: str) -> Optional[str]:
    """Extract Portfolio URL from text."""
    # First try to find URLs after "Portfolio:" or similar keywords
    portfolio_keywords = ['portfolio:', 'portfolio website:', 'portfolio url:', 'portfolio link:']
    for keyword in portfolio_keywords:
        if keyword.lower() in text.lower():
            # Get the text after the keyword
            after_keyword = text.lower().split(keyword.lower())[1].strip()
            # Find the first URL in the text after the keyword
            url_pattern = r'(?:https?://|www\.)[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?'
            match = re.search(url_pattern, after_keyword)
            if match:
                url = match.group(0)
                if not url.startswith('http'):
                    url = 'https://' + url
                return url

    # If no URL found after keywords, try to find any URL that might be a portfolio
    url_pattern = r'(?:https?://|www\.)[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?'
    matches = re.finditer(url_pattern, text)
    for match in matches:
        url = match.group(0)
        # Skip if it's a GitHub or Instagram URL
        if 'github.com' in url.lower() or 'instagram.com' in url.lower():
            continue
        # Check if it might be a portfolio URL
        if any(domain in url.lower() for domain in ['vercel.app', 'netlify.app', 'github.io', 'portfolio', 'personal']):
            if not url.startswith('http'):
                url = 'https://' + url
            return url

    return None

def extract_instagram_username(text: str) -> Optional[str]:
    """Extract Instagram username from text."""
    instagram_pattern = r'(?i)(?:@|instagram\.com/)([A-Za-z0-9_.]+)'
    match = re.search(instagram_pattern, text)
    if match:
        # If it's a URL, extract just the username part
        if "instagram.com/" in match.group(0):
            return match.group(1)
        return match.group(0).lstrip('@') # Remove the leading '@' if present
    return None

def extract_skills(text: str) -> List[str]:
    """Extract skills from text with improved pattern matching."""
    found_skills = set()
    
    # Normalize text for better matching
    text_lower = text.lower()
    
    # Check for explicit skill mentions with context
    for skill in common_skills:
        skill_lower = skill.lower()
        # Look for skill mentions with context
        patterns = [
            rf'\b{re.escape(skill_lower)}\b',
            rf'\bproficient\s+in\s+{re.escape(skill_lower)}\b',
            rf'\bexpert\s+in\s+{re.escape(skill_lower)}\b',
            rf'\bexperienced\s+with\s+{re.escape(skill_lower)}\b',
            rf'\bknowledge\s+of\s+{re.escape(skill_lower)}\b'
        ]
        
        for pattern in patterns:
            if re.search(pattern, text_lower):
                found_skills.add(skill)
                break
    
    # Check for skill patterns with context
    skill_patterns = [
        r'\b(?:proficient|expert|skilled|experienced|familiar|knowledgeable)\s+(?:in|with|at)\s+([\w\s\+#\.]+)',
        r'\b(?:experience|knowledge|skills)\s+(?:in|with)\s+([\w\s\+#\.]+)',
        r'\b(?:worked|developed|built|created|implemented)\s+(?:with|using)\s+([\w\s\+#\.]+)',
        r'\b(?:certified|certification)\s+(?:in|for)\s+([\w\s\+#\.]+)'
    ]
    
    for pattern in skill_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            skill_phrase = match.group(1).strip()
            for skill in common_skills:
                if skill.lower() in skill_phrase.lower():
                    found_skills.add(skill)
    
    return sorted(list(found_skills))

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters
    text = re.sub(r'[^\w\s\-\.@]', '', text)
    return text.strip()

def extract_education(text: str) -> List[Dict[str, str]]:
    """Extract education information with improved pattern matching."""
    education = []
    
    # Education patterns
    degree_patterns = [
        r'(?i)(bachelor|master|phd|b\.?tech|m\.?tech|b\.?e|m\.?e|b\.?sc|m\.?sc|mba|diploma)[^\n]*',
        r'(?i)(computer science|engineering|technology|science|arts|commerce)[^\n]*'
    ]
    
    institution_patterns = [
        r'(?i)(university|college|institute|school)[^\n]*',
        r'(?i)(iiit|iit|nit)[^\n]*'
    ]
    
    year_pattern = r'(?i)(\d{4})\s*[-–]\s*(?:\d{4}|present|current)'
    
    lines = text.split('\n')
    current_edu = {}
    
    for line in lines:
        line = clean_text(line)
        if not line:
            continue
            
        line_lower = line.lower()
        
        # Check for degree
        if any(re.search(pattern, line_lower) for pattern in degree_patterns):
            if current_edu and any(current_edu.values()):
                education.append(current_edu)
            current_edu = {
                "degree": line,
                "institution": "",
                "year": "",
                "gpa": ""
            }
            continue
        
        # Check for institution
        if any(re.search(pattern, line_lower) for pattern in institution_patterns):
            if current_edu:
                current_edu["institution"] = line
            continue
        
        # Check for year
        year_match = re.search(year_pattern, line)
        if year_match:
            if current_edu:
                current_edu["year"] = line
            continue
            
        # Check for GPA
        gpa_match = re.search(r'(?i)(?:gpa|cgpa)[:\s]*(\d+\.?\d*)', line)
        if gpa_match and current_edu:
            current_edu["gpa"] = gpa_match.group(1)
    
    if current_edu and any(current_edu.values()):
        education.append(current_edu)
    
    return education[:5]  # Limit to 5 entries

def extract_experience(text: str) -> List[Dict[str, str]]:
    """Extract work experience with improved pattern matching."""
    experience = []
    
    # Job title keywords
    job_keywords = [
        'engineer', 'developer', 'architect', 'scientist', 'manager', 'lead', 
        'consultant', 'analyst', 'specialist', 'intern', 'associate', 'director',
        'software', 'web', 'mobile', 'full stack', 'frontend', 'backend', 'devops',
        'data', 'ml', 'ai', 'project', 'technical', 'senior', 'junior', 'principal'
    ]
    
    lines = text.split('\n')
    current_exp = {}
    
    for line in lines:
        line = clean_text(line)
        if not line:
            continue
            
        line_lower = line.lower()
        
        # Skip if line contains contact information
        if '@' in line or re.search(r'\d{10}', line):
            continue
        
        # Check for job title
        if any(keyword in line_lower for keyword in job_keywords) and len(line) > 10:
            if current_exp and any(current_exp.values()):
                experience.append(current_exp)
            current_exp = {
                "title": line,
                "company": "",
                "duration": "",
                "description": []
            }
            continue
        
        # Check for company name (usually follows job title)
        elif current_exp and not current_exp.get("company") and len(line) > 3:
            current_exp["company"] = line
            continue
        
        # Check for duration
        elif re.search(r'\d{4}', line) and current_exp:
            current_exp["duration"] = line
            continue
            
        # Add description points
        elif current_exp and line.startswith(('-', '•', '*', '·')):
            current_exp["description"].append(line.lstrip('-•*· '))
    
    if current_exp and any(current_exp.values()):
        experience.append(current_exp)
    
    return experience[:5]  # Limit to 5 entries

def extract_certifications(text: str) -> List[Dict[str, str]]:
    """Extract certifications from text."""
    certifications = []
    
    cert_keywords = [
        'aws', 'azure', 'gcp', 'cisco', 'microsoft', 'oracle', 'ibm', 'google',
        'amazon', 'comptia', 'cissp', 'pmp', 'itil', 'scrum', 'agile',
        'certified', 'certification', 'certificate'
    ]
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        line_lower = line.lower()
        has_cert_keyword = any(keyword in line_lower for keyword in cert_keywords)
        
        if has_cert_keyword and len(line) > 5:
            certifications.append({"name": line})
    
    return certifications[:5]  # Limit to 5 entries

def extract_projects(text: str) -> List[Dict[str, str]]:
    """Extract projects with improved pattern matching."""
    projects = []
    
    project_keywords = [
        'project', 'application', 'system', 'platform', 'website', 'app',
        'software', 'tool', 'framework', 'library', 'developed', 'created',
        'built', 'implemented', 'designed'
    ]
    
    lines = text.split('\n')
    current_project = {}
    
    for line in lines:
        line = clean_text(line)
        if not line:
            continue
            
        line_lower = line.lower()
        
        # Check for project title
        if any(keyword in line_lower for keyword in project_keywords) and len(line) > 10:
            if current_project and any(current_project.values()):
                projects.append(current_project)
            current_project = {
                "name": line,
                "description": [],
                "technologies": []
            }
            continue
            
        # Add description points
        elif current_project and line.startswith(('-', '•', '*', '·')):
            current_project["description"].append(line.lstrip('-•*· '))
            continue
            
        # Add technologies
        elif current_project and any(tech.lower() in line_lower for tech in common_skills):
            current_project["technologies"].append(line)
    
    if current_project and any(current_project.values()):
        projects.append(current_project)
    
    return projects[:5]  # Limit to 5 entries

def parse_resume(content: bytes, filename: str) -> Dict[str, Any]:
    """Parse resume content and extract structured information."""
    try:
        # Validate file size
        validate_file_size(content)
        
        # Extract text based on file type
        if filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(content)
        elif filename.lower().endswith('.docx'):
            text = extract_text_from_docx(content)
        else:
            raise ResumeParserError(f"Unsupported file type: {filename}")

        if not text or len(text.strip()) < 50:
            raise ResumeParserError("Unable to extract meaningful text from the resume")

        # Extract all information
        resume_data = {
            "text": text,
            "email": extract_email(text),
            "phone": extract_phone(text),
            "skills": extract_skills(text),
            "education": extract_education(text),
            "experience": extract_experience(text),
            "certifications": extract_certifications(text),
            "projects": extract_projects(text),
            "github_url": extract_github_url(text),
            "portfolio_url": extract_portfolio_url(text),
            "instagram_username": extract_instagram_username(text),
            "metadata": {
                "raw_text_length": len(text),
                "timestamp": datetime.now().isoformat()
            }
        }

        # Validate extracted data
        if not any([
            resume_data["email"],
            resume_data["phone"],
            resume_data["skills"],
            resume_data["education"],
            resume_data["experience"]
        ]):
            logger.warning("No meaningful data extracted from resume")
            raise ResumeParserError("Could not extract meaningful information from the resume")

        # Further analysis or cleanup if needed
        # For example, ensure no empty lists/strings are returned if not found
        for key, value in resume_data.items():
            if isinstance(value, list) and not value:
                resume_data[key] = None
            elif isinstance(value, str) and not value.strip():
                resume_data[key] = None

        logger.info(f"Successfully parsed resume {filename}")
        return resume_data

    except Exception as e:
        logger.error(f"Resume parsing error: {str(e)}")
        raise ResumeParserError(f"Error parsing resume: {str(e)}")

if __name__ == "__main__":
    # Example Usage
    pass
