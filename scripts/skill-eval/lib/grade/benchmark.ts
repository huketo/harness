/**
 * Iteration-wide aggregation: `benchmark.json` (numbers) and `benchmark.md`
 * (the Korean report a person reads to decide what to take from upstream).
 * Nothing here invents a score: a case without a judgement contributes no
 * judged numbers.
 */

import type { Case, CaseJudgement, IterationMeta, RunGrading, RunMeta, Suite } from "../schema";

export interface RunData {
	k: number;
	meta: RunMeta | null;
	grading: RunGrading;
}

export interface CaseData {
	def: Case;
	arms: { key: string; runs: RunData[] }[];
	judgement: CaseJudgement | null;
	judgeError: boolean;
}

export interface Ratio {
	passed: number;
	total: number;
	rate: number | null;
}

export interface ArmStats {
	arm: string;
	cases: number;
	judgedCases: number;
	expectations: Ratio;
	rubricMean: number | null;
	checks: Ratio & { nulls: number };
	firstPlaces: number;
	meanRank: number | null;
	meanSecs: number | null;
	meanOutputTokens: number | null;
	costUsd: number | null;
	runs: number;
	failed: number;
	timedOut: number;
}

export interface CaseArmRow {
	arm: string;
	judged: boolean;
	expectations: { passed: number; total: number } | null;
	rubricMean: number | null;
	checks: { passed: number; evaluated: number };
	rank: number | null;
}

export interface CaseRow {
	case: string;
	title: string;
	judged: boolean;
	judgeError: boolean;
	judgeModel: string | null;
	labels: Record<string, string> | null;
	arms: CaseArmRow[];
}

export interface Comparison {
	case: string;
	focus: string;
	other: string;
	/** focus rubric mean − other rubric mean. */
	rubricDiff: number | null;
	result: "win" | "loss" | null;
}

export interface ComparisonSummary {
	focus: string;
	other: string;
	cases: number;
	wins: number;
	losses: number;
	meanRubricDiff: number | null;
}

export interface Benchmark {
	suite: string;
	iteration: number;
	generatedAt: string;
	meta: Pick<
		IterationMeta,
		"harnessCommit" | "model" | "effort" | "runs" | "sources" | "localRefs" | "createdAt" | "suiteVersion"
	>;
	judgeModels: string[];
	focusArms: string[];
	perArm: ArmStats[];
	perCase: CaseRow[];
	comparisons: Comparison[];
	comparisonSummary: ComparisonSummary[];
	limitations: string[];
}

const mean = (xs: number[]): number | null => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const ratio = (passed: number, total: number): Ratio => ({ passed, total, rate: total ? passed / total : null });

/** Arms whose skills include a local (this repository's) skill: the arms under study. */
export function focusArms(suite: Suite): string[] {
	return Object.entries(suite.arms)
		.filter(([, arm]) => arm.skills.some((s) => s.source === "local"))
		.map(([key]) => key);
}

function armRubricMean(j: CaseJudgement, arm: string): number | null {
	const per = j.perArm[arm];
	return per ? mean(per.rubric.map((r) => r.score)) : null;
}

function rankOf(j: CaseJudgement, arm: string): number | null {
	const i = j.ranking.indexOf(arm);
	return i >= 0 ? i + 1 : null;
}

function checkCounts(runs: RunData[]) {
	const all = runs.flatMap((r) => r.grading.checks);
	const evaluated = all.filter((c) => c.pass !== null);
	return { passed: evaluated.filter((c) => c.pass).length, evaluated: evaluated.length, nulls: all.length - evaluated.length };
}

export function aggregate(
	suite: Suite,
	meta: IterationMeta,
	cases: CaseData[],
	options: { judgeModel: string; generatedAt?: string },
): Benchmark {
	const order = Object.keys(suite.arms).filter((key) => cases.some((c) => c.arms.some((a) => a.key === key)));
	const perArm: ArmStats[] = order.map((arm) => {
		const mine = cases.filter((c) => c.arms.some((a) => a.key === arm));
		const runs = mine.flatMap((c) => c.arms.find((a) => a.key === arm)!.runs);
		const judged = mine.map((c) => c.judgement).filter((j): j is CaseJudgement => !!j?.perArm[arm]);
		const exps = judged.flatMap((j) => j.perArm[arm].expectations);
		const scores = judged.flatMap((j) => j.perArm[arm].rubric.map((r) => r.score));
		const ranks = judged.map((j) => rankOf(j, arm)).filter((r): r is number => r !== null);
		const metas = runs.map((r) => r.meta).filter((m): m is RunMeta => m !== null);
		const costs = metas.map((m) => m.costUsd).filter((c): c is number => c !== null);
		const checks = checkCounts(runs);
		return {
			arm,
			cases: mine.length,
			judgedCases: judged.length,
			expectations: ratio(exps.filter((e) => e.pass).length, exps.length),
			rubricMean: mean(scores),
			checks: { ...ratio(checks.passed, checks.evaluated), nulls: checks.nulls },
			firstPlaces: judged.filter((j) => j.ranking[0] === arm).length,
			meanRank: mean(ranks),
			meanSecs: mean(metas.map((m) => m.secs)),
			meanOutputTokens: mean(metas.filter((m) => m.usage).map((m) => m.usage!.outputTokens)),
			costUsd: costs.length ? costs.reduce((a, b) => a + b, 0) : null,
			runs: runs.length,
			failed: runs.filter((r) => !r.meta || (r.meta.rc !== 0 && !r.meta.timedOut)).length,
			timedOut: metas.filter((m) => m.timedOut).length,
		};
	});

	const perCase: CaseRow[] = cases.map((c) => {
		const j = c.judgement;
		return {
			case: c.def.id,
			title: c.def.title,
			judged: !!j,
			judgeError: c.judgeError,
			judgeModel: j?.judgeModel ?? null,
			labels: j?.labels ?? null,
			arms: c.arms.map((a) => {
				const per = j?.perArm[a.key];
				const { passed, evaluated } = checkCounts(a.runs);
				return {
					arm: a.key,
					judged: !!per,
					expectations: per
						? { passed: per.expectations.filter((e) => e.pass).length, total: per.expectations.length }
						: null,
					rubricMean: j && per ? armRubricMean(j, a.key) : null,
					checks: { passed, evaluated },
					rank: j && per ? rankOf(j, a.key) : null,
				};
			}),
		};
	});

	const focus = focusArms(suite);
	const comparisons: Comparison[] = [];
	for (const c of cases) {
		for (const f of focus) {
			if (!c.arms.some((a) => a.key === f)) continue;
			for (const other of c.arms.map((a) => a.key).filter((k) => k !== f)) {
				const j = c.judgement;
				const fr = j ? rankOf(j, f) : null;
				const or = j ? rankOf(j, other) : null;
				const fm = j ? armRubricMean(j, f) : null;
				const om = j ? armRubricMean(j, other) : null;
				comparisons.push({
					case: c.def.id,
					focus: f,
					other,
					rubricDiff: fm !== null && om !== null ? fm - om : null,
					result: fr !== null && or !== null ? (fr < or ? "win" : "loss") : null,
				});
			}
		}
	}
	const comparisonSummary: ComparisonSummary[] = [];
	for (const f of focus) {
		for (const other of order.filter((k) => k !== f)) {
			const rows = comparisons.filter((r) => r.focus === f && r.other === other && r.result !== null);
			if (!comparisons.some((r) => r.focus === f && r.other === other)) continue;
			comparisonSummary.push({
				focus: f,
				other,
				cases: rows.length,
				wins: rows.filter((r) => r.result === "win").length,
				losses: rows.filter((r) => r.result === "loss").length,
				meanRubricDiff: mean(rows.map((r) => r.rubricDiff).filter((d): d is number => d !== null)),
			});
		}
	}

	const judgeModels = [...new Set(cases.map((c) => c.judgement?.judgeModel).filter((m): m is string => !!m))];
	const unjudged = perCase.filter((c) => !c.judged).length;
	const limitations = [
		`표본: case ${cases.length}개, arm당 case마다 run ${meta.runs}회이며 판정은 각 arm의 run-1만 사용했습니다. 통계 검정은 하지 않았으므로 작은 차이는 우연일 수 있습니다.`,
		`판정자: 단일 모델(${judgeModels.join(", ") || options.judgeModel})의 단일 판정이며, 여러 판정자의 합의나 판정 반복은 하지 않았습니다.`,
		"자동 트리거 미측정: 스킬은 작업공간에 미리 놓였을 뿐이므로, 에이전트가 요청만 보고 스킬을 스스로 찾아 쓰는지는 측정하지 않았습니다.",
		"블라인드 경계: 판정자는 Codex 읽기 전용 sandbox에서 판정 패킷을 cwd로 실행되지만, 이 sandbox는 패킷 밖 파일 읽기를 막지 않습니다. 원본 run 디렉터리를 찾아보지 말라는 제한은 지시로만 걸려 있습니다.",
		...(unjudged ? [`판정 없음: case ${unjudged}개는 판정 결과가 없어서 판정 기반 수치에서 빠졌습니다.`] : []),
	];

	return {
		suite: suite.suite,
		iteration: meta.iteration,
		generatedAt: options.generatedAt ?? new Date().toISOString(),
		meta: {
			harnessCommit: meta.harnessCommit,
			model: meta.model,
			effort: meta.effort,
			runs: meta.runs,
			sources: meta.sources,
			localRefs: meta.localRefs,
			createdAt: meta.createdAt,
			suiteVersion: meta.suiteVersion,
		},
		judgeModels,
		focusArms: focus,
		perArm,
		perCase,
		comparisons,
		comparisonSummary,
		limitations,
	};
}

// ---------------------------------------------------------------- markdown

const NO_JUDGE = "판정 없음";
const dash = "–";
const fixed = (n: number | null, digits = 2) => (n === null ? dash : n.toFixed(digits));
const pct = (r: Ratio) => (r.rate === null ? dash : `${(r.rate * 100).toFixed(0)}% (${r.passed}/${r.total})`);
const signed = (n: number | null) => (n === null ? dash : `${n > 0 ? "+" : ""}${n.toFixed(2)}`);
const cell = (s: string) => s.replace(/\|/g, "\\|").replace(/\n/g, " ");

function table(head: string[], rows: string[][]): string[] {
	return [
		`| ${head.join(" | ")} |`,
		`| ${head.map(() => "---").join(" | ")} |`,
		...rows.map((r) => `| ${r.map(cell).join(" | ")} |`),
	];
}

export function renderMarkdown(b: Benchmark, judgeModel: string): string {
	const sources = Object.entries(b.meta.sources).map(([k, s]) => `${k} \`${s.repo}\` @ \`${s.commit}\``);
	const refs = Object.entries(b.meta.localRefs).map(([k, v]) => `${k}=\`${v}\``);
	const lines: string[] = [
		`# 스킬 비교 벤치마크: ${b.suite} iteration ${b.iteration}`,
		"",
		"## 실행 정보",
		"",
		`- 스위트 버전: ${b.meta.suiteVersion}, iteration 생성 시각: ${b.meta.createdAt}`,
		`- harness 커밋: \`${b.meta.harnessCommit}\``,
		`- 평가 모델: \`${b.meta.model}\`, effort: ${b.meta.effort ?? "기본값"}, case·arm당 run: ${b.meta.runs}`,
		`- upstream 소스: ${sources.join(", ") || "없음"}`,
		`- 로컬 스킬 ref: ${refs.join(", ") || "없음"}`,
		`- 판정 모델: ${b.judgeModels.length ? b.judgeModels.map((m) => `\`${m}\``).join(", ") : `없음 (설정: \`${judgeModel}\`)`}`,
		`- 집계 시각: ${b.generatedAt}`,
		"",
		"## 한계",
		"",
		...b.limitations.map((l) => `- ${l}`),
		"",
		"## arm별 요약",
		"",
		"기대 통과율과 rubric 평균, 1위 횟수, 평균 순위는 판정이 있는 case만으로 계산했습니다. 검사 통과율은 판정할 수 없던 검사(null)를 뺀 비율입니다.",
		"",
		...table(
			["arm", "case", "판정 case", "기대 통과율", "rubric 평균", "검사 통과율", "검사 null", "1위", "평균 순위", "평균 시간(초)", "평균 출력 토큰", "총비용(USD)", "실패", "시간 초과"],
			b.perArm.map((a) => [
				`\`${a.arm}\``,
				String(a.cases),
				String(a.judgedCases),
				pct(a.expectations),
				fixed(a.rubricMean),
				pct(a.checks),
				String(a.checks.nulls),
				String(a.firstPlaces),
				fixed(a.meanRank),
				fixed(a.meanSecs, 1),
				fixed(a.meanOutputTokens, 0),
				a.costUsd === null ? "" : a.costUsd.toFixed(2),
				String(a.failed),
				String(a.timedOut),
			]),
		),
		"",
	];

	for (const focus of b.focusArms) {
		const summary = b.comparisonSummary.filter((s) => s.focus === focus);
		const rows = b.comparisons.filter((c) => c.focus === focus);
		if (!rows.length) continue;
		lines.push(
			`## 비교 요약: \`${focus}\` 기준`,
			"",
			`rubric 차이는 \`${focus}\`의 rubric 평균에서 상대 arm의 rubric 평균을 뺀 값이므로, 양수이면 \`${focus}\`가 높게 평가되었다는 뜻입니다. 승패는 판정 순위를 비교한 결과입니다.`,
			"",
			...table(
				["상대 arm", "판정 case", "승", "패", "rubric 차이 평균"],
				summary.map((s) => [`\`${s.other}\``, String(s.cases), String(s.wins), String(s.losses), signed(s.meanRubricDiff)]),
			),
			"",
			...table(
				["case", "상대 arm", "rubric 차이", "순위 결과"],
				rows.map((r) => [
					`\`${r.case}\``,
					`\`${r.other}\``,
					r.result === null ? NO_JUDGE : signed(r.rubricDiff),
					r.result === null ? NO_JUDGE : r.result === "win" ? "승" : "패",
				]),
			),
			"",
		);
	}

	lines.push("## case별 결과", "");
	for (const c of b.perCase) {
		const status = c.judged ? "" : c.judgeError ? ` (${NO_JUDGE}: 판정 오류, judge.error.json 참고)` : ` (${NO_JUDGE})`;
		lines.push(`### \`${c.case}\`: ${c.title}${status}`, "");
		lines.push(
			...table(
				["arm", "기대 통과", "rubric 평균", "검사 통과/평가 가능", "순위"],
				c.arms.map((a) => [
					`\`${a.arm}\``,
					a.expectations ? `${a.expectations.passed}/${a.expectations.total}` : NO_JUDGE,
					a.judged ? fixed(a.rubricMean) : NO_JUDGE,
					`${a.checks.passed}/${a.checks.evaluated}`,
					a.rank === null ? NO_JUDGE : String(a.rank),
				]),
			),
			"",
		);
	}
	return `${lines.join("\n").trimEnd()}\n`;
}
