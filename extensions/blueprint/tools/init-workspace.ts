import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { execFilePromise, resolvePackagePaths } from "../utils";

export function registerInitWorkspace(pi: ExtensionAPI) {
  pi.registerTool({
    name: "init_workspace",
    label: "Init Workspace",
    description:
      "Create the artifacts and tasks directory structure and " +
      "pre-create all artifact " +
      "Markdown files with frontmatter, and install python dependencies. " +
      "Safe to run multiple times — skips existing files.",
    parameters: Type.Object({
      force: Type.Optional(Type.Boolean({
        description:
          "Overwrite existing skills and artifact files instead of skipping them.",
      })),
    }),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      const cwd = ctx.cwd;
      const pkgPaths = resolvePackagePaths(cwd);
      const schemasSrc = pkgPaths.schemasSrc;

      // 1. Create directories
      const dirs = [
        path.resolve(cwd, "artifacts"),
        path.resolve(cwd, "tasks"),
        path.resolve(cwd, "tasks/epics"),
        path.resolve(cwd, "tasks/reviews"),
      ];
      for (const d of dirs) {
        fs.mkdirSync(d, { recursive: true });
      }

      // 2. Pre-create artifact files with frontmatter
      const artifactDefs: Array<{ name: string; file: string }> = [
        { name: "GoalSpec", file: "GoalSpec.md" },
        { name: "Glossary", file: "Glossary.md" },
        { name: "DesignSpec", file: "DesignSpec.md" },
        { name: "ArchitectureSpec", file: "ArchitectureSpec.md" },
        { name: "DataSpec", file: "DataSpec.md" },
        { name: "ApiSpec", file: "ApiSpec.md" },
        { name: "TestSpec", file: "TestSpec.md" },
      ];

      function extractSections(schemaPath: string): string[] {
        if (!fs.existsSync(schemaPath)) return [];
        const content = fs.readFileSync(schemaPath, "utf-8");
        const headingRegex = /^###\s+(.+)$/gm;
        const all: string[] = [];
        let m: RegExpExecArray | null;
        while ((m = headingRegex.exec(content)) !== null) {
          const name = m[1].trim();
          if (name.toLowerCase().includes("confirmation gate")) continue;
          if (/^Stage\s+\d/.test(name)) continue;
          all.push(name);
        }
        return all;
      }

      const created: string[] = [];
      const skippedArtifacts: string[] = [];

      if (fs.existsSync(schemasSrc)) {
        for (const def of artifactDefs) {
          const schemaPath = path.join(schemasSrc, def.file);
          const artifactPath = path.resolve(cwd, "artifacts", def.file);

          let artifactName = def.name;
          if (fs.existsSync(schemaPath)) {
            const schemaContent = fs.readFileSync(schemaPath, "utf-8");
            const nameMatch = schemaContent.match(/^---\nname:\s*(.+?)\n/m);
            if (nameMatch) {
              artifactName = nameMatch[1].trim();
            }
          }

          const pendingSections = extractSections(schemaPath);

          const fmLines: string[] = ["---"];
          fmLines.push(`artifact: ${artifactName}`);
          fmLines.push("status: in_progress");
          fmLines.push("sections_complete: []");
          if (pendingSections.length > 0) {
            fmLines.push("sections_pending:");
            for (const s of pendingSections) {
              fmLines.push(`  - ${s}`);
            }
          } else {
            fmLines.push("sections_pending: []");
          }
          fmLines.push("---");

          const fm = fmLines.join("\n") + "\n";

          if (fs.existsSync(artifactPath) && !_params.force) {
            skippedArtifacts.push(def.file);
          } else {
            fs.writeFileSync(artifactPath, fm, "utf-8");
            created.push(def.file);
          }
        }
      }

      // 4. Validate artifact filenames against expected naming convention
      const artifactsDir = path.resolve(cwd, 'artifacts');
      const expectedJsonNames = artifactDefs.map(d => `${d.file.replace('.md', '.json')}`);
      const expectedMdNames = artifactDefs.map(d => d.file);
      const mismatches: Array<{
        current: string;
        expected: string;
        reason: string;
      }> = [];

      if (fs.existsSync(artifactsDir)) {
        const existingJsonFiles = fs.readdirSync(artifactsDir)
          .filter(f => f.endsWith('.json') && !f.endsWith('.schema.json'));

        for (const jsonFile of existingJsonFiles) {
          if (expectedJsonNames.includes(jsonFile)) continue;
          const baseName = jsonFile.replace(/\.json$/, '');
          const mdWithSpec = baseName + 'Spec.md';
          const mdWithoutSpec = baseName + '.md';
          const actualMd = expectedMdNames.includes(mdWithSpec) ? mdWithSpec
            : expectedMdNames.includes(mdWithoutSpec) ? mdWithoutSpec
            : null;

          if (actualMd) {
            const expectedJson = actualMd.replace('.md', '.json');
            if (expectedJsonNames.includes(expectedJson) && jsonFile !== expectedJson) {
              mismatches.push({
                current: jsonFile,
                expected: expectedJson,
                reason: `JSON uses "${baseName}" but corresponding "${actualMd}" expects "${expectedJson}"`,
              });
            }
          }
        }
      }

      // 5. Install python dependencies
      let pipOutput = '';
      let pipSuccess = false;
      const venvPython = path.resolve(cwd, '.venv/bin/pip');
      const pipCmd = fs.existsSync(venvPython) ? venvPython : 'pip';
      try {
        const { stdout, stderr } = await execFilePromise(
          pipCmd, ['install', 'jsonschema'],
          { timeout: 30000, cwd },
        );
        pipOutput = stdout || stderr || '';
        pipSuccess = true;
      } catch {
        pipOutput = 'jsonschema installation failed — linting may not work without it.';
      }

      // 6. Rename mismatched files
      const renamed: Array<{ from: string; to: string }> = [];
      for (const m of mismatches) {
        const fromPath = path.join(artifactsDir, m.current);
        const toPath = path.join(artifactsDir, m.expected);
        fs.renameSync(fromPath, toPath);
        renamed.push({ from: m.current, to: m.expected });
      }

      // 7. Report
      const lines: string[] = [
        `Workspace initialized:`,
        ...dirs.map((d) => `  ✓ ${path.relative(cwd, d)}/`),
      ];

      if (created.length > 0) {
        lines.push(`  ✓ artifact files created: ${created.join(", ")}`);
      }
      if (skippedArtifacts.length > 0) {
        lines.push(`  • artifact files skipped (already exist): ${skippedArtifacts.join(", ")}`);
      }
      if (created.length === 0 && skippedArtifacts.length === 0) {
        lines.push(`  • artifact files already present — use force:true to overwrite`);
      }

      lines.push(`  ✓ python deps: jsonschema ${pipSuccess ? 'installed' : '⚠ install failed'}`);
      if (pipOutput) {
        const firstLine = pipOutput.split('\n')[0]?.trim();
        if (firstLine) lines.push(`    ${firstLine}`);
      }

      if (renamed.length > 0) {
        lines.push(`  ✓ renamed ${renamed.length} file(s) to standard naming:`);
        for (const r of renamed) {
          lines.push(`    ${r.from} → ${r.expected}`);
        }
      } else if (mismatches.length > 0) {
        lines.push(`  ⚠ ${mismatches.length} filename mismatch(es) detected and auto-renamed`);
      }

      return {
        content: [{ type: "text", text: lines.join('\n') }],
        details: {
          dirs_created: dirs.filter((d) => fs.existsSync(d)),
          artifacts_created: created,
          artifacts_skipped: skippedArtifacts,
          pipSuccess,
          mismatches: mismatches.length > 0 ? mismatches : undefined,
          renamed,
        },
      };
    },
  });
}
