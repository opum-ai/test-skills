// Run by the ts-audit scaffold (outside the eval sandbox) on the run's own node_modules copy.
// Stryker's parent process opens a TCP "logging server" that its workers connect to. The plugin
// eval OS sandbox denies every listen() (TCP and Unix), so Stryker dies with EPERM before running
// a mutant. Worker <-> parent traffic itself uses Node's IPC channel, which is allowed; only log
// forwarding needs the socket. This makes the server a no-op and the worker-side client drop its
// log lines (the parent still logs). Mutation results are unaffected. Fails loudly if Stryker's
// code no longer matches, rather than silently leaving a broken tool in the workspace.
const fs = require('fs');
const path = require('path');
const dir = path.join(process.cwd(), 'node_modules/@stryker-mutator/core/dist/src/logging');
const patches = [
  ['logging-server.js', [
    ['this.#server.listen(() => {\n                res({ port: this.#server.address().port });\n            });',
     'res({ port: 0 }); // test-skills eval sandbox: no listen() allowed'],
    ['await promisify(this.#server.close).bind(this.#server)();',
     'if (this.#server.listening) await promisify(this.#server.close).bind(this.#server)();'],
  ]],
  ['logging-client.js', [
    ["this.#socket = net.createConnection(this.loggingServerAddress.port, 'localhost', res);",
     "if (!this.loggingServerAddress.port) { this.#socket = { writable: false, end: (cb) => cb && cb() }; return res(); } // test-skills eval sandbox\n            this.#socket = net.createConnection(this.loggingServerAddress.port, 'localhost', res);"],
  ]],
];
for (const [file, edits] of patches) {
  const p = path.join(dir, file);
  let src = fs.readFileSync(p, 'utf8');
  if (src.includes('test-skills eval sandbox')) continue;
  for (const [from, to] of edits) {
    if (!src.includes(from)) { console.error(`sandbox_patch_stryker: ${file} changed; update the patch`); process.exit(1); }
    src = src.replace(from, to);
  }
  fs.writeFileSync(p, src);
}
