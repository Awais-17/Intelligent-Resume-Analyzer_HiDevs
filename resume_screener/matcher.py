"""Candidate-to-job matching module.

Computes a match score (0-100) between a parsed resume and a set of job
requirements using a weighted scoring rubric.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

WEIGHTS = {
    "required_skills": 0.50,
    "preferred_skills": 0.15,
    "experience": 0.25,
    "education": 0.10,
}


@dataclass
class JobRequirements:
    """Requirements a candidate is being matched against."""

    title: str = ""
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    min_years_experience: float = 0.0
    education_level: str = ""
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "JobRequirements":
        return cls(
            title=data.get("title", ""),
            required_skills=list(data.get("required_skills", [])),
            preferred_skills=list(data.get("preferred_skills", [])),
            min_years_experience=float(data.get("min_years_experience", 0.0)),
            education_level=data.get("education_level", ""),
            description=data.get("description", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    """Result of matching one resume against job requirements."""

    candidate_name: str = ""
    email: str = ""
    score: float = 0.0
    required_matched: list[str] = field(default_factory=list)
    required_missing: list[str] = field(default_factory=list)
    preferred_matched: list[str] = field(default_factory=list)
    preferred_missing: list[str] = field(default_factory=list)
    experience_years: float = 0.0
    min_experience_gap: float = 0.0
    education_matched: bool = False
    education_detail: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


LEVELS = ("bachelor", "master", "mba", "phd", "doctorate", "associate")


def _normalise_skill(skill: str) -> str:
    return " ".join(skill.lower().strip().split())


def _score_experience(years: float, required: float) -> float:
    if required <= 0:
        return 1.0
    if years >= required:
        return 1.0
    return max(years / required, 0.0)


def _score_education(degree_text: str, education: list[str]) -> tuple[float, bool]:
    """Score education on a basic tier (Bachelor < Master < PhD)."""
    if not education:
        return (0.5, False)  # No education section found
    target = degree_text.lower().strip()
    if not target:
        return (1.0, False)
    if "ph" in target or "doctor" in target:
        need_level = 3
    elif "master" in target or "mba" in target:
        need_level = 2
    elif "bachelor" in target or "b." in target or "assoc" in target:
        need_level = 1
    else:
        need_level = 0

    combined = " ".join(education).lower()
    has_phd = ("ph" in combined and "d" in combined) or "doctorate" in combined
    has_masters = "master" in combined or "mba" in combined
    has_bachelors = "bachelor" in combined or "b.s" in combined or "b.tech" in combined

    if need_level == 0:
        return (1.0, True)
    actual_level = 3 if has_phd else (2 if has_masters else (1 if has_bachelors else 0))
    if actual_level >= need_level:
        return (1.0, True)
    return (float(actual_level) / need_level, False)


def _recommendation(score: float) -> str:
    if score >= 80:
        return "Strong Match"
    if score >= 60:
        return "Good Match"
    if score >= 40:
        return "Partial Match"
    return "Not a Match"


def compute_match(parsed, requirements: JobRequirements) -> MatchResult:
    """Compute the match between a parsed resume and job requirements."""
    resume_skills = set(_normalise_skill(s) for s in parsed.skills)
    required_norm = set(_normalise_skill(s) for s in requirements.required_skills)
    preferred_norm = set(_normalise_skill(s) for s in requirements.preferred_skills)

    required_matched = sorted(
        s for s in requirements.required_skills
        if _normalise_skill(s) in resume_skills
    )
    required_missing = sorted(
        s for s in requirements.required_skills
        if _normalise_skill(s) not in resume_skills
    )
    preferred_matched = sorted(
        s for s in requirements.preferred_skills
        if _normalise_skill(s) in resume_skills
    )
    preferred_missing = sorted(
        s for s in requirements.preferred_skills
        if _normalise_skill(s) not in resume_skills
    )

    required_score = (
        len(required_matched) / len(required_norm) if required_norm else 1.0
    )
    preferred_score = (
        len(preferred_matched) / len(preferred_norm) if preferred_norm else 1.0
    )
    exp_score = _score_experience(parsed.years_of_experience,
                                  requirements.min_years_experience)
    edu_score, edu_matched = _score_education(requirements.education_level,
                                              parsed.education)

    raw = (
        required_score * WEIGHTS["required_skills"]
        + preferred_score * WEIGHTS["preferred_skills"]
        + exp_score * WEIGHTS["experience"]
        + edu_score * WEIGHTS["education"]
    )
    score = round(raw * 100.0, 1)

    return MatchResult(
        candidate_name=parsed.name,
        email=parsed.email or "",
        score=score,
        required_matched=required_matched,
        required_missing=required_missing,
        preferred_matched=preferred_matched,
        preferred_missing=preferred_missing,
        experience_years=parsed.years_of_experience,
        min_experience_gap=max(requirements.min_years_experience
                               - parsed.years_of_experience, 0.0),
        education_matched=edu_matched,
        education_detail=list(parsed.education),
        recommendation=_recommendation(score),
    )