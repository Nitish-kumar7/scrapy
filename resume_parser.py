import pdfplumber
import docx
import io
from typing import Dict, Any, List
import re
from datetime import datetime

class ResumeParserError(Exception):
    pass

def extract_text_from_pdf(content: bytes) -> str:
    """
    Extract text from PDF content.
    
    Args:
        content (bytes): PDF file content
        
    Returns:
        str: Extracted text
    """
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except Exception as e:
        raise ResumeParserError(f"Error extracting text from PDF: {str(e)}")

def extract_text_from_docx(content: bytes) -> str:
    """
    Extract text from DOCX content.
    
    Args:
        content (bytes): DOCX file content
        
    Returns:
        str: Extracted text
    """
    try:
        doc = docx.Document(io.BytesIO(content))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        raise ResumeParserError(f"Error extracting text from DOCX: {str(e)}")

def extract_email(text: str) -> str:
    """Extract email address from text."""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else ""

def extract_phone(text: str) -> str:
    """Extract phone number from text."""
    phone_pattern = r'\+?[\d\s-]{10,}'
    match = re.search(phone_pattern, text)
    return match.group(0) if match else ""

def extract_skills(text: str) -> List[str]:
    """Extract skills from text with improved pattern matching."""
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
    
    # Additional patterns for skill detection
    skill_patterns = [
        r'\b(?:proficient|expert|skilled|experienced|familiar|knowledgeable)\s+(?:in|with|at)\s+([\w\s\+#\.]+)',
        r'\b(?:experience|knowledge|skills)\s+(?:in|with)\s+([\w\s\+#\.]+)',
        r'\b(?:worked|developed|built|created|implemented)\s+(?:with|using)\s+([\w\s\+#\.]+)',
        r'\b(?:certified|certification)\s+(?:in|for)\s+([\w\s\+#\.]+)'
    ]
    
    found_skills = set()
    
    # Check for explicit skill mentions
    for skill in common_skills:
        if re.search(r'\b' + re.escape(skill) + r'\b', text, re.IGNORECASE):
            found_skills.add(skill)
    
    # Check for skill patterns
    for pattern in skill_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            skill_phrase = match.group(1).strip()
            # Check if the matched phrase contains any of our known skills
            for skill in common_skills:
                if skill.lower() in skill_phrase.lower():
                    found_skills.add(skill)
    
    return sorted(list(found_skills))

def extract_education(text: str) -> List[Dict[str, str]]:
    """Extract education information with improved pattern matching."""
    education = []
    
    # Comprehensive education patterns
    edu_patterns = [
        # Full pattern with degree, institution, and years
        r"(?P<degree>(?:Bachelor(?:'s)?|Master(?:'s)?|Ph\.?D\.?|B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|MBA|Associate|Diploma)(?:(?: of| in)? [\w\s\-.,&()\/]+)?)" # Degree
        r"(?:\s+from)?\s*(?P<institution>[\w\s\-.,&]+(?:University|College|Institute|Polytechnic|School|Academy))" # Institution
        r"(?:[\s,]*\(?(?P<year>\d{4}\s*[-–]\s*(?:\d{4}|Present|Current|[Pp]resent)\)?)?", # Years
        
        # Pattern with degree and institution
        r"(?P<degree>(?:Bachelor|Master|PhD|B\.?Tech|M\.?Tech|B\.?E|M\.?E|B\.?Sc|M\.?Sc)[^.\n]*)"
        r"\s+(?:from|at)\s+(?P<institution>[^.\n]+)",
        
        # Pattern with institution and year
        r"(?P<institution>[^.\n]+(?:University|College|Institute))"
        r"\s*(?P<year>\d{4}\s*[-–]\s*(?:\d{4}|Present))",
        
        # Simple degree pattern
        r"(?P<degree>(?:Bachelor|Master|PhD|B\.?Tech|M\.?Tech|B\.?E|M\.?E|B\.?Sc|M\.?Sc)[^.\n]*)"
    ]
    
    # Process each pattern
    for pattern in edu_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            edu_entry = {
                "degree": match.group("degree").strip() if match.group("degree") else "",
                "institution": match.group("institution").strip() if match.group("institution") else "",
                "year": match.group("year").strip() if match.group("year") else ""
            }
            
            # Only add if we have at least a degree or institution
            if edu_entry["degree"] or edu_entry["institution"]:
                # Check for duplicates
                if not any(
                    e["degree"] == edu_entry["degree"] and 
                    e["institution"] == edu_entry["institution"]
                    for e in education
                ):
                    education.append(edu_entry)
    
    return education

def extract_experience(text: str) -> List[Dict[str, str]]:
    """Extract work experience with improved pattern matching."""
    experience = []
    
    # Comprehensive experience patterns
    exp_patterns = [
        # Full pattern with title, company, and duration
        r"(?P<title>(?:Senior|Junior|Lead|Staff|Principal)?\s*(?:[\w\s-]+)?(?:Software|Web|Mobile|Full Stack|Frontend|Backend|DevOps|Data|ML|AI|Project|Technical)\s*(?:Engineer|Developer|Architect|Scientist|Manager|Lead|Consultant|Analyst|Specialist))" # Title
        r"(?:\s+at\s+(?P<company>[\w\s\-.,&]+))?" # Company
        r"(?:[\s,]*\(?(?P<duration>\d{4}\s*[-–]\s*(?:\d{4}|Present|Current|[Pp]resent)\)?)?", # Duration
        
        # Pattern with title and company
        r"(?P<title>(?:Senior|Junior|Lead|Staff|Principal)?\s*(?:[\w\s-]+)?(?:Software|Web|Mobile|Full Stack|Frontend|Backend|DevOps|Data|ML|AI|Project|Technical)\s*(?:Engineer|Developer|Architect|Scientist|Manager|Lead|Consultant|Analyst|Specialist))"
        r"\s+(?:at|with|for)\s+(?P<company>[^.\n]+)",
        
        # Pattern with company and duration
        r"(?P<company>[^.\n]+)"
        r"\s*(?P<duration>\d{4}\s*[-–]\s*(?:\d{4}|Present))",
        
        # Simple title pattern
        r"(?P<title>(?:Senior|Junior|Lead|Staff|Principal)?\s*(?:[\w\s-]+)?(?:Software|Web|Mobile|Full Stack|Frontend|Backend|DevOps|Data|ML|AI|Project|Technical)\s*(?:Engineer|Developer|Architect|Scientist|Manager|Lead|Consultant|Analyst|Specialist))"
    ]
    
    # Process each pattern
    for pattern in exp_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            exp_entry = {
                "title": match.group("title").strip() if match.group("title") else "",
                "company": match.group("company").strip() if match.group("company") else "",
                "duration": match.group("duration").strip() if match.group("duration") else ""
            }
            
            # Only add if we have at least a title or company
            if exp_entry["title"] or exp_entry["company"]:
                # Check for duplicates
                if not any(
                    e["title"] == exp_entry["title"] and 
                    e["company"] == exp_entry["company"]
                    for e in experience
                ):
                    experience.append(exp_entry)
    
    return experience

def extract_certifications(text: str) -> List[Dict[str, str]]:
    """Extract certifications from text."""
    certifications = []
    
    # Certification patterns
    cert_patterns = [
        r"(?P<name>(?:AWS|Azure|GCP|Cisco|Microsoft|Oracle|IBM|Google|Amazon|CompTIA|CISSP|PMP|ITIL|Scrum|Agile)[^.\n]+(?:Certified|Certification|Professional|Associate|Expert|Master|Developer|Architect|Engineer|Administrator|Specialist))",
        r"(?P<name>[^.\n]+(?:Certified|Certification|Professional|Associate|Expert|Master|Developer|Architect|Engineer|Administrator|Specialist))",
        r"(?P<name>(?:AWS|Azure|GCP|Cisco|Microsoft|Oracle|IBM|Google|Amazon|CompTIA|CISSP|PMP|ITIL|Scrum|Agile)[^.\n]+)"
    ]
    
    # Process each pattern
    for pattern in cert_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            cert_name = match.group("name").strip()
            if cert_name:
                # Check for duplicates
                if not any(c["name"] == cert_name for c in certifications):
                    certifications.append({"name": cert_name})
    
    return certifications

def extract_projects(text: str) -> List[Dict[str, str]]:
    """Extract projects from text."""
    projects = []
    
    # Project patterns
    project_patterns = [
        r"(?P<name>[^.\n]+(?:Project|Application|System|Platform|Website|App|Software|Tool|Framework|Library))",
        r"(?P<name>(?:Developed|Created|Built|Implemented|Designed)[^.\n]+)",
        r"(?P<name>(?:Led|Managed|Oversaw)[^.\n]+(?:project|initiative|development))"
    ]
    
    # Process each pattern
    for pattern in project_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            project_name = match.group("name").strip()
            if project_name:
                # Check for duplicates
                if not any(p["name"] == project_name for p in projects):
                    projects.append({"name": project_name})
    
    return projects

def parse_resume(content: bytes, filename: str) -> Dict[str, Any]:
    """Parse resume content and extract structured information."""
    try:
        # Extract text based on file type
        if filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(content)
        elif filename.lower().endswith('.docx'):
            text = extract_text_from_docx(content)
        else:
            raise ResumeParserError(f"Unsupported file type: {filename}")

        # Extract all information
        resume_data = {
            "email": extract_email(text),
            "phone": extract_phone(text),
            "skills": extract_skills(text),
            "education": extract_education(text),
            "experience": extract_experience(text),
            "certifications": extract_certifications(text),
            "projects": extract_projects(text),
            "timestamp": datetime.now().isoformat()
        }

        return resume_data

    except Exception as e:
        raise ResumeParserError(f"Error parsing resume: {str(e)}") 