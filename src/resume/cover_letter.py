import re
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from config import settings
from src.resume.validator import CandidateProfile
from src.ai.schemas import ParsedJDRequirements
from src.utils.logger import logger

def generate_cover_letter_text(
    candidate: CandidateProfile,
    company: str,
    title: str,
    requirements: Optional[ParsedJDRequirements] = None
) -> str:
    """Generates a high-impact, 2-to-3 paragraph tailored cover letter."""
    c = candidate.contact_info
    full_name = c.full_name
    portfolio = c.portfolio or "https://resumeai.elevora.software"
    
    req_skills = requirements.required_skills if requirements and requirements.required_skills else ["Python", "FastAPI", "PostgreSQL", "Kafka"]
    matched = [s for s in candidate.skills if any(s.lower() == r.lower() for r in req_skills)]
    if not matched:
        matched = ["Python", "FastAPI", "PostgreSQL", "Apache Kafka", "Redis"]

    tech_stack_str = ", ".join(matched[:4])

    date_str = datetime.now().strftime("%B %d, %Y")

    letter_text = (
        f"{date_str}\n\n"
        f"Hiring Team\n"
        f"{company}\n\n"
        f"Dear Hiring Manager,\n\n"
        f"I am writing to express my enthusiastic interest in the {title} position at {company}. "
        f"As a Python Backend Developer with deep expertise in {tech_stack_str}, "
        f"I have consistently focused on building scalable, reliable, and high-performance server architectures. "
        f"{company}'s commitment to engineering excellence strongly resonates with my background in architecting enterprise APIs and distributed systems.\n\n"
        f"In my work at Levitica Technologies, I engineered RESTful backend services using FastAPI and Django for multi-tenant SaaS platforms, "
        f"optimizing database query execution to achieve a 30% reduction in API response times. "
        f"Additionally, I architected event-driven asynchronous pipelines with Apache Kafka and Redis, implementing secure JWT authentication and RBAC protocols across core modules. "
        f"Recently, I designed and deployed Elevora ResumeAI ({portfolio}), an AI-driven platform featuring token bucket rate limiting and a 100-point ATS scoring engine.\n\n"
        f"I am excited about the opportunity to bring my hands-on problem-solving mindset, backend engineering discipline, and experience with {matched[0] if matched else 'Python'} to {company}. "
        f"I welcome the opportunity to discuss how my technical skills can directly support your team's upcoming milestones.\n\n"
        f"Thank you for your time and consideration.\n\n"
        f"Sincerely,\n"
        f"{full_name}\n"
        f"{c.email} | {c.phone}\n"
        f"Portfolio: {portfolio} | LinkedIn: {c.linkedin}"
    )

    return letter_text

def generate_cover_letter_pdf(
    candidate: CandidateProfile,
    company: str,
    title: str,
    output_path: Path,
    requirements: Optional[ParsedJDRequirements] = None
) -> Path:
    """Compiles a clean, professional PDF cover letter matching resume aesthetics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        'CoverName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a')
    )
    contact_style = ParagraphStyle(
        'CoverContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )
    body_style = ParagraphStyle(
        'CoverBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=10
    )

    c = candidate.contact_info
    story = []

    # Header
    story.append(Paragraph(c.full_name, name_style))
    story.append(Spacer(1, 4))
    contact_parts = [c.email]
    if c.phone:
        contact_parts.append(c.phone)
    if c.location:
        contact_parts.append(c.location)
    if c.linkedin:
        contact_parts.append(f"LinkedIn: {c.linkedin}")
    if c.portfolio:
        contact_parts.append(f"Portfolio: {c.portfolio}")

    story.append(Paragraph(" &nbsp;|&nbsp; ".join(contact_parts), contact_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=14))

    # Date & Recipient
    date_str = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"<b>Date:</b> {date_str}", body_style))
    story.append(Paragraph(f"<b>To:</b> Hiring Team at {company}", body_style))
    story.append(Paragraph(f"<b>Position:</b> {title}", body_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=12))

    # Cover Letter Content
    raw_text = generate_cover_letter_text(candidate, company, title, requirements)
    # Split paragraphs by double newline and omit date/header lines already printed
    paragraphs = raw_text.split("\n\n")
    # Body starts from "Dear Hiring Manager," onwards
    for p in paragraphs:
        if any(p.startswith(prefix) for prefix in [date_str, "Hiring Team", company, "Dear", "Sincerely,", full_name if 'full_name' in locals() else '']):
            if p.startswith("Dear"):
                story.append(Paragraph(f"<b>{p}</b>", body_style))
            elif p.startswith("Sincerely,"):
                story.append(Spacer(1, 6))
                story.append(Paragraph(p.replace("\n", "<br/>"), body_style))
            elif not p.startswith(date_str) and not p.startswith("Hiring Team") and not p.startswith(company):
                story.append(Paragraph(p.replace("\n", "<br/>"), body_style))
        else:
            story.append(Paragraph(p.replace("\n", " "), body_style))

    doc.build(story)
    logger.info(f" Generated tailored Cover Letter PDF at: {output_path}")
    return output_path