#!/bin/sh
# Prints p95 latency in ms for the current checkout. Takes about 40 seconds.
set -eu
npm run --silent build
node dist/bench.js --requests 2000 --print p95
