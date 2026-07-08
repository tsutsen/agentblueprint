import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";

/**
 * Parse a JSON path like "userJourneys[0].description" into segments
 * ["userJourneys", 0, "description"]. Array indices become numbers.
 */
function parsePath(jsonPath: string): (string | number)[] {
  const segments: (string | number)[] = [];
  // Split on "." and also tokenize bracket notation
  const parts = jsonPath.split(".");
  for (const part of parts) {
    // Match patterns like "key[0][1]" or just "key"
    const regex = /([^[\]]+)(\[(\d+)\])?/g;
    let match;
    // Handle the case where part is just an index like "[0]" (shouldn't normally happen but be safe)
    if (part.startsWith("[")) {
      const idxMatch = part.match(/^\[(\d+)\]$/);
      if (idxMatch) {
        segments.push(parseInt(idxMatch[1], 10));
      }
      continue;
    }
    while ((match = regex.exec(part)) !== null) {
      segments.push(match[1]);
      if (match[3] !== undefined) {
        segments.push(parseInt(match[3], 10));
      }
    }
  }
  return segments;
}

/**
 * Deep set a value on an object using a JSON path that supports both
 * dot-notation and array brackets (e.g. "userJourneys[0].description").
 * Creates intermediate objects/arrays as needed.
 */
function deepSet(obj: Record<string, unknown>, path: string, value: unknown): void {
  const segments = parsePath(path);
  let current: Record<string, unknown> | unknown[] = obj;
  for (let i = 0; i < segments.length - 1; i++) {
    const segment = segments[i];
    const nextSegment = segments[i + 1];
    const isIndex = typeof segment === "number";
    const key = String(segment);

    if (isIndex) {
      // Ensure current is an array and long enough
      if (!Array.isArray(current)) {
        current = [];
      }
      const arr = current as unknown[];
      if (arr.length <= segment) {
        arr.length = segment + 1;
      }
      if (!arr[segment] || typeof arr[segment] !== "object" || arr[segment] === null) {
        arr[segment] = typeof nextSegment === "number" ? [] : {};
      }
      current = arr[segment] as Record<string, unknown>;
    } else {
      if (!(key in current) || typeof (current as Record<string, unknown>)[key] !== "object" || (current as Record<string, unknown>)[key] === null) {
        (current as Record<string, unknown>)[key] = typeof nextSegment === "number" ? [] : {};
      }
      current = (current as Record<string, unknown>)[key] as Record<string, unknown>;
    }
  }

  // Set the final value
  const lastSegment = segments[segments.length - 1];
  if (typeof lastSegment === "number") {
    (current as unknown as unknown[])[lastSegment] = value;
  } else {
    (current as Record<string, unknown>)[lastSegment] = value;
  }
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
