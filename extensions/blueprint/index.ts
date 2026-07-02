import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import path from "node:path";
import { registerInitWorkspace } from "./tools/init-workspace";
import { registerLoadArtifact } from "./tools/load-artifact";
import { registerLint } from "./tools/lint";
import { registerWriteSpecFields } from "./tools/write-spec-fields";
import { registerHandoff } from "./tools/handoff";
import { registerGenerateTests } from "./tools/generate-tests";
import { registerGenerateDiagrams } from "./tools/generate-diagrams";
import { registerGenerateArtifactMarkdown } from "./tools/generate-artifact-markdown";
import { registerGraphTools } from "./tools/graph";
import { registerGithubIssues } from "./tools/github-issues";

export default function (pi: ExtensionAPI) {
  const extDir = path.resolve(__dirname);

  registerInitWorkspace(pi);
  registerLoadArtifact(pi);
  registerLint(pi, extDir);
  registerWriteSpecFields(pi);
  registerHandoff(pi);
  registerGenerateTests(pi, extDir);
  registerGenerateDiagrams(pi, extDir);
  registerGenerateArtifactMarkdown(pi, extDir);
  registerGraphTools(pi, extDir);
  registerGithubIssues(pi);
}
