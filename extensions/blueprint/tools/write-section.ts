import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";

export function registerWriteSection(pi: ExtensionAPI) {
  pi.registerTool({
    name: "write_section",
    label: "Write Section",
    description:
      "Write a confirmed artifact section to JSON during the interview. " +
      "The JSON is the single source of truth — Markdown is derived later " +
      "via generate_artifact_markdown. Tracks section progress in a _sections " +
      "field on the JSON artifact.",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Output file path (e.g. artifacts/GoalSpec.json)",
      }),
      section: Type.String({
        description: "Section name (e.g. Project Objective, Non-Goals)",
      }),
      content: Type.String({
        description: "The validated section content to write.",
      }),
      sections_complete: Type.Array(Type.String(), {
        description: "List of confirmed section names (including the one just written).",
      }),
      sections_pending: Type.Array(Type.String(), {
        description: "List of section names still to be confirmed.",
      }),
      jsonContent: Type.Optional(Type.Object({}, {
        description: "Complete JSON object for the entire artifact. Written to the .json file. The blueprint skill accumulates this across sections.",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { filePath, section, content, sections_complete, sections_pending, jsonContent } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);
      const dir = path.dirname(fullPath);
      const updated = new Date().toISOString().slice(0, 10);

      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      let jsonPath: string | null = null;
      let jsonWritten = false;
      if (jsonContent) {
        jsonPath = fullPath.replace(/\.md$/, '.json');
        if (!jsonContent._sections) {
          jsonContent._sections = { sections_complete: [], sections_pending: [] };
        }
        jsonContent._sections.sections_complete = sections_complete;
        jsonContent._sections.sections_pending = sections_pending;
        jsonContent._sections.updated = updated;
        fs.writeFileSync(jsonPath, JSON.stringify(jsonContent, null, 2) + '\n');
        jsonWritten = true;
      }

      if (!jsonWritten) {
        return {
          content: [{ type: "text", text: `ERROR: write_section requires jsonContent. The JSON is the single source of truth; Markdown is derived later.` }],
          details: { success: false },
          isError: true,
        };
      }

      const written = fs.readFileSync(jsonPath, "utf-8");
      const revalidated = JSON.parse(written);
      const hasSections = revalidated._sections?.sections_complete?.includes(section);

      if (!hasSections) {
        return {
          content: [{ type: "text", text: `ERROR: section '${section}' not found in written JSON.` }],
          details: { success: false },
          isError: true,
        };
      }

      return {
        content: [{
          type: "text",
          text: `Section written: ${section}\n` +
            `  JSON: ${jsonPath}\n` +
            `  Sections complete: ${sections_complete.length}\n` +
            `  Sections pending: ${sections_pending.length}`,
        }],
        details: { success: true, section, jsonPath },
      };
    },
  });
}
