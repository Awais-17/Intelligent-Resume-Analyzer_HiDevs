"""Entry point for the Resume Screening System.

Usage:
    python main.py data/resumes data/job_requirements.json
"""

import sys

from resume_screener.cli import main

if __name__ == "__main__":
    sys.exit(main())