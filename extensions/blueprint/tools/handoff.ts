import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { DEPS, resolveCommand } from "../utils";

export function registerHandoff(pi: ExtensionAPI) {
  pi.registerTool({
    name: "handoff",
    label: "Handoff",
    description:
      "Produce a handoff table listing all artifacts whose dependencies are " +
      "met. Reads frontmatter from each artifact to report accurate status.",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const cwd = ctx.cwd;

      // Map of command -> artifact name -> expected JSON file
      const artifactOrder = [
        { command: "goal", name: "GoalSpec", jsonPath: "artifacts/GoalSpec.json", mdPath: "artifacts/GoalSpec.md" },
        { command: "glossary", name: "Glossary", jsonPath: "artifacts/Glossary.json", mdPath: "artifacts/Glossary.md" },
        { command: "design", name: "Design", jsonPath: "artifacts/DesignSpec.json", mdPath: "artifacts/DesignSpec.md" },
        { command: "arch", name: "Architecture", jsonPath: "artifacts/ArchitectureSpec.json", mdPath: "artifacts/ArchitectureSpec.md" },
        { command: "data", name: "DataSpec", jsonPath: "artifacts/DataSpec.json", mdPath: "artifacts/DataSpec.md" },
        { command: "api", name: "ApiSpec", jsonPath: "artifacts/ApiSpec.json", mdPath: "artifacts/ApiSpec.md" },
        { command: "test", name: "TestSpec", jsonPath: "artifacts/TestSpec.json", mdPath: "artifacts/TestSpec.md" },
        { command: "plan", name: "TaskPlan", jsonPath: "", mdPath: "tasks/PLAN.md" }, // plan produces tasks/PLAN.md, not artifacts/
      ];

      // Build set of completed artifacts (JSON exists)
      const completed: Set<string> = new Set();
      for (const art of artifactOrder) {
        if (art.jsonPath && fs.existsSync(path.resolve(cwd, art.jsonPath))) {
          completed.add(art.command);
        }
      }

      // Check dependencies and build handoff list
      const available: Array<{ command: string; name: string; status: string }> = [];

      for (const art of artifactOrder) {
        if (art.command === "plan") continue; // plan handled separately

        const deps = DEPS[art.command]?.dependencies || [];
        const missingDeps = deps.filter(d => d.required && !completed.has(resolveCommand(d.name)));

        if (missingDeps.length > 0) continue;

        // Read status from JSON (JSON is the single source of truth)
        let status = "in_progress";
        const jsonPath = path.resolve(cwd, art.jsonPath);
        if (fs.existsSync(jsonPath)) {
          const json = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
          status = json.status || "in_progress";
        }

        available.push({ command: art.command, name: art.name, status });
      }

      // Check if plan is available
      let planAvailable = false;
      const planDeps = DEPS.plan?.dependencies || [];
      const planMissing = planDeps.filter(d => d.required && !completed.has(resolveCommand(d.name)));
      if (planMissing.length === 0 && fs.existsSync(path.resolve(cwd, "tasks/PLAN.md"))) {
        planAvailable = true;
      }

      // Build output
      if (available.length === 0 && !planAvailable) {
        return {
          content: [{ type: "text", text: "No artifacts ready for handoff yet. Complete the current artifact first." }],
          details: { available: [] },
        };
      }

      const nextSteps = available.map(a => {
        const statusLabel = a.status === "complete" ? "complete" : a.status === "needs_review" ? "needs_review" : "in_progress";
        return `| ${a.name} | /skill:blueprint ${a.command} | ${statusLabel} |`;
      });

      if (planAvailable) {
        nextSteps.push(`| TaskPlan | /skill:blueprint plan | complete |`);
      }

      const output = `\`artifacts/<ArtifactType>.json\` is complete.\n\nYou can now proceed to:\n\n| Next step | Command | Status |\n|---|---|---|\n${nextSteps.join('\n')}\n\nOpen a fresh session for each next step.`;

      return {
        content: [{ type: "text", text: output }],
        details: { available, planAvailable },
      };
    },
  });
}
