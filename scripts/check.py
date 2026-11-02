"""Run local checks; --postgres uses an isolated schema; --live makes billable API calls."""

import argparse
import os

import pytest
from dotenv import load_dotenv

parser = argparse.ArgumentParser()
parser.add_argument("--postgres", action="store_true")
parser.add_argument("--live", action="store_true")
args = parser.parse_args()
load_dotenv(".env")
if args.postgres:
    os.environ["TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
if args.live:
    os.environ["RUN_LIVE_EVALS"] = "1"
raise SystemExit(pytest.main(["-q", "--tb=short"]))
