import sys
from typing import List, Optional, Dict
from config import settings
from src.utils.logger import logger
from src.notifications.telegram import TelegramNotifier
from src.notifications.discord import DiscordNotifier

class NotificationManager:
    """Manages multi-channel user alerts (Console, Desktop Toast, Telegram, and Discord)."""

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.discord = DiscordNotifier()

    @classmethod
    def notify_top_match_found(
        cls,
        company: str,
        title: str,
        score: int,
        source: str,
        url: str = "",
        matched_skills: Optional[List[str]] = None,
        job_id: Optional[int] = None,
        resume_pdf_path: Optional[str] = None
    ) -> None:
        """Sends instant high-priority mobile alert when a top job match is discovered, AND delivers the tailored PDF resume."""
        skills_str = ", ".join(matched_skills[:4]) if matched_skills else "Python, FastAPI, PostgreSQL"
        src_label = "Python.org (Low Competition)" if "python_org" in source.lower() else "Direct ATS" if "ats" in source.lower() or "greenhouse" in source.lower() or "lever" in source.lower() else source

        min_tg_score = getattr(settings, "TELEGRAM_MIN_SCORE", 80)
        if score < min_tg_score:
            return

        # 1. Console Log
        logger.info(f"[NOTIFIER] HIGH-PRIORITY MATCH ({score}%): {title} at {company} [{src_label}]")

        # 2. Desktop Toast
        cls._send_desktop_toast(f"Top Match: {score}% Fit", f"{title} at {company} ({src_label})")

        # 3. Telegram Alert & Tailored Resume Delivery
        import urllib.parse
        from pathlib import Path
        clean_url = url if (url and url.startswith("http") and "hirect.in" not in url) else f"https://www.google.com/search?q={urllib.parse.quote(f'{title} {company} jobs')}"
        tg = TelegramNotifier()
        if tg.is_configured:
            tg_msg = (
                f"🎯 *NEW MATCH FOUND ({score}/100)*\n\n"
                f"🏢 *Company:* {company}\n"
                f"💼 *Role:* {title}\n"
                f"🌐 *Platform:* {src_label}\n"
                f"⚡ *Tech Match:* {skills_str}\n\n"
                f"🔗 *Apply Link:*\n{clean_url}\n\n"
                f"📄 *Tailored ATS Resume attached below:* 👇"
            )
            tg.send_message(tg_msg)

            # Auto-compile and deliver tailored PDF resume directly under the link
            pdf_to_send = resume_pdf_path
            if not pdf_to_send and job_id:
                try:
                    from src.agents.resume_agent import ResumeTailorAgent
                    agent = ResumeTailorAgent()
                    pdf_to_send = agent.tailor_resume_for_job(job_id)
                except Exception as te:
                    logger.debug(f"Resume compile for notification notice: {te}")

            if pdf_to_send and Path(pdf_to_send).exists():
                caption = f"📄 Tailored Resume: {title} @ {company} ({score}/100 Match)"
                tg.send_document(Path(pdf_to_send), caption=caption)

        # 4. Discord Alert
        dc = DiscordNotifier()
        if dc.is_configured:
            fields = [
                {"name": "🏢 Company", "value": company, "inline": True},
                {"name": "🎯 Match Score", "value": f"{score}/100 (VERY HIGH)", "inline": True},
                {"name": "🌐 Platform Source", "value": src_label, "inline": True},
                {"name": "⚡ Tech Match", "value": skills_str, "inline": False}
            ]
            if url:
                fields.append({"name": "🔗 Job Link", "value": f"[Apply Directly]({url})", "inline": False})
            dc.send_embed(
                title=f"🔥 Top Job Match: {title} ({score}%)",
                description=f"A new high-shortlisting role was discovered for you!",
                color=0x10b981,
                fields=fields
            )

    @classmethod
    def notify_human_intervention(cls, company: str, title: str, reason: str = "CAPTCHA detected") -> None:
        """Sends prominent alert when human intervention is required."""
        msg = f"{reason} — manual action required for [{company} / {title}]. Complete it in the open browser."
        
        # 1. Console Alert
        logger.info("\n" + "!" * 70)
        logger.info(f"[bold red]HUMAN INTERVENTION REQUIRED[/bold red]")
        logger.info(f"[bold white]{msg}[/bold white]")
        logger.info("!" * 70 + "\n")

        # 2. Terminal Bell Audio Cue
        sys.stdout.write("\a")
        sys.stdout.flush()

        # 3. Windows Toast Notification
        cls._send_desktop_toast("Action Required", msg)

        # 4. Telegram Notification
        tg = TelegramNotifier()
        if tg.is_configured:
            tg.send_message(f"⚠️ *HUMAN INTERVENTION REQUIRED*\n\n{msg}")

        # 5. Discord Notification
        dc = DiscordNotifier()
        if dc.is_configured:
            dc.send_embed(
                title="⚠️ Human Intervention Required",
                description=msg,
                color=0xef4444
            )

    @classmethod
    def notify_application_status(cls, company: str, title: str, status: str) -> None:
        """Sends alert on application status change (e.g. SUBMITTED or READY_TO_SUBMIT)."""
        msg = f"Job Application for [{company} - {title}] is now {status}."
        logger.info(f"[bold green][UPDATE] {msg}[/bold green]")
        
        cls._send_desktop_toast("Application Update", msg)
        
        tg = TelegramNotifier()
        if tg.is_configured:
            tg.send_message(f"🚀 *Application Update*\n\n{msg}")

        dc = DiscordNotifier()
        if dc.is_configured:
            dc.send_embed(
                title=f"🚀 Application Status: {status}",
                description=f"**{company}** - {title}",
                color=0x3b82f6
            )

    @classmethod
    def notify_daily_summary(cls, discovered: int, qualified: int, submitted: int, skipped: int) -> None:
        """Sends daily digest report."""
        summary = (
            f"*Job Application Agent Daily Digest*\n\n"
            f"- Discovered: {discovered}\n"
            f"- Qualified: {qualified}\n"
            f"- Submitted / Ready: {submitted}\n"
            f"- Skipped: {skipped}"
        )
        logger.info("\n" + "=" * 50)
        logger.info("[bold cyan]DAILY SUMMARY REPORT[/bold cyan]")
        logger.info(summary)
        logger.info("=" * 50 + "\n")

        cls._send_desktop_toast("Daily Summary", f"Processed: {submitted} submitted / ready, {qualified} qualified.")

        tg = TelegramNotifier()
        if tg.is_configured:
            tg.send_message(summary)

        dc = DiscordNotifier()
        if dc.is_configured:
            dc.send_embed(
                title="📊 Daily Job Application Digest",
                description="Summary of today's autonomous job applications and discovery.",
                color=0x8b5cf6,
                fields=[
                    {"name": "🔍 Discovered", "value": str(discovered), "inline": True},
                    {"name": "🎯 Qualified", "value": str(qualified), "inline": True},
                    {"name": "🚀 Submitted / Ready", "value": str(submitted), "inline": True},
                    {"name": "⏭️ Skipped", "value": str(skipped), "inline": True}
                ]
            )

    @classmethod
    def send_test_notification(cls) -> Dict[str, bool]:
        """Dispatches a test notification across all channels."""
        results = {}
        tg = TelegramNotifier()
        results["telegram"] = tg.send_message("🧪 *Test Alert from your AI Job Agent!* Notifications are working.") if tg.is_configured else False

        dc = DiscordNotifier()
        results["discord"] = dc.send_embed(
            title="🧪 Test Notification",
            description="Your AI Job Application Agent notifications are active and working properly!",
            color=0x10b981
        ) if dc.is_configured else False

        cls._send_desktop_toast("Test Alert", "Desktop notifications are working!")
        results["desktop"] = True
        return results

    @staticmethod
    def _send_desktop_toast(title: str, message: str) -> None:
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                f"Job Agent: {title}",
                message,
                duration=5,
                threaded=True
            )
        except Exception:
            pass

