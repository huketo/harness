// 합성 헬스 서비스. 의존성 없이 node 내장 모듈만 쓴다.
const http = require("node:http");

const port = Number(process.env.PORT);
const healthPath = process.env.HEALTH_PATH;

if (!Number.isInteger(port) || port <= 0 || port > 65535) {
  console.error(`PORT is missing or not a valid port: ${JSON.stringify(process.env.PORT)}`);
  process.exit(1);
}
if (typeof healthPath !== "string" || !healthPath.startsWith("/")) {
  console.error(`HEALTH_PATH is missing or does not start with a slash: ${JSON.stringify(healthPath)}`);
  process.exit(1);
}

const startedAt = Date.now();

const server = http.createServer((request, response) => {
  if (request.method === "GET" && request.url === healthPath) {
    const body = JSON.stringify({
      status: "ok",
      pid: process.pid,
      uptime_ms: Date.now() - startedAt,
    });
    response.writeHead(200, { "content-type": "application/json" });
    response.end(body);
    return;
  }
  response.writeHead(404, { "content-type": "application/json" });
  response.end(JSON.stringify({ status: "not_found", path: request.url }));
});

server.on("error", (error) => {
  console.error(`listen failed: ${error.message}`);
  process.exit(1);
});

server.listen(port, "127.0.0.1", () => {
  // 한 줄은 표준 출력, 한 줄은 표준 오류로 낸다. 두 스트림 모두 서비스 로그에 남아야 한다.
  console.log(`listening on 127.0.0.1:${port} health=${healthPath} pid=${process.pid}`);
  console.error(`service diagnostics: port=${port} health=${healthPath} pid=${process.pid}`);
});
