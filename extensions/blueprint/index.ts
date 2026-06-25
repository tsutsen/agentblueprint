import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import path from "node:path";
import { registerInitWorkspace } from "./tools/init-workspace";
import { registerLoadArtifact } from "./tools/load-artifact";
import { registerLint } from "./tools/lint";
import { registerUpdateFrontmatter } from "./tools/update-frontmatter";
import { registerWriteSection } from "./tools/write-section";
import { registerHandoff } from "./tools/handoff";
import { registerGenerateTests } from "./tools/generate-tests";
import { registerGenerateDiagrams } from "./tools/generate-diagrams";
import { registerGenerateArtifactMarkdown } from "./tools/generate-artifact-markdown";
import { registerSpecUpgrade } from "./tools/spec-upgrade";
import { registerGraphMetrics } from "./tools/graph-metrics";
import { registerGraphVisualize } from "./tools/graph-visualize";

export default function (pi: ExtensionAPI) {
  const extDir = path.resolve(__dirname);

  registerInitWorkspace(pi);
  registerLoadArtifact(pi);
  registerLint(pi, extDir);
  registerUpdateFrontmatter(pi);
  registerWriteSection(pi);
  registerHandoff(pi);
  registerGenerateTests(pi, extDir);
  registerGenerateDiagrams(pi, extDir);
  registerGenerateArtifactMarkdown(pi, extDir);
  registerSpecUpgrade(pi, extDir);
  registerGraphMetrics(pi, extDir);
  registerGraphVisualize(pi, extDir);
}
