from typing import Dict, Optional
from src.resume.validator import CandidateProfile
from src.ai.schemas import ParsedJDRequirements
from src.utils.logger import logger

def generate_outreach_messages(
    candidate: CandidateProfile,
    company: str,
    title: str,
    requirements: Optional[ParsedJDRequirements] = None
) -> Dict[str, str]:
    """
    Generates high-converting, personalized cold outreach notes for:
    1. LinkedIn Connection Request (< 300 chars)
    2. Hiring Manager Direct Cold Email (Subject + Body)
    3. Technical Recruiter InMail
    """
    c = candidate.contact_info
    full_name = c.full_name
    first_name = full_name.split()[0]
    portfolio = c.portfolio or "https://resumeai.elevora.software"
    email = c.email
    phone = c.phone or "+91-8790039883"

    req_skills = requirements.required_skills if requirements and requirements.required_skills else ["Python", "FastAPI", "PostgreSQL", "Kafka"]
    matched = [s for s in candidate.skills if any(s.lower() == r.lower() for r in req_skills)]
    if not matched:
        matched = ["Python", "FastAPI", "PostgreSQL", "Kafka", "Redis"]

    top_tech = ", ".join(matched[:3])

    # 1. LinkedIn Connection Note (< 300 characters limit)
    li_note = (
        f"Hi! Noticed {company}'s opening for {title}. "
        f"I'm a Python Backend Dev specialized in {top_tech}. "
        f"Built high-throughput APIs & Elevora ResumeAI ({portfolio}). "
        f"Would love to connect and share how I can contribute!"
    )
    if len(li_note) > 298:
        li_note = (
            f"Hi! Saw {company}'s {title} role. "
            f"I'm a Python Backend Dev ({top_tech}). "
            f"Built scalable REST APIs & Elevora ResumeAI ({portfolio}). "
            f"Would love to connect!"
        )

    # 2. Hiring Manager Cold Email
    email_subject = f"Application: {title} - {full_name} ({top_tech})"
    email_body = (
        f"Hi Hiring Team,\n\n"
        f"I came across the {title} role at {company} and wanted to reach out directly. "
        f"With hands-on experience building distributed backend systems using {top_tech}, "
        f"I specialize in architecting high-performance REST APIs, event-driven Kafka workflows, and query-optimized PostgreSQL databases.\n\n"
        f"Recently, I built Elevora ResumeAI ({portfolio}) featuring automated ATS scoring and dual-LLM fallback architecture. "
        f"At Levitica Technologies, I engineered multi-tenant SaaS services that improved API response times by 30%.\n\n"
        f"I would love to bring this experience to {company}. Are you open to a brief 10-minute conversation this week?\n\n"
        f"Best regards,\n"
        f"{full_name}\n"
        f"{email} | {phone}\n"
        f"Portfolio: {portfolio}\n"
        f"LinkedIn: {c.linkedin}"
    )

    # 3. Recruiter InMail
    recruiter_subject = f"{title} Opportunity - {full_name}"
    recruiter_inmail = (
        f"Hi,\n\n"
        f"I hope you're having a great week! I noticed you are hiring for the {title} position at {company}.\n\n"
        f"I am a Python Backend Developer with strong expertise in {top_tech}, Docker, and asynchronous microservices. "
        f"I have delivered scalable SaaS backends for 200+ active users and built Elevora ResumeAI ({portfolio}).\n\n"
        f"I have attached my tailored resume for your review and would welcome the opportunity to discuss how my technical background aligns with your team's goals.\n\n"
        f"Thanks for your time,\n"
        f"{full_name}\n"
        f"{email} | {phone}"
    )

    return {
        "linkedin_note": li_note,
        "linkedin_char_count": str(len(li_note)),
        "email_subject": email_subject,
        "email_body": email_body,
        "recruiter_subject": recruiter_subject,
        "recruiter_inmail": recruiter_inmail,
        "company": company,
        "title": title
    }