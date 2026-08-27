import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Optional, Dict, Any

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.database.audit import AuditManager

class EmailDispatcher:
    """
    Dispatches direct cold emails and job applications with attached tailored PDF resumes and cover letters.
    Supports standard Gmail SMTP (with Google App Password), Outlook, and custom SMTP servers.
    """

    def __init__(
        self,
        smtp_server: str = getattr(settings, "SMTP_SERVER", "smtp.gmail.com"),
        smtp_port: int = getattr(settings, "SMTP_PORT", 587),
        smtp_user: str = getattr(settings, "SMTP_USER", ""),
        smtp_password: str = getattr(settings, "SMTP_PASSWORD", ""),
        sender_name: str = getattr(settings, "SMTP_FROM_NAME", "Sasi Kumar Reddy Chintala")
    ):
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port)
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender_name = sender_name

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)

    def send_cold_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        resume_pdf_path: Optional[Path] = None,
        cover_letter_pdf_path: Optional[Path] = None,
        job_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Dispatches email with tailored PDF resume attached and logs the application timestamp.
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "SMTP credentials not configured. Please set your Gmail address and 16-character Google App Password in Alerts Setup or .env"
            }

        if not to_email or "@" not in to_email:
            return {
                "success": False,
                "error": f"Invalid recipient email address: {to_email}"
            }

        try:
            msg = MIMEMultipart()
            msg["From"] = f"{self.sender_name} <{self.smtp_user}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            # Body content
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

            # Attach Tailored PDF Resume
            if resume_pdf_path and Path(resume_pdf_path).exists():
                with open(resume_pdf_path, "rb") as f:
                    part = MIMEApplication(f.read(), _subtype="pdf")
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=Path(resume_pdf_path).name
                    )
                    msg.attach(part)
                    logger.info(f" Attached Resume: {Path(resume_pdf_path).name}")

            # Attach Tailored PDF Cover Letter
            if cover_letter_pdf_path and Path(cover_letter_pdf_path).exists():
                with open(cover_letter_pdf_path, "rb") as f:
                    part = MIMEApplication(f.read(), _subtype="pdf")
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=Path(cover_letter_pdf_path).name
                    )
                    msg.attach(part)
                    logger.info(f" Attached Cover Letter: {Path(cover_letter_pdf_path).name}")

            # Connect and send via TLS (Port 587) or SSL (Port 465)
            logger.info(f" Connecting to SMTP server {self.smtp_server}:{self.smtp_port}...")
            sent_ok = False
            last_err = None

            # Attempt 1: Port 587 STARTTLS
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.smtp_user, [to_email], msg.as_string())
                    sent_ok = True
            except Exception as e587:
                last_err = e587
                logger.warning(f"Port {self.smtp_port} STARTTLS notice: {e587}. Trying Port 465 SSL fallback...")
                try:
                    # Attempt 2: Port 465 Direct SSL
                    with smtplib.SMTP_SSL(self.smtp_server, 465, timeout=15) as server_ssl:
                        server_ssl.login(self.smtp_user, self.smtp_password)
                        server_ssl.sendmail(self.smtp_user, [to_email], msg.as_string())
                        sent_ok = True
                except Exception as e465:
                    last_err = e465

            if not sent_ok:
                raise last_err or Exception("Failed to connect to SMTP server.")

            logger.info(f"[bold green] Direct cold email dispatched successfully to {to_email}![/bold green]")

            # Log audit event and update SQLite status if job_id provided
            if job_id:
                try:
                    audit = AuditManager()
                    audit.log_application_event(
                        job_id=job_id,
                        event_type="COLD_EMAIL_SENT",
                        payload={
                            "recipient": to_email,
                            "subject": subject,
                            "resume_attached": bool(resume_pdf_path and Path(resume_pdf_path).exists()),
                            "cover_letter_attached": bool(cover_letter_pdf_path and Path(cover_letter_pdf_path).exists())
                        }
                    )
                    conn = init_db(settings.DATABASE_PATH)
                    with conn:
                        conn.execute(
                            "UPDATE applications SET status = 'SUBMITTED', applied_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                            (job_id,)
                        )
                    conn.close()
                except Exception as e:
                    logger.debug(f"Audit log notice: {e}")

            return {
                "success": True,
                "recipient": to_email,
                "subject": subject,
                "message": f"Cold email sent successfully to {to_email} with PDF attachments!"
            }

        except Exception as e:
            logger.error(f"Email dispatch failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

email_dispatcher = EmailDispatcher()

