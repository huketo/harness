import { expect, test } from "bun:test";
import {
	patchCompactionTimeout,
	patchNativePreparation,
} from "./native-runtime";

test("only native compaction receives the API deadline; shutdown and ordinary hooks retain their caps", () => {
	const source =
		'let shutdown=2000,normal=30000;function timeout(event){return event==="session_shutdown"?shutdown:normal}';
	const patched = patchCompactionTimeout(source);
	const timeout = new Function(`${patched};return timeout`)() as (
		event: string,
	) => number;
	expect(timeout("session_before_compact")).toBe(180000);
	expect(timeout("session_shutdown")).toBe(2000);
	expect(timeout("before_provider_request")).toBe(30000);
	expect(patchCompactionTimeout(patched)).toBe(patched);
});

test("unrecognized or ambiguous OMP runtime is not patched", () => {
	expect(() =>
		patchCompactionTimeout("function changed(){return 30000}"),
	).toThrow("구조가 변경");
	const source =
		'function a(e){return e==="session_shutdown"?x:y}function b(e){return e==="session_shutdown"?x:y}';
	expect(() => patchCompactionTimeout(source)).toThrow("구조가 변경");
});

test("a persisted native window reaches the compaction hook even with a small new transcript", () => {
	const source =
		'function prepare(){return undefined}class Compact{#host;#tokenizer;constructor(host){this.#host=host}run(){let settings={},model={};let entries=this.#host.sessionManager.getBranch(),prepared=prepare(entries,settings,model,this.#tokenizer);if(!prepared){if(entries[entries.length-1]?.type==="compaction")throw Error("Already compacted");throw Error("Nothing to compact (session too small)")}return prepared}}';
	const Patched = new Function(
		`${patchNativePreparation(source)};return Compact`,
	)();
	const native = {
		type: "compaction",
		id: "native",
		preserveData: { harnessNativeCompaction: { version: 1 } },
	};
	const host = {
		sessionManager: { getBranch: () => [native] },
		extensionRunner: { hasHandlers: () => true },
	};
	expect(new Patched(host).run().firstKeptEntryId).toBe("native");
	const ordinary = {
		...host,
		sessionManager: { getBranch: () => [{ type: "message", id: "message" }] },
	};
	expect(() => new Patched(ordinary).run()).toThrow("Nothing to compact");
	expect(() =>
		new Patched({
			...host,
			extensionRunner: { hasHandlers: () => false },
		}).run(),
	).toThrow("Already compacted");
});
