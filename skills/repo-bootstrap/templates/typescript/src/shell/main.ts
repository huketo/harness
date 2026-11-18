import { argv, stdout } from "node:process";
import { greet } from "../core/greeting/index.ts";

stdout.write(`${greet(argv[2] ?? "")}\n`);
