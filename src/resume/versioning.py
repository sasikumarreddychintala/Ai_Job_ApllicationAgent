import re
from pathlib import Path
from typing import List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from src.resume.validator import CandidateProfile
from src.ai.schemas import TailoredResumeOutput
from src.utils.logger import logger

def sanitize_filename(name: str) -> str:
    """Sanitizes strings for safe cross-platform file paths."""
    clean = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[-\s]+", "_", clean).strip("_")

def create_resume_version_filename(job_id: int, company: str, title: str) -> str:
    """Generates a structured, readable filename for tailored resume PDFs."""
    clean_co = sanitize_filename(company)
    clean_ti = sanitize_filename(title)
    return f"tailored_job{job_id}_{clean_co}_{clean_ti}.pdf"

def generate_pdf_resume(
    candidate: CandidateProfile,
    tailored_output: TailoredResumeOutput,
    output_path: Path
) -> Path:
    """
    Compiles a clean, professional, ATS-optimized PDF resume using ReportLab.
    Ensures precise typography, automated flow, and zero text overlap.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        'ResumeName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a')
    )
    contact_style = ParagraphStyle(
        'ResumeContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )
    sec_hdr_style = ParagraphStyle(
        'ResumeSecHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=6,
        spaceAfter=1
    )
    body_style = ParagraphStyle(
        'ResumeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#1e293b')
    )
    exp_hdr_style = ParagraphStyle(
        'ResumeExpHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#0f172a')
    )
    bullet_style = ParagraphStyle(
        'ResumeBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        leftIndent=14,
        spaceAfter=3
    )

    story = []

    # 1. Header (Name & Contact Details)
    c = candidate.contact_info
    story.append(Paragraph(c.full_name, name_style))
    story.append(Spacer(1, 4))

    contact_parts = [c.email]
    if c.phone:
        contact_parts.append(c.phone)
    if c.location:
        contact_parts.append(c.location)
    if c.linkedin:
        contact_parts.append(f'LinkedIn: {c.linkedin}')
    if c.portfolio:
        contact_parts.append(f'Portfolio: {c.portfolio}')

    story.append(Paragraph(" &nbsp;|&nbsp; ".join(contact_parts), contact_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    # 2. Professional Summary
    summary_text = tailored_output.summary or candidate.summary or "Experienced software professional."
    story.append(Paragraph("PROFESSIONAL SUMMARY", sec_hdr_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=4))
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 6))

    # 3. Technical Skills
    story.append(Paragraph("TECHNICAL SKILLS", sec_hdr_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=4))
    
    # Combine highlighted skills with candidate skills
    raw_skills = (tailored_output.highlighted_skills or []) + (candidate.skills or [])
    # Deduplicate preserving order
    seen = set()
    all_skills = []
    for s in raw_skills:
        if s and s.lower() not in seen:
            seen.add(s.lower())
            all_skills.append(s)

    cat_map = {
        "Languages & Frameworks": ["Python", "FastAPI", "Django", "Django REST Framework", "Flask", "TypeScript", "JavaScript", "SQLAlchemy", "REST APIs"],
        "Data & Analytics": ["Pandas", "NumPy", "SQL", "ETL Pipelines", "Data Analytics", "Quantitative Analysis", "Scikit-Learn", "Matplotlib", "PyTorch"],
        "Distributed Systems & Caching": ["Apache Kafka", "Redis", "Microservices", "Event-Driven Architecture", "Multi-processing", "Concurrency", "High Availability"],
        "Databases & Cloud": ["PostgreSQL", "MySQL", "AWS (EC2, S3, RDS)", "AWS EC2", "AWS S3", "AWS RDS", "Docker", "Linux", "Git"],
        "AI Tools & Practices": ["AI-Assisted Dev Toolchains", "LangChain", "Generative AI", "RAG Pipelines", "Ollama", "Prompt Engineering", "JWT", "RBAC", "OAuth 2.0", "Unit Testing"]
    }

    categorized_rendered = set()
    for cat_name, cat_items in cat_map.items():
        present = [s for s in cat_items if any(s.lower() == k.lower() for k in all_skills)]
        if present:
            for p in present:
                categorized_rendered.add(p.lower())
            line = f"<b>{cat_name}:</b> {', '.join(present)}"
            story.append(Paragraph(line, body_style))
            story.append(Spacer(1, 2))

    other_skills = [s for s in all_skills if s.lower() not in categorized_rendered]
    if other_skills:
        story.append(Paragraph(f"<b>Key Competencies:</b> {', '.join(other_skills[:6])}", body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 4))

    # 4. Work Experience
    if candidate.experience:
        story.append(Paragraph("WORK EXPERIENCE", sec_hdr_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=4))

        tailored_bullets = [b.tailored for b in tailored_output.revised_bullet_points if b.tailored]
        bullet_idx = 0

        for exp in candidate.experience:
            period = getattr(tailored_output, "tailored_period", None) or f"{exp.start_date or ''} - {exp.end_date or ''}"
            exp_header = f"<b>{exp.position}</b> | {exp.company} <font color=\"#64748b\">({period})</font>"
            story.append(Paragraph(exp_header, exp_hdr_style))
            story.append(Spacer(1, 3))

            bullets_to_show = exp.highlights or []
            for b in bullets_to_show:
                text_to_print = tailored_bullets[bullet_idx] if bullet_idx < len(tailored_bullets) else b
                story.append(Paragraph(f"&bull;&nbsp;&nbsp;{text_to_print}", bullet_style))
                bullet_idx += 1

            story.append(Spacer(1, 4))

    # 5. Projects
    if candidate.projects:
        story.append(Paragraph("KEY PROJECTS", sec_hdr_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=4))
        
        tailored_proj_map = {tp.name.lower(): tp for tp in (tailored_output.tailored_projects or [])}
        for proj in candidate.projects:
            tp = tailored_proj_map.get(proj.name.lower())
            techs = tp.technologies if (tp and tp.technologies) else proj.technologies
            desc = tp.description if (tp and tp.description) else proj.description
            
            tech_str = f" <font color=\"#64748b\">({', '.join(techs)})</font>" if techs else ""
            story.append(Paragraph(f"<b>{proj.name}</b>{tech_str}", exp_hdr_style))
            story.append(Spacer(1, 2))
            story.append(Paragraph(f"&bull;&nbsp;&nbsp;{desc}", bullet_style))
            story.append(Spacer(1, 4))

    # 6. Education
    if candidate.education:
        story.append(Paragraph("EDUCATION", sec_hdr_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=4))
        for edu in candidate.education:
            # Clean degree & field of study formatting
            deg = edu.degree or "Bachelor of Technology"
            field = edu.field_of_study or ""
            if field and field.lower() != "n/a" and field.lower() not in deg.lower():
                deg_display = f"{deg} in {field}"
            else:
                deg_display = deg
            
            grad_display = f" <font color=\"#64748b\">({edu.graduation_year})</font>" if edu.graduation_year else ""
            edu_line = f"<b>{deg_display}</b> &mdash; {edu.institution}{grad_display}"
            story.append(Paragraph(edu_line, body_style))
            story.append(Spacer(1, 3))

    doc.build(story)
    logger.info(f" Generated tailored PDF resume at: {output_path}")
    return output_path
