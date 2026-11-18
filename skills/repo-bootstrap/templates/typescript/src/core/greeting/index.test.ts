import assert from "node:assert/strict";
import { test } from "node:test";
import { greet } from "./index.ts";

test("greets a trimmed name", () => {
	assert.equal(greet("  Ada "), "Hello, Ada.");
});

test("asks for a name when the input is blank", () => {
	assert.equal(greet("   "), "Tell me your name.");
});

test("names the limit when the input is too long", () => {
	assert.equal(greet("x".repeat(41)), "Use at most 40 characters.");
});
