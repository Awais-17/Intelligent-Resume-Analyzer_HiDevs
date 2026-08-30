# Resume Screening System

A Python application that automates resume screening: parses resumes,
matches candidates to job requirements, and generates detailed hiring reports.

## Features

- **Parsing** — extracts name, email, phone, skills, experience (years), and
  education from `.txt` resumes. `.docx` and `.pdf` are supported when
  `python-docx` / `pypdf` are installed (graceful error otherwise).
- **Matching** — weighted 0–100 match score:
  - Required skills: 50%
  - Preferred skills: 15%
  - Experience vs. minimum: 25%
  - Education level: 10%
- **Storage** — all data persisted as JSON (`results.json`, per-candidate
  `*.report.json`, `summary.json`).
- **Reports** — per-candidate text report with verdict and key gaps, plus a
  ranked candidate summary. Hiring recommendations: *Strong Match*
  (≥ 80), *Good Match* (≥ 60), *Partial Match* (≥ 40), *Not a Match* (< 40).
- **Error handling** — missing files, unreadable formats, empty resumes, and
  malformed JSON are reported gracefully without crashing the run.

## Requirements

- Python 3.9+ (standard library only)
- Optional: `pip install python-docx pypdf` for DOCX/PDF resumes

## Usage

```bash
# Screen a directory of resumes
python main.py data/resumes -r data/job_requirements.json

# Screen individual files
python main.py resume_a.txt resume_b.txt -r data/job_requirements.json

# Custom output directory
python main.py data/resumes -r data/job_requirements.json -o out
```

### Job requirements format (`data/job_requirements.json`)

```json
{
  "title": "Senior Python Backend Engineer",
  "required_skills": ["python", "rest api", "sql", "docker", "aws"],
  "preferred_skills": ["kubernetes", "django", "fastapi", "kafka", "machine learning"],
  "min_years_experience": 4.0,
  "education_level": "Bachelor",
  "description": "Design and maintain scalable Python services and REST APIs."
}
```

## Output

Files are written to `output/`:

- `output/<name>.report.txt` — human-readable candidate analysis
- `output/<name>.report.json` — machine-readable record for one candidate
- `output/results.json` — all records from the run (fresh each run)
- `output/summary.txt` — ranked leaderboard
- `output/summary.json` — ranked results as JSON

Example per-candidate report:

```
========================================================================
CANDIDATE ANALYSIS REPORT
========================================================================
Job title   : Senior Python Backend Engineer
Candidate   : Alice Johnson
Contact     : alice.johnson@example.com
Experience  : 7.0 years
Match score : 100.0 / 100
Verdict     : [ OK  ] Strong Match
------------------------------------------------------------------------
Required skills
  + aws, docker, python, rest api, sql
Preferred skills
  + django, fastapi, kafka, kubernetes, machine learning
Education
  * B.S. Computer Science - State University (2012 - 2016)
------------------------------------------------------------------------
Recommendation
Proceed to interview. Candidate closely matches the role.
```

## Project layout

```
main.py                     CLI entry point
resume_screener/
  parser.py                 Resume parsing (text -> structured data)
  matcher.py                Weighted matching algorithm + recommendations
  storage.py                JSON save/load helpers
  report.py                 Report + summary rendering
  cli.py                    Screening pipeline and argument parsing
data/
  job_requirements.json     Sample job posting
  resumes/                  Sample resumes (.txt)
tests/
  test_all.py               Unit tests
```

## Running tests

```bash
python -m unittest discover -s tests -v
```

## Design notes

- Skill detection uses a curated skill dictionary matched against an explicit
  skills section or the full text, using word-boundary-aware regex so
  `python` in `pythonic` is not a false positive.
- Experience is derived first from explicit "N years of experience"
  statements, then from date ranges (e.g. `Mar 2021 - Present`).
- The matcher normalises skill names (`c++` vs `c# `, case, whitespace) before
  scoring, and caps scores at 0–100.
- Invalid resumes are skipped with a `[SKIP]` message; the run continues.