"""Report generation.

Produces a human-readable text report and a JSON record for each candidate,
then writes a ranked summary for all candidates evaluated in a run.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .matcher import MatchResult, JobRequirements
from .storage import save_json

SEVERITY_TO_MARK = {
    "Strong Match": "[ OK  ]",
    "Good Match": "[ OK  ]",
    "Partial Match": "[ WARN]",
    "Not a Match": "[FAIL ]",
}


def _hrule(char: str = "=", width: int = 72) -> str:
    return char * width


def render_report(result: MatchResult, requirements: JobRequirements) -> str:
    """Render a professional candidate analysis report as text."""
    mark = SEVERITY_TO_MARK.get(result.recommendation, "[    ]")
    lines: list[str] = []
    lines.append(_hrule())
    lines.append("CANDIDATE ANALYSIS REPORT")
    lines.append(_hrule())
    lines.append(f"Job title   : {requirements.title or '(unspecified)'}")
    lines.append(f"Candidate   : {result.candidate_name}")
    lines.append(f"Contact     : {result.email or 'N/A'}")
    lines.append(f"Experience  : {result.experience_years} years")
    lines.append(f"Match score : {result.score:.1f} / 100")
    lines.append(f"Verdict     : {mark} {result.recommendation}")
    lines.append(_hrule("-"))

    lines.append("Required skills")
    for skill in result.required_matched:
        lines.append(f"  + {skill}")
    for skill in result.required_missing:
        lines.append(f"  - {skill}  (missing)")
    if not requirements.required_skills:
        lines.append("  (no required skills specified)")

    lines.append("Preferred skills")
    for skill in result.preferred_matched:
        lines.append(f"  + {skill}")
    for skill in result.preferred_missing:
        lines.append(f"  - {skill}  (not found)")
    if not requirements.preferred_skills:
        lines.append("  (no preferred skills specified)")

    lines.append("Education")
    if result.education_detail:
        for edu in result.education_detail:
            lines.append(f"  * {edu}")
    else:
        lines.append("  (no education details found)")
    lines.append(_hrule("-"))

    lines.append("Recommendation")
    if result.recommendation == "Strong Match":
        lines.append("Proceed to interview. Candidate closely matches the role.")
    elif result.recommendation == "Good Match":
        lines.append("Consider interviewing. Minor gaps vs requirements.")
    elif result.recommendation == "Partial Match":
        lines.append("Review carefully; significant requirements unmet.")
    else:
        lines.append("Not recommended for this role.")

    gaps = list(result.required_missing)
    if result.min_experience_gap > 0:
        gaps.append(
            f"{result.min_experience_gap:.1f} more year(s) of experience"
        )
    if not result.education_matched:
        gaps.append(f"education level below {requirements.education_level}")
    if gaps:
        lines.append(f"\nKey gaps: {', '.join(gaps)}")
    return "\n".join(lines)


def result_to_json(result: MatchResult, source: str = "") -> dict:
    """Build an ordered dict record for long-term storage."""
    return OrderedDict([
        ("candidate", result.candidate_name),
        ("email", result.email),
        ("source_file", source),
        ("score", result.score),
        ("recommendation", result.recommendation),
        ("experience_years", result.experience_years),
        ("required_matched", result.required_matched),
        ("required_missing", result.required_missing),
        ("preferred_matched", result.preferred_matched),
        ("preferred_missing", result.preferred_missing),
        ("education_matched", result.education_matched),
        ("generated_at", datetime.now().isoformat(timespec="seconds")),
    ])


def save_candidate_report(
    result: MatchResult,
    requirements: JobRequirements,
    output_dir: str | Path,
    source_stem: str,
) -> dict:
    """Save a per-candidate report as .txt and .json; return the JSON dict."""
    text = render_report(result, requirements)
    base = (Path(output_dir) / (source_stem or result.candidate_name)
            .replace(" ", "_"))
    txt_path = Path(str(base) + ".report.txt")
    json_path = Path(str(base) + ".report.json")
    txt_path.write_text(text, encoding="utf-8")
    record = result_to_json(result, source=source_stem)
    save_json(record, json_path)
    return record


def render_summary(results: Iterable[MatchResult], limit: int = 10) -> str:
    """Render a leaderboard-style ranked summary."""
    ranked = sorted(results, key=lambda r: r.score, reverse=True)
    lines: list[str] = []
    lines.append(_hrule())
    lines.append("RANKED CANDIDATE SUMMARY")
    lines.append(_hrule())
    lines.append(f"{'Rank':<5}{'Score':>7}  {'Candidate':<28}{'Verdict'}")
    lines.append("-" * 72)
    for idx, result in enumerate(ranked[:limit], start=1):
        lines.append(f"{idx:<5}{result.score:>6.1f}  "
                     f"{result.candidate_name[:28]:<28}"
                     f"{SEVERITY_TO_MARK.get(result.recommendation, '')} "
                     f"{result.recommendation}")
    return "\n".join(lines)