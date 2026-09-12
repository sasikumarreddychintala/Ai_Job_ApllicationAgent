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

def sanitize_pdf_text(text: str) -> str:
    """
    Sanitizes text for ReportLab PDF rendering.
    Converts Unicode hyphens/dashes, quotes, spaces, and stray symbols to ASCII equivalents
    so standard Type 1 fonts (Helvetica/Times) do not render black boxes/tofu glyphs (■).
    """
    if not text:
        return ""
    # Normalize Unicode dashes & hyphens to standard ASCII hyphen
    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u00ad\ufe58\ufe63\uff0d]", "-", text)
    # Normalize Unicode quotes to ASCII
    text = re.sub(r"[\u2018\u2019\u201a\u201b]", "'", text)
    text = re.sub(r'[\u201c\u201d\u201e\u201f]', '"', text)
    # Normalize Unicode spaces to standard space
    text = re.sub(r"[\u00a0\u2002\u2003\u2007\u2009\u202f]", " ", text)
    # Remove zero-width spaces / BOM
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    # Remove stray box / bullet symbols if any
    text = re.sub(r"[\u25a0\u25aa\u25cf\u25cb]", "", text)
    return text

def create_resume_version_filename(job_id: int, company: str, title: str) -> str:
    """Generates a structured, readable filename for tailored resume PDFs."""
    clean_co = sanitize_filename(company)
    clean_ti = sanitize_filename(title)
    return f"tailored_job{job_id}_{clean_co}_{clean_ti}.pdf"

def generate_pdf_resume(
    candidate: CandidateProfile,
    tailored_output: TailoredResumeOutput,
    output_path: Path,
    theme: Optional[str] = None
) -> Path:
    """
    Compiles a clean, professional, ATS-optimized PDF resume using ReportLab.
    Supports 'tech' (Modern Sans-Serif) and 'corporate' (Classic Serif) themes.
    """
    from config import settings
    active_theme = (theme or getattr(settings, "RESUME_THEME", "tech")).lower()
    is_corporate = "corp" in active_theme or "classic" in active_theme

    font_bold = 'Times-Bold' if is_corporate else 'Helvetica-Bold'
    font_regular = 'Times-Roman' if is_corporate else 'Helvetica'
    primary_color = colors.HexColor('#1e293b') if is_corporate else colors.HexColor('#0f172a')

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
        fontName=font_bold,
        fontSize=18,
        leading=22,
        textColor=primary_color
    )
    contact_style = ParagraphStyle(
        'ResumeContact',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )
    sec_hdr_style = ParagraphStyle(
        'ResumeSecHdr',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=10.5,
        leading=14,
        textColor=primary_color,
        spaceBefore=6,
        spaceAfter=1
    )
    body_style = ParagraphStyle(
        'ResumeBody',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#1e293b')
    )
    exp_hdr_style = ParagraphStyle(
        'ResumeExpHdr',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=9.5,
        leading=13.5,
        textColor=primary_color
    )
    bullet_style = ParagraphStyle(
        'ResumeBullet',
        parent=styles['Normal'],
        fontName=font_regular,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155'),
        leftIndent=14,
        spaceAfter=3
    )

    story = []

    # 1. Header (Name & Contact Details)
    c = candidate.contact_info
    story.append(Paragraph(sanitize_pdf_text(c.full_name), name_style))
    story.append(Spacer(1, 4))

    contact_parts = [f'<a href="mailto:{c.email}" color="#0284c7"><u>{c.email}</u></a>']
    if c.phone:
        contact_parts.append(sanitize_pdf_text(c.phone))
    if c.location:
        contact_parts.append(sanitize_pdf_text(c.location))
    if c.linkedin:
        contact_parts.append(f'<a href="{c.linkedin}" color="#0284c7"><u>LinkedIn</u></a>')
    if c.portfolio:
        contact_parts.append(f'<a href="{c.portfolio}" color="#0284c7"><u>Portfolio</u></a>')
    github_link = getattr(c, "github", "") or "https://github.com/sasikumarreddychintala"
    if github_link:
        contact_parts.append(f'<a href="{github_link}" color="#0284c7"><u>GitHub</u></a>')

    story.append(Paragraph(" &nbsp;|&nbsp; ".join(contact_parts), contact_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    # 2. Professional Summary
    summary_text = sanitize_pdf_text(tailored_output.summary or candidate.summary or "Experienced software professional.")
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
            all_skills.append(sanitize_pdf_text(s))

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

        tailored_bullets = [sanitize_pdf_text(b.tailored) for b in tailored_output.revised_bullet_points if b.tailored]
        bullet_idx = 0

        for exp in candidate.experience:
            period = sanitize_pdf_text(getattr(tailored_output, "tailored_period", None) or f"{exp.start_date or ''} - {exp.end_date or ''}")
            exp_pos = sanitize_pdf_text(exp.position)
            exp_comp = sanitize_pdf_text(exp.company)
            exp_header = f"<b>{exp_pos}</b> | {exp_comp} <font color=\"#64748b\">({period})</font>"
            story.append(Paragraph(exp_header, exp_hdr_style))
            story.append(Spacer(1, 3))

            bullets_to_show = exp.highlights or []
            for b in bullets_to_show:
                raw_text = tailored_bullets[bullet_idx] if bullet_idx < len(tailored_bullets) else b
                text_to_print = sanitize_pdf_text(raw_text)
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
            techs = [sanitize_pdf_text(t) for t in (techs or [])]
            desc = tp.description if (tp and tp.description) else proj.description
            desc = sanitize_pdf_text(desc or "")
            proj_name = sanitize_pdf_text(proj.name)
            
            tech_str = f" <font color=\"#64748b\">({', '.join(techs)})</font>" if techs else ""
            story.append(Paragraph(f"<b>{proj_name}</b>{tech_str}", exp_hdr_style))
            story.append(Spacer(1, 2))
            story.append(Paragraph(f"&bull;&nbsp;&nbsp;{desc}", bullet_style))
            story.append(Spacer(1, 4))

    # 6. Education
    if candidate.education:
        story.append(Paragraph("EDUCATION", sec_hdr_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1, spaceAfter=4))
        for edu in candidate.education:
            # Clean degree & field of study formatting
            deg = sanitize_pdf_text(edu.degree or "Bachelor of Technology")
            field = sanitize_pdf_text(edu.field_of_study or "")
            if field and field.lower() != "n/a" and field.lower() not in deg.lower():
                deg_display = f"{deg} in {field}"
            else:
                deg_display = deg
            
            inst = sanitize_pdf_text(edu.institution or "")
            grad_yr = sanitize_pdf_text(str(edu.graduation_year or ""))
            grad_display = f" <font color=\"#64748b\">({grad_yr})</font>" if grad_yr else ""
            edu_line = f"<b>{deg_display}</b> &mdash; {inst}{grad_display}"
            story.append(Paragraph(edu_line, body_style))
            story.append(Spacer(1, 3))

    doc.build(story)
    logger.info(f" Generated tailored PDF resume at: {output_path}")
    return output_path
