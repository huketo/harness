#!/usr/bin/env node
'use strict';
// Expose the Windows host's Chrome to WSL over CDP.
//
// Headed Chrome binds its remote-debugging port to the Windows loopback only
// (`--remote-debugging-address` is ignored outside headless mode), and the
// Windows firewall drops connections from the WSL NAT subnet to the host. So
// instead of the network, this bridge listens on WSL 127.0.0.1:PORT and, per
// connection, spawns a Windows `node.exe` relay through WSL interop whose
// stdin/stdout are piped to Windows 127.0.0.1:HOST_PORT.
//
// The two ports must differ: WSL's localhost forwarding (wslrelay.exe) binds
// Windows 127.0.0.1:PORT as soon as the bridge listens, so a Chrome on the same
// port loses the address to the relay and the relay loops back into the bridge.
// Chrome derives the `ws://` URL it returns from the request's `Host` header,
// so clients talking to 127.0.0.1:PORT get URLs that resolve to the bridge.

const net = require('net');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn, execFileSync } = require('child_process');

const PORT = Number(process.env.WINDOWS_CHROME_PORT || 9222);
const HOST_PORT = Number(process.env.WINDOWS_CHROME_HOST_PORT || PORT + 10000);
const PROFILE = process.env.WINDOWS_CHROME_PROFILE || 'default';
const WIN_CWD = '/mnt/c';
const STATE_DIR = path.join(process.env.XDG_STATE_HOME || path.join(os.homedir(), '.local', 'state'), 'windows-chrome');
const PID_FILE = path.join(STATE_DIR, `bridge-${PORT}.pid`);
const LOG_FILE = path.join(STATE_DIR, `bridge-${PORT}.log`);
const ENDPOINT = `http://127.0.0.1:${PORT}`;
const READY_TIMEOUT_MS = 30000;

// Runs under Windows node.exe. argv[1] is the port because `-e` leaves no script name.
const RELAY = `
const net = require('net');
const s = net.connect(Number(process.argv[1]), '127.0.0.1');
s.on('connect', () => { process.stdin.pipe(s); s.pipe(process.stdout); });
s.on('error', () => process.exit(2));
s.on('close', () => process.exit(0));
process.stdin.on('end', () => s.end());
process.stdout.on('error', () => process.exit(0));
`;

function fail(message) {
  process.stderr.write(`windows-chrome: ${message}\n`);
  process.exit(1);
}

function winEnv(name) {
  const out = execFileSync('cmd.exe', ['/c', `echo %${name}%`], { cwd: WIN_CWD, stdio: ['ignore', 'pipe', 'ignore'] });
  const value = out.toString().replace(/\r?\n$/, '');
  if (!value || value === `%${name}%`) fail(`Windows environment variable ${name} is not set`);
  return value;
}

function toWslPath(winPath) {
  return execFileSync('wslpath', ['-u', winPath]).toString().trim();
}

function firstExisting(candidates) {
  return candidates.find(candidate => candidate && fs.existsSync(candidate));
}

function chromeExe() {
  const exe = firstExisting([
    process.env.WINDOWS_CHROME_EXE,
    '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
    '/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    path.join(toWslPath(winEnv('LOCALAPPDATA')), 'Google', 'Chrome', 'Application', 'chrome.exe'),
  ]);
  if (!exe) fail('chrome.exe not found on the Windows side; set WINDOWS_CHROME_EXE');
  return exe;
}

function nodeExe() {
  const exe = firstExisting([
    process.env.WINDOWS_NODE_EXE,
    '/mnt/c/Program Files/nodejs/node.exe',
    ...(process.env.PATH || '').split(':').map(dir => path.join(dir, 'node.exe')),
  ]);
  if (!exe) fail('node.exe not found on the Windows side; install Node.js on Windows or set WINDOWS_NODE_EXE');
  return exe;
}

function readPid() {
  try {
    const pid = Number(fs.readFileSync(PID_FILE, 'utf8'));
    const cmdline = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8');
    return cmdline.includes(__filename) ? pid : null;
  } catch {
    return null;
  }
}

async function version() {
  try {
    const res = await fetch(`${ENDPOINT}/json/version`, { signal: AbortSignal.timeout(3000) });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

async function waitReady() {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const info = await version();
    if (info) return info;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  return null;
}

function serve() {
  const relayExe = nodeExe();
  const server = net.createServer(socket => {
    const relay = spawn(relayExe, ['-e', RELAY, String(HOST_PORT)], { cwd: WIN_CWD, stdio: ['pipe', 'pipe', 'ignore'] });
    socket.pipe(relay.stdin);
    relay.stdout.pipe(socket);
    socket.on('error', () => relay.kill());
    socket.on('close', () => relay.kill());
    relay.stdin.on('error', () => socket.destroy());
    relay.on('error', () => socket.destroy());
    relay.on('exit', () => socket.destroy());
  });
  server.on('error', error => fail(`cannot listen on 127.0.0.1:${PORT}: ${error.message}`));
  server.listen(PORT, '127.0.0.1', () => {
    fs.mkdirSync(STATE_DIR, { recursive: true });
    fs.writeFileSync(PID_FILE, String(process.pid));
    process.stdout.write(`bridge listening on ${ENDPOINT} (pid ${process.pid})\n`);
  });
  const shutdown = () => {
    if (readPid() === process.pid) fs.rmSync(PID_FILE, { force: true });
    process.exit(0);
  };
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}

function startBridge() {
  if (readPid()) return;
  fs.mkdirSync(STATE_DIR, { recursive: true });
  const log = fs.openSync(LOG_FILE, 'a');
  const child = spawn(process.execPath, [__filename, 'serve'], { detached: true, stdio: ['ignore', log, log] });
  child.unref();
}

function launchChrome(url) {
  const userDataDir = `${winEnv('LOCALAPPDATA')}\\windows-chrome\\${PROFILE}`;
  const args = [
    `--remote-debugging-port=${HOST_PORT}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    url || 'about:blank',
  ];
  const child = spawn(chromeExe(), args, { cwd: WIN_CWD, detached: true, stdio: 'ignore' });
  child.unref();
  return userDataDir;
}

function report(info) {
  process.stdout.write(`endpoint: ${ENDPOINT}\n`);
  process.stdout.write(`browser: ${info.Browser}\n`);
  process.stdout.write(`websocket: ${info.webSocketDebuggerUrl}\n`);
}

async function start(url) {
  startBridge();
  let info = await version();
  if (!info) {
    const userDataDir = launchChrome(url);
    info = await waitReady();
    if (!info) {
      fail(`Chrome did not expose ${ENDPOINT} within ${READY_TIMEOUT_MS / 1000}s. ` +
        `If a Chrome window using ${userDataDir} is already open without remote debugging, close it and retry. ` +
        `Bridge log: ${LOG_FILE}`);
    }
  } else if (url) {
    await fetch(`${ENDPOINT}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
  }
  report(info);
}

async function status() {
  const pid = readPid();
  process.stdout.write(`bridge: ${pid ? `running (pid ${pid})` : 'stopped'}\n`);
  const info = await version();
  if (!info) {
    process.stdout.write(`chrome: unreachable at ${ENDPOINT}\n`);
    process.exit(pid ? 2 : 3);
  }
  report(info);
}

async function stop() {
  const info = await version();
  if (info) {
    await new Promise(resolve => {
      const ws = new WebSocket(info.webSocketDebuggerUrl);
      ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: 'Browser.close' }));
      ws.onclose = resolve;
      ws.onerror = resolve;
      setTimeout(resolve, 5000);
    });
    process.stdout.write('chrome: closed\n');
  }
  const pid = readPid();
  if (pid) {
    process.kill(pid, 'SIGTERM');
    process.stdout.write(`bridge: stopped (pid ${pid})\n`);
  } else {
    process.stdout.write('bridge: not running\n');
  }
}

const [command, arg] = process.argv.slice(2);
switch (command) {
  case 'start': start(arg); break;
  case 'status': status(); break;
  case 'stop': stop(); break;
  case 'serve': serve(); break;
  default:
    process.stderr.write(
      'usage: windows-chrome.js start [url] | status | stop\n' +
      `env: WINDOWS_CHROME_PORT (${PORT}) WINDOWS_CHROME_HOST_PORT (${HOST_PORT}) WINDOWS_CHROME_PROFILE (${PROFILE}) WINDOWS_CHROME_EXE WINDOWS_NODE_EXE\n`);
    process.exit(64);
}
