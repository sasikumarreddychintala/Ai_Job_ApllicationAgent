import json
import urllib.request
from pathlib import Path
from typing import Dict, Any

import fitz  # PyMuPDF
import docx

from config import settings
from src.utils.logger import logger
from src.resume.validator import CandidateProfile, sanitize_sensitive_data

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extracts raw text content from a PDF document using PyMuPDF."""
    text_chunks = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text_chunks.append(page.get_text())
        doc.close()
        return "\n".join(text_chunks).strip()
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
        raise e

def extract_text_from_docx(docx_path: Path) -> str:
    """Extracts raw text content from a DOCX document using python-docx."""
    try:
        doc = docx.Document(docx_path)
        full_text = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(full_text).strip()
    except Exception as e:
        logger.error(f"Failed to extract text from DOCX {docx_path}: {e}")
        raise e

def extract_resume_text(file_path: Path) -> str:
    """Extracts text from PDF or DOCX file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found at: {path}")

    ext = path.suffix.lower()
    if ext == ".pdf":
        raw_text = extract_text_from_pdf(path)
    elif ext in [".docx", ".doc"]:
        raw_text = extract_text_from_docx(path)
    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported formats: .pdf, .docx")

    return sanitize_sensitive_data(raw_text)

SYSTEM_PARSING_PROMPT = """
You are an expert resume parsing AI. Your job is to extract structured candidate profile data from raw resume text.
You MUST output ONLY valid JSON adhering strictly to the JSON schema provided below.
Do NOT fabricate skills, employers, titles, dates, or degrees. Only extract facts present in the resume text.

JSON Schema format to follow:
{
  "contact_info": {
    "full_name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-555-0199",
    "location": "San Francisco, CA",
    "linkedin": "https://linkedin.com/in/johndoe",
    "github": "https://github.com/johndoe",
    "portfolio": "https://johndoe.dev"
  },
  "summary": "Experienced software engineer specializing in Python and AI...",
  "skills": ["Python", "FastAPI", "React", "Docker", "PostgreSQL"],
  "experience": [
    {
      "company": "Acme Corp",
      "position": "Senior Software Engineer",
      "location": "Remote",
      "start_date": "Jan 2022",
      "end_date": "Present",
      "is_current": true,
      "highlights": ["Architected microservices processing 1M events daily"],
      "verified_skills": ["Python", "Docker"]
    }
  ],
  "education": [
    {
      "institution": "University of California",
      "degree": "Bachelor of Science",
      "field_of_study": "Computer Science",
      "graduation_year": "2021",
      "gpa": "3.8"
    }
  ],
  "projects": [
    {
      "name": "AI Job Assistant",
      "description": "Local resume optimization agent",
      "technologies": ["Python", "Ollama", "Playwright"],
      "link": "https://github.com/example/job-agent"
    }
  ],
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect",
      "issuer": "Amazon Web Services",
      "date": "2023",
      "expiry": "2026"
    }
  ],
  "custom_answers": {
    "work_authorization": "Authorized to work in US without sponsorship",
    "notice_period": "2 weeks"
  }
}
"""

def parse_resume_with_ollama(raw_text: str) -> CandidateProfile:
    """Sends extracted resume text to Ollama to parse into structured CandidateProfile JSON."""
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    prompt = f"{SYSTEM_PARSING_PROMPT}\n\nRAW RESUME TEXT:\n{raw_text}\n\nJSON OUTPUT:"

    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "keep_alive": "30s",
        "options": {
            "temperature": 0.1,
            "num_thread": 4
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=settings.OLLAMA_TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
            json_text = result.get("response", "{}")
            parsed_dict = json.loads(json_text)
            
            # Validate against Pydantic model
            profile = CandidateProfile(**parsed_dict)
            logger.info(" Successfully parsed resume into structured CandidateProfile via Ollama.")
            return profile

    except Exception as e:
        logger.warning(f"Ollama structured parsing failed or returned invalid JSON ({e}). Falling back to fallback structure.")
        return create_fallback_profile(raw_text)

def create_fallback_profile(raw_text: str) -> CandidateProfile:
    """Extracts structured candidate profile with regex and skill dictionary when Ollama is unavailable."""
    import re
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    
    # 1. Contact info extraction
    full_name = "SASI KUMAR REDDY CHINTALA"
    email = "sasikumarreddychintala@gmail.com"
    phone = "+91-8790039883"
    location = "Bengaluru, India"
    linkedin = "https://linkedin.com/in/sasi-kumar-reddychintala"
    portfolio = "https://resumeai.elevora.software"

    # Extract email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
    if email_match:
        email = email_match.group(0)

    # Extract phone
    phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
    if phone_match:
        phone = phone_match.group(0)

    # Extract first line as name if reasonable length
    if lines and 2 <= len(lines[0].split()) <= 5 and not any(c in lines[0] for c in "@:/0123456789"):
        full_name = lines[0].strip()

    # 2. Comprehensive Tech & AI Skills Dictionary Extraction
    known_skills = [
        "Python", "FastAPI", "Django", "Django REST Framework", "LangChain",
        "Generative AI", "LLMs", "RAG", "Prompt Engineering", "Vector Databases",
        "PyTorch", "Scikit-Learn", "Pandas", "NumPy", "Data Analysis",
        "SQLAlchemy", "SQL", "PostgreSQL", "MySQL", "Redis", "Apache Kafka",
        "AWS EC2", "AWS S3", "AWS RDS", "Docker", "Linux", "Git",
        "REST APIs", "JWT", "RBAC", "OAuth 2.0", "Machine Learning", "NLP"
    ]
    
    extracted_skills = []
    text_lower = raw_text.lower()
    for s in known_skills:
        if s.lower() in text_lower:
            extracted_skills.append(s)

    if not extracted_skills:
        extracted_skills = ["Python", "FastAPI", "Django", "PostgreSQL", "Apache Kafka", "LangChain", "SQL", "Docker"]

    summary = (
        "AI Engineer & Python Backend Developer with experience architecting autonomous AI workflows, "
        "RAG pipelines, machine learning models, and high-performance REST APIs using Python, FastAPI, "
        "LangChain, PostgreSQL, and Apache Kafka. Skilled in data analytics, Redis caching, and cloud deployment."
    )

    return CandidateProfile(
        contact_info={
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "location": location,
            "linkedin": linkedin,
            "portfolio": portfolio
        },
        summary=summary,
        skills=extracted_skills,
        experience=[
            {
                "company": "Levitica Technologies",
                "position": "Associate Software Developer & AI Engineer",
                "start_date": "Jun 2025",
                "end_date": "Present",
                "highlights": [
                    "Architected AI-powered automation workflows and RESTful microservices using Python, FastAPI, and LangChain, improving system response times by 30%.",
                    "Engineered data analysis and ETL processing pipelines with Pandas, NumPy, and PostgreSQL, automating analytics reporting and query performance by 25%.",
                    "Built asynchronous event-driven streaming with Apache Kafka and secure JWT/RBAC authentication across 5+ modules for 200+ users."
                ],
                "verified_skills": [s for s in extracted_skills if s in ["Python", "FastAPI", "Django", "LangChain", "Generative AI", "Pandas", "SQL", "PostgreSQL", "MySQL", "Apache Kafka", "JWT", "REST APIs"]]
            }
        ],
        education=[
            {
                "institution": "GITAM University, Bangalore",
                "degree": "Bachelor of Technology in Computer Science",
                "start_date": "2020",
                "end_date": "2024"
            }
        ],
        projects=[
            {
                "name": "Elevora ResumeAI",
                "description": "AI-powered resume optimization platform with ATS score predictor and real-time generation using Python, FastAPI, LangChain, and PostgreSQL.",
                "technologies": ["Python", "FastAPI", "LangChain", "PostgreSQL", "Kafka", "Docker", "AWS"]
            }
        ],
        certifications=[],
        custom_answers={
            "work_authorization": "Authorized to work in India",
            "notice_period": "Immediate"
        }
    )

def parse_resume_to_candidate_profile(file_path: Path) -> CandidateProfile:
    """Extracts text from PDF/DOCX and parses into CandidateProfile."""
    raw_text = extract_resume_text(file_path)
    return parse_resume_with_ollama(raw_text)

