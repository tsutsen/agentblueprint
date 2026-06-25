import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";

export function registerUpdateFrontmatter(pi: ExtensionAPI) {
  pi.registerTool({
    name: "update_frontmatter",
    label: "Update Frontmatter",
    description:
      "Update an artifact's frontmatter: status, sections_complete, " +
      "sections_pending. The 'updated' field is set automatically to " +
      "today's date. Preserves the artifact name from existing frontmatter.",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Artifact file path (e.g. artifacts/GoalSpec.md)",
      }),
      status: Type.String({
        description: "New status: in_progress | needs_review | complete",
      }),
      sections_complete: Type.Array(Type.String(), {
        description: "List of confirmed section names.",
      }),
      sections_pending: Type.Array(Type.String(), {
        description: "List of pending section names.",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { filePath, status, sections_complete, sections_pending } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);

      if (!fs.existsSync(fullPath)) {
        return {
          content: [{ type: "text", text: `ERROR: file not found: ${filePath}` }],
          details: { verified: false, path: filePath },
          isError: true,
        };
      }

      const text = fs.readFileSync(fullPath, "utf-8");
      const updated = new Date().toISOString().slice(0, 10);

      const artifactMatch = text.match(/^---\nartifact:\s*(.+?)\n/m);
      const existingArtifact = artifactMatch?.[1].trim();

      const fmLines: string[] = ["---"];
      if (existingArtifact) {
        fmLines.push(`artifact: ${existingArtifact}`);
      }
      fmLines.push(`status: ${status}`);
      fmLines.push(`sections_complete:`);
      for (const s of sections_complete) {
        fmLines.push(`  - ${s}`);
      }
      fmLines.push(`sections_pending:`);
      for (const s of sections_pending) {
        fmLines.push(`  - ${s}`);
      }
      fmLines.push(`updated: ${updated}`);
      fmLines.push("---");

      const newFm = fmLines.join("\n") + "\n";
      const fmRegex = /^---\n[\s\S]*?\n---\n/;
      const body = text.replace(fmRegex, newFm);

      fs.writeFileSync(fullPath, body, "utf-8");

      const written = fs.readFileSync(fullPath, "utf-8");
      const hasStatus = written.includes(`status: ${status}`);
      const hasUpdated = written.includes(`updated: ${updated}`);

      if (!hasStatus || !hasUpdated) {
        return {
          content: [{ type: "text", text: `ERROR: frontmatter update verification failed for ${filePath}` }],
          details: { verified: false, path: filePath },
          isError: true,
        };
      }

      return {
        content: [{ type: "text", text: `Frontmatter updated: status=${status}, ${sections_complete.length} complete, ${sections_pending.length} pending` }],
        details: { verified: true, path: filePath, status, updated },
      };
    },
  });
}
