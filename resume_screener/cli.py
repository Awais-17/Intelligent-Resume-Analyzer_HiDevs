"""Command-line interface and screening pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .matcher import JobRequirements, MatchResult, compute_match
from .parser import ParsedResume, ResumeParsingError, parse_resume
from .report import save_candidate_report, render_summary, result_to_json
from .storage import (StorageError, ensure_directory, load_json, save_json)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _load_requirements(path: str | Path) -> JobRequirements:
    try:
        data = load_json(path)
    except StorageError as exc:
        print(f"[ERROR] Could not load job requirements: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        print("[ERROR] Job requirements file must contain a JSON object.",
              file=sys.stderr)
        sys.exit(1)
    return JobRequirements.from_dict(data)


def _collect_resumes(paths: Sequence[Path]) -> list[Path]:
    """Expand files and directories to a flat list of candidate files."""
    collected: list[Path] = []
    for entry in paths:
        if entry.is_dir():
            collected.extend(sorted(
                p for p in entry.rglob("*")
                if p.suffix.lower() in {".txt", ".docx", ".doc", ".pdf"}
            ))
        elif entry.is_file():
            collected.append(entry)
        else:
            print(f"[SKIP] Not found: {entry}", file=sys.stderr)
    return collected


def screen_resume(
    resume_path: Path,
    requirements: JobRequirements,
    output_dir: Path,
) -> MatchResult | None:
    """Parse, match, report, and write a per-candidate record."""
    try:
        parsed: ParsedResume = parse_resume(resume_path)
    except ResumeParsingError as exc:
        print(f"[SKIP] {resume_path}: {exc}", file=sys.stderr)
        return None

    result = compute_match(parsed, requirements)
    try:
        save_candidate_report(
            result, requirements, output_dir,
            source_stem=Path(resume_path).stem,
        )
    except (OSError, StorageError) as exc:
        print(f"[WARN] Could not write report for {resume_path}: {exc}",
              file=sys.stderr)
    return result


def run(args: argparse.Namespace) -> int:
    requirements = _load_requirements(args.requirements)
    resumes = _collect_resumes([Path(p) for p in args.resumes])
    if not resumes:
        print("[ERROR] No resume files found to screen.", file=sys.stderr)
        return 1

    output_dir = ensure_directory(args.output_dir)
    results_path = output_dir / "results.json"
    results_path = output_dir / "results.json"

    print(f"[INFO] Screening {len(resumes)} resume(s) against "
          f"'{requirements.title or 'untitled role'}'")
    print(f"[INFO] Output: {output_dir}\n")

    results: list[MatchResult] = []
    records: list[dict] = []
    successes = 0
    for resume in resumes:
        print(f"  -> {resume}")
        result = screen_resume(resume, requirements, output_dir)
        if result is not None:
            results.append(result)
            record = result_to_json(result, source=resume.name)
            records.append(dict(record))
            successes += 1

    # results.json mirrors *this* run (fresh each time, no duplicates).
    if records:
        results_path.parent.mkdir(parents=True, exist_ok=True)
        save_json(records, results_path)
        print(f"[INFO] Fresh run results saved to {results_path}")

    print(f"\n[DONE] Processed {successes}/{len(resumes)} resume(s) "
          f"successfully.")
    if results:
        summary = render_summary(results)
        print("\n" + summary)
        summary_path = output_dir / "summary.txt"
        save_json([r.to_dict() for r in results], output_dir / "summary.json")
        summary_path.write_text(summary, encoding="utf-8")
        print(f"\n[INFO] Summary saved to {summary_path}")
        print(f"[INFO] Machine-readable results in {output_dir / 'summary.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-screener",
        description="Automated resume screening and candidate matching.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "resumes", nargs="+",
        help="One or more resume files or directories to screen.",
    )
    parser.add_argument(
        "-r", "--requirements", default="data/job_requirements.json",
        help="JSON file with job requirements.",
    )
    parser.add_argument(
        "-o", "--output-dir", default=str(OUTPUT_DIR),
        help="Directory for reports and results.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\n[ABORT] Interrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())