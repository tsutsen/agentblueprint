import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";
import { execFilePromise } from "../utils";

export function registerGenerateTests(pi: ExtensionAPI, extDir: string) {
  pi.registerTool({
    name: "generate_tests",
    label: "Generate Tests",
    description:
      "Generate TestSpec test cases for all ApiSpec functions that don't have tests yet. " +
      "Reads GoalSpec for REQ/NFR traceability. Produces structured test entries with " +
      "happy-path, edge-case, and error-path categories. Writes directly to TestSpec.json.",
    parameters: Type.Object({
      apiSpecPath: Type.Optional(Type.String({
        description: "Path to ApiSpec JSON. Default: artifacts/Api.json",
      })),
      goalSpecPath: Type.Optional(Type.String({
        description: "Path to GoalSpec JSON for REQ/NFR traceability. Default: artifacts/GoalSpec.json",
      })),
      testSpecPath: Type.Optional(Type.String({
        description: "Path to existing TestSpec JSON. Default: artifacts/Test.json",
      })),
      reqMappingPath: Type.Optional(Type.String({
        description: "Path to REQ→Fn mapping JSON. Default: artifacts/req_fn_mapping.json",
      })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      const script = path.join(extDir, "scripts/generate_tests.py");

      if (!fs.existsSync(script)) {
        return {
          content: [{ type: "text", text: `ERROR: generate_tests.py not found at ${script}` }],
          details: { success: false },
          isError: true,
        };
      }

      const args: string[] = [];
      const defaults = {
        api: "artifacts/ApiSpec.json",
        goal: "artifacts/GoalSpec.json",
        test: "artifacts/TestSpec.json",
        mapping: "artifacts/req_fn_mapping.json",
      };

      const apiPath = params.apiSpecPath || path.resolve(ctx.cwd, defaults.api);
      const goalPath = params.goalSpecPath ? path.resolve(ctx.cwd, params.goalSpecPath) : undefined;
      const testPath = params.testSpecPath ? path.resolve(ctx.cwd, params.testSpecPath) : undefined;
      const mappingPath = params.reqMappingPath ? path.resolve(ctx.cwd, params.reqMappingPath) : undefined;

      if (!fs.existsSync(apiPath)) {
        return {
          content: [{ type: "text", text: `ERROR: ApiSpec not found at ${apiPath}` }],
          details: { success: false },
          isError: true,
        };
      }
      args.push(apiPath);
      if (goalPath && fs.existsSync(goalPath)) args.push(goalPath);
      if (testPath) args.push(testPath);
      if (mappingPath && fs.existsSync(mappingPath)) args.push(mappingPath);

      try {
        const { stdout, stderr } = await execFilePromise("python", [script, ...args], {
          cwd: ctx.cwd,
          timeout: 30000,
        });
        return {
          content: [{ type: "text", text: stdout.trim() }],
          details: { success: true, output: stdout.trim(), stderr: stderr.trim() },
        };
      } catch (err: any) {
        return {
          content: [{ type: "text", text: `generate_tests failed:\n${err.stderr || err.message}` }],
          details: { success: false, error: err.stderr || err.message },
          isError: true,
        };
      }
    },
  });
}
