#!/usr/bin/env python3
"""
lint_cross.py — Cross-spec reference validation.

Checks that references between specs are consistent:
  - All REQ-IDs in DesignSpec, ArchitectureSpec, TaskPlan exist in GoalSpec
  - All NFR-IDs in ArchitectureSpec exist in GoalSpec
  - All US-IDs in DesignSpec user journeys exist in GoalSpec
  - All REQ-IDs in DesignSpec exist in GoalSpec
  - All AR-IDs (accessibility requirements) in DesignSpec exist in GoalSpec
  - All VDR-IDs (visual design requirements) in DesignSpec exist in GoalSpec
  - All DG-IDs (design guidelines) in DesignSpec exist in GoalSpec
  - All UJ-IDs (user journeys) in DesignSpec exist in GoalSpec
  - All CON-IDs (constraints) in ArchitectureSpec exist in GoalSpec
  - All NFR-IDs in ArchitectureSpec exist in GoalSpec
  - All REQ-IDs in ArchitectureSpec exist in GoalSpec
  - All fnRefs in TestSpec exist in ApiSpec
  - All REQ-IDs in TestSpec (via reqRefs) exist in GoalSpec
  - All NFR-IDs in SuccessCriteria exist in GoalSpec
  - All entity names in ApiSpec exist in DataSpec
  - All fnRefs in DataSpec exist in ApiSpec

Usage:
    python lint_cross.py --data data.json --api api.json --test test.json \
      --goal goalspec.json --design design.json --arch archspec.json \
      --plan taskplan.json
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import Optional
from shared import Issue, LayerResult, print_human, print_json_output

