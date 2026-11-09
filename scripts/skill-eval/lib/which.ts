import { accessSync, constants, statSync } from "node:fs";
import { delimiter, isAbsolute, join, resolve } from "node:path";

function executable(file: string): boolean {
	try {
		if (!statSync(file).isFile()) return false;
		accessSync(file, constants.X_OK);
		return true;
	} catch {
		return false;
	}
}

/** Absolute path of the executable `command` on `PATH` (or of `command` itself when it has a slash), or null. */
export function which(command: string, path = process.env.PATH ?? ""): string | null {
	if (command.includes("/")) {
		const file = isAbsolute(command) ? command : resolve(command);
		return executable(file) ? file : null;
	}
	for (const dir of path.split(delimiter)) {
		if (!dir) continue;
		const file = resolve(join(dir, command));
		if (executable(file)) return file;
	}
	return null;
}
