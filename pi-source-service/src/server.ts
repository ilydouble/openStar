import archiver from "archiver";
import { mkdirSync, realpathSync, constants as fsConstants } from "fs";
import {
	access as fsAccess,
	readFile as fsReadFile,
	readdir as fsReaddir,
	stat as fsStat,
	writeFile as fsWriteFile,
	mkdir as fsMkdir,
} from "fs/promises";
import { exec as execCallback } from "child_process";
import { promisify } from "util";
import { resolve as resolvePath, sep as pathSep } from "path";
import express, { type Request, type Response } from "express";
import { Agent, type AgentMessage } from "@earendil-works/pi-agent-core";
import { createReadOnlyTools, createWriteTool, createEditTool } from "@earendil-works/pi-coding-agent";
import {
	getModel,
	getEnvApiKey,
	registerBuiltInApiProviders,
	streamSimple,
	type KnownProvider,
} from "@earendil-works/pi-ai";

registerBuiltInApiProviders();

const exec = promisify(execCallback);

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
// Max file size Pi is allowed to write/edit — guards against disk-filling attacks
const MAX_WRITE_BYTES = parseInt(process.env.PI_MAX_WRITE_BYTES ?? String(1 * 1024 * 1024)); // 1 MB default

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

// -----------------------------------------------------------
// Git helpers — used by sandboxed write/edit tools to maintain
// a per-workspace history that powers Undo and Save All.
// -----------------------------------------------------------

/**
 * Ensure the workspace has a git repo with a baseline commit so we always
 * have a parent to revert to. Idempotent — safe to call multiple times.
 */
// Git identity passed inline with every commit so no global or per-repo
// config is required — the container does not need `git config --global`.
const GIT_ID_FLAGS = `-c user.email="pi-agent@icore.local" -c user.name="Pi Agent"`;

async function ensureGitRepo(dir: string): Promise<void> {
	try {
		await exec(`git -C "${dir}" rev-parse --git-dir`);
		// repo already exists — nothing to do
	} catch {
		await exec(`git -C "${dir}" init`);
		// Baseline snapshot: commit whatever files are already there so every
		// subsequent write/edit commit has a clean parent to revert against.
		await exec(`git -C "${dir}" add -A`);
		await exec(`git ${GIT_ID_FLAGS} -C "${dir}" commit -m "pi: baseline snapshot" --allow-empty`);
		console.log(`[pi-src] git repo initialized at ${dir}`);
	}
}

/**
 * Stage all changes in `dir` and create a commit with `message`.
 * Returns the new commit hash (40-char SHA).
 */
async function gitCommit(dir: string, message: string): Promise<string> {
	await exec(`git -C "${dir}" add -A`);
	await exec(`git ${GIT_ID_FLAGS} -C "${dir}" commit -m "${message.replace(/"/g, "'")}" --allow-empty`);
	const { stdout } = await exec(`git -C "${dir}" rev-parse HEAD`);
	return stdout.trim();
}

// -----------------------------------------------------------
// Pending-change tracking — every sandboxed write/edit records
// a PendingChange so the frontend can show Undo / Save All.
// -----------------------------------------------------------

interface PendingChange {
	changeId: string;
	/** Relative path inside the sandbox, for display purposes */
	path: string;
	/** Full absolute path — needed for targeted undo */
	absolutePath: string;
	/** Git commit hash created right after this write/edit */
	commitHash: string;
	/** Tool that produced this change: "write" or "edit" */
	tool: "write" | "edit";
	/** File size in bytes at write time */
	bytes: number;
	/** Unix ms timestamp of the change */
	changedAt: number;
	/**
	 * When the user clicked "Save All": Unix ms timestamp (> 0).
	 * 0 = still undoable. The frontend hides Undo once this is set.
	 */
	savedAt: number;
}

/**
 * A mutable ref that lets the tool operations notify the currently-open SSE
 * stream about file changes without baking a specific `sendEvent` closure
 * into the agent's tools at creation time (which would go stale across chat
 * calls on the same long-lived session).
 */
interface NotifyRef {
	current: (change: PendingChange) => void;
}

/**
 * Create sandboxed write+edit+read-only tools for a project workspace.
 * Every write/edit is:
 *   1. Validated with `assertContained` (no sandbox escape)
 *   2. Size-checked (MAX_WRITE_BYTES)
 *   3. Written to disk
 *   4. Committed to the workspace's local git repo
 *   5. Reported back via `notifyRef.current` so the SSE stream can push
 *      a `file_changed` event to the frontend in real time.
 *
 * `notifyRef` is a mutable ref rather than a plain callback so it can be
 * updated at the start of every chat request without recreating the agent.
 */
function createSandboxedCodingTools(sandboxRoot: string, notifyRef: NotifyRef) {
	const rootReal = safeRealpath(sandboxRoot);
	const assertContained = makeContainmentGuard(rootReal);

	/** Build a short relative path for display / git messages */
	const relPath = (absolutePath: string): string =>
		absolutePath.replace(rootReal, "").replace(/^[/\\]/, "") || absolutePath;

	/** Shared write-then-commit logic used by both write and edit tools */
	const writeAndCommit = async (
		absolutePath: string,
		content: string,
		tool: "write" | "edit",
	): Promise<void> => {
		const bytes = Buffer.byteLength(content, "utf-8");
		if (bytes > MAX_WRITE_BYTES) {
			throw new Error(
				`${tool} denied: content ${bytes} bytes exceeds the ${MAX_WRITE_BYTES}-byte limit per file.`,
			);
		}
		await fsWriteFile(absolutePath, content, "utf-8");
		const rel = relPath(absolutePath);
		const commitHash = await gitCommit(sandboxRoot, `pi: ${tool} ${rel}`);
		const change: PendingChange = {
			changeId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
			path: rel,
			absolutePath,
			commitHash,
			tool,
			bytes,
			changedAt: Date.now(),
			savedAt: 0,
		};
		console.log(`[pi-src] ${tool} path=${rel} bytes=${bytes} commit=${commitHash.slice(0, 8)}`);
		notifyRef.current(change);
	};

	// Build tool set: read + grep + find + ls (read-only, containment-guarded)
	// plus write + edit (sandboxed with git-commit tracking).
	// Bash is intentionally excluded — it cannot be safely sandboxed without
	// a container boundary and would bypass all containment guards.
	const readOnlyTools = createReadOnlyTools(sandboxRoot, {
		read: {
			operations: {
				readFile: async (path: string) => fsReadFile(await assertContained(path)),
				access: async (path: string) => fsAccess(await assertContained(path), fsConstants.R_OK),
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

	const writeTool = createWriteTool(sandboxRoot, {
		operations: {
			writeFile: async (path: string, content: string): Promise<void> => {
				const safePath = await assertContained(path);
				await writeAndCommit(safePath, content, "write");
			},
			mkdir: async (dir: string): Promise<void> => {
				await assertContained(dir);
				await fsMkdir(dir, { recursive: true });
			},
		},
	});

	const editTool = createEditTool(sandboxRoot, {
		operations: {
			readFile: async (path: string): Promise<Buffer> => fsReadFile(await assertContained(path)),
			writeFile: async (path: string, content: string): Promise<void> => {
				const safePath = await assertContained(path);
				await writeAndCommit(safePath, content, "edit");
			},
			access: async (path: string): Promise<void> =>
				fsAccess(await assertContained(path), fsConstants.R_OK | fsConstants.W_OK),
		},
	});

	return [...readOnlyTools, writeTool, editTool];
}

// -----------------------------------------------------------
// Session store
// -----------------------------------------------------------

interface SessionEntry {
	agent: Agent;
	lastUsed: number;
	workspaceDir: string;
	/**
	 * All write/edit changes recorded in this session, keyed by changeId.
	 * Persists across multiple chat turns so Undo / Save All work at any time
	 * until the session is evicted.
	 */
	pendingChanges: Map<string, PendingChange>;
	/**
	 * Mutable ref updated at the start of every chat request so tool callbacks
	 * always reach the current SSE response stream without recreating the agent.
	 */
	notifyRef: NotifyRef;
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

		// notifyRef starts as a no-op; it is replaced below (and on every
		// subsequent chat call) so the tool callbacks always reach the live SSE stream.
		const notifyRef: NotifyRef = { current: () => {} };

		// When a sandbox workspace is present, use the full coding tool set
		// (read + write + edit + grep + find + ls) with containment guards and
		// automatic git commits. Without a sandbox we fall back to the read-only
		// set so Pi cannot write to arbitrary filesystem locations.
		const tools = usingSandbox
			? createSandboxedCodingTools(resolvedWorkspace, notifyRef)
			: createSandboxedReadOnlyTools(resolvedWorkspace);

		// Initialize git repo for the sandbox workspace so the first write/edit
		// always has a clean baseline commit to revert against.
		if (usingSandbox) {
			ensureGitRepo(resolvedWorkspace).catch((err) =>
				console.warn(`[pi-src] git init failed for ${resolvedWorkspace}: ${err}`),
			);
		}

		const agent = new Agent({
			initialState: {
				systemPrompt: system_prompt ?? "",
				model,
				thinkingLevel: "off",
				tools,
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

		entry = {
			agent,
			lastUsed: Date.now(),
			workspaceDir: resolvedWorkspace,
			pendingChanges: new Map(),
			notifyRef,
		};
		sessions.set(session_id, entry);
	} else {
		entry.lastUsed = Date.now();
	}

	// Wire the current SSE stream into the notifyRef so write/edit tool callbacks
	// reach this response. Each chat call refreshes the ref — the agent and its
	// tools are reused, but they always call through the ref to the live stream.
	entry.notifyRef.current = (change: PendingChange) => {
		entry!.pendingChanges.set(change.changeId, change);
		sendEvent({ type: "file_changed", change });
	};

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

	// Timeout: if the LLM provider does not respond within PI_REQUEST_TIMEOUT_MS
	// the stream is killed with a user-visible error instead of hanging forever.
	const REQUEST_TIMEOUT_MS = parseInt(process.env.PI_REQUEST_TIMEOUT_MS ?? String(90 * 1000));
	const timeoutHandle = setTimeout(() => {
		unsubscribe();
		agent.abort();
		sendEvent({ type: "error", message: `LLM provider did not respond within ${REQUEST_TIMEOUT_MS / 1000}s. Please try again.` });
		if (!res.writableEnded) res.end();
		console.warn(`[pi-src] request timeout session=${session_id} after ${REQUEST_TIMEOUT_MS}ms`);
	}, REQUEST_TIMEOUT_MS);

	try {
		await agent.prompt(message);
		clearTimeout(timeoutHandle);
	} catch (err: unknown) {
		clearTimeout(timeoutHandle);
		unsubscribe();
		const msg = err instanceof Error ? err.message : String(err);
		sendEvent({ type: "error", message: msg });
		if (!res.writableEnded) res.end();
	}
});

// -----------------------------------------------------------
// Undo endpoint — revert a single file change identified by changeId.
// Uses `git checkout <parentHash> -- <relPath>` to restore the file to its
// state before that specific commit, then creates a new "revert" commit.
// -----------------------------------------------------------
app.post("/v1/session/:id/undo/:changeId", async (req: Request, res: Response) => {
	const entry = sessions.get(req.params.id);
	if (!entry) {
		res.status(404).json({ error: "Session not found" });
		return;
	}
	const change = entry.pendingChanges.get(req.params.changeId);
	if (!change) {
		res.status(404).json({ error: "Change not found" });
		return;
	}
	if (change.savedAt > 0) {
		res.status(409).json({ error: "Change has already been saved and can no longer be undone" });
		return;
	}

	try {
		const dir = entry.workspaceDir;
		// Restore the file to the content it had in the parent commit
		await exec(`git -C "${dir}" checkout "${change.commitHash}^" -- "${change.path}"`);
		const undoHash = await gitCommit(dir, `pi: undo ${change.tool} ${change.path}`);
		entry.pendingChanges.delete(change.changeId);
		console.log(`[pi-src] undo changeId=${change.changeId} path=${change.path} undoCommit=${undoHash.slice(0, 8)}`);
		res.json({ ok: true, undoCommit: undoHash });
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		console.error(`[pi-src] undo failed changeId=${change.changeId}: ${msg}`);
		res.status(500).json({ error: `Undo failed: ${msg}` });
	}
});

// -----------------------------------------------------------
// Save All endpoint — mark all current pending changes as permanent.
// The files are already committed to the local git repo; this just sets
// `savedAt` on each change so the frontend knows to hide the Undo buttons.
// -----------------------------------------------------------
app.post("/v1/session/:id/save-all", (req: Request, res: Response) => {
	const entry = sessions.get(req.params.id);
	if (!entry) {
		res.status(404).json({ error: "Session not found" });
		return;
	}

	const now = Date.now();
	let count = 0;
	for (const change of entry.pendingChanges.values()) {
		if (change.savedAt === 0) {
			change.savedAt = now;
			count++;
		}
	}
	console.log(`[pi-src] save-all session=${req.params.id} savedChanges=${count}`);
	res.json({ ok: true, savedChanges: count });
});

// -----------------------------------------------------------
// List pending changes for a session — lets the frontend reconstruct
// state after a page refresh (changes survive until session TTL).
// -----------------------------------------------------------
app.get("/v1/session/:id/changes", (req: Request, res: Response) => {
	const entry = sessions.get(req.params.id);
	if (!entry) {
		res.status(404).json({ error: "Session not found" });
		return;
	}
	res.json({ changes: Array.from(entry.pendingChanges.values()) });
});

// -----------------------------------------------------------
// Download endpoint — stream the entire workspace as a ZIP archive.
// The .git directory is excluded so the user receives clean source files.
// -----------------------------------------------------------
app.get("/v1/session/:id/download", async (req: Request, res: Response) => {
	const entry = sessions.get(req.params.id);
	if (!entry) {
		res.status(404).json({ error: "Session not found" });
		return;
	}

	const dir = entry.workspaceDir;
	// Use the leaf directory name as the base for the downloaded filename
	const leafName = dir.split("/").filter(Boolean).pop() ?? "workspace";
	const filename = `pi-workspace-${leafName}.zip`;

	res.setHeader("Content-Type", "application/zip");
	res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);

	const archive = archiver("zip", { zlib: { level: 6 } });

	archive.on("error", (err) => {
		console.error(`[pi-src] download archive error: ${err.message}`);
		// Headers already sent — can't change status; just end the stream
		if (!res.headersSent) res.status(500).json({ error: err.message });
		else res.end();
	});

	archive.pipe(res);
	// Include all files recursively, excluding .git (internal change-tracking history)
	archive.glob("**/*", { cwd: dir, dot: true, ignore: [".git/**", ".git"] });
	await archive.finalize();
	console.log(`[pi-src] download session=${req.params.id} workspace=${dir}`);
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
		`[pi-src] workspace=${WORKSPACE} workspace_root=${WORKSPACE_ROOT} max_sessions=${MAX_SESSIONS} ttl=${SESSION_TTL_MS}ms max_write_bytes=${MAX_WRITE_BYTES}`,
	);
});
