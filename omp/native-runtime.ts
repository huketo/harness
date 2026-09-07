#!/usr/bin/env bun
import { createHash } from "node:crypto";
import {
	chmodSync,
	readFileSync,
	realpathSync,
	renameSync,
	statSync,
	writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";

export const NATIVE_TIMEOUT_MARKER = "/*harness-native-compaction-timeout*/";
const PREPARATION_MARKER = "/*harness-native-compaction-preparation*/";
export const ACCOUNT_SESSION_MARKER = "/*harness-account-session*/";

/** Expose the live provider-routing identity to extension contexts. */
export function patchAccountSessionIdentity(bundle: string): string {
	if (bundle.includes(ACCOUNT_SESSION_MARKER)) return bundle;
	const constructorSelector =
		/constructor\(([\w$]+),([\w$]+),([\w$]+),([\w$]+),([\w$]+),([\w$]+),([\w$]+),([\w$]+),([\w$]+)\)\{this\.extensions=\1;this\.runtime=\2;this\.sessionManager=\4;this\.modelRegistry=\5;/g;
	const contextSelector =
		"sessionManager:this.sessionManager,modelRegistry:this.modelRegistry";
	const snapshotSelector =
		/,\(\)=>([\w$]+)\?([\w$]+)\.getAsyncJobSnapshot\(\):null\)/g;
	if (
		[...bundle.matchAll(constructorSelector)].length !== 1 ||
		bundle.split(contextSelector).length !== 2 ||
		[...bundle.matchAll(snapshotSelector)].length !== 1
	)
		throw new Error(
			"OMP 계정 세션 라우팅 구조가 변경되었습니다. 호환 패치를 검토해야 합니다.",
		);
	let patched = bundle.replace(
		constructorSelector,
		(
			_match,
			ext,
			runtime,
			cwd,
			manager,
			registry,
			memory,
			settings,
			local,
			snapshot,
		) =>
			`constructor(${ext},${runtime},${cwd},${manager},${registry},${memory},${settings},${local},${snapshot},harnessRequestSessionId){this.harnessRequestSessionId=harnessRequestSessionId??(()=>void 0);this.extensions=${ext};this.runtime=${runtime};this.sessionManager=${manager};this.modelRegistry=${registry};`,
	);
	patched = patched.replace(
		contextSelector,
		`sessionManager:this.sessionManager,sessionId:${ACCOUNT_SESSION_MARKER}this.harnessRequestSessionId?.()??this.sessionManager.getSessionId(),modelRegistry:this.modelRegistry`,
	);
	return patched.replace(
		snapshotSelector,
		(_match, ready, session) =>
			`,()=>${ready}?${session}.getAsyncJobSnapshot():null,()=>${ready}?${session}.sessionId:void 0)`,
	);
}

/** Narrow compatibility patch: native compaction is an API operation, not an observer. */
export function patchCompactionTimeout(bundle: string): string {
	if (bundle.includes(NATIVE_TIMEOUT_MARKER)) return bundle;
	const selector =
		/function ([\w$]+)\(([\w$]+)\)\{return \2==="session_shutdown"\?([\w$]+):([\w$]+)\}/g;
	const matches = [...bundle.matchAll(selector)];
	if (matches.length !== 1)
		throw new Error(
			"OMP compaction 이벤트 시간 제한 구조가 변경되었습니다. 호환 패치를 검토해야 합니다.",
		);
	return bundle.replace(
		selector,
		(_match, fn, arg, shutdown, normal) =>
			`function ${fn}(${arg}){${NATIVE_TIMEOUT_MARKER}return ${arg}==="session_before_compact"?180000:${arg}==="session_shutdown"?${shutdown}:${normal}}`,
	);
}

function nativePreparation(
	entries: string,
	settings: string,
	host: string,
): string {
	return `(${entries}.some(entry=>entry.type==="compaction"&&entry.preserveData?.harnessNativeCompaction)&&${host}.extensionRunner?.hasHandlers("session_before_compact")?{firstKeptEntryId:${entries}.at(-1).id,messagesToSummarize:[],turnPrefixMessages:[],recentMessages:[],isSplitTurn:false,tokensBefore:0,fileOps:{read:new Set(),written:new Set(),edited:new Set()},settings:${settings}}:undefined)`;
}

/** A native window can need a portable handoff even with no sizable new transcript. */
export function patchNativePreparation(bundle: string): string {
	if (bundle.includes(PREPARATION_MARKER)) return bundle;
	const selector =
		/let ([\w$]+)=this\.(#[\w$]+)\.sessionManager\.getBranch\(\),([\w$]+)=([\w$]+)\(\1,([\w$]+),([\w$]+),this\.(#[\w$]+)\);if\(!\3\)\{if\(\1\[\1.length-1\]\?\.type==="compaction"\)throw Error\("Already compacted"\);throw Error\("Nothing to compact \(session too small\)"\)\}/g;
	if ([...bundle.matchAll(selector)].length !== 1)
		throw new Error(
			"OMP 수동 압축 준비 구조가 변경되었습니다. 호환 패치를 검토해야 합니다.",
		);
	return bundle.replace(
		selector,
		(match, entries, host, preparation, _prepare, settings) =>
			match.replace(
				`;if(!${preparation})`,
				`;${PREPARATION_MARKER}${preparation}??=${nativePreparation(entries, settings, `this.${host}`)};if(!${preparation})`,
			),
	);
}

function replaceOnce(text: string, old: string, replacement: string): string {
	if (text.includes(replacement)) return text;
	if (text.split(old).length !== 2)
		throw new Error(
			"OMP SDK 소스가 변경되었습니다. 호환 패치를 검토해야 합니다.",
		);
	return text.replace(old, replacement);
}

function patchRunnerSource(source: string): string {
	let patched = replaceOnce(
		source,
		'return eventType === "session_shutdown" ? sessionShutdownHandlerTimeoutMs : extensionHandlerTimeoutMs;',
		`${NATIVE_TIMEOUT_MARKER}\n\treturn eventType === "session_before_compact" ? 180000 : eventType === "session_shutdown" ? sessionShutdownHandlerTimeoutMs : extensionHandlerTimeoutMs;`,
	);
	patched = replaceOnce(
		patched,
		"\t\tgetAsyncJobSnapshot?: () => AsyncJobSnapshot | null,\n\t) {",
		"\t\tgetAsyncJobSnapshot?: () => AsyncJobSnapshot | null,\n\t\tprivate readonly getRequestSessionId?: () => string | undefined,\n\t) {",
	);
	return replaceOnce(
		patched,
		"\t\t\tsessionManager: this.sessionManager,\n\t\t\tmodelRegistry: this.modelRegistry,",
		`\t\t\tsessionManager: this.sessionManager,\n\t\t\t...({ sessionId: ${ACCOUNT_SESSION_MARKER}this.getRequestSessionId?.() ?? this.sessionManager.getSessionId() } as object),\n\t\t\tmodelRegistry: this.modelRegistry,`,
	);
}

if (import.meta.main) {
	const executable = Bun.which("omp");
	if (!executable) throw new Error("OMP 실행 파일을 찾을 수 없습니다.");
	const cli = realpathSync(executable);
	const packageDir = join(dirname(cli), "..");
	const pkg = JSON.parse(
		readFileSync(join(packageDir, "package.json"), "utf8"),
	);
	if (pkg.name !== "@oh-my-pi/pi-coding-agent" || pkg.version !== "18.1.13")
		throw new Error(`네이티브 호환 검증이 필요한 OMP 버전: ${pkg.version}`);
	const files = [
		cli,
		join(packageDir, "src/extensibility/extensions/runner.ts"),
		join(packageDir, "src/session/session-maintenance.ts"),
		join(packageDir, "src/sdk.ts"),
	];
	const changes = files.map((file) => {
		const before = readFileSync(file, "utf8");
		let after: string;
		if (file === cli)
			after = patchAccountSessionIdentity(
				patchNativePreparation(patchCompactionTimeout(before)),
			);
		else if (file.endsWith("extensibility/extensions/runner.ts"))
			after = patchRunnerSource(before);
		else if (file.endsWith("session-maintenance.ts"))
			after = replaceOnce(
				before,
				"const preparation = prepareCompaction(pathEntries, effectiveSettings, activeModel, this.#tokenizer);",
				`const preparation = prepareCompaction(pathEntries, effectiveSettings, activeModel, this.#tokenizer) ?? ${PREPARATION_MARKER}${nativePreparation("pathEntries", "effectiveSettings", "this.#host")};`,
			);
		else
			after = replaceOnce(
				before,
				"\t\t\t() => (hasSession ? session.getAsyncJobSnapshot() : null),\n\t\t);",
				"\t\t\t() => (hasSession ? session.getAsyncJobSnapshot() : null),\n\t\t\t() => (hasSession ? session.sessionId : undefined),\n\t\t);",
			);
		return { file, before, after };
	});
	if (process.argv.includes("--check")) {
		if (changes.some((change) => change.before !== change.after))
			throw new Error("OMP 네이티브 호환 패치가 설치되지 않았습니다.");
		console.log(`native runtime: ready (${pkg.version})`);
	} else {
		// Validate every target before modifying any installation file.
		for (const { file, before, after } of changes) {
			if (before === after) continue;
			const backup = `${file}.harness-native-original`;
			try {
				writeFileSync(backup, before, {
					flag: "wx",
					mode: statSync(file).mode,
				});
			} catch (error) {
				if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
			}
			const temporary = `${file}.harness-native-${process.pid}`;
			writeFileSync(temporary, after);
			chmodSync(temporary, statSync(file).mode);
			renameSync(temporary, file);
		}
		const bundle = changes[0].after;
		writeFileSync(
			`${cli}.harness-native.json`,
			`${JSON.stringify({ version: pkg.version, markerOffset: Buffer.byteLength(bundle.slice(0, bundle.indexOf(NATIVE_TIMEOUT_MARKER))), sha256: createHash("sha256").update(bundle).digest("hex") })}\n`,
		);
		console.log(`native runtime: installed (${pkg.version})`);
	}
}
