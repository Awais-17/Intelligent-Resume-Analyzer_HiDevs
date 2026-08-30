"""Resume parsing module.

Extracts structured information (name, contact info, skills, experience,
education) from plain-text resumes. Supports .txt files natively and
.docx/.pdf files when the optional libraries are installed.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
YEARS_RE = re.compile(r"(\d+)\+?\s*(?:to\s*(\d+)\s*)?years?", re.IGNORECASE)
NON_WORD_RE = re.compile(r"[^A-Za-z\s.'-]")

MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)"
)
DATE_RANGE_RE = re.compile(
    rf"{MONTH}\.?\s*\d{{4}}\s*(?:-|–|to|until)\s*("
    rf"{MONTH}\.?\s*\d{{4}}|Present|Current|Now)",
    re.IGNORECASE,
)
YEAR_RANGE_RE = re.compile(r"\b(19|20)\d{2}\s*(?:-|–|to)\s*((19|20)\d{2}|Present)",
                           re.IGNORECASE)
DEGREE_RE = re.compile(
    r"\b(Ph\.?D\.?|Doctorate|Masters?|M\.S\.?|M\.Sc\.?|M\.A\.?|M\.B\.A\.?|"
    r"Bachelors?|B\.S\.?|B\.Sc\.?|B\.A\.?|B\.Tech|Associate)['s]*\b",
    re.IGNORECASE,
)

# Skills recognised anywhere in the resume text (case-insensitive).
KNOWN_SKILLS = {
    "python", "java", "javascript", "typescript", "c++", "c#", "c", "go",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "sql", "html",
    "css", "react", "angular", "vue", "node.js", "django", "flask",
    "fastapi", "spring", ".net", "aws", "azure", "gcp", "docker",
    "kubernetes", "terraform", "jenkins", "git", "github", "gitlab",
    "linux", "bash", "postgresql", "mysql", "mongodb", "redis",
    "elasticsearch", "kafka", "spark", "hadoop", "airflow", "pandas",
    "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "nlp",
    "machine learning", "deep learning", "data analysis", "data science",
    "tableau", "power bi", "excel", "agile", "scrum", "jira", "rest api",
    "graphql", "microservices", "ci/cd", "tdd", "oop", "selenium",
}

SECTION_HEADERS = {
    "skills": ("skill", "technical skill", "competencies", "technologies"),
    "experience": ("experience", "employment", "work history",
                   "professional experience", "career"),
    "education": ("education", "academic", "qualifications"),
}


@dataclass
class ParsedResume:
    """Structured data extracted from a single resume."""

    file_path: str = ""
    name: str = "Unknown Candidate"
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    years_of_experience: float = 0.0
    education: list[str] = field(default_factory=list)
    raw_text_length: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class ResumeParsingError(Exception):
    """Raised when a resume cannot be read or parsed."""


def read_resume_text(file_path: str | Path) -> str:
    """Read the raw text of a resume, supporting .txt/.docx/.pdf."""
    path = Path(file_path)
    if not path.is_file():
        raise ResumeParsingError(f"File not found: {path}")
    suffix = path.suffix.lower()
    try:
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="replace")
        if suffix in (".docx", ".doc"):
            return _read_docx(path)
        if suffix == ".pdf":
            return _read_pdf(path)
        # Fallback: attempt plain text for unknown extensions.
        return path.read_text(encoding="utf-8", errors="replace")
    except ResumeParsingError:
        raise
    except OSError as exc:
        raise ResumeParsingError(f"Could not read {path}: {exc}") from exc


def _read_docx(path: Path) -> str:
    try:
        import docx  # type: ignore
    except ImportError as exc:
        raise ResumeParsingError(
            f"{path}: .docx support requires the 'python-docx' package "
            "(pip install python-docx)"
        ) from exc
    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError as exc:
            raise ResumeParsingError(
                f"{path}: .pdf support requires 'pypdf' (pip install pypdf)"
            ) from exc
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_resume(file_path: str | Path, text: Optional[str] = None) -> ParsedResume:
    """Parse a resume file and return a :class:`ParsedResume`."""
    path = Path(file_path)
    if text is None:
        text = read_resume_text(path)
    if not text or not text.strip():
        raise ResumeParsingError(f"{path}: resume is empty or unreadable")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lower_lines = [line.lower() for line in lines]

    resume = ParsedResume(
        file_path=str(path),
        name=_extract_name(lines, lower_lines),
        email=_extract_email(text),
        phone=_extract_phone(text),
        skills=_extract_skills(text, lower_lines),
        years_of_experience=_extract_experience_years(text),
        education=_extract_education(text),
        raw_text_length=len(text),
    )
    return resume


def _extract_name(lines: list[str], lower_lines: list[str]) -> str:
    """Heuristic: the name is usually the first line before contact info."""
    for i, line in enumerate(lines[:6]):
        if EMAIL_RE.search(line) or re.search(r"\d{4,}", line):
            continue
        if any(h in lower_lines[i] for h in ("curriculum vitae", "resume", "profile of")):
            continue
        cleaned = NON_WORD_RE.sub("", line).strip()
        words = cleaned.split()
        if 2 <= len(words) <= 4 and all(w.isalpha() for w in words):
            return cleaned.title()
    return "Unknown Candidate"


def _extract_email(text: str) -> Optional[str]:
    match = EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


def _extract_phone(text: str) -> Optional[str]:
    match = PHONE_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    return match.group(0).strip() if 7 <= len(digits) <= 15 else None


def _extract_skills(text: str, lower_lines: list[str]) -> list[str]:
    """Extract skills, preferring an explicit skills section."""
    skills: list[str] = []
    section_text = _extract_section(lower_lines, "skills")
    source = section_text if section_text else text.lower()
    for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
        pattern = re.escape(skill)
        if re.search(rf"(?<![\w+./-]){pattern}(?![\w+./-])", source):
            skills.append(skill)
    return skills


def _extract_section(lower_lines: list[str], section: str) -> Optional[str]:
    """Return the body text of a `section` (until the next header), if any."""
    headers = SECTION_HEADERS[section]
    for idx, line in enumerate(lower_lines):
        stripped = line.strip(" :#-*")
        if stripped in headers or (len(stripped) < 40 and
                                   any(stripped == h or stripped.startswith(h)
                                       for h in headers)):
            body: list[str] = []
            for following in lower_lines[idx + 1:]:
                if _is_section_header(following):
                    break
                body.append(following)
            return "\n".join(body)
    return None


def _is_section_header(line: str) -> bool:
    stripped = line.strip(" :#-*")
    return any(
        stripped.startswith(h) and len(stripped) < 40
        for headers in SECTION_HEADERS.values()
        for h in headers
    )


def _extract_experience_years(text: str) -> float:
    """Estimate total experience from explicit statements, then date ranges."""
    statements = re.findall(
        r"(\d+)\+?\s*years?(?:\s*of)?(?:\s*\w+){0,3}\s*experience",
        text,
        re.IGNORECASE,
    )
    if statements:
        return min(float(max(int(s) for s in statements)), 50.0)

    ranges = DATE_RANGE_RE.findall(text) + YEAR_RANGE_RE.findall(text)
    if not ranges:
        return 0.0
    total_months = 0
    for match in DATE_RANGE_RE.finditer(text):
        total_months += _range_months(match.group(1))
    if total_months == 0:
        # Fall back to coarse year ranges (e.g. 2019 - 2023).
        years = [1900 + int(f"{a}{b}") for a, b in
                 re.findall(r"\b(19|20)(\d{2})\b", text)]
        if len(years) >= 2:
            span = max(years) - min(years)
            return float(min(max(span, 0), 50))
        return 0.0
    return round(total_months / 12.0, 1)


def _range_months(end_value: str) -> int:
    """Months implied by a single date-range end value (approximate)."""
    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    cleaned = end_value.strip().lower()
    if cleaned.startswith(("present", "current", "now")):
        return 12  # Assume at least the current year for an open-ended role.
    match = re.match(rf"({MONTH})\.?\s*(\d{{4}})", end_value, re.IGNORECASE)
    if not match:
        return 12
    month_num = months_map.get(match.group(1)[:3].lower(), 1)
    year = int(match.group(2))
    months_since_2000 = (year - 2000) * 12 + month_num
    now_months = (2026 - 2000) * 12 + 8  # Approximate "today".
    return max(min(now_months - months_since_2000, 12 * 50), 0) or 1


def _extract_education(text: str) -> list[str]:
    """Extract degree mentions, preferring an education section."""
    lower_lines = [line.lower() for line in text.splitlines()]
    section = _extract_section(lower_lines, "education")

    if section:
        # Focus on lines belonging to the education section.
        probe = next((w for w in section.split() if len(w) > 3), None)
        start = max(0, text.lower().find(probe) - 60) if probe else 0
        end = min(len(text), start + len(section) + 120)
        region_lines = text[start:end].splitlines()
    else:
        region_lines = text.splitlines()

    degrees: list[str] = []
    for line in region_lines:
        stripped = line.strip()
        if DEGREE_RE.search(stripped) and "education" not in stripped.lower():
            if stripped.lower() not in [d.lower() for d in degrees]:
                degrees.append(stripped)
    return degrees[:5]
