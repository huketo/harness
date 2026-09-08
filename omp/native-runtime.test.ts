import { expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
	patchAccountSessionIdentity,
	patchCompactionTimeout,
	patchNativePreparation,
	patchShakeFallback,
	patchShakeFallbackSource,
	patchShakePersistence,
	patchShakePersistenceSource,
} from "./native-runtime";

test("only native compaction receives the API deadline; shutdown and ordinary hooks retain their caps", () => {
	const source =
		'let shutdown=2000,normal=30000;function timeout(event){return event==="session_shutdown"?shutdown:normal}';
	const patched = patchCompactionTimeout(source);
	const timeout = new Function(`${patched};return timeout`)() as (
		event: string,
	) => number;
	expect(timeout("session_before_compact")).toBeGreaterThan(600000);
	expect(timeout("session_before_compact")).toBeLessThanOrEqual(610000);
	expect(timeout("session_shutdown")).toBe(2000);
	expect(timeout("before_provider_request")).toBe(30000);
	expect(patchCompactionTimeout(patched)).toBe(patched);
});

test("upgrades the installed three-minute hook without changing other deadlines", () => {
	const source =
		'let shutdown=2000,normal=30000;function timeout(event){/*harness-native-compaction-timeout*/return event==="session_before_compact"?180000:event==="session_shutdown"?shutdown:normal}';
	const patched = patchCompactionTimeout(source);
	const timeout = new Function(`${patched};return timeout`)();
	expect(timeout("session_before_compact")).toBeGreaterThan(600000);
	expect(timeout("session_shutdown")).toBe(2000);
	expect(timeout("before_provider_request")).toBe(30000);
	expect(patchCompactionTimeout(patched)).toBe(patched);
});

test("shake refuses to rewrite history when no recovery artifact was saved", async () => {
	const source =
		'class Shake{#save;constructor(save){this.#save=save}async run(e,r){if(r.length===0)return{mode:e,toolResultsDropped:0,blocksDropped:0,tokensFreed:0};let i=await this.#save(r),a=r.map(item=>{item.text="artifact://"+i;return item});return a}}';
	const patched = patchShakePersistence(source);
	const Shake = new Function(`${patched};return Shake`)() as new (
		save: () => Promise<string | undefined>,
	) => { run(mode: string, regions: { text: string }[]): Promise<unknown> };
	expect(
		await new Shake(async () => {
			throw new Error("empty regions must not reach storage");
		}).run("elide", []),
	).toEqual({
		mode: "elide",
		toolResultsDropped: 0,
		blocksDropped: 0,
		tokensFreed: 0,
	});
	const regions = [{ text: "unrecoverable command output" }];
	await expect(
		new Shake(async () => undefined).run("elide", regions),
	).rejects.toBeInstanceOf(Error);
	expect(regions).toEqual([{ text: "unrecoverable command output" }]);
	const saved = new Shake(async () => "saved");
	await saved.run("elide", regions);
	expect(regions).toEqual([{ text: "artifact://saved" }]);
	expect(patchShakePersistence(patched)).toBe(patched);
});

test("SDK shake uses the same artifact-before-rewrite boundary", async () => {
	const source =
		'class Shake { #saveShakeArtifact; constructor(save) { this.#saveShakeArtifact = save; } async run(regions) { const artifactId = await this.#saveShakeArtifact(regions); for (const region of regions) region.text = "artifact://" + artifactId; } }';
	const patched = patchShakePersistenceSource(source);
	const Shake = new Function(`${patched};return Shake`)() as new (
		save: () => Promise<string | undefined>,
	) => { run(regions: { text: string }[]): Promise<void> };
	const regions = [{ text: "original" }];
	await expect(
		new Shake(async () => undefined).run(regions),
	).rejects.toBeInstanceOf(Error);
	expect(regions).toEqual([{ text: "original" }]);
	expect(patchShakePersistenceSource(patched)).toBe(patched);
	expect(() => patchShakePersistence("unrecognized layout")).toThrow();
	expect(() => patchShakePersistenceSource("unrecognized layout")).toThrow();
});

test("automatic shake falls back after a refused archive write, without broadening other errors", async () => {
	const guardSource =
		"class Guard{#saveShakeArtifact=async()=>undefined;async run(regions){const artifactId = await this.#saveShakeArtifact(regions);return artifactId}}";
	const Guard = new Function(
		`${patchShakePersistenceSource(guardSource)};return Guard`,
	)() as new () => { run(regions: unknown[]): Promise<unknown> };
	let message = "";
	await new Guard().run([{}]).catch((error: Error) => {
		message = error.message;
	});
	const source =
		'function notice(){}function recover(e,d,a){return notice({type:"auto_compaction_end",action:"shake",result:void 0,aborted:!1,willRetry:!1,errorMessage:d,skipped:!1},a),e==="overflow"?"fallback":"none"}';
	const patched = patchShakeFallback(source);
	const recover = new Function(`${patched};return recover`)() as (
		reason: string,
		message: string,
		detach: boolean,
	) => string;
	expect(recover("threshold", message, false)).toBe("fallback");
	expect(recover("threshold", "other failure", false)).toBe("none");
	expect(recover("overflow", "other failure", false)).toBe("fallback");
	expect(patchShakeFallback(patched)).toBe(patched);
	const sdk =
		'const COMPACTION_CHECK_NONE="none";function recover(reason,message){return reason === "overflow" ? "fallback" : COMPACTION_CHECK_NONE;}';
	const sdkPatched = patchShakeFallbackSource(sdk);
	const sdkRecover = new Function(`${sdkPatched};return recover`)() as (
		reason: string,
		message: string,
	) => string;
	expect(sdkRecover("threshold", message)).toBe("fallback");
	expect(sdkRecover("threshold", "other failure")).toBe("none");
	expect(patchShakeFallbackSource(sdkPatched)).toBe(sdkPatched);
	expect(() => patchShakeFallback("unrecognized layout")).toThrow();
	expect(() => patchShakeFallbackSource("unrecognized layout")).toThrow();
});

test("managed settings are not written while the required runtime guard is missing", () => {
	const dir = mkdtempSync(join(tmpdir(), "harness-config-guard-"));
	const marker = join(dir, "settings-written");
	try {
		writeFileSync(
			join(dir, "bun"),
			'#!/bin/sh\ncase "$1" in */native-runtime.ts) exit 1;; esac\ncase "$2" in roles) echo "{}";; *) echo "openai-codex/gpt-6-astra";; esac\n',
			{ mode: 0o755 },
		);
		writeFileSync(
			join(dir, "omp"),
			'#!/bin/sh\ncase "$1 $2" in "config set") echo changed >> "$MARKER";; *) echo \'{"value":null}\';; esac\n',
			{ mode: 0o755 },
		);
		const result = spawnSync(
			"bash",
			[join(import.meta.dir, "config.apply.sh")],
			{
				env: {
					...process.env,
					PATH: `${dir}:${process.env.PATH}`,
					MARKER: marker,
					HOME: dir,
					PI_CODING_AGENT_DIR: dir,
				},
				stdio: "ignore",
				timeout: 5000,
			},
		);
		expect(result.error).toBeUndefined();
		expect(result.status).toBe(1);
		expect(existsSync(marker)).toBe(false);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});

test("extension contexts expose the provider request identity used by ModelRegistry", () => {
	const source =
		'class Runner{extensions;runtime;sessionManager;modelRegistry;settings;localProtocolOptions;constructor(e,t,s,n,o,r,i,a,l){this.extensions=e;this.runtime=t;this.sessionManager=n;this.modelRegistry=o;this.settings=i;this.localProtocolOptions=a;this.memory=r;this.snapshot=l??(()=>null)}createContext(){return{sessionManager:this.sessionManager,modelRegistry:this.modelRegistry}}}let ready=false,manager={getSessionId:()=>"transcript"},session={sessionId:"provider",getAsyncJobSnapshot:()=>null},extensions={extensions:[],runtime:{}};let runner=new Runner(extensions.extensions,extensions.runtime,"cwd",manager,{},()=>ready?{}:void 0,{},null,()=>ready?session.getAsyncJobSnapshot():null)';
	const patched = patchAccountSessionIdentity(source);
	const state = new Function(
		`${patched};return {runner,activate:()=>{ready=true}}`,
	)() as {
		runner: { createContext(): { sessionId: string } };
		activate(): void;
	};
	expect(state.runner.createContext().sessionId).toBe("transcript");
	state.activate();
	expect(state.runner.createContext().sessionId).toBe("provider");
	expect(patchAccountSessionIdentity(patched)).toBe(patched);
});

test("unrecognized or ambiguous OMP runtime is not patched", () => {
	expect(() =>
		patchCompactionTimeout("function changed(){return 30000}"),
	).toThrow("구조가 변경");
	const source =
		'function a(e){return e==="session_shutdown"?x:y}function b(e){return e==="session_shutdown"?x:y}';
	expect(() => patchCompactionTimeout(source)).toThrow("구조가 변경");
	expect(() => patchAccountSessionIdentity("class Changed {}")).toThrow(
		"구조가 변경",
	);
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
	expect(() =>
		new Patched({
			...host,
			sessionManager: {
				getBranch: () => [native, { type: "compaction", id: "portable" }],
			},
		}).run(),
	).toThrow("Already compacted");
	expect(() =>
		new Patched({
			...host,
			sessionManager: {
				getBranch: () => [native, { type: "reset_boundary", id: "reset" }],
			},
		}).run(),
	).toThrow("Nothing to compact");
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
