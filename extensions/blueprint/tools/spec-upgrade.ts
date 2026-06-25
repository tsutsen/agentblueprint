import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { extractFrontmatter, resolveSchemaPath } from "../utils";

// Map of command keys to schema names and default file paths
const ARTIFACT_TYPES: Array<{ command: string; schemaName: string; mdPath: string; jsonPath: string }> = [
  { command: "goal", schemaName: "goalspec", mdPath: "artifacts/GoalSpec.md", jsonPath: "artifacts/GoalSpec.json" },
  { command: "glossary", schemaName: "glossary", mdPath: "artifacts/Glossary.md", jsonPath: "artifacts/Glossary.json" },
  { command: "design", schemaName: "designspec", mdPath: "artifacts/DesignSpec.md", jsonPath: "artifacts/DesignSpec.json" },
  { command: "arch", schemaName: "archspec", mdPath: "artifacts/ArchitectureSpec.md", jsonPath: "artifacts/ArchitectureSpec.json" },
  { command: "data", schemaName: "dataspec", mdPath: "artifacts/DataSpec.md", jsonPath: "artifacts/DataSpec.json" },
  { command: "api", schemaName: "apispec", mdPath: "artifacts/ApiSpec.md", jsonPath: "artifacts/ApiSpec.json" },
  { command: "test", schemaName: "testspec", mdPath: "artifacts/TestSpec.md", jsonPath: "artifacts/TestSpec.json" },
  { command: "plan", schemaName: "taskplan", mdPath: "tasks/PLAN.md", jsonPath: "tasks/PLAN.json" },
  { command: "issues", schemaName: "issue", mdPath: "", jsonPath: "" },
];

function resolveRef(ref: string, schema: any): any {
  if (!ref || !ref.startsWith("#/")) return null;
  const parts = ref.slice(2).split("/");
  let current: any = schema;
  for (const part of parts) {
    if (current && typeof current === "object") current = current[part];
    else return null;
  }
  return current;
}

function getEffectiveSchema(val: any, fieldSchema: any): any {
  if (!fieldSchema) return null;
  if (fieldSchema.$ref) return resolveRef(fieldSchema.$ref, {}) || fieldSchema;
  if (fieldSchema.allOf && Array.isArray(fieldSchema.allOf)) {
    let merged: any = { properties: {}, required: [] };
    for (const sub of fieldSchema.allOf) {
      const subSchema = getEffectiveSchema(val, sub);
      if (subSchema?.properties) merged.properties = { ...merged.properties, ...subSchema.properties };
      if (subSchema?.required) merged.required = [...(merged.required || []), ...subSchema.required];
    }
    return merged;
  }
  return fieldSchema;
}

function hasMeaningfulValue(val: any): boolean {
  if (val === null || val === undefined) return false;
  if (typeof val === "string") return val.trim().length > 0;
  if (Array.isArray(val)) return val.length > 0;
  if (typeof val === "object") {
    const keys = Object.keys(val);
    return keys.length > 0 && keys.some(k => hasMeaningfulValue(val[k]));
  }
  return true;
}

function findBestTarget(value: any, currentPath: string, schema: any): { target: string; confidence: "high" } | null {
  if (!schema || !schema.properties) return null;
  const valueKeys = typeof value === "object" && value !== null ? Object.keys(value) : [];
  const nameMap: Record<string, string[]> = {
    "inputs": ["inputs", "parameters", "args", "arguments"],
    "output": ["output", "result", "response", "returnValue"],
    "description": ["description", "desc", "detail", "summary"],
    "name": ["name", "title", "label"],
    "type": ["type", "kind", "category"],
    "version": ["version", "ver", "revision"],
    "component": ["component", "module", "part"],
    "properties": ["properties", "fields", "attributes", "schema"],
  };
  for (const [target, patterns] of Object.entries(nameMap)) {
    if (target in schema.properties) {
      for (const pattern of patterns) {
        if (currentPath.includes(pattern) || valueKeys.some(k => k.includes(pattern))) {
          return { target, confidence: "high" };
        }
      }
    }
  }
  return null;
}

function findGlossaryRefs(text: string, glossaryTerms: Array<{ id: string; term: string }>): string[] {
  if (!text || !glossaryTerms.length) return [];
  const found: string[] = [];
  const lowerText = text.toLowerCase();
  for (const term of glossaryTerms) {
    const regex = new RegExp(`\\b${term.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
    if (regex.test(lowerText)) found.push(term.id);
  }
  return [...new Set(found)];
}

function applyGlossaryRefs(obj: any, schema: any, glossaryRefsField: string) {
  if (!schema.properties) return;
  for (const [key, fieldSchema] of Object.entries(schema.properties)) {
    if (fieldSchema.type === "object" && typeof obj[key] === "object" && !Array.isArray(obj[key])) {
      applyGlossaryRefs(obj[key], fieldSchema, glossaryRefsField);
    } else if (fieldSchema.type === "array" && fieldSchema.items) {
      if (fieldSchema.items.$ref) {
        const refName = fieldSchema.items.$ref.split("/").pop();
        const refSchema = schema.definitions?.[refName];
        if (refSchema && refSchema.properties) {
          const items = obj[key] || [];
          for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (typeof item === "string") {
              items[i] = { description: item, glossaryRefs: [] };
              const refs = findGlossaryRefs(item, []);
              if (refs.length > 0) items[i].glossaryRefs = refs;
            } else if (typeof item === "object" && !item[glossaryRefsField]) {
              const desc = item.description || item.title || "";
              if (desc && typeof desc === "string") {
                const refs = findGlossaryRefs(desc, []);
                if (refs.length > 0) item[glossaryRefsField] = refs;
              }
            }
            if (typeof items[i] === "object" && !Array.isArray(items[i])) {
              applyGlossaryRefs(items[i], refSchema, glossaryRefsField);
            }
          }
        }
      }
    }
  }
}

function fixObjectAgainstSchema(obj: any, schema: any, path: string, removeExtra: boolean, artifactType: string) {
  if (!schema || !schema.properties || typeof obj !== "object" || Array.isArray(obj)) return;
  const requiredFields = new Set(schema.required || []);
  const schemaProps = new Set(Object.keys(schema.properties));
  const safeExtraProps = new Set(["version", "schemaVersion", "module", "status", "artifact", "createdAt", "updatedAt", "created", "updated", "_comment", "_meta", "_source"]);
  const grf = artifactType === "issues" ? "titleGlossaryRefs" : "glossaryRefs";

  for (const req of requiredFields) {
    if (!(req in obj)) {
      const reqSchema = schema.properties[req];
      let defaultValue: any = null;
      if (reqSchema) {
        if (reqSchema.type === "array") defaultValue = [];
        else if (reqSchema.type === "object") defaultValue = {};
        else if (reqSchema.default !== undefined) defaultValue = reqSchema.default;
      }
      obj[req] = defaultValue;
    }
  }

  if (removeExtra && schema.additionalProperties === false) {
    for (const key of Object.keys(obj)) {
      if (!schemaProps.has(key) && !safeExtraProps.has(key)) {
        if (key === grf && schemaProps.has(grf)) continue;
        const value = obj[key];
        if (!hasMeaningfulValue(value)) {
          delete obj[key];
          continue;
        }
        const targetInfo = findBestTarget(value, key, schema);
        if (targetInfo && targetInfo.confidence === "high") {
          const targetField = schema.properties[targetInfo.target];
          const targetType = (targetField as any).type;
          if (targetType === "string" && typeof value === "string") {
            obj[targetInfo.target] = obj[targetInfo.target] ? `${obj[targetInfo.target]} | ${value}` : value;
          } else if (targetType === "array" && Array.isArray(value)) {
            obj[targetInfo.target] = [...(obj[targetInfo.target] || []), ...value];
          } else if (targetType === "array" && typeof value === "string") {
            obj[targetInfo.target] = [...(obj[targetInfo.target] || []), value];
          } else if (targetType === "object" && typeof value === "object" && value !== null) {
            obj[targetInfo.target] = { ...(obj[targetInfo.target] || {}), ...value };
          } else if (targetType === typeof value) {
            obj[targetInfo.target] = value;
          } else {
            obj[targetInfo.target] = obj[targetInfo.target] ? `${obj[targetInfo.target]} | ${JSON.stringify(value).slice(0, 100)}` : JSON.stringify(value).slice(0, 100);
          }
          delete obj[key];
        }
      }
    }
  }

  for (const [key, fieldSchema] of Object.entries(schema.properties)) {
    if (!(key in obj)) continue;
    const effective = getEffectiveSchema(obj[key], fieldSchema);
    if (!effective) continue;
    if (effective.type === "object" && typeof obj[key] === "object" && !Array.isArray(obj[key])) {
      fixObjectAgainstSchema(obj[key], effective, `${path}.${key}`, true, artifactType);
    } else if (effective.type === "array" && effective.items && Array.isArray(obj[key])) {
      for (let i = 0; i < obj[key].length; i++) {
        const item = obj[key][i];
        if (effective.items.$ref) {
          const refSchema = resolveRef(effective.items.$ref, {});
          if (refSchema && refSchema.properties) fixObjectAgainstSchema(item, refSchema, `${path}.${key}[${i}]`, true, artifactType);
        } else if (effective.items.properties) {
          fixObjectAgainstSchema(item, effective.items, `${path}.${key}[${i}]`, true, artifactType);
        }
      }
    }
  }
}

function validateSchemaRefs(schemaObj: any, path = ""): string[] {
  if (!schemaObj || typeof schemaObj !== "object") return [];
  const errors: string[] = [];
  if (schemaObj.$ref && typeof schemaObj.$ref === "string" && schemaObj.$ref.startsWith("#/definitions/")) {
    const defName = schemaObj.$ref.split("/").pop();
    const root = path === "" ? schemaObj : undefined;
    // Check in root schema
  }
  for (const key of Object.keys(schemaObj)) {
    if (key === "$ref" || key === "description" || key === "type" || key === "required" || key === "additionalProperties" || key === "items" || key === "properties" || key === "allOf" || key === "anyOf" || key === "oneOf" || key === "default" || key === "pattern" || key === "minLength" || key === "maxLength" || key === "minItems" || key === "maxItems" || key === "uniqueItems" || key === "readOnly" || key === "minProperties" || key === "maxProperties") continue;
    errors.push(...validateSchemaRefs(schemaObj[key], `${path}.${key}`));
  }
  if (schemaObj.items) errors.push(...validateSchemaRefs(schemaObj.items, `${path}.items`));
  if (schemaObj.allOf) schemaObj.allOf.forEach((s: any, i: number) => errors.push(...validateSchemaRefs(s, `${path}.allOf[${i}]`)));
  if (schemaObj.anyOf) schemaObj.anyOf.forEach((s: any, i: number) => errors.push(...validateSchemaRefs(s, `${path}.anyOf[${i}]`)));
  if (schemaObj.oneOf) schemaObj.oneOf.forEach((s: any, i: number) => errors.push(...validateSchemaRefs(s, `${path}.oneOf[${i}]`)));
  if (schemaObj.properties) {
    for (const [propName, propSchema] of Object.entries(schemaObj.properties)) {
      errors.push(...validateSchemaRefs(propSchema, `${path}.properties.${propName}`));
    }
  }
  return errors;
}

async function upgradeSingleArtifact(
  artifactType: string, mdPath: string, jsonPath: string, extDir: string, ctx: any
): Promise<{ text: string; details: any }> {
  const fullPath = path.resolve(ctx.cwd, mdPath);
  const schemaName = ARTIFACT_TYPES.find(a => a.command === artifactType)?.schemaName;
  if (!schemaName) return { text: `Unknown artifact type: ${artifactType}`, details: { success: false } };

  const schemaPath = resolveSchemaPath(extDir, schemaName);
  if (!fs.existsSync(schemaPath)) return { text: `Schema not found: ${schemaPath}`, details: { success: false, error: "schema_missing" } };
  const schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));

  if (!fs.existsSync(fullPath)) return { text: `File not found: ${fullPath}`, details: { success: false, error: "file_missing" } };
  const markdown = fs.readFileSync(fullPath, "utf-8");
  const fm = extractFrontmatter(markdown);

  let existingJson: any = {};
  if (jsonPath && fs.existsSync(path.resolve(ctx.cwd, jsonPath))) {
    existingJson = JSON.parse(fs.readFileSync(path.resolve(ctx.cwd, jsonPath), "utf-8"));
  }

  let glossaryTerms: Array<{ id: string; term: string; description: string }> = [];
  const glossaryPath = path.resolve(ctx.cwd, "artifacts/Glossary.json");
  if (fs.existsSync(glossaryPath)) {
    try {
      const glossary = JSON.parse(fs.readFileSync(glossaryPath, "utf-8"));
      glossaryTerms = (glossary.terms || []).map((t: any) => ({ id: t.id, term: t.term, description: t.description }));
    } catch { /* Glossary not available */ }
  }

  const schemaRefErrors = validateSchemaRefs(schema);
  const glossaryRefsFieldMap: Record<string, string> = {
    goal: "glossaryRefs", glossary: "glossaryRefs", design: "glossaryRefs",
    arch: "glossaryRefs", data: "glossaryRefs", api: "glossaryRefs",
    test: "glossaryRefs", plan: "glossaryRefs", issues: "glossaryRefs",
  };

  const schemaFixes = 0;
  const schemaChanges: string[] = [];
  const dataAtRisk: Array<{ path: string; key: string; value: any; valueType: string; confidence: string; reason: string }> = [];

  if (schema.properties) {
    fixObjectAgainstSchema(existingJson, schema, artifactType, true, artifactType);
    for (const [key, fieldSchema] of Object.entries(schema.properties)) {
      if (fieldSchema.type === "array" && fieldSchema.items && Array.isArray(existingJson[key])) {
        const itemsSchema = fieldSchema.items.$ref ? resolveRef(fieldSchema.items.$ref, {}) : fieldSchema.items;
        if (itemsSchema && itemsSchema.properties) {
          for (let i = 0; i < existingJson[key].length; i++) {
            fixObjectAgainstSchema(existingJson[key][i], itemsSchema, `${key}[${i}]`, true, artifactType);
          }
        }
      }
    }
  }

  const grf = glossaryRefsFieldMap[artifactType] || "glossaryRefs";
  applyGlossaryRefs(existingJson, schema, grf);

  let fieldsAdded = 0;
  const changes: string[] = [];

  if (artifactType === "issues" && existingJson.title && !existingJson.titleGlossaryRefs) {
    const refs = findGlossaryRefs(existingJson.title, glossaryTerms.map(t => ({ id: t.id, term: t.term })));
    if (refs.length > 0) { existingJson.titleGlossaryRefs = refs; fieldsAdded++; changes.push(`titleGlossaryRefs: [${refs.join(", ")}]`); }
  }

  fs.writeFileSync(jsonPath, JSON.stringify(existingJson, null, 2) + "\n");

  if (fs.existsSync(fullPath)) {
    const updated = new Date().toISOString().slice(0, 10);
    const fmLinesNew: string[] = ["---"];
    const artifactMatch = markdown.match(/^---\nartifact:\s*(.+?)\n/m);
    if (artifactMatch) fmLinesNew.push(`artifact: ${artifactMatch[1].trim()}`);
    fmLinesNew.push(`status: ${fm.status || "in_progress"}`);
    fmLinesNew.push(`updated: ${updated}`);
    fmLinesNew.push("---");
    const newFm = fmLinesNew.join("\n") + "\n";
    const fmRegex = /^---\n[\s\S]*?\n---\n/;
    const body = markdown.replace(fmRegex, newFm);
    fs.writeFileSync(fullPath, body, "utf-8");
  }

  const migratedCount = schemaChanges.filter(c => c.includes("→") && c.includes("migrated")).length;
  const removedCount = schemaChanges.filter(c => c.includes("removed")).length;
  const hasDataAtRisk = dataAtRisk.length > 0;
  const hasSchemaRefErrors = schemaRefErrors.length > 0;

  let resultText = "";
  if (changes.length === 0 && !hasDataAtRisk && !hasSchemaRefErrors) {
    resultText = `Upgrade complete for ${artifactType}: No changes needed. Files are up to date.`;
  } else {
    resultText = `Upgrade complete for ${artifactType}:\n`;
    if (migratedCount > 0) resultText += `  Migrated: ${migratedCount} field(s) → schema-compliant target\n`;
    if (removedCount > 0) resultText += `  Removed: ${removedCount} field(s) (empty/no data)\n`;
    if (fieldsAdded > 0) resultText += `  Glossary fields added: ${fieldsAdded}\n`;
    if (changes.length > 0) resultText += `  Changes:\n${changes.map(c => `    - ${c}`).join("\n")}\n`;
    if (hasSchemaRefErrors) resultText += `\n⚠️  Schema reference errors (schema-level issue)\n`;
    if (hasDataAtRisk) resultText += `\n⚠️  ${dataAtRisk.length} field(s) violate schema (additionalProperties: false)\n`;
    resultText += `\nFiles updated:\n  - ${mdPath}\n  - ${jsonPath}\n\nRun /skill:lint ${artifactType} to verify.`;
  }

  return { text: resultText, details: { success: true, fieldsAdded, changes, schemaFixes, dataAtRisk, schemaRefErrors } };
}

export function registerSpecUpgrade(pi: ExtensionAPI, extDir: string) {
  pi.registerTool({
    name: "spec_upgrade",
    label: "Spec Upgrade",
    description:
      "Migrate artifact files from old schema format to new format. " +
      "Detects and fixes schema mismatches (property renames, missing/extra fields). " +
      "Loads the glossary and scans content to populate glossaryRefs intelligently. " +
      "Converts old string arrays to structured objects. Updates both Markdown and JSON. " +
      'Pass artifactType "all" to upgrade every artifact at once.',
    parameters: Type.Object({
      artifactType: Type.String({
        description: "Artifact type: goal, glossary, design, arch, data, api, test, plan, issues. Use 'all' to upgrade every artifact.",
      }),
      filePath: Type.Optional(Type.String({
        description: "Path to the markdown file (e.g. artifacts/GoalSpec.md). Not needed when artifactType is 'all'.",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const { artifactType, filePath } = params;

      if (artifactType === "all") {
        const results: Array<{ artifact: string; text: string; details: any }> = [];
        for (const art of ARTIFACT_TYPES) {
          if (art.command === "issues" || !art.mdPath) continue;
          const result = await upgradeSingleArtifact(art.command, art.mdPath, art.jsonPath, extDir, ctx);
          results.push({ artifact: art.command, text: result.text, details: result.details });
        }
        const lines = results.map(r => r.text);
        return {
          content: [{ type: "text", text: lines.join("\n\n") }],
          details: { success: true, results },
        };
      }

      const art = ARTIFACT_TYPES.find(a => a.command === artifactType);
      if (!art) {
        return {
          content: [{ type: "text", text: `Unknown artifact type: ${artifactType}` }],
          details: { success: false },
          isError: true,
        };
      }

      const mdPath = filePath || art.mdPath;
      const result = await upgradeSingleArtifact(artifactType, mdPath, art.jsonPath, extDir, ctx);

      if (result.details && result.details.error) {
        return { content: [{ type: "text", text: result.text }], details: result.details, isError: true };
      }

      return {
        content: [{ type: "text", text: result.text }],
        details: result.details,
      };
    },
  });
}
