import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";

interface HookContext {
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown>;
  cwd: string;
}

interface HookResult {
  inject?: string;
  error?: string;
}

export async function handler(ctx: HookContext): Promise<HookResult> {
  // Gate 1: opt-in env var must be set
  if (process.env.NIGHTJAR_AUTO_VERIFY !== "1") {
    return {};
  }

  // Gate 2: extract the written file path from tool input
  const filePath =
    (ctx.tool_input.file_path as string) ||
    (ctx.tool_input.path as string) ||
    "";
  if (!filePath.endsWith(".py")) {
    return {};
  }

  // Gate 3: check for per-file opt-out marker
  const absolutePath = path.isAbsolute(filePath)
    ? filePath
    : path.join(ctx.cwd, filePath);
  try {
    const contents = fs.readFileSync(absolutePath, "utf8");
    if (contents.includes("# nightjar: skip")) {
      return {};
    }
  } catch {
    return {};
  }

  // Gate 4: look for a matching .card.md spec
  const moduleName = path.basename(filePath, ".py");
  const specPath = path.join(ctx.cwd, ".card", `${moduleName}.card.md`);
  if (!fs.existsSync(specPath)) {
    return {};
  }

  // All gates passed — run fast verification
  try {
    const cmd = `nightjar verify --fast --spec "${specPath}" --format=vscode`;
    const output = execSync(cmd, {
      cwd: ctx.cwd,
      timeout: 60_000,
      encoding: "utf8",
    });
    return {
      inject: `**Nightjar auto-verify:** ${moduleName}.py\n\`\`\`\n${output.trim()}\n\`\`\``,
    };
  } catch (err: unknown) {
    const e = err as { stdout?: string; stderr?: string; message?: string };
    const output = (e.stdout || e.stderr || e.message || "unknown error").trim();
    return {
      inject: `**Nightjar auto-verify FAILED:** ${moduleName}.py\n\`\`\`\n${output}\n\`\`\`\nRun \`nightjar explain\` for details or \`nightjar retry\` to attempt auto-fix.`,
    };
  }
}
