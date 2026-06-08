import { mkdirSync, realpathSync, constants as fsConstants } from "fs";
import {
	access as fsAccess,
	readFile as fsReadFile,
	readdir as fsReaddir,
	stat as fsStat,
} from "fs/promises";
import { resolve as resolvePath, sep as pathSep } from "path";
import express, { type Request, type Response } from "express";
import { Agent, type AgentMessage } from "@earendil-works/pi-agent-core";
import { createReadOnlyTools } from "@earendil-works/pi-coding-agent";
import {
	getModel,
	getEnvApiKey,
	registerBuiltInApiProviders,
	streamSimple,
	type KnownProvider,
} from "@earendil-works/pi-ai";

registerBuiltInApiProviders();

const PORT = parseInt(process.env.PI_SERVICE_PORT ?? "11002");
const PROVIDER = (process.env.PI_PROVIDER ?? "anthropic") as KnownProvider;
const MODEL_ID = process.env.PI_MODEL_ID ?? "claude-sonnet-4-6";
// PI_BASE_URL: ZAI/OpenAI-compatible providers üçün URL override.
// Claude, GPT, Gemini kimi provayderlərdə ignore edilir.
const ZAI_PROVIDERS = new Set(["zai", "zai-coding-cn"]);
const PI_BASE_URL = ZAI_PROVIDERS.has(PROVIDER) ? (process.env.PI_BASE_URL ?? null) : null;
const MAX_TOKENS = parseInt(process.env.PI_MAX_TOKENS ?? "8192");
const WORKSPACE = process.env.PI_WORKSPACE ?? "/workspace";
// Root directory under which per-project sandbox workspaces are extracted by
// icore-agent (see PiWorkspaceService.extract_into_sandbox). Any `workspace_dir`
// requested by a chat call MUST resolve to a path inside this root — this is
// the service-side half of the "Pi can never escape the uploaded project" bound.
// Defaults to a `projects` subfolder of the global WORKSPACE so a fresh
// deployment works without extra config.
const WORKSPACE_ROOT = process.env.PI_WORKSPACE_ROOT ?? `${WORKSPACE.replace(/[/\\]+$/, "")}/projects`;
// Max concurrent sessions — evicts oldest when limit is reached
const MAX_SESSIONS = parseInt(process.env.PI_MAX_SESSIONS ?? "500");
// Session idle TTL in ms — sessions unused longer than this are garbage collected
const SESSION_TTL_MS = parseInt(process.env.PI_SESSION_TTL_MS ?? String(30 * 60 * 1000));

// Ensure workspace directories exist at startup
mkdirSync(WORKSPACE, { recursive: true });
mkdirSync(WORKSPACE_ROOT, { recursive: true });

/**
 * Resolve and validate a per-project workspace directory requested by
 * icore-agent. Returns the canonical, contained path, or `null` if the
 * request is missing/invalid — callers should fall back to the default
 * read-only WORKSPACE in that case.
 *
 * This re-validates containment at the boundary of this service too —
 * never trust an upstream caller's path string blindly, even an internal
 * one. Symlink-aware via `realpathSync` so a crafted symlink inside an
 * extracted archive cannot be used to point the agent outside its root.
 */
function resolveSandboxWorkspace(requested: string | undefined | null): string | null {
	if (!requested || typeof requested !== "string") return null;
	const rootReal = safeRealpath(WORKSPACE_ROOT);
	let candidateReal: string;
	try {
		mkdirSync(requested, { recursive: true });
		candidateReal = realpathSync(resolvePath(requested));
	} catch {
		return null;
	}
	const isContained =
		candidateReal === rootReal || candidateReal.startsWith(rootReal + pathSep);
	if (!isContained) {
		console.warn(`[pi-src] rejected workspace_dir outside root: ${requested}`);
		return null;
	}
	return candidateReal;
}

function safeRealpath(path: string): string {
	try {
		return realpathSync(resolvePath(path));
	} catch {
		return resolvePath(path);
	}
}

/**
 * Build a containment guard bound to `rootReal` (an already-canonicalized
 * directory). Returns a function that resolves `candidate` to its real path
 * (resolving symlinks so a crafted symlink inside an extracted archive can't
 * be used to escape) and throws if it falls outside the root.
 *
 * IMPORTANT: `createReadOnlyTools(cwd, ...)` only uses `cwd` to resolve
 * *relative* paths — it happily reads/lists/greps *absolute* paths anywhere
 * on the filesystem (e.g. `/etc/passwd`, `/root/.ssh/id_rsa`). That is a
 * read-only coding-agent default, not a jail. To get an actual "Pi can never
 * leave the uploaded project" guarantee we must intercept every filesystem
 * operation the bundled tools perform and reject anything that resolves
 * outside the sandbox root — which is what the wrappers below do.
 */
function makeContainmentGuard(rootReal: string) {
	return async function assertContained(candidate: string): Promise<string> {
		const resolved = resolvePath(candidate);
		let real: string;
		try {
			real = realpathSync(resolved);
		} catch {
			// Path may not exist yet (e.g. a glob root probe) — fall back to the
			// resolved (non-canonical) form so we still bound it structurally.
			real = resolved;
		}
		const contained = real === rootReal || real.startsWith(rootReal + pathSep);
		if (!contained) {
			throw new Error(
				`Access denied: '${candidate}' resolves outside the project sandbox. ` +
					`Pi can only read files inside the uploaded project.`,
			);
		}
		return real;
	};
}

/**
 * Wrap the read-only tool set's filesystem operations so every read/list/grep/
 * find call is bound inside `sandboxRoot`. This is the actual enforcement
 * layer — `resolveSandboxWorkspace` only validates the *requested workspace
 * directory* itself, not what the agent does with it afterwards.
 */
function createSandboxedReadOnlyTools(sandboxRoot: string) {
	const rootReal = safeRealpath(sandboxRoot);
	const assertContained = makeContainmentGuard(rootReal);

	return createReadOnlyTools(sandboxRoot, {
		read: {
			operations: {
				readFile: async (path: string) => fsReadFile(await assertContained(path)),
				access: async (path: string) => fsAccess(await assertContained(path), fsConstants.R_OK),
				// Image MIME sniffing lives in the package's internal utils (not part
				// of its public export surface) — rather than reach past the package
				// boundary, we simply treat sandboxed reads as non-image content.
				// Pi can still read image files as raw bytes/text; it just won't get
				// the inline-preview treatment. Containment is what matters here.
				detectImageMimeType: async (path: string) => {
					await assertContained(path);
					return undefined;
				},
			},
		},
		grep: {
			operations: {
				isDirectory: async (path: string) => (await fsStat(await assertContained(path))).isDirectory(),
				readFile: async (path: string) => fsReadFile(await assertContained(path), "utf-8"),
			},
		},
		find: {
			operations: {
				exists: async (path: string) => {
					try {
						await fsAccess(await assertContained(path), fsConstants.F_OK);
						return true;
					} catch {
						return false;
					}
				},
				glob: async () => [],
			},
		},
		ls: {
			operations: {
				exists: async (path: string) => {
					try {
						await fsAccess(await assertContained(path), fsConstants.F_OK);
						return true;
					} catch {
						return false;
					}
				},
				stat: async (path: string) => fsStat(await assertContained(path)),
				readdir: async (path: string, options?: { withFileTypes?: boolean }) =>
					fsReaddir(await assertContained(path), options as never),
			},
		},
	});
}

// Session store: session_id → { agent, lastUsed, workspaceDir }
interface SessionEntry {
	agent: Agent;
	lastUsed: number;
	workspaceDir: string;
}
const sessions = new Map<string, SessionEntry>();

// Periodic GC: remove sessions idle longer than SESSION_TTL_MS
setInterval(() => {
	const now = Date.now();
	let removed = 0;
	for (const [id, entry] of sessions) {
		if (now - entry.lastUsed > SESSION_TTL_MS) {
			entry.agent.abort();
			sessions.delete(id);
			removed++;
		}
	}
	if (removed > 0) {
		console.log(`[pi-src] gc: removed ${removed} idle sessions, active=${sessions.size}`);
	}
}, 5 * 60 * 1000);

const app = express();
app.use(express.json({ limit: "10mb" }));

app.get("/health", (_req: Request, res: Response) => {
	res.json({ status: "ok", provider: PROVIDER, model: MODEL_ID, sessions: sessions.size });
});

interface ChatRequest {
	session_id: string;
	message: string;
	system_prompt?: string;
	history?: Array<{ role: "user" | "assistant"; content: string }>;
	// Absolute path to a per-project sandbox directory (extracted by
	// icore-agent's PiWorkspaceService). Must resolve inside WORKSPACE_ROOT —
	// validated by `resolveSandboxWorkspace`. When absent/invalid, the agent
	// falls back to the default global, read-only WORKSPACE.
	workspace_dir?: string;
}

app.post("/v1/chat", async (req: Request, res: Response) => {
	const { session_id, message, system_prompt, history, workspace_dir } = req.body as ChatRequest;
	const resolvedWorkspace = resolveSandboxWorkspace(workspace_dir) ?? WORKSPACE;
	const usingSandbox = resolvedWorkspace !== WORKSPACE;
	console.log(
		`[pi-src] chat session=${session_id} msg=${String(message).slice(0, 80)}` +
			(usingSandbox ? ` workspace=${resolvedWorkspace}` : ""),
	);

	if (!session_id || !message) {
		res.status(400).json({ error: "session_id and message are required" });
		return;
	}

	res.setHeader("Content-Type", "text/event-stream");
	res.setHeader("Cache-Control", "no-cache");
	res.setHeader("Connection", "keep-alive");
	res.flushHeaders();

	const sendEvent = (data: object) => {
		if (!res.writableEnded) {
			res.write(`data: ${JSON.stringify(data)}\n\n`);
		}
	};

	let entry = sessions.get(session_id);

	// A session is permanently bound to one tool's workspace at creation time
	// (tools are wired into the Agent's initialState). If the caller now wants
	// a different project sandbox than the session was created with, the old
	// agent must be retired and a fresh one created against the new workspace —
	// silently reusing it would let Pi keep reading the previous project.
	if (entry && entry.workspaceDir !== resolvedWorkspace) {
		console.log(
			`[pi-src] session=${session_id} switching workspace ${entry.workspaceDir} -> ${resolvedWorkspace}`,
		);
		entry.agent.abort();
		sessions.delete(session_id);
		entry = undefined;
	}

	if (!entry) {
		// Evict oldest session when at capacity
		if (sessions.size >= MAX_SESSIONS) {
			let oldestId = "";
			let oldestTime = Infinity;
			for (const [id, e] of sessions) {
				if (e.lastUsed < oldestTime) {
					oldestTime = e.lastUsed;
					oldestId = id;
				}
			}
			if (oldestId) {
				sessions.get(oldestId)?.agent.abort();
				sessions.delete(oldestId);
				console.log(`[pi-src] evicted oldest session=${oldestId}, active=${sessions.size}`);
			}
		}

		const apiKey = process.env.PI_API_KEY ?? getEnvApiKey(PROVIDER) ?? undefined;
		const modelBase = getModel(PROVIDER, MODEL_ID as never);
		const model = PI_BASE_URL ? { ...modelBase, baseUrl: PI_BASE_URL } : modelBase;

		const agent = new Agent({
			initialState: {
				systemPrompt: system_prompt ?? "",
				model,
				thinkingLevel: "off",
				// Always go through the containment-guarded tool set — even when
				// falling back to the global WORKSPACE — so every read/grep/find/ls
				// the agent performs is verified to resolve inside `resolvedWorkspace`
				// before touching the filesystem. `createReadOnlyTools(cwd)` alone
				// only uses `cwd` for *relative*-path resolution; it does not stop
				// the agent from reading absolute paths like `/etc/passwd`.
				tools: createSandboxedReadOnlyTools(resolvedWorkspace),
			},
			streamFn: (m, context, opts) =>
				streamSimple(m, context, {
					...opts,
					apiKey,
					maxTokens: MAX_TOKENS,
				}),
		});

		if (history?.length) {
			agent.state.messages = history.flatMap<AgentMessage>((msg) => {
				if (msg.role === "user") {
					return [{ role: "user", content: [{ type: "text", text: msg.content }], timestamp: Date.now() }];
				}
				return [
					{
						role: "assistant",
						content: [{ type: "text", text: msg.content }],
						api: "anthropic-messages",
						provider: PROVIDER,
						model: MODEL_ID,
						usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
						stopReason: "end_turn",
						timestamp: Date.now(),
					},
				];
			});
		}

		entry = { agent, lastUsed: Date.now(), workspaceDir: resolvedWorkspace };
		sessions.set(session_id, entry);
	} else {
		entry.lastUsed = Date.now();
	}

	const { agent } = entry;

	const unsubscribe = agent.subscribe((event) => {
		switch (event.type) {
			case "message_update":
				if (event.assistantMessageEvent.type === "text_delta") {
					sendEvent({ type: "token", text: event.assistantMessageEvent.delta });
				}
				break;
			case "tool_execution_start":
				sendEvent({ type: "tool_start", name: event.toolName, args: event.args });
				break;
			case "tool_execution_end":
				sendEvent({ type: "tool_end", name: event.toolName, is_error: event.isError });
				break;
			case "agent_end":
				unsubscribe();
				sendEvent({ type: "done" });
				if (!res.writableEnded) res.end();
				break;
		}
	});

	try {
		await agent.prompt(message);
	} catch (err: unknown) {
		unsubscribe();
		const msg = err instanceof Error ? err.message : String(err);
		sendEvent({ type: "error", message: msg });
		if (!res.writableEnded) res.end();
	}
});

app.delete("/v1/session/:id", (req: Request, res: Response) => {
	const entry = sessions.get(req.params.id);
	if (entry) {
		entry.agent.abort();
		sessions.delete(req.params.id);
	}
	res.json({ ok: true });
});

// Client disconnect → abort the running agent
app.use((req: Request, res: Response) => {
	res.on("close", () => {
		const sessionId = (req.body as ChatRequest | undefined)?.session_id;
		if (sessionId) {
			sessions.get(sessionId)?.agent.abort();
		}
	});
});

app.listen(PORT, () => {
	console.log(`pi-source-service running on port ${PORT} (${PROVIDER}/${MODEL_ID})`);
	console.log(
		`[pi-src] workspace=${WORKSPACE} workspace_root=${WORKSPACE_ROOT} max_sessions=${MAX_SESSIONS} ttl=${SESSION_TTL_MS}ms`,
	);
});
