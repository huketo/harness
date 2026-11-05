/**
 * Blind comparison judging: one packet per case holding every judged arm under
 * a shuffled label, one judge call over the whole packet, and the label-keyed
 * answer mapped back to arm keys as a CaseJudgement.
 */

import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { DISABLED_FEATURES, REVIEW_APPROVAL_POLICY, REVIEW_SANDBOX } from "../../../../codex/review";
import type { ArmJudgement, Case, CaseJudgement, Changes, RunGrading, Suite } from "../schema";
import { decodeText, readJson, readText, runMeta, writeJson, type CaseRef } from "./layout";

export const DEFAULT_JUDGE_MODEL = "gpt-6.1-sol";
export const JUDGE_EFFORT = "high";
export const MAX_FILE_BYTES = 200 * 1024;
/** Above this many screens in a packet, attach two per label instead of all. */
export const MAX_ATTACHED_IMAGES = 8;
const JUDGE_TIMEOUT_MS = 30 * 60 * 1000;
export const REDACTED = "[redacted]";

/** Names that identify a skill source regardless of the suite. */
const FIXED_TERMS = ["awesome-interface", "emilkowalski", "Emil Kowalski", ".skills"];

// ---------------------------------------------------------------- shuffle

/** FNV-1a 32-bit over `<case>#<iteration>`. */
export function judgeSeed(caseId: string, iteration: number): number {
	let h = 0x811c9dc5;
	for (const byte of new TextEncoder().encode(`${caseId}#${iteration}`)) {
		h ^= byte;
		h = Math.imul(h, 0x01000193) >>> 0;
	}
	return h >>> 0;
}

function mulberry32(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

export function shuffled<T>(items: T[], seed: number): T[] {
	const out = [...items];
	const rand = mulberry32(seed);
	for (let i = out.length - 1; i > 0; i--) {
		const j = Math.floor(rand() * (i + 1));
		[out[i], out[j]] = [out[j], out[i]];
	}
	return out;
}

/** A, B, …, Z, AA, AB, … */
export function labelName(index: number): string {
	let n = index;
	let s = "";
	do {
		s = String.fromCharCode(65 + (n % 26)) + s;
		n = Math.floor(n / 26) - 1;
	} while (n >= 0);
	return s;
}

/** Label → arm, in label order. */
export function assignLabels(arms: string[], seed: number): Record<string, string> {
	const labels: Record<string, string> = {};
	shuffled(arms, seed).forEach((arm, i) => {
		labels[labelName(i)] = arm;
	});
	return labels;
}

// ---------------------------------------------------------------- redaction

/**
 * Terms hidden from the judge: every skill directory name in the suite, the
 * fixed source names, and arm keys. Arm keys of skill-less arms and keys
 * shorter than three characters (e.g. `none`, `ai`) are not redacted as words:
 * they are ordinary words that also appear in code (`display: none`), and an
 * agent only learns its arm key through its workspace path, which is redacted
 * separately.
 */
export function redactionTerms(suite: Suite): string[] {
	const terms = new Set<string>(FIXED_TERMS);
	for (const [key, arm] of Object.entries(suite.arms)) {
		if (arm.skills.length && key.length >= 3) terms.add(key);
		for (const skill of arm.skills) {
			const name = skill.path.split("/").filter(Boolean).at(-1);
			if (name) terms.add(name);
		}
	}
	return [...terms].sort((a, b) => b.length - a.length || a.localeCompare(b));
}

const escapeRegex = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function makeRedactor(terms: string[]): (text: string) => string {
	const alt = (list: string[]) => list.map((t) => escapeRegex(t).replace(/\s+/g, "\\s+")).join("|");
	// A single plain word (`animate`, `prototype`) is also an ordinary code identifier, so it is
	// hidden only where it names a skill; compound names and the fixed terms are hidden everywhere.
	const generic = terms.filter((t) => /^[a-z]+$/.test(t) && !FIXED_TERMS.includes(t));
	const always = terms.filter((t) => !generic.includes(t));
	// Kebab-aware word boundaries: `animate` does not match inside `animated` or `emil-animate`.
	const words = always.length ? new RegExp(`(?<![A-Za-z0-9_-])(?:${alt(always)})(?![A-Za-z0-9_-])`, "gi") : null;
	const skillWord = "(?:skills?|스킬)";
	const before = generic.length
		? new RegExp(`(${skillWord}[\\s:\`'"/]*)(?:${alt(generic)})(?![A-Za-z0-9_-])`, "gi")
		: null;
	const after = generic.length
		? new RegExp(`(?<![A-Za-z0-9_.-])(?:${alt(generic)})(?=[\\s\`'"]*${skillWord})`, "gi")
		: null;
	const runPath = /\/tmp\/skill-eval\/[^\s/'"`)]+\/iteration-\d+\/[^\s/'"`)]+\/[^\s/'"`)]+\/run-\d+/g;
	const anyPath = /\/tmp\/skill-eval(?:\/[^\s'"`)]*)?/g;
	return (text) => {
		let out = text.replace(runPath, REDACTED).replace(anyPath, REDACTED);
		if (before) out = out.replace(before, `$1${REDACTED}`);
		if (after) out = out.replace(after, REDACTED);
		if (words) out = out.replace(words, REDACTED);
		return out;
	};
}

// ---------------------------------------------------------------- packet

export interface PacketScreen {
	label: string;
	/** Packet-relative path. */
	path: string;
	width: number;
	scheme: "light" | "dark";
}

export interface Packet {
	dir: string;
	seed: number;
	labels: Record<string, string>;
	screens: PacketScreen[];
	/** Packet-relative image paths to attach, in order. */
	attach: string[];
}

export interface JudgedArm {
	arm: string;
	runDir: string;
	grading: RunGrading;
}

function caseMarkdown(def: Case, labels: string[]): string {
	return [
		`# ${def.title}`,
		"",
		"## The person's request",
		"",
		def.prompt.trim(),
		"",
		"## Expectations (decide pass or fail for each, by number)",
		"",
		...def.expectations.map((e, i) => `${i + 1}. ${e}`),
		"",
		"## Rubric (score each criterion 1-5, by number)",
		"",
		...def.rubric.map((r, i) => `${i + 1}. ${r}`),
		"",
		"## Attempts",
		"",
		`Labels: ${labels.join(", ")}. Each label directory holds one attempt:`,
		"",
		"- `final.md`: the attempt's final reply to the person",
		"- `diff.patch`: unified diff of text files against the starting workspace",
		"- `changes.json`: added, modified, and deleted paths",
		"- `checks.json`: automatic checks (`pass: null` means the check could not be evaluated) and render measurements",
		"- `files/<path>`: copies of added or modified text files up to 200 KB",
		"- `screens/<entry>-<width>-<scheme>.png`: full-page renders, when the case renders a page",
		"",
	].join("\n");
}

/** Picks the 390-light and 1280-dark screens, falling back to the narrowest light and widest dark. */
function representative(screens: PacketScreen[]): PacketScreen[] {
	const light = screens.filter((s) => s.scheme === "light").sort((a, b) => a.width - b.width);
	const dark = screens.filter((s) => s.scheme === "dark").sort((a, b) => b.width - a.width);
	const picks = [
		light.find((s) => s.width === 390) ?? light[0],
		dark.find((s) => s.width === 1280) ?? dark[0],
	].filter((s): s is PacketScreen => s !== undefined);
	if (!picks.length && screens[0]) picks.push(screens[0]);
	return [...new Set(picks)];
}

/**
 * Writes the blind packet for one case into `dir`. Nothing from
 * `transcript.jsonl`, `system-append.md`, or `meta.json` is copied, and every
 * text file passes through the redactor.
 */
export function buildPacket(
	dir: string,
	def: Case,
	iteration: number,
	arms: JudgedArm[],
	redact: (text: string) => string,
): Packet {
	const seed = judgeSeed(def.id, iteration);
	const labels = assignLabels(
		arms.map((a) => a.arm),
		seed,
	);
	const byArm = new Map(arms.map((a) => [a.arm, a]));
	mkdirSync(dir, { recursive: true });
	writeFileSync(join(dir, "case.md"), redact(caseMarkdown(def, Object.keys(labels))));
	const screens: PacketScreen[] = [];
	for (const [label, arm] of Object.entries(labels)) {
		const judged = byArm.get(arm)!;
		const out = join(dir, label);
		mkdirSync(out, { recursive: true });
		const write = (name: string, text: string) => {
			const target = join(out, redact(name));
			mkdirSync(dirname(target), { recursive: true });
			writeFileSync(target, redact(text));
		};
		write("final.md", readText(join(judged.runDir, "final.md")) ?? "(no final reply was recorded)\n");
		write("diff.patch", readText(join(judged.runDir, "diff.patch")) ?? "");
		const changes = readJson<Changes>(join(judged.runDir, "changes.json"));
		write("changes.json", `${JSON.stringify(changes ?? { added: [], modified: [], deleted: [] }, null, 2)}\n`);
		write("checks.json", `${JSON.stringify(judged.grading, null, 2)}\n`);
		for (const rel of [...(changes?.added ?? []), ...(changes?.modified ?? [])].sort()) {
			const src = join(judged.runDir, "workspace", rel);
			if (!existsSync(src) || !statSync(src).isFile() || statSync(src).size > MAX_FILE_BYTES) continue;
			const text = decodeText(readFileSync(src));
			if (text !== null) write(`files/${rel}`, text);
		}
		for (const screen of judged.grading.screens) {
			const src = join(judged.runDir, screen.path);
			if (!existsSync(src)) continue;
			const name = redact(screen.path.split("/").at(-1)!);
			mkdirSync(join(out, "screens"), { recursive: true });
			copyFileSync(src, join(out, "screens", name));
			screens.push({ label, path: `${label}/screens/${name}`, width: screen.width, scheme: screen.scheme });
		}
	}
	const attach =
		screens.length <= MAX_ATTACHED_IMAGES
			? screens.map((s) => s.path)
			: Object.keys(labels).flatMap((label) =>
					representative(screens.filter((s) => s.label === label)).map((s) => s.path),
				);
	return { dir, seed, labels, screens, attach };
}

// ---------------------------------------------------------------- prompt and schema

export const JUDGE_INSTRUCTIONS =
	"You are a blind evaluator. Several anonymous attempts answered the same request from a person. Judge how well each attempt solved that request from its outcomes alone: the diff, the resulting files, the rendered screens, and the final reply. You cannot modify anything; read files with shell commands only, and only inside the current directory: do not list, search, or read anything outside it. Do not ask anyone a question.";

export function judgePrompt(packet: Packet): string {
	const labels = Object.keys(packet.labels);
	const attached = packet.attach.length
		? `Attached images, in order: ${packet.attach.join(", ")}.`
		: "No images are attached.";
	return [
		"Read `case.md` in the current directory, then every file under each label directory before deciding.",
		`Labels: ${labels.join(", ")}. ${attached} Every screen PNG is also in the packet under <label>/screens/.`,
		"",
		"Rules:",
		"- Judge results, not process. Reward what the files, screens, and reply actually deliver for the person's request. Do not reward naming a methodology, using particular vocabulary, or claiming work that the files do not show.",
		`- \`${REDACTED}\` replaces identifying names in the packet. Ignore it; it is neither a defect nor a merit.`,
		"- Automatic checks in checks.json are evidence, not verdicts; confirm them against the files and screens.",
		"- For every label and every expectation (by its number in case.md), decide pass or fail and cite evidence: a packet path with a line (for example `files/index.html:42` or `diff.patch:17`) or a screen file name. Cite paths inside the label directory without the label prefix.",
		"- For every label and every rubric criterion (by its number), give a score from 1 (poor) to 5 (excellent) with a reason.",
		"- Give each label a one-paragraph summary.",
		"- Rank all labels best first. No ties: every label appears exactly once.",
		"- Give a one-paragraph rationale for the ranking.",
		"- Write every evidence, reason, summary, and rationale in Korean. Keep label letters, file paths, and code as they are.",
		"",
		"Answer with a single JSON object that matches the provided output schema.",
	].join("\n");
}

export function judgeSchema(labels: string[], expectations: number, rubric: number): object {
	const indexes = (n: number) => Array.from({ length: n }, (_, i) => i + 1);
	const obj = (properties: Record<string, object>) => ({
		type: "object",
		additionalProperties: false,
		required: Object.keys(properties),
		properties,
	});
	return obj({
		labels: {
			type: "array",
			items: obj({
				label: { type: "string", enum: labels },
				expectations: {
					type: "array",
					items: obj({
						index: { type: "integer", enum: indexes(expectations) },
						pass: { type: "boolean" },
						evidence: { type: "string" },
					}),
				},
				rubric: {
					type: "array",
					items: obj({
						index: { type: "integer", enum: indexes(rubric) },
						score: { type: "integer", enum: [1, 2, 3, 4, 5] },
						reason: { type: "string" },
					}),
				},
				summary: { type: "string" },
			}),
		},
		ranking: { type: "array", items: { type: "string", enum: labels } },
		rationale: { type: "string" },
	});
}

interface LabelAnswer {
	label: string;
	expectations: { index: number; pass: boolean; evidence: string }[];
	rubric: { index: number; score: number; reason: string }[];
	summary: string;
}

interface JudgeAnswer {
	labels: LabelAnswer[];
	ranking: string[];
	rationale: string;
}

const isString = (v: unknown): v is string => typeof v === "string";

function exactIndexes(items: { index: unknown }[], n: number): boolean {
	const seen = items.map((i) => i.index);
	return seen.length === n && Array.from({ length: n }, (_, i) => i + 1).every((x) => seen.includes(x));
}

/**
 * Parses and validates the judge's raw answer against the case; returns the
 * arm-keyed judgement or the reason it does not fit.
 */
export function parseJudgeAnswer(
	raw: string,
	def: Case,
	packet: Pick<Packet, "labels" | "seed">,
	judgeModel: string,
): { ok: true; judgement: CaseJudgement } | { ok: false; error: string } {
	let answer: JudgeAnswer;
	try {
		const body = raw.trim().replace(/^```(?:json)?\s*\n([\s\S]*?)\n```$/, "$1");
		answer = JSON.parse(body);
	} catch (e) {
		return { ok: false, error: `not JSON: ${(e as Error).message}` };
	}
	try {
		return validateAnswer(answer, def, packet, judgeModel);
	} catch (e) {
		return { ok: false, error: `malformed answer: ${(e as Error).message}` };
	}
}

function validateAnswer(
	answer: JudgeAnswer,
	def: Case,
	packet: Pick<Packet, "labels" | "seed">,
	judgeModel: string,
): { ok: true; judgement: CaseJudgement } | { ok: false; error: string } {
	const labels = Object.keys(packet.labels);
	const errors: string[] = [];
	if (!answer || typeof answer !== "object" || !Array.isArray(answer.labels) || !Array.isArray(answer.ranking))
		return { ok: false, error: "missing labels or ranking array" };
	if (!isString(answer.rationale)) errors.push("rationale must be a string");
	const given = answer.labels.map((l) => l?.label);
	if (given.length !== labels.length || !labels.every((l) => given.includes(l)))
		errors.push(`labels must cover ${labels.join(", ")} exactly once, got ${given.join(", ")}`);
	if (answer.ranking.length !== labels.length || !labels.every((l) => answer.ranking.includes(l)))
		errors.push(`ranking must list ${labels.join(", ")} exactly once, got ${answer.ranking.join(", ")}`);
	for (const l of answer.labels) {
		const at = `label ${l?.label}`;
		if (!Array.isArray(l?.expectations) || !exactIndexes(l.expectations, def.expectations.length))
			errors.push(`${at}: expectations must cover 1..${def.expectations.length} once each`);
		else if (!l.expectations.every((e) => typeof e.pass === "boolean" && isString(e.evidence)))
			errors.push(`${at}: expectation needs boolean pass and string evidence`);
		if (!Array.isArray(l?.rubric) || !exactIndexes(l.rubric, def.rubric.length))
			errors.push(`${at}: rubric must cover 1..${def.rubric.length} once each`);
		else if (!l.rubric.every((r) => [1, 2, 3, 4, 5].includes(r.score) && isString(r.reason)))
			errors.push(`${at}: rubric score must be an integer 1-5 with a string reason`);
		if (!isString(l?.summary)) errors.push(`${at}: summary must be a string`);
	}
	if (errors.length) return { ok: false, error: errors.join("; ") };
	const perArm: Record<string, ArmJudgement> = {};
	for (const l of answer.labels) {
		const byIndex = <T extends { index: number }>(items: T[]) => [...items].sort((a, b) => a.index - b.index);
		perArm[packet.labels[l.label]] = {
			expectations: byIndex(l.expectations).map((e) => ({
				text: def.expectations[e.index - 1],
				pass: e.pass,
				evidence: e.evidence,
			})),
			rubric: byIndex(l.rubric).map((r) => ({
				criterion: def.rubric[r.index - 1],
				score: r.score as 1 | 2 | 3 | 4 | 5,
				reason: r.reason,
			})),
			summary: l.summary,
		};
	}
	return {
		ok: true,
		judgement: {
			case: def.id,
			judgeModel,
			seed: packet.seed,
			labels: packet.labels,
			ranking: answer.ranking.map((l) => packet.labels[l]),
			perArm,
			rationale: answer.rationale,
		},
	};
}

// ---------------------------------------------------------------- invocation

export interface JudgeRequest {
	packetDir: string;
	prompt: string;
	schema: object;
	/** Absolute image paths. */
	images: string[];
	model: string;
}

/** Returns the judge's final message; throws when the call itself fails. */
export type JudgeInvoker = (request: JudgeRequest) => Promise<string>;

/** `codex exec` arguments: read-only sandbox, approval `never`, the reviewer's disabled features. */
export function buildJudgeArgs(options: {
	packetDir: string;
	model: string;
	schemaFile: string;
	outputFile: string;
	images: string[];
}): string[] {
	const args = [
		"exec",
		"--sandbox",
		REVIEW_SANDBOX,
		"-c",
		`approval_policy=${JSON.stringify(REVIEW_APPROVAL_POLICY)}`,
		"-c",
		'web_search="disabled"',
		"-c",
		`model_reasoning_effort=${JSON.stringify(JUDGE_EFFORT)}`,
		"-c",
		`developer_instructions=${JSON.stringify(JUDGE_INSTRUCTIONS)}`,
		"-c",
		"agents.max_threads=1",
		"-c",
		"features.multi_agent_v2={enabled=false,max_concurrent_threads_per_session=1}",
	];
	for (const feature of DISABLED_FEATURES) if (feature !== "multi_agent_v2") args.push("--disable", feature);
	args.push(
		"--ephemeral",
		"--ignore-user-config",
		"--ignore-rules",
		"--skip-git-repo-check",
		"--color",
		"never",
		"-m",
		options.model,
		"-C",
		options.packetDir,
		"--output-schema",
		options.schemaFile,
	);
	for (const image of options.images) args.push("-i", image);
	// `-o` ends the variadic `-i` list; the prompt comes from stdin.
	args.push("-o", options.outputFile, "-");
	return args;
}

export const codexJudge: JudgeInvoker = async (request) => {
	const codex = Bun.which("codex");
	if (!codex) throw new Error("codex is not installed");
	const work = await mkdtemp(join(tmpdir(), "skill-eval-judge-io-"));
	try {
		const schemaFile = join(work, "schema.json");
		const outputFile = join(work, "last-message.json");
		writeFileSync(schemaFile, JSON.stringify(request.schema));
		const child = Bun.spawn(
			[
				codex,
				...buildJudgeArgs({
					packetDir: request.packetDir,
					model: request.model,
					schemaFile,
					outputFile,
					images: request.images,
				}),
			],
			{ cwd: request.packetDir, stdin: new Blob([request.prompt]), stdout: "ignore", stderr: "pipe" },
		);
		const stderr = new Response(child.stderr).text();
		const timer = setTimeout(() => child.kill("SIGTERM"), JUDGE_TIMEOUT_MS);
		const code = await child.exited.finally(() => clearTimeout(timer));
		let output = "";
		try {
			output = (await readFile(outputFile, "utf8")).trim();
		} catch {}
		if (code === 0 && output) return output;
		const tail = (await stderr).trim().split("\n").slice(-5).join("\n");
		throw new Error(`codex exec exited with ${code}${output ? "" : " and no output"}: ${tail}`);
	} finally {
		await rm(work, { recursive: true, force: true });
	}
};

// ---------------------------------------------------------------- case judging

export interface JudgeCaseOptions {
	caseRef: CaseRef;
	suite: Suite;
	iteration: number;
	gradings: Map<string, RunGrading>;
	model: string;
	invoke: JudgeInvoker;
	/** Which run of every arm is judged; the contract judges run 1. */
	run?: number;
	/** Called with the packet before the judge runs (tests inspect it here). */
	onPacket?: (packet: Packet) => void;
}

export type JudgeCaseResult =
	| { status: "judged"; judgement: CaseJudgement }
	| { status: "error"; error: string }
	| { status: "skipped"; reason: string };

/**
 * Judges one case: arms whose judged run has `meta.json`. Writes
 * `<case>/judge.json`, or `<case>/judge.error.json` after one retry.
 */
export async function judgeCase(options: JudgeCaseOptions): Promise<JudgeCaseResult> {
	const { caseRef, suite, iteration, model, invoke } = options;
	const k = options.run ?? 1;
	const arms: JudgedArm[] = [];
	for (const arm of caseRef.arms) {
		const run = arm.runs.find((r) => r.k === k);
		if (!run || !runMeta(run.dir)) continue;
		arms.push({ arm: arm.key, runDir: run.dir, grading: options.gradings.get(`${arm.key}/${k}`)! });
	}
	const judgeFile = join(caseRef.dir, "judge.json");
	const errorFile = join(caseRef.dir, "judge.error.json");
	if (arms.length < 2) return { status: "skipped", reason: `${arms.length} judgeable arm(s) at run-${k}` };
	const packetDir = await mkdtemp(join(tmpdir(), "skill-eval-judge-"));
	try {
		const packet = buildPacket(packetDir, caseRef.def, iteration, arms, makeRedactor(redactionTerms(suite)));
		options.onPacket?.(packet);
		const request: JudgeRequest = {
			packetDir,
			prompt: judgePrompt(packet),
			schema: judgeSchema(Object.keys(packet.labels), caseRef.def.expectations.length, caseRef.def.rubric.length),
			images: packet.attach.map((p) => join(packetDir, p)),
			model,
		};
		const attempts: { raw: string | null; error: string }[] = [];
		for (let attempt = 0; attempt < 2; attempt++) {
			let raw: string;
			try {
				raw = await invoke(request);
			} catch (e) {
				attempts.push({ raw: null, error: (e as Error).message });
				continue;
			}
			const parsed = parseJudgeAnswer(raw, caseRef.def, packet, model);
			if (parsed.ok) {
				writeJson(judgeFile, parsed.judgement);
				rmSync(errorFile, { force: true });
				return { status: "judged", judgement: parsed.judgement };
			}
			attempts.push({ raw, error: parsed.error });
		}
		rmSync(judgeFile, { force: true });
		writeJson(errorFile, { case: caseRef.def.id, judgeModel: model, labels: packet.labels, attempts });
		return { status: "error", error: attempts.map((a) => a.error).join(" | ") };
	} finally {
		await rm(packetDir, { recursive: true, force: true });
	}
}
