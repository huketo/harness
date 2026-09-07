import {
	closeSync,
	openSync,
	readFileSync,
	readSync,
	realpathSync,
} from "node:fs";
import { dirname } from "node:path";
import { NATIVE_TIMEOUT_MARKER } from "../../native-runtime";

// Resolve the running installation, not Bun's package auto-install cache.
export async function loadOmp<T>(specifier: string): Promise<T> {
	const executable = Bun.which("omp");
	if (!executable) throw new Error("OMP 실행 파일을 찾을 수 없습니다.");
	return import(Bun.resolveSync(specifier, dirname(realpathSync(executable))));
}

export function hasNativeCompactionRuntime(): boolean {
	const executable = Bun.which("omp");
	if (!executable) return false;
	try {
		const cli = realpathSync(executable);
		const stamp = JSON.parse(
			readFileSync(`${cli}.harness-native.json`, "utf8"),
		);
		if (!Number.isSafeInteger(stamp.markerOffset) || stamp.markerOffset < 0)
			return false;
		const fd = openSync(cli, "r");
		try {
			const bytes = Buffer.alloc(NATIVE_TIMEOUT_MARKER.length);
			readSync(fd, bytes, 0, bytes.length, stamp.markerOffset);
			return bytes.toString() === NATIVE_TIMEOUT_MARKER;
		} finally {
			closeSync(fd);
		}
	} catch {
		return false;
	}
}
