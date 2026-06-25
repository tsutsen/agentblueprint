import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";

export function registerWriteSection(pi: ExtensionAPI) {
  pi.registerTool({
    name: "write_section",
    label: "Write Section",
    description:
      "Write the complete JSON artifact to disk during the interview. " +
      "Call this after every section is confirmed — pass the full accumulated " +
      "JSON object. This ensures data is persisted incrementally: if the session " +
      "crashes, the latest JSON on disk can be loaded to resume. " +
      "The JSON is the single source of truth — Markdown is derived later via " +
      "generate_artifact_markdown.",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Output file path (e.g. artifacts/GoalSpec.json)",
      }),
      section: Type.String({
        description: "Section name just confirmed (e.g. Project Objective, Non-Goals). Used for logging.",
      }),
      content: Type.String({
        description: "The validated section content to write.",
      }),
      jsonContent: Type.Object({}, {
        description: "Complete accumulated JSON object for the entire artifact. Must include all previously confirmed sections plus the new one. This is written atomically to disk.",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { filePath, section, content, jsonContent } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);
      const dir = path.dirname(fullPath);
      const now = new Date().toISOString();

      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      // Add metadata to the JSON
      jsonContent._meta = jsonContent._meta || {};
      jsonContent._meta.updated = now;
      jsonContent._meta.updatedSection = section;

      const jsonPath = fullPath.replace(/\.md$/, '.json');
      fs.writeFileSync(jsonPath, JSON.stringify(jsonContent, null, 2) + '\n');

      return {
        content: [{
          type: "text",
          text: `Section written: ${section}\n` +
            `  JSON: ${jsonPath}\n` +
            `  Updated: ${now}`,
        }],
        details: { success: true, section, jsonPath, updated: now },
      };
    },
  });
}
