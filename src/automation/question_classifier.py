import re
from enum import Enum

class QuestionCategory(str, Enum):
    FULL_NAME = "full_name"
    EMAIL = "email"
    PHONE = "phone"
    LOCATION = "location"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    WORK_AUTHORIZATION = "work_authorization"
    NOTICE_PERIOD = "notice_period"
    SALARY_EXPECTATION = "salary_expectation"
    CUSTOM_OPEN_ENDED = "custom_open_ended"
    UNKNOWN = "unknown"

def classify_question(question_text: str) -> QuestionCategory:
    """Classifies application question string into standard QuestionCategory enum."""
    q = question_text.lower().strip()

    if re.search(r"\b(full name|first and last name|your name)\b", q):
        return QuestionCategory.FULL_NAME

    if re.search(r"\b(email|email address)\b", q):
        return QuestionCategory.EMAIL

    if re.search(r"\b(phone|phone number|mobile|telephone)\b", q):
        return QuestionCategory.PHONE

    if re.search(r"\b(location|city|address|where are you located)\b", q):
        return QuestionCategory.LOCATION

    if "linkedin" in q:
        return QuestionCategory.LINKEDIN

    if "github" in q:
        return QuestionCategory.GITHUB

    if re.search(r"\b(portfolio|website|personal site)\b", q):
        return QuestionCategory.PORTFOLIO

    if re.search(r"\b(authorized|sponsorship|legally authorized|work authorization|visa)\b", q):
        return QuestionCategory.WORK_AUTHORIZATION

    if re.search(r"\b(notice period|start date|how soon|availability|available to start)\b", q):
        return QuestionCategory.NOTICE_PERIOD

    if re.search(r"\b(salary|desired compensation|expected salary|pay rate)\b", q):
        return QuestionCategory.SALARY_EXPECTATION

    if len(q.split()) >= 4 or "?" in q:
        return QuestionCategory.CUSTOM_OPEN_ENDED

    return QuestionCategory.UNKNOWN
