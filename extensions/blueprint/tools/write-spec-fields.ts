import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";

/**
 * Deep set a value on an object using a dot-separated path.
 * Creates intermediate objects/arrays as needed.
 */
function deepSet(obj: Record<string, unknown>, path: string, value: unknown): void {
  const parts = path.split(".");
  let current: Record<string, unknown> = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i];
    if (!(key in current) || typeof current[key] !== "object" || current[key] === null) {
      const nextKey = parts[i + 1];
      current[key] = /^\d+$/.test(nextKey) ? [] : {};
    }
    current = current[key] as Record<string, unknown>;
  }
  current[parts[parts.length - 1]] = value;
}

/**
 * Load an existing JSON file, or return an empty object if it doesn't exist.
 */
function loadExisting(filePath: string): Record<string, unknown> {
  if (fs.existsSync(filePath)) {
    try {
      const raw = fs.readFileSync(filePath, "utf-8");
      const parsed = JSON.parse(raw);
      return typeof parsed === "object" && parsed !== null ? parsed : {};
    } catch {
      return {};
    }
  }
  return {};
}

export function registerWriteSpecFields(pi: ExtensionAPI) {
  pi.registerTool({
    name: "write_spec_fields",
    label: "Write Spec Fields",
    description:
      "Surgically update one or more fields on the JSON artifact. The tool " +
      "loads the existing JSON from disk, applies all updates, and writes back " +
      "atomically. Data is persisted incrementally — if the session crashes, the " +
      "latest JSON on disk can be loaded to resume. Resume state is determined by " +
      "checking which fields have content. The JSON is the single source of truth — " +
      "Markdown is derived later via generate_artifact_markdown.",
    parameters: Type.Object({
      filePath: Type.String({
        description: "Output file path (e.g. artifacts/GoalSpec.json)",
      }),
      field: Type.String({
        description: "Human-readable label for this write operation (e.g. 'Project Objective', 'Functional Requirements'). Used for logging.",
      }),
      content: Type.String({
        description: "The validated section content.",
      }),
      updates: Type.Array(Type.Object({
        jsonPath: Type.String({
          description: "Dot-separated path to the field to set (e.g. 'functionalRequirements', 'userStories[0].statement'). Arrays can be indexed.",
        }),
        jsonValue: Type.Unknown({
          description: "The value to set at jsonPath. Can be a string, number, boolean, object, or array.",
        }),
      }), {
        description: "List of field updates to apply atomically.",
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { filePath, field, content, updates } = params;
      const fullPath = path.resolve(ctx.cwd, filePath);
      const jsonPath = fullPath.replace(/\.md$/, '.json');
      const dir = path.dirname(jsonPath);

      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      // Load existing JSON, apply all updates, write back
      const data = loadExisting(jsonPath);
      for (const update of updates) {
        deepSet(data, update.jsonPath, update.jsonValue);
      }

      fs.writeFileSync(jsonPath, JSON.stringify(data, null, 2) + '\n');

      return {
        content: [{
          type: "text",
          text: `Field written: ${field}\n` +
            `  JSON: ${jsonPath}\n` +
            `  Updates: ${updates.length} field(s)`,
        }],
        details: { success: true, field, jsonPath, updates },
      };
    },
  });
}
