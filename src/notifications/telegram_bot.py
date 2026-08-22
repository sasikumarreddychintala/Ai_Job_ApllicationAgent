import os
import json
import time
import uuid
import mimetypes
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any, List

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.resume.profile import ProfileManager

class TelegramInteractiveBot:
    """
    2-Way Interactive Telegram Assistant for controlling the AI Job Application Agent from your phone.
    Allows searching 10+ platforms, viewing live statistics, generating interview prep, and receiving
    tailored PDF resumes directly in your Telegram chat!
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        db_path: Path = settings.DATABASE_PATH
    ):
        self.bot_token = bot_token or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(chat_id or getattr(settings, "TELEGRAM_CHAT_ID", ""))
        self.db_path = db_path
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_update_id = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def start(self):
        """Starts the Telegram polling daemon thread."""
        if not self.is_configured:
            logger.debug("[Telegram Bot] Cannot start: Bot token or Chat ID not configured.")
            return
        if self._running and self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="TelegramBotPollingThread")
        self._thread.start()
        logger.info("[Telegram Bot] 2-Way Interactive Assistant is online & listening for commands!")

    def stop(self):
        """Stops the polling daemon."""
        self._running = False
        logger.info("[Telegram Bot] Interactive Assistant stopped.")

    def send_message(self, text: str, target_chat_id: Optional[str] = None) -> bool:
        """Sends markdown formatted text to Telegram chat."""
        cid = target_chat_id or self.chat_id
        if not self.bot_token or not cid:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": cid,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.debug(f"[Telegram Bot] Send message notice: {e}")
            return False

    def send_document(self, file_path: Path, caption: str = "", target_chat_id: Optional[str] = None) -> bool:
        """Uploads and sends a PDF file (e.g. tailored resume or cover letter) directly to Telegram."""
        cid = target_chat_id or self.chat_id
        if not self.bot_token or not cid or not file_path.exists():
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        try:
            import requests
            with open(file_path, "rb") as f:
                resp = requests.post(
                    url,
                    data={"chat_id": cid, "caption": caption},
                    files={"document": (file_path.name, f, "application/pdf")},
                    timeout=25
                )
            if resp.status_code == 200:
                logger.info(f"[Telegram Bot] PDF '{file_path.name}' delivered to Telegram successfully!")
                return True
            else:
                logger.warning(f"[Telegram Bot] Send document returned {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"[Telegram Bot] Send document error: {e}")

        return False

    def _poll_loop(self):
        """Continuously long-polls Telegram for incoming messages."""
        while self._running:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self._last_update_id + 1}&timeout=15"
                req = urllib.request.Request(url, headers={"User-Agent": "JobAgent/2.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        updates = data.get("result", [])
                        for update in updates:
                            self._last_update_id = update.get("update_id", self._last_update_id)
                            msg = update.get("message", {})
                            text = (msg.get("text") or "").strip()
                            doc = msg.get("document")
                            sender_id = str(msg.get("chat", {}).get("id", ""))
                            sender_name = msg.get("from", {}).get("first_name", "User")

                            if doc:
                                self._handle_document(doc, sender_id, sender_name)
                            elif text:
                                self._handle_command(text, sender_id, sender_name)
                time.sleep(1.0)
            except Exception as e:
                time.sleep(3.0)

    def _handle_document(self, doc: Dict[str, Any], sender_id: str, sender_name: str):
        """Downloads, parses, and updates candidate master resume when a user sends a PDF file."""
        if self.chat_id and sender_id != self.chat_id:
            self.send_message("⛔ Unauthorized.", target_chat_id=sender_id)
            return

        file_name = doc.get("file_name", "resume.pdf")
        file_id = doc.get("file_id")
        if not file_id or not file_name.lower().endswith((".pdf", ".docx")):
            self.send_message("⚠️ Please send your resume as a **.PDF** (or .DOCX) document.", target_chat_id=sender_id)
            return

        self.send_message(f"📥 *Received '{file_name}'!* Downloading and parsing your new Master Resume...", target_chat_id=sender_id)

        def _bg_process_doc():
            try:
                # 1. Get file path from Telegram
                info_url = f"https://api.telegram.org/bot{self.bot_token}/getFile?file_id={file_id}"
                req = urllib.request.Request(info_url, headers={"User-Agent": "JobAgent/2.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    info_data = json.loads(resp.read().decode("utf-8"))
                
                file_path_tg = info_data.get("result", {}).get("file_path")
                if not file_path_tg:
                    self.send_message("❌ Failed to retrieve document from Telegram servers.", target_chat_id=sender_id)
                    return

                # 2. Download file
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path_tg}"
                local_dest = Path(settings.MASTER_RESUME_PATH)
                local_dest.parent.mkdir(parents=True, exist_ok=True)
                
                down_req = urllib.request.Request(download_url, headers={"User-Agent": "JobAgent/2.0"})
                with urllib.request.urlopen(down_req, timeout=30) as dresp:
                    content = dresp.read()
                    local_dest.write_bytes(content)

                # 3. Parse resume with ResumeParser
                from src.resume.parser import ResumeParser
                parser = ResumeParser()
                parsed_profile = parser.parse(local_dest)

                # 4. Save to candidate_profile.json
                pm = ProfileManager()
                pm.save_profile(parsed_profile)

                c_info = parsed_profile.contact_info
                skills_preview = ", ".join(parsed_profile.skills[:6]) if parsed_profile.skills else "Python, FastAPI, SQL"

                success_msg = (
                    f"✅ *Master Resume Successfully Updated & Parsed!*\n\n"
                    f"👤 *Candidate:* `{c_info.full_name or sender_name}`\n"
                    f"📧 *Email:* `{c_info.email or 'N/A'}`\n"
                    f"📱 *Phone:* `{c_info.phone or 'N/A'}`\n"
                    f"⚡ *Top Skills Detected:* {skills_preview} (+{max(0, len(parsed_profile.skills)-6)} more)\n\n"
                    f"🎉 All future job searches and tailored PDF resumes will now use your newly uploaded resume!"
                )
                self.send_message(success_msg, target_chat_id=sender_id)

            except Exception as e:
                logger.error(f"[Telegram Bot] Error parsing uploaded resume: {e}")
                self.send_message(f"❌ Error processing resume document: {e}", target_chat_id=sender_id)

        threading.Thread(target=_bg_process_doc, daemon=True).start()

    def _handle_command(self, text: str, sender_id: str, sender_name: str):
        """Processes incoming user commands."""
        # Security: Only allow authorized chat_id if configured
        if self.chat_id and sender_id != self.chat_id:
            self.send_message("⛔ Unauthorized. This bot is private to its owner.", target_chat_id=sender_id)
            return

        cmd = text.split()[0].lower()
        args = text.split()[1:]

        logger.info(f"[Telegram Bot] Received command '{text}' from {sender_name}")

        if cmd in ("/start", "/help"):
            help_msg = (
                f"👋 *Hello {sender_name}! I am your AI Job Application Assistant.*\n\n"
                f"Here is what you can do from your phone:\n\n"
                f"🌱 `/fresher [location]`\n"
                f"↳ Searches high-priority **Fresher & 0–1 Year** openings across 10+ platforms!\n\n"
                f"🚀 `/junior [location]`\n"
                f"↳ Searches **1–2 Years Experience & Associate** roles.\n\n"
                f"🔍 `/search <query> [location]`\n"
                f"↳ Custom search targeting 0–2 years openings (e.g. `/search AI Engineer Bengaluru`).\n\n"
                f"⭐ `/top`\n"
                f"↳ Lists your Top 5 highest matching qualified jobs.\n\n"
                f"📊 `/stats`\n"
                f"↳ View total discovered, qualified, and submitted job counts.\n\n"
                f"📄 `/resume <job_id>`\n"
                f"↳ Compiles & sends the tailored PDF resume for that job to this chat!\n\n"
                f"📝 `/letter <job_id>`\n"
                f"↳ Compiles & sends the tailored PDF cover letter!\n\n"
                f"✉️ `/outreach <job_id>`\n"
                f"↳ Generates ready-to-copy LinkedIn pitch & cold email for the Hiring Manager.\n\n"
                f"🧠 `/prep <job_id>`\n"
                f"↳ Predicts Top 5 technical interview questions & STAR answers.\n\n"
                f"⏰ `/schedule [time]`\n"
                f"↳ Check or configure daily morning auto-pilot time."
            )
            self.send_message(help_msg, target_chat_id=sender_id)
            return

        elif cmd == "/stats":
            conn = init_db(self.db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM jobs")
                total = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM applications WHERE status IN ('QUALIFIED', 'RESUME_READY', 'READY_TO_SUBMIT', 'SUBMITTED')")
                qualified = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM resume_versions")
                resumes = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM applications WHERE status = 'SUBMITTED'")
                submitted = c.fetchone()[0]

                stats_msg = (
                    f"📊 *Your Job Application Agent Stats:*\n\n"
                    f"🔍 *Total Discovered Jobs:* {total}\n"
                    f"🎯 *Qualified Matches (≥70%):* {qualified}\n"
                    f"📄 *Tailored Resumes Compiled:* {resumes}\n"
                    f"🚀 *Submitted Applications:* {submitted}\n\n"
                    f"_Send /top to view your highest ranked openings!_"
                )
                self.send_message(stats_msg, target_chat_id=sender_id)
            finally:
                conn.close()
            return

        elif cmd == "/top":
            conn = init_db(self.db_path)
            try:
                c = conn.cursor()
                c.execute(
                    """
                    SELECT j.id, j.company, j.title, j.location, j.source, j.url, jm.overall_score
                    FROM jobs j
                    JOIN job_matches jm ON j.id = jm.job_id
                    ORDER BY jm.overall_score DESC, j.id DESC
                    LIMIT 5
                    """
                )
                rows = c.fetchall()
                if not rows:
                    self.send_message("No evaluated jobs found yet. Run `/search Python Bengaluru` to discover fresh jobs!", target_chat_id=sender_id)
                    return

                msg_lines = ["⭐ *Top 5 Highest Matching Jobs:*\n"]
                for r in rows:
                    jid, comp, tit, loc, src, url, score = r
                    src_label = "Ashby" if "ashby" in src.lower() else "Python.org" if "python_org" in src.lower() else "HN" if "hacker" in src.lower() else src
                    clean_url = url if (url and url.startswith("http") and "hirect.in" not in url) else f"https://www.google.com/search?q={urllib.parse.quote(f'{tit} {comp} jobs {loc}')}"
                    msg_lines.append(
                        f"🔹 *[Job ID: #{jid}] {tit}* at *{comp}*\n"
                        f"   🎯 Match: `{score}%` | 🌐 Source: `{src_label}` | 📍 `{loc}`\n"
                        f"   🔗 [Open Job Application Link]({clean_url})\n"
                        f"   📄 *Resume:* `/resume {jid}` | 🧠 *Interview Prep:* `/prep {jid}`\n"
                        f"   👤 *Hiring Leads:* `/hiring {jid}` | ✉️ *Cold Email:* `/email {jid} hr@company.com`\n"
                    )
                self.send_message("\n".join(msg_lines), target_chat_id=sender_id)
            finally:
                conn.close()
            return

        elif cmd in ("/fresher", "/entry"):
            location_arg = " ".join(args) if args else "Bengaluru"
            query_arg = "Fresher Junior Python AI 0-1 year"
            self.send_message(f"🌱 *Searching Fresher & 0–1 Year Openings* in *'{location_arg}'* across 10+ platforms... This will take ~5s.", target_chat_id=sender_id)
            
            def _bg_fresher_search():
                from src.jobs.finder import JobFinder
                from src.agents.jd_agent import JDAgent
                from src.agents.match_agent import MatchAgent

                finder = JobFinder.create_multi_source_finder()
                discovered = finder.discover_jobs(query=query_arg, location=location_arg, time_range="3d")
                
                jd_agent = JDAgent()
                analyzed = jd_agent.analyze_all_pending_jobs(limit=100)

                match_agent = MatchAgent()
                evals = match_agent.evaluate_all_pending_jobs()

                qualified = [e for e in evals if e.overall_score >= 70]
                self.send_message(f"✅ *Fresher Search Complete!*\n\nDiscovered: *{len(discovered)}* | Qualified (≥70%): *{len(qualified)}*", target_chat_id=sender_id)
                self._handle_command("/top", sender_id, sender_name)

            threading.Thread(target=_bg_fresher_search, daemon=True).start()
            return

        elif cmd in ("/junior", "/associate"):
            location_arg = " ".join(args) if args else "Bengaluru"
            query_arg = "Associate Junior Python AI 1-2 years"
            self.send_message(f"🚀 *Searching 1–2 Years Experience Openings* in *'{location_arg}'* across 10+ platforms... This will take ~5s.", target_chat_id=sender_id)
            
            def _bg_jr_search():
                from src.jobs.finder import JobFinder
                from src.agents.jd_agent import JDAgent
                from src.agents.match_agent import MatchAgent

                finder = JobFinder.create_multi_source_finder()
                discovered = finder.discover_jobs(query=query_arg, location=location_arg, time_range="3d")
                
                jd_agent = JDAgent()
                analyzed = jd_agent.analyze_all_pending_jobs(limit=100)

                match_agent = MatchAgent()
                evals = match_agent.evaluate_all_pending_jobs()

                qualified = [e for e in evals if e.overall_score >= 70]
                self.send_message(f"✅ *1–2 Yrs Search Complete!*\n\nDiscovered: *{len(discovered)}* | Qualified (≥70%): *{len(qualified)}*", target_chat_id=sender_id)
                self._handle_command("/top", sender_id, sender_name)

        elif cmd in ("/ai", "/genai", "/llm"):
            location_arg = " ".join(args) if args else "Bengaluru"
            query_arg = "AI Engineer GenAI LLM LangChain RAG 0-2 years"
            self.send_message(f"🤖 *Searching AI & GenAI Roles* in *'{location_arg}'* across 28 platforms... This will take ~10s.", target_chat_id=sender_id)
            
            def _bg_ai_search():
                from src.jobs.finder import JobFinder
                from src.agents.jd_agent import JDAgent
                from src.agents.match_agent import MatchAgent

                finder = JobFinder.create_multi_source_finder()
                discovered = finder.discover_jobs(query=query_arg, location=location_arg, time_range="3d")
                
                jd_agent = JDAgent()
                analyzed = jd_agent.analyze_all_pending_jobs(limit=100)

                match_agent = MatchAgent()
                evals = match_agent.evaluate_all_pending_jobs()

                qualified = [e for e in evals if e.overall_score >= 70]
                self.send_message(f"✅ *AI & GenAI Search Complete!*\n\nDiscovered: *{len(discovered)}* | Qualified (≥70%): *{len(qualified)}*", target_chat_id=sender_id)
                self._handle_command("/top", sender_id, sender_name)

            threading.Thread(target=_bg_ai_search, daemon=True).start()
            return

        elif cmd in ("/data", "/analytics"):
            location_arg = " ".join(args) if args else "Bengaluru"
            query_arg = "Data Analyst Python SQL Analytics Pandas 0-2 years"
            self.send_message(f"📊 *Searching Data Analyst & Analytics Roles* in *'{location_arg}'* across 28 platforms...", target_chat_id=sender_id)
            
            def _bg_data_search():
                from src.jobs.finder import JobFinder
                from src.agents.jd_agent import JDAgent
                from src.agents.match_agent import MatchAgent

                finder = JobFinder.create_multi_source_finder()
                discovered = finder.discover_jobs(query=query_arg, location=location_arg, time_range="3d")
                
                jd_agent = JDAgent()
                analyzed = jd_agent.analyze_all_pending_jobs(limit=100)

                match_agent = MatchAgent()
                evals = match_agent.evaluate_all_pending_jobs()

                qualified = [e for e in evals if e.overall_score >= 70]
                self.send_message(f"✅ *Data Analytics Search Complete!*\n\nDiscovered: *{len(discovered)}* | Qualified (≥70%): *{len(qualified)}*", target_chat_id=sender_id)
                self._handle_command("/top", sender_id, sender_name)

            threading.Thread(target=_bg_data_search, daemon=True).start()
            return

        elif cmd in ("/backend", "/python", "/swe", "/software"):
            location_arg = " ".join(args) if args else "Bengaluru"
            query_arg = "Associate Software Engineer Python FastAPI Backend 0-2 years"
            self.send_message(f"💻 *Searching Software & Python Backend Roles* in *'{location_arg}'* across 28 platforms...", target_chat_id=sender_id)
            
            def _bg_swe_search():
                from src.jobs.finder import JobFinder
                from src.agents.jd_agent import JDAgent
                from src.agents.match_agent import MatchAgent

                finder = JobFinder.create_multi_source_finder()
                discovered = finder.discover_jobs(query=query_arg, location=location_arg, time_range="3d")
                
                jd_agent = JDAgent()
                analyzed = jd_agent.analyze_all_pending_jobs(limit=100)

                match_agent = MatchAgent()
                evals = match_agent.evaluate_all_pending_jobs()

                qualified = [e for e in evals if e.overall_score >= 70]
                self.send_message(f"✅ *Software / Backend Search Complete!*\n\nDiscovered: *{len(discovered)}* | Qualified (≥70%): *{len(qualified)}*", target_chat_id=sender_id)
                self._handle_command("/top", sender_id, sender_name)

            threading.Thread(target=_bg_swe_search, daemon=True).start()
            return

        elif cmd == "/search":
            query_arg = "AI Python Developer 0-2 years"
            location_arg = "Bengaluru"
            if args:
                full_arg = " ".join(args)
                if " in " in full_arg.lower():
                    parts = full_arg.lower().split(" in ")
                    query_arg = parts[0].strip()
                    location_arg = parts[1].strip()
                else:
                    query_arg = full_arg

            if not any(k in query_arg.lower() for k in ["year", "fresher", "junior", "associate", "intern"]):
                query_arg = f"{query_arg} 0-2 years"

            self.send_message(f"⏳ Searching 0–2 Yrs Openings for *'{query_arg}'* in *'{location_arg}'*...", target_chat_id=sender_id)
            
            def _bg_search():
                from src.jobs.finder import JobFinder
                from src.agents.jd_agent import JDAgent
                from src.agents.match_agent import MatchAgent

                finder = JobFinder.create_multi_source_finder()
                discovered = finder.discover_jobs(query=query_arg, location=location_arg, time_range="3d")
                
                jd_agent = JDAgent()
                analyzed = jd_agent.analyze_all_pending_jobs(limit=100)

                match_agent = MatchAgent()
                evals = match_agent.evaluate_all_pending_jobs()

                qualified = [e for e in evals if e.overall_score >= 70]

                res_msg = (
                    f"✅ *Search & Scoring Complete!*\n\n"
                    f"🔍 Discovered: *{len(discovered)}* new jobs\n"
                    f"🎯 Qualified Matches (≥70%): *{len(qualified)}*\n\n"
                    f"_Send /top to see your highest scoring matches!_"
                )
                self.send_message(res_msg, target_chat_id=sender_id)
                self._handle_command("/top", sender_id, sender_name)

            threading.Thread(target=_bg_search, daemon=True).start()
            return

        elif cmd == "/resume":
            if not args or not args[0].isdigit():
                self.send_message("Please provide a valid Job ID. Example: `/resume 1`", target_chat_id=sender_id)
                return

            job_id = int(args[0])
            self.send_message(f"⏳ Compiling tailored ATS PDF resume for Job ID {job_id}...", target_chat_id=sender_id)

            def _bg_resume():
                from src.agents.resume_agent import ResumeTailorAgent
                try:
                    agent = ResumeTailorAgent()
                    pdf_path = agent.tailor_resume_for_job(job_id)
                    if pdf_path and Path(pdf_path).exists():
                        caption = f"📄 Tailored Resume for Job #{job_id} (Elevora AI Engine)"
                        self.send_document(Path(pdf_path), caption=caption, target_chat_id=sender_id)
                    else:
                        self.send_message(f"❌ Could not compile resume for Job ID {job_id}.", target_chat_id=sender_id)
                except Exception as e:
                    self.send_message(f"❌ Error compiling resume: {e}", target_chat_id=sender_id)

            threading.Thread(target=_bg_resume, daemon=True).start()
            return

        elif cmd in ("/letter", "/cover"):
            if not args or not args[0].isdigit():
                self.send_message("Please provide a valid Job ID. Example: `/letter 1`", target_chat_id=sender_id)
                return

            job_id = int(args[0])
            self.send_message(f"⏳ Generating metric-tailored PDF cover letter for Job ID {job_id}...", target_chat_id=sender_id)

            def _bg_cover():
                from src.resume.cover_letter import generate_cover_letter_pdf
                from src.ai.schemas import ParsedJDRequirements
                conn = init_db(self.db_path)
                try:
                    c = conn.cursor()
                    c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (job_id,))
                    row = c.fetchone()
                    if not row:
                        self.send_message(f"❌ Job #{job_id} not found.", target_chat_id=sender_id)
                        return
                    comp, tit, req_json = row
                    reqs = ParsedJDRequirements(**json.loads(req_json)) if req_json else None
                    pm = ProfileManager()
                    prof = pm.load_profile()
                    pdf_path = generate_cover_letter_pdf(prof, comp, tit, reqs)
                    if pdf_path and Path(pdf_path).exists():
                        caption = f"📝 Tailored Cover Letter for {tit} at {comp}"
                        self.send_document(Path(pdf_path), caption=caption, target_chat_id=sender_id)
                    else:
                        self.send_message(f"❌ Could not compile cover letter.", target_chat_id=sender_id)
                except Exception as e:
                    self.send_message(f"❌ Error: {e}", target_chat_id=sender_id)
                finally:
                    conn.close()

            threading.Thread(target=_bg_cover, daemon=True).start()
            return

        elif cmd == "/outreach":
            if not args or not args[0].isdigit():
                self.send_message("Please provide a valid Job ID. Example: `/outreach 1`", target_chat_id=sender_id)
                return

            job_id = int(args[0])
            conn = init_db(self.db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (job_id,))
                row = c.fetchone()
                if not row:
                    self.send_message(f"❌ Job #{job_id} not found.", target_chat_id=sender_id)
                    return
                comp, tit, req_json = row
                from src.ai.schemas import ParsedJDRequirements
                from src.ai.outreach import generate_recruiter_outreach
                reqs = ParsedJDRequirements(**json.loads(req_json)) if req_json else None
                pm = ProfileManager()
                prof = pm.load_profile()
                data = generate_recruiter_outreach(prof, comp, tit, reqs)

                outreach_msg = (
                    f"✉️ *Recruiter Outreach for [{comp} - {tit}]*\n\n"
                    f"🔗 *1. LinkedIn Note (<300 chars):*\n"
                    f"`{data['linkedin_connection_note']}`\n\n"
                    f"📧 *2. Cold Email Subject:*\n"
                    f"`{data['cold_email_subject']}`\n\n"
                    f"📧 *Cold Email Body:*\n"
                    f"`{data['cold_email_body']}`\n\n"
                    f"👉 *To send this email with tailored resume attached:* `/email {job_id} recruiter@company.com`"
                )
                self.send_message(outreach_msg, target_chat_id=sender_id)
            finally:
                conn.close()
            return

        elif cmd == "/email":
            if len(args) < 2 or not args[0].isdigit() or "@" not in args[1]:
                self.send_message("Usage: `/email <job_id> <recipient_email>`\nExample: `/email 1 careers@company.com`", target_chat_id=sender_id)
                return

            job_id = int(args[0])
            to_email = args[1].strip()
            self.send_message(f"⏳ Compiling tailored PDF resume & cover letter for Job #{job_id}, then sending cold email to *{to_email}*...", target_chat_id=sender_id)

            def _bg_email():
                try:
                    conn = init_db(self.db_path)
                    c = conn.cursor()
                    c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (job_id,))
                    row = c.fetchone()
                    if not row:
                        self.send_message(f"❌ Job #{job_id} not found.", target_chat_id=sender_id)
                        conn.close()
                        return
                    comp, tit, req_json = row
                    conn.close()

                    from src.agents.resume_agent import ResumeTailorAgent
                    from src.resume.cover_letter import generate_cover_letter_pdf
                    from src.ai.schemas import ParsedJDRequirements
                    from src.ai.outreach import generate_recruiter_outreach
                    from src.outreach.email_dispatcher import email_dispatcher

                    reqs = ParsedJDRequirements(**json.loads(req_json)) if req_json else None
                    pm = ProfileManager()
                    prof = pm.load_profile()

                    # Tailor PDF Resume
                    tailor_agent = ResumeTailorAgent()
                    pdf_resume = tailor_agent.tailor_resume_for_job(job_id)

                    # Tailor PDF Cover Letter
                    pdf_cover = generate_cover_letter_pdf(prof, comp, tit, reqs)

                    # Draft Outreach
                    outreach_data = generate_recruiter_outreach(prof, comp, tit, reqs)

                    res = email_dispatcher.send_cold_email(
                        to_email=to_email,
                        subject=outreach_data["cold_email_subject"],
                        body_text=outreach_data["email_body"],
                        resume_pdf_path=Path(pdf_resume) if pdf_resume else None,
                        cover_letter_pdf_path=Path(pdf_cover) if pdf_cover else None,
                        job_id=job_id
                    )

                    if res.get("success"):
                        self.send_message(f"✅ *Cold Email Dispatched!*\n\n📬 *To:* `{to_email}`\n🏢 *Company:* {comp}\n💼 *Role:* {tit}\n📎 *Attachments:* Tailored PDF Resume & Cover Letter\nStatus logged in database.", target_chat_id=sender_id)
                    else:
                        self.send_message(f"❌ *Failed to send email:* {res.get('error')}", target_chat_id=sender_id)

                except Exception as e:
                    self.send_message(f"❌ Error sending email: {e}", target_chat_id=sender_id)

            threading.Thread(target=_bg_email, daemon=True).start()
            return

        elif cmd == "/prep":
            if not args or not args[0].isdigit():
                self.send_message("Please provide a valid Job ID. Example: `/prep 1`", target_chat_id=sender_id)
                return

            job_id = int(args[0])
            conn = init_db(self.db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (job_id,))
                row = c.fetchone()
                if not row:
                    self.send_message(f"❌ Job #{job_id} not found.", target_chat_id=sender_id)
                    return
                comp, tit, req_json = row
                from src.ai.schemas import ParsedJDRequirements
                from src.ai.interview_prep import generate_interview_prep
                reqs = ParsedJDRequirements(**json.loads(req_json)) if req_json else None
                pm = ProfileManager()
                prof = pm.load_profile()
                data = generate_interview_prep(prof, comp, tit, reqs)

                prep_lines = [f"🧠 *Interview Prep for {tit} at {comp}*\n"]
                prep_lines.append("🎯 *Top Predicted Technical Questions:*")
                for q in data.get("top_technical_questions", [])[:5]:
                    prep_lines.append(f"• *{q.get('question')}*\n  _Key Focus: {q.get('expected_focus')}_\n")

                prep_lines.append("🌟 *STAR Talking Point:*")
                for s in data.get("star_talking_points", [])[:1]:
                    prep_lines.append(f"• *Context:* {s.get('situation')}\n• *Action:* {s.get('action')}\n• *Result:* `{s.get('result')}`")

                self.send_message("\n".join(prep_lines), target_chat_id=sender_id)
            finally:
                conn.close()
            return

        elif cmd == "/sync":
            self.send_message("⏳ Synchronizing all qualified and applied jobs to your Google Sheet / Notion tracker...", target_chat_id=sender_id)
            def _bg_sync():
                from src.sync.tracker_sync import tracker_sync
                res = tracker_sync.sync_all_qualified()
                if res.get("success"):
                    self.send_message(f"✅ *Tracker Synchronized!*\n\n📊 *Synced Applications:* `{res.get('synced_count', 0)}`\nUpdated in your live Google Sheet / Notion tracker.", target_chat_id=sender_id)
                else:
                    self.send_message(f"❌ *Sync Notice:* {res.get('error')}", target_chat_id=sender_id)
            threading.Thread(target=_bg_sync, daemon=True).start()
            return

        elif cmd in ("/followups", "/nudge"):
            self.send_message("⏳ Scanning submitted applications for 5–7 day follow-up candidates...", target_chat_id=sender_id)
            def _bg_followup():
                from src.outreach.followup_agent import followup_manager
                followups = followup_manager.get_pending_followups()
                if not followups:
                    self.send_message("🎉 *All caught up!* No applications currently require a 7-day follow-up.", target_chat_id=sender_id)
                    return

                msg_lines = [f"⏰ *Found {len(followups)} Applications Ready for Follow-Up:*\n"]
                for idx, f in enumerate(followups[:3]):
                    msg_lines.append(
                        f"*{idx+1}. {f['company']} — {f['title']}*\n"
                        f"📅 Applied: ~{f['days_ago']} days ago | Fit: `{f['score']}%`\n"
                        f"💬 *LinkedIn Note (Tap to copy):*\n`{f['linkedin_followup']}`\n"
                        f"👉 *Send Cold Email:* `/email {f['job_id']} careers@{f['company'].lower().replace(' ', '')}.com`\n"
                    )
                self.send_message("\n".join(msg_lines), target_chat_id=sender_id)
            threading.Thread(target=_bg_followup, daemon=True).start()
            return

        elif cmd == "/schedule":
            from src.automation.scheduler import scheduler
            if args:
                new_time = args[0]
                scheduler.schedule_time = new_time
                scheduler.start()
                self.send_message(f"⏰ Daily Morning Auto-Pilot updated to *{new_time}* and activated!", target_chat_id=sender_id)
            else:
                st = scheduler.get_status()
                status_text = "Active 🟢" if st["enabled"] else "Paused ⏸️"
                self.send_message(f"⏰ *Auto-Pilot Status:* {status_text}\nTarget Daily Time: `{st['schedule_time']}`\nNext Scheduled Run: `{st['next_run'] or 'Not set'}`", target_chat_id=sender_id)
            return

        elif cmd in ("/hiring", "/hiring_managers", "/leads"):
            if not args or not args[0].isdigit():
                self.send_message("Usage: `/hiring <job_id>`\nExample: `/hiring 890`", target_chat_id=sender_id)
                return

            job_id = int(args[0])
            conn = init_db(self.db_path)
            try:
                c = conn.cursor()
                c.execute("SELECT company, title, location FROM jobs WHERE id = ?", (job_id,))
                row = c.fetchone()
                if not row:
                    self.send_message(f"❌ Job #{job_id} not found.", target_chat_id=sender_id)
                    return
                comp, tit, loc = row
                import urllib.parse
                q_em = urllib.parse.quote(f'"{comp}" ("Engineering Manager" OR "Head of Engineering")')
                q_cto = urllib.parse.quote(f'"{comp}" ("CTO" OR "Founder" OR "Co-Founder")')
                q_rec = urllib.parse.quote(f'"{comp}" ("Technical Recruiter" OR "Talent Acquisition")')

                msg = (
                    f"👤 *1-Click LinkedIn Hiring Manager Finder for [{job_id}] {tit} at {comp}:*\n\n"
                    f"🔹 [View Engineering Managers & Leads](https://www.linkedin.com/search/results/people/?keywords={q_em})\n"
                    f"🔹 [View CTOs & Founders](https://www.linkedin.com/search/results/people/?keywords={q_cto})\n"
                    f"🔹 [View Technical Recruiters](https://www.linkedin.com/search/results/people/?keywords={q_rec})\n\n"
                    f"💡 *Tip:* Send them a short connection note mentioning your experience and link: `https://resumeai.elevora.software`!"
                )
                self.send_message(msg, target_chat_id=sender_id)
            finally:
                conn.close()
            return

        elif cmd == "/theme":
            if args and args[0].lower() in ("tech", "corporate", "classic"):
                new_theme = "corporate" if "corp" in args[0].lower() or "class" in args[0].lower() else "tech"
                settings.RESUME_THEME = new_theme
                label = "🏛️ Classic Corporate (Serif)" if new_theme == "corporate" else "🚀 Modern Tech (Sans-Serif)"
                self.send_message(f"🎨 Resume ATS Theme updated to: *{label}*!", target_chat_id=sender_id)
            else:
                curr = getattr(settings, "RESUME_THEME", "tech")
                self.send_message(f"🎨 *Current Resume Theme:* `{curr}`\n\nOptions:\n• `/theme tech` (Modern Silicon Valley Style)\n• `/theme corporate` (Traditional Enterprise / Wall St Style)", target_chat_id=sender_id)
            return

        else:
            self.send_message("❓ Unknown command. Type `/help` to see all available commands!", target_chat_id=sender_id)

# Global singleton bot instance
telegram_bot = TelegramInteractiveBot()

