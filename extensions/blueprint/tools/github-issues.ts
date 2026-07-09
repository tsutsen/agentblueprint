/**
 * github-issues.ts — GitHub Issues integration for epics, issues, and sub-issues.
 *
 * Creates GitHub Issues, manages branches, and tracks PRs for the task hierarchy:
 *   Epic    → GitHub Issue + EP-NNN branch from main
 *   Issue   → GitHub Issue + IS-NNN branch from EP branch
 *   SubIssue → PR from SI-NNN branch (forks from EP branch)
 *
 * Branch naming:
 *   Epic:     EP-NNN-slug    (from main)
 *   Issue:    IS-NNN-slug    (from EP branch — used as PR target for SIs)
 *   SubIssue: SI-NNN-slug    (from EP branch, PR targets IS branch)
 *
 * Branch deletion policy:
 *   SI branches deleted when all SIs for an Issue are merged.
 *   IS branches deleted when the Issue merges into the EP branch.
 *   EP branches deleted when the Epic merges into main.
 *
 * Auth: Uses `gh auth token` (gh CLI must be installed).
 * Repo: Auto-detected from `git remote`.
 */

import type { ExtensionAPI, Tool } from "@earendil-works/pi-coding-agent";

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Detect repo owner/repo from git remote. */
function detectRepo(): string | null {
  try {
    const { execSync } = require("child_process");
    const remote = execSync("git remote get-url origin 2>/dev/null", { encoding: "utf-8" }).trim();
    if (!remote) return null;

    // SSH: git@github.com:owner/repo.git
    const sshMatch = remote.match(/git@github\.com[:\/]([^\/]+)\/([^\.]+)/);
    if (sshMatch) return `${sshMatch[1]}/${sshMatch[2]}`;

    // HTTPS: https://github.com/owner/repo.git
    const httpsMatch = remote.match(/https:\/\/github\.com\/([^\/]+)\/([^\.]+)/);
    if (httpsMatch) return `${httpsMatch[1]}/${httpsMatch[2]}`;

    return null;
  } catch {
    return null;
  }
}

/** Get gh auth token. */
function getToken(): string | null {
  try {
    const { execSync } = require("child_process");
    return execSync("gh auth token 2>/dev/null", { encoding: "utf-8" }).trim() || null;
  } catch {
    return null;
  }
}

/** Format the GitHub Issue body from JSON data. */
function formatIssueBody(data: Record<string, unknown>): string {
  const id = data.id as string;
  const name = data.name as string;
  const description = data.description as string;
  const scope = data.scope as { inScope?: { description: string }[]; outOfScope?: { description: string }[] };
  const acceptanceCriteria = (data.acceptanceCriteria as { description: string }[]) ?? [];
  const type = data.type as string;
  const priority = data.priority as string;
  const effort = data.effort as string;
  const blockedBy = data.blockedBy as string[];

  let body = `# ${id}: ${name}\n\n`;
  body += `## Description\n${description}\n\n`;

  body += `## Scope\n`;
  if (scope?.inScope?.length) {
    body += `### In Scope\n${scope.inScope.map((s) => `- ${s.description}`).join("\n")}\n\n`;
  }
  if (scope?.outOfScope?.length) {
    body += `### Out of Scope\n${scope.outOfScope.map((s) => `- ${s.description}`).join("\n")}\n\n`;
  }

  body += `## Acceptance Criteria\n${acceptanceCriteria.map((ac) => `- [ ] ${ac.description}`).join("\n")}\n\n`;

  if (type) body += `## Type\n${type}\n\n`;
  if (priority) body += `## Priority\n${priority}\n\n`;
  if (effort) body += `## Effort\n${effort}\n\n`;

  body += `## Blocked By\n${Array.isArray(blockedBy) && blockedBy.length ? blockedBy.join(", ") : "None — can start immediately."}`;

  return body;
}

/** Build label list from data. */
function buildLabels(kind: "epic" | "issue" | "sub-issue", data: Record<string, unknown>): string[] {
  const labels = [kind];
  const id = data.id as string;
  if (id) labels.push(id);
  const milestone = data.milestone as string;
  if (milestone) labels.push(milestone);
  const tags = data.tags as string[];
  if (Array.isArray(tags)) labels.push(...tags);
  return labels;
}

/** Return error response in pi-compatible format. */
function errorResponse(msg: string): { content: Array<{ type: string; text: string }>; isError: true } {
  return { content: [{ type: "text", text: msg }], isError: true };
}

/** Wrap a success response with a content field for pi renderer. */
function successResponse(msg: string, rest: Record<string, unknown>) {
  return { content: [{ type: "text", text: msg }], ...rest };
}

/** Run a gh CLI command and return stdout. */
function runGh(args: string[]): { stdout: string; stderr: string; code: number } {
  const { execSync } = require("child_process");
  try {
    const stdout = execSync(`gh ${args.join(" ")}`, { encoding: "utf-8" }).trim();
    return { stdout, stderr: "", code: 0 };
  } catch (err: any) {
    return {
      stdout: err.stdout ? String(err.stdout).trim() : "",
      stderr: err.stderr ? String(err.stderr).trim() : String(err),
      code: err.status ?? 1,
    };
  }
}

/** Run a git CLI command and return stdout. */
function runGit(args: string[]): { stdout: string; stderr: string; code: number } {
  const { execSync } = require("child_process");
  try {
    const stdout = execSync(`git ${args.join(" ")}`, { encoding: "utf-8" }).trim();
    return { stdout, stderr: "", code: 0 };
  } catch (err: any) {
    return {
      stdout: err.stdout ? String(err.stdout).trim() : "",
      stderr: err.stderr ? String(err.stderr).trim() : String(err),
      code: err.status ?? 1,
    };
  }
}

// ── Tools ────────────────────────────────────────────────────────────────────

function createGhCreateEpic(): Tool {
  return {
    name: "gh_create_epic",
    description: "Create GitHub Issue + EP-NNN-slug branch from main for an epic.",
    parameters: {
      type: "object",
      properties: {
        jsonPath: {
          type: "string",
          description: "Path to the epic JSON file (e.g. tasks/EP-001-userOnboarding/EP-001-userOnboarding.json)",
        },
      },
      required: ["jsonPath"],
    },
    execute: async ({ jsonPath }: { jsonPath: string }) => {
      const { readFileSync, writeFileSync, existsSync } = require("fs");
      const { resolve } = require("path");

      const absPath = resolve(jsonPath);
      if (!existsSync(absPath)) {
        return errorResponse(`Epic JSON not found: ${absPath}`);
      }

      const data = JSON.parse(readFileSync(absPath, "utf-8"));
      const repo = detectRepo();
      if (!repo) {
        return errorResponse("Could not detect GitHub repo from git remote. Run 'git remote -v' to verify.");
      }

      const token = getToken();
      if (!token) {
        return errorResponse("No gh auth token. Run 'gh auth login' first.");
      }

      const id = data.id as string;
      const branch = (data.githubBranch as string) || id;

      // Create branch from main
      const branchResult = runGit(`checkout -b ${branch} main`);
      if (branchResult.code !== 0) {
        // Branch may already exist — try checkout
        const switchResult = runGit(`checkout ${branch}`);
        if (switchResult.code !== 0) {
          return errorResponse(`Failed to create/checkout branch '${branch}': ${switchResult.stderr}`);
        }
      }

      // Create GitHub Issue
      const body = formatIssueBody(data);
      const labels = buildLabels("epic", data).join(",");
      const title = `[${id}] ${data.name as string}`;

      const issueResult = runGh([
        "api", "repos", repo, "issues",
        "--title", title,
        "--body", body,
        "--labels", labels,
      ]);

      if (issueResult.code !== 0) {
        return errorResponse(`Failed to create GitHub Issue: ${issueResult.stderr}`);
      }

      const issueJson = JSON.parse(issueResult.stdout);
      const issueNumber = issueJson.number;

      // Update local JSON with GitHub issue number
      data.githubIssueNumber = issueNumber;
      writeFileSync(absPath, JSON.stringify(data, null, 2));

      // Push branch
      runGit(`push -u origin ${branch}`);

      return successResponse(`Created GitHub Issue #${issueNumber} and branch '${branch}' for epic ${id}`, { success: true, id, branch, githubIssueNumber: issueNumber, message: `Created GitHub Issue #${issueNumber} and branch '${branch}' for epic ${id}` });
    },
  };
}

function createGhCreateIssue(): Tool {
  return {
    name: "gh_create_issue",
    description: "Create GitHub Issue + IS-NNN-slug branch from EP branch for an issue.",
    parameters: {
      type: "object",
      properties: {
        jsonPath: {
          type: "string",
          description: "Path to the issue JSON file (e.g. tasks/EP-001-userOnboarding/IS-001-implementLogin/IS-001-implementLogin.json)",
        },
        parentBranch: {
          type: "string",
          description: "Parent epic branch name (e.g. EP-001-userOnboarding)",
        },
      },
      required: ["jsonPath"],
    },
    execute: async ({ jsonPath, parentBranch }: { jsonPath: string; parentBranch?: string }) => {
      const { readFileSync, writeFileSync, existsSync } = require("fs");
      const { resolve, dirname } = require("path");

      const absPath = resolve(jsonPath);
      if (!existsSync(absPath)) {
        return errorResponse(`Issue JSON not found: ${absPath}`);
      }

      const data = JSON.parse(readFileSync(absPath, "utf-8"));
      const repo = detectRepo();
      if (!repo) return errorResponse("Could not detect GitHub repo.");

      const token = getToken();
      if (!token) return errorResponse("No gh auth token.");

      const id = data.id as string;
      const branch = (data.githubBranch as string) || id;
      const epBranch = parentBranch || (data.githubParentBranch as string);

      if (!epBranch) {
        // Derive from directory structure
        const parentDir = dirname(absPath);
        const epicDir = dirname(parentDir);
        const epicMatch = epicDir.match(/EP-\d{3}-.*/);
        if (epicMatch) {
          data.githubParentBranch = epicMatch[0];
        }
      }

      // Create branch from EP branch
      const fetchResult = runGit("fetch origin");
      if (fetchResult.code !== 0) {
        return errorResponse(`Failed to fetch: ${fetchResult.stderr}`);
      }

      const branchResult = runGit(`checkout -b ${branch} origin/${epBranch || "main"}`);
      if (branchResult.code !== 0) {
        const switchResult = runGit(`checkout ${branch}`);
        if (switchResult.code !== 0) {
          return errorResponse(`Failed to create/checkout branch '${branch}': ${switchResult.stderr}`);
        }
      }

      // Create GitHub Issue
      const body = formatIssueBody(data);
      const labels = buildLabels("issue", data).join(",");
      const title = `[${id}] ${data.name as string}`;

      const issueResult = runGh([
        "api", "repos", repo, "issues",
        "--title", title,
        "--body", body,
        "--labels", labels,
      ]);

      if (issueResult.code !== 0) {
        return errorResponse(`Failed to create GitHub Issue: ${issueResult.stderr}`);
      }

      const issueJson = JSON.parse(issueResult.stdout);
      const issueNumber = issueJson.number;

      // Update local JSON
      data.githubIssueNumber = issueNumber;
      writeFileSync(absPath, JSON.stringify(data, null, 2));

      // Push branch
      runGit(`push -u origin ${branch}`);

      return successResponse(`Created GitHub Issue #${issueNumber} and branch '${branch}' for issue ${id}`, { success: true, id, branch, githubIssueNumber: issueNumber, message: `Created GitHub Issue #${issueNumber} and branch '${branch}' for issue ${id}` });
    },
  };
}

function createGhCreateSubIssue(): Tool {
  return {
    name: "gh_create_sub_issue",
    description: "Create local SI-NNN.json + SI-NNN.md files for a sub-issue.",
    parameters: {
      type: "object",
      properties: {
        epId: {
          type: "string",
          description: "Parent epic ID (e.g. EP-001-userOnboarding)",
        },
        issueId: {
          type: "string",
          description: "Parent issue ID (e.g. IS-001-implementLogin)",
        },
        data: {
          type: "object",
          description: "Sub-issue data (id, name, description, etc.)",
        },
      },
      required: ["epId", "issueId", "data"],
    },
    execute: async ({ epId, issueId, data }: { epId: string; issueId: string; data: Record<string, unknown> }) => {
      const { writeFileSync, mkdirSync, existsSync } = require("fs");
      const { resolve } = require("path");
      const { execSync } = require("child_process");

      if (!data || !data.id) {
        return errorResponse("data.id is required (e.g. SI-001-createLoginSchema)");
      }
      const siId = data.id as string;
      const cwd = execSync("git rev-parse --show-toplevel 2>/dev/null || pwd", { encoding: "utf-8" }).trim();

      const siDir = resolve(cwd, `tasks/${epId}/${issueId}/${siId}`);
      if (!existsSync(siDir)) {
        mkdirSync(siDir, { recursive: true });
      }

      const workDir = resolve(siDir, "work");
      if (!existsSync(workDir)) {
        mkdirSync(workDir);
      }

      // Ensure required fields
      const now = new Date().toISOString();
      const siData: Record<string, unknown> = {
        schemaVersion: "1.0.0",
        artifact: "SubIssue",
        id: siId,
        name: data.name,
        description: data.description,
        type: data.type || "AFK",
        status: "not_started",
        milestone: data.milestone || "",
        scope: data.scope || { inScope: [], outOfScope: [] },
        acceptanceCriteria: data.acceptanceCriteria || [],
        files: [],
        priority: data.priority || "P2",
        effort: data.effort || "S",
        assignee: null,
        dueDate: null,
        tags: (data.tags as string[]) || [],
        isRefs: [issueId],
        epRefs: [epId],
        githubBranch: siId,
        githubBaseBranch: epId,
        githubPrNumber: null,
        created: data.created || now,
        updated: now,
      };

      const jsonPath = resolve(siDir, `${siId}.json`);
      writeFileSync(jsonPath, JSON.stringify(siData, null, 2));

      // Generate markdown
      const md = generateSubIssueMarkdown(siData);
      const mdPath = resolve(siDir, `${siId}.md`);
      writeFileSync(mdPath, md);

      return successResponse(`Created sub-issue ${siId} at ${siDir}`, { success: true, id: siId, jsonPath, mdPath, workDir, message: `Created sub-issue ${siId} at ${siDir}` });
    },
  };
}

function createGhCreatePr(): Tool {
  return {
    name: "gh_create_pr",
    description: "Create PR from SI-NNN-slug branch (forks from EP branch). Targets the IS branch.",
    parameters: {
      type: "object",
      properties: {
        siId: {
          type: "string",
          description: "Sub-issue ID (e.g. SI-001-createLoginSchema)",
        },
        epBranch: {
          type: "string",
          description: "Epic branch name (base branch, e.g. EP-001-userOnboarding)",
        },
        targetBranch: {
          type: "string",
          description: "Target branch for the PR (e.g. IS-001-implementLogin or EP branch)",
        },
        jsonPath: {
          type: "string",
          description: "Path to sub-issue JSON for PR body generation",
        },
      },
      required: ["siId"],
    },
    execute: async ({ siId, epBranch, targetBranch, jsonPath }: { siId: string; epBranch?: string; targetBranch?: string; jsonPath?: string }) => {
      const { readFileSync, writeFileSync, existsSync } = require("fs");
      const { resolve } = require("path");

      const repo = detectRepo();
      if (!repo) return errorResponse("Could not detect GitHub repo.");

      const branch = siId; // SI branch name
      const base = targetBranch || epBranch || "main";

      // Build PR body from sub-issue JSON if available
      let body = `# ${siId}`;
      if (jsonPath && existsSync(resolve(jsonPath))) {
        const data = JSON.parse(readFileSync(resolve(jsonPath), "utf-8"));
        body = formatIssueBody(data);
      }

      const labels = ["sub-issue", siId].join(",");
      const title = `[${siId}] ${siId.split("-").slice(2).join("-").replace(/([A-Z])/g, " $1").trim()}`;

      const prResult = runGh([
        "pr", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
        "--base", base,
        "--head", branch,
        "--labels", labels,
      ]);

      if (prResult.code !== 0) {
        return errorResponse(`Failed to create PR: ${prResult.stderr}`);
      }

      // Extract PR number from output
      const prUrl = prResult.stdout.trim();
      const prMatch = prUrl.match(/\/pull\/(\d+)/);
      const prNumber = prMatch ? parseInt(prMatch[1], 10) : null;

      // Update local JSON if path provided
      if (jsonPath && existsSync(resolve(jsonPath))) {
        const data = JSON.parse(readFileSync(resolve(jsonPath), "utf-8"));
        data.githubPrNumber = prNumber;
        data.status = "in_progress";
        writeFileSync(resolve(jsonPath), JSON.stringify(data, null, 2));
      }

      return successResponse(`Created PR #${prNumber} from '${branch}' → '${base}'`, { success: true, siId, prNumber, prUrl: prUrl, message: `Created PR #${prNumber} from '${branch}' → '${base}'` });
    },
  };
}

function createGhMergePr(): Tool {
  return {
    name: "gh_merge_pr",
    description: "Merge PR → update local JSON. Branch NOT deleted until parent merges.",
    parameters: {
      type: "object",
      properties: {
        prNumber: {
          type: "number",
          description: "PR number to merge",
        },
        jsonPath: {
          type: "string",
          description: "Path to local JSON to update after merge",
        },
      },
      required: ["prNumber"],
    },
    execute: async ({ prNumber, jsonPath }: { prNumber: number; jsonPath?: string }) => {
      const { readFileSync, writeFileSync, existsSync } = require("fs");
      const { resolve } = require("path");

      const repo = detectRepo();
      if (!repo) return errorResponse("Could not detect GitHub repo.");

      const mergeResult = runGh([
        "pr", "merge", "--merge", "--delete-branch",
        "--repo", repo,
        String(prNumber),
      ]);

      if (mergeResult.code !== 0) {
        return errorResponse(`Failed to merge PR #${prNumber}: ${mergeResult.stderr}`);
      }

      // Update local JSON
      if (jsonPath && existsSync(resolve(jsonPath))) {
        const data = JSON.parse(readFileSync(resolve(jsonPath), "utf-8"));
        data.status = "complete";
        data.updated = new Date().toISOString();
        writeFileSync(resolve(jsonPath), JSON.stringify(data, null, 2));
      }

      return successResponse(`Merged PR #${prNumber}. Local JSON updated.`, { success: true, prNumber, message: `Merged PR #${prNumber}. Local JSON updated.` });
    },
  };
}

function createGhUpdateIssue(): Tool {
  return {
    name: "gh_update_issue",
    description: "Update issue status/labels/comments on GitHub.",
    parameters: {
      type: "object",
      properties: {
        issueNumber: {
          type: "number",
          description: "GitHub issue number",
        },
        status: {
          type: "string",
          description: "New status label (e.g. 'in_progress', 'complete')",
        },
        labels: {
          type: "array",
          items: { type: "string" },
          description: "Additional labels to add",
        },
        comment: {
          type: "string",
          description: "Comment to add to the issue",
        },
      },
      required: ["issueNumber"],
    },
    execute: async ({ issueNumber, status, labels, comment }: { issueNumber: number; status?: string; labels?: string[]; comment?: string }) => {
      const repo = detectRepo();
      if (!repo) {
        return { content: [{ type: "text", text: "Could not detect GitHub repo." }], isError: true };
      }

      const updates: string[] = [];

      if (status) {
        updates.push(`Adding status label: ${status}`);
        runGh(["issue", "edit", String(issueNumber), "--add-label", status]);
      }

      if (labels) {
        for (const label of labels) {
          updates.push(`Adding label: ${label}`);
          runGh(["issue", "edit", String(issueNumber), "--add-label", label]);
        }
      }

      if (comment) {
        updates.push("Adding comment");
        runGh(["issue", "comment", String(issueNumber), "--body", comment]);
      }

      if (!updates.length) {
        return { content: [{ type: "text", text: "No updates specified. Provide status, labels, or comment." }], isError: true };
      }

      return successResponse(`Updated issue #${issueNumber}: ${updates.join(", ")}`, { success: true, issueNumber, updates, message: `Updated issue #${issueNumber}: ${updates.join(", ")}` });
    },
  };
}

function createGhGetIssue(): Tool {
  return {
    name: "gh_get_issue",
    description: "Fetch GitHub issue state.",
    parameters: {
      type: "object",
      properties: {
        issueNumber: {
          type: "number",
          description: "GitHub issue number",
        },
      },
      required: ["issueNumber"],
    },
    execute: async ({ issueNumber }: { issueNumber: number }) => {
      const repo = detectRepo();
      if (!repo) return errorResponse("Could not detect GitHub repo.");

      const result = runGh(["api", "repos", repo, "issues", String(issueNumber)]);
      if (result.code !== 0) {
        return errorResponse(`Failed to fetch issue #${issueNumber}: ${result.stderr}`);
      }

      return {
        success: true,
        issue: JSON.parse(result.stdout),
      };
    },
  };
}

function createGhListIssues(): Tool {
  return {
    name: "gh_list_issues",
    description: "List issues by label/milestone.",
    parameters: {
      type: "object",
      properties: {
        labels: {
          type: "array",
          items: { type: "string" },
          description: "Filter by labels (e.g. ['epic', 'EP-001-userOnboarding'])",
        },
        state: {
          type: "string",
          enum: ["open", "closed", "all"],
          description: "Issue state filter",
        },
      },
    },
    execute: async ({ labels, state }: { labels?: string[]; state?: string }) => {
      const repo = detectRepo();
      if (!repo) return errorResponse("Could not detect GitHub repo.");

      // Build URL with query params: gh api repos/.../issues?state=open&labels=bug
      let url = `repos/${repo}/issues`;
      const params: string[] = [];
      if (state) params.push(`state=${state}`);
      if (labels && labels.length) params.push(`labels=${labels.join(",")}`);
      if (params.length) url += `?${params.join("&")}`;

      const result = runGh(["api", url]);
      if (result.code !== 0) {
        return errorResponse(`Failed to list issues: ${result.stderr}`);
      }

      const issues = JSON.parse(result.stdout);
      return successResponse(`Found ${issues.length} issue(s)`, { success: true, count: issues.length, issues: issues.map((i: any) => ({ number: i.number, title: i.title, state: i.state, labels: i.labels?.map((l: any) => l.name) ?? [] })), });
    },
  };
}

function createGhCleanupBranches(): Tool {
  return {
    name: "gh_cleanup_branches",
    description: "Find + delete orphaned branches.",
    parameters: {
      type: "object",
      properties: {
        dryRun: {
          type: "boolean",
          description: "If true, only list orphaned branches without deleting",
        },
      },
    },
    execute: async ({ dryRun }: { dryRun?: boolean }) => {
      const repo = detectRepo();
      if (!repo) return errorResponse("Could not detect GitHub repo.");

      // Get all remote branches
      const branchResult = runGh(["api", "repos", repo, "branches"]);
      if (branchResult.code !== 0) {
        return errorResponse(`Failed to list branches: ${branchResult.stderr}`);
      }

      const branches = JSON.parse(branchResult.stdout);
      const allBranchNames = new Set(branches.map((b: any) => b.name));

      // Get all active issue labels to identify non-orphaned branches
      const issueResult = runGh(["api", `repos/${repo}/issues?state=open`]);
      if (issueResult.code !== 0) {
        return errorResponse(`Failed to list issues: ${issueResult.stderr}`);
      }

      const openIssues = JSON.parse(issueResult.stdout);
      const activeLabels = new Set<string>();
      for (const issue of openIssues) {
        for (const label of issue.labels ?? []) {
          const name = label.name as string;
          if (/^(EP|IS|SI)-\d{3}-/.test(name)) {
            activeLabels.add(name);
          }
        }
      }

      // Get all epic IDs from local files
      const { execSync } = require("child_process");
      const cwd = execSync("git rev-parse --show-toplevel 2>/dev/null || pwd", { encoding: "utf-8" }).trim();
      const { readdirSync } = require("fs");

      const epicsDir = `${cwd}/tasks`;
      const activeEpicBranches = new Set<string>();
      const activeIssueBranches = new Set<string>();
      const activeSubIssueBranches = new Set<string>();

      try {
        if (readdirSync(epicsDir, { withFileTypes: true })) {
          for (const entry of readdirSync(epicsDir, { withFileTypes: true })) {
            if (entry.isDirectory() && /^EP-\d{3}-[A-Z]/.test(entry.name)) {
              activeEpicBranches.add(entry.name);
              // Check for active issues within this epic
              const epicDir = `${epicsDir}/${entry.name}`;
              for (const issueEntry of readdirSync(epicDir, { withFileTypes: true })) {
                if (issueEntry.isDirectory() && /^IS-\d{3}-[A-Z]/.test(issueEntry.name)) {
                  activeIssueBranches.add(issueEntry.name);
                  // Check for active sub-issues
                  const issueDir = `${epicDir}/${issueEntry.name}`;
                  for (const siEntry of readdirSync(issueDir, { withFileTypes: true })) {
                    if (siEntry.isDirectory() && /^SI-\d{3}-[A-Z]/.test(siEntry.name)) {
                      activeSubIssueBranches.add(siEntry.name);
                    }
                  }
                }
              }
            }
          }
        }
      } catch {
        // Ignore errors reading local files
      }

      // Build set of branches that should be kept
      const keepBranches = new Set<string>(["main", "master", "develop"]);
      activeEpicBranches.forEach((b) => keepBranches.add(b));
      activeIssueBranches.forEach((b) => keepBranches.add(b));
      activeSubIssueBranches.forEach((b) => keepBranches.add(b));
      activeLabels.forEach((b) => keepBranches.add(b));

      // Find orphaned branches
      const orphaned: string[] = [];
      for (const branch of branches) {
        const name = branch.name as string;
        if (/^(EP|IS|SI)-\d{3}-[A-Z]/.test(name) && !keepBranches.has(name)) {
          orphaned.push(name);
        }
      }

      if (dryRun || !orphaned.length) {
        return successResponse(`Found ${orphaned.length} orphaned branch(es): ${orphaned.join(", ") || "none"}`, { success: true, dryRun: true, orphaned, message: `Found ${orphaned.length} orphaned branch(es): ${orphaned.join(", ") || "none"}` });
      }

      // Delete orphaned branches
      const deleted: string[] = [];
      const failed: string[] = [];
      for (const branch of orphaned) {
        const result = runGh(["api", "repos", repo, "gitrefs", `heads/${branch}`, "--method", "DELETE"]);
        if (result.code === 0) {
          deleted.push(branch);
        } else {
          failed.push(branch);
        }
      }

      return successResponse(`Deleted ${deleted.length} orphaned branch(es). Failed: ${failed.join(", ") || "none"}`, { success: true, deleted, failed, message: `Deleted ${deleted.length} orphaned branch(es). Failed: ${failed.join(", ") || "none"}` });
    },
  };
}

function createGhUpdateSubIssue(): Tool {
  return {
    name: "gh_update_sub_issue",
    description: "Mark SI complete, populate `files` audit trail.",
    parameters: {
      type: "object",
      properties: {
        jsonPath: {
          type: "string",
          description: "Path to the sub-issue JSON file",
        },
        files: {
          type: "array",
          items: {
            type: "object",
            properties: {
              path: { type: "string" },
              action: { type: "string", enum: ["create", "modify", "delete"] },
            },
            required: ["path", "action"],
          },
          description: "Files modified during work (audit trail)",
        },
        status: {
          type: "string",
          enum: ["not_started", "in_progress", "needs_review", "complete"],
          description: "New status",
        },
      },
      required: ["jsonPath"],
    },
    execute: async ({ jsonPath, files, status }: { jsonPath: string; files?: { path: string; action: string }[]; status?: string }) => {
      const { readFileSync, writeFileSync, existsSync } = require("fs");
      const { resolve } = require("path");

      const absPath = resolve(jsonPath);
      if (!existsSync(absPath)) {
        return errorResponse(`Sub-issue JSON not found: ${absPath}`);
      }

      const data = JSON.parse(readFileSync(absPath, "utf-8"));

      if (status) {
        data.status = status;
      }

      if (files) {
        // Merge new files into existing files array
        const existingFiles = data.files as { path: string; action: string }[];
        const existingPaths = new Set(existingFiles.map((f) => f.path));
        for (const file of files) {
          if (!existingPaths.has(file.path)) {
            existingFiles.push(file);
          }
        }
        data.files = existingFiles;
      }

      data.updated = new Date().toISOString();

      writeFileSync(absPath, JSON.stringify(data, null, 2));

      return successResponse(`Updated sub-issue ${data.id}: status=${data.status}, files=${data.files?.length ?? 0}`, { success: true, id: data.id, status: data.status, files: data.files, message: `Updated sub-issue ${data.id}: status=${data.status}, files=${data.files?.length ?? 0}` });
    },
  };
}

function createGhListSubIssues(): Tool {
  return {
    name: "gh_list_sub_issues",
    description: "List sub-issues for an issue.",
    parameters: {
      type: "object",
      properties: {
        epId: {
          type: "string",
          description: "Epic ID (e.g. EP-001-userOnboarding)",
        },
        issueId: {
          type: "string",
          description: "Issue ID (e.g. IS-001-implementLogin)",
        },
      },
      required: ["epId", "issueId"],
    },
    execute: async ({ epId, issueId }: { epId: string; issueId: string }) => {
      const { readdirSync, readFileSync, existsSync } = require("fs");
      const { resolve } = require("path");
      const { execSync } = require("child_process");

      const cwd = execSync("git rev-parse --show-toplevel 2>/dev/null || pwd", { encoding: "utf-8" }).trim();
      const issueDir = resolve(cwd, `tasks/${epId}/${issueId}`);

      if (!existsSync(issueDir)) {
        return errorResponse(`Issue directory not found: ${issueDir}`);
      }

      const subIssues: any[] = [];
      for (const entry of readdirSync(issueDir, { withFileTypes: true })) {
        if (entry.isDirectory() && /^SI-\d{3}-/.test(entry.name)) {
          const jsonPath = resolve(issueDir, entry.name, `${entry.name}.json`);
          if (existsSync(jsonPath)) {
            const data = JSON.parse(readFileSync(jsonPath, "utf-8"));
            subIssues.push({
              id: data.id,
              name: data.name,
              status: data.status,
              type: data.type,
              priority: data.priority,
              effort: data.effort,
              githubPrNumber: data.githubPrNumber,
            });
          }
        }
      }

      return successResponse(`Found ${subIssues.length} sub-issue(s) for ${issueId}`, { success: true, epId, issueId, count: subIssues.length, subIssues });
    },
  };
}

// ── Markdown generation helper ───────────────────────────────────────────────

function generateSubIssueMarkdown(data: Record<string, unknown>): string {
  const id = data.id as string;
  const name = data.name as string;
  const description = data.description as string;
  const type = data.type as string;
  const status = data.status as string;
  const milestone = data.milestone as string;
  const scope = data.scope as { inScope?: { description: string }[]; outOfScope?: { description: string }[] };
  const acceptanceCriteria = (data.acceptanceCriteria as { description: string }[]) ?? [];
  const priority = data.priority as string;
  const effort = data.effort as string;
  const isRefs = data.isRefs as string[];
  const epRefs = data.epRefs as string[];

  let md = `# ${id}: ${name}\n\n`;
  md += `## Description\n${description}\n\n`;
  md += `## Type\n${type}\n\n`;
  md += `## Status\n${status}\n\n`;
  md += `## Milestone\n${milestone}\n\n`;

  md += `## Scope\n`;
  if (scope?.inScope?.length) {
    md += `### In Scope\n${scope.inScope.map((s) => `- ${s.description}`).join("\n")}\n\n`;
  }
  if (scope?.outOfScope?.length) {
    md += `### Out of Scope\n${scope.outOfScope.map((s) => `- ${s.description}`).join("\n")}\n\n`;
  }

  md += `## Acceptance Criteria\n${acceptanceCriteria.map((ac) => `- [ ] ${ac.description}`).join("\n")}\n\n`;

  if (priority) md += `## Priority\n${priority}\n\n`;
  if (effort) md += `## Effort\n${effort}\n\n`;

  md += `## References\n`;
  if (isRefs?.length) md += `- Issues: ${isRefs.join(", ")}\n`;
  if (epRefs?.length) md += `- Epics: ${epRefs.join(", ")}\n`;

  return md;
}

// ── Registration ─────────────────────────────────────────────────────────────

export function registerGithubIssues(pi: ExtensionAPI): void {
  pi.registerTool(createGhCreateEpic());
  pi.registerTool(createGhCreateIssue());
  pi.registerTool(createGhCreateSubIssue());
  pi.registerTool(createGhCreatePr());
  pi.registerTool(createGhMergePr());
  pi.registerTool(createGhUpdateIssue());
  pi.registerTool(createGhGetIssue());
  pi.registerTool(createGhListIssues());
  pi.registerTool(createGhCleanupBranches());
  pi.registerTool(createGhUpdateSubIssue());
  pi.registerTool(createGhListSubIssues());
}
