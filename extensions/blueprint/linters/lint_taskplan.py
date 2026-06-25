#!/usr/bin/env python3
"""
lint_taskplan.py — Linter for TaskPlan artifact.

Validates:
  - Every GoalSpec requirement appears in at least one epic's coverage list
  - Every epic covers at least one requirement
  - No epic implements a GoalSpec non-goal
  - Epics are listed in dependency order (blockers before dependents)
  - Milestones have demonstrable outcomes
  - Every epic belongs to exactly one milestone
  - All REQ-IDs referenced in TaskPlan exist in GoalSpec

Usage:
    python lint_taskplan.py plan.json --goal goalspec.json
"""

import sys
import json
from pathlib import Path
from typing import Optional
from shared import Issue, LayerResult, print_human, print_json_output

