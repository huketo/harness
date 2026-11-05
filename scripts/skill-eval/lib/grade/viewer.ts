import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Case, CaseJudgement, RunGrading, RunMeta } from "../schema";
import type { Benchmark } from "./benchmark";

export interface ViewerRun {
	k: number;
	meta: RunMeta | null;
	grading: RunGrading;
	final: string | null;
	diff: string | null;
}

export interface ViewerCase {
	id: string;
	title: string;
	prompt: string;
	judgement: CaseJudgement | null;
	judgeError: boolean;
	arms: { key: string; runs: ViewerRun[] }[];
}

export const VIEWER_TEMPLATE = join(import.meta.dir, "viewer.template.html");

export function viewerCase(def: Case, rest: Omit<ViewerCase, "id" | "title" | "prompt">): ViewerCase {
	return { id: def.id, title: def.title, prompt: def.prompt, ...rest };
}

/** One self-contained HTML file; data is inlined, screens are referenced relative to the iteration dir. */
export function renderViewer(benchmark: Benchmark, cases: ViewerCase[]): string {
	const template = readFileSync(VIEWER_TEMPLATE, "utf8");
	// `<` escaped so no string can close the data <script>.
	const json = JSON.stringify({ benchmark, cases }).replace(/</g, "\\u003c");
	return template.replace("/*__DATA__*/", () => json);
}
