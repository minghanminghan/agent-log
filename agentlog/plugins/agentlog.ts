/**
 * agentlog OpenCode plugin
 *
 * Subscribes to OpenCode events and shells out to `agentlog hook <event>`,
 * passing JSON payloads on stdin — reusing the same hook subcommands that
 * the Claude Code integration uses.
 *
 * Written by `agentlog init` to `.opencode/plugins/agentlog.ts`.
 * Remove with `agentlog stop --agent opencode`.
 */

import { definePlugin } from "opencode/plugin";
import { spawnSync } from "child_process";

function runHook(subcommand: string, payload: Record<string, unknown>): void {
  try {
    const result = spawnSync("agentlog", ["hook", subcommand], {
      input: JSON.stringify(payload),
      encoding: "utf-8",
      timeout: 10000,
    });
    if (result.stderr) {
      console.error(`[agentlog] ${subcommand}:`, result.stderr.trim());
    }
  } catch (err) {
    console.error(`[agentlog] ${subcommand}: unexpected error:`, err);
  }
}

export default definePlugin({
  name: "agentlog",

  init(app) {
    // Track whether we have sent the first user-prompt for this session
    const seenSessions = new Set<string>();

    app.on("tool.execute.before", (event) => {
      const { sessionId, toolName, toolInput, storageDir } = event;

      // On first event for this session, fire user-prompt hook if prompt available
      if (!seenSessions.has(sessionId)) {
        seenSessions.add(sessionId);
        const prompt: string = event.userMessage ?? "";
        if (prompt) {
          runHook("user-prompt", {
            session_id: sessionId,
            transcript_path: storageDir,
            prompt,
          });
        }
      }

      runHook("pre-tool", {
        session_id: sessionId,
        transcript_path: storageDir,
        tool_name: toolName,
        tool_input: toolInput ?? {},
      });
    });

    app.on("tool.execute.after", (event) => {
      const { sessionId, toolName, toolInput, toolOutput, storageDir } = event;

      runHook("post-tool", {
        session_id: sessionId,
        transcript_path: storageDir,
        tool_name: toolName,
        tool_input: toolInput ?? {},
        tool_response: { output: toolOutput ?? "" },
      });
    });

    app.on("session.idle", (event) => {
      const { sessionId, storageDir } = event;

      runHook("stop", {
        session_id: sessionId,
        transcript_path: storageDir,
        stop_reason: "idle",
      });
    });
  },
});
