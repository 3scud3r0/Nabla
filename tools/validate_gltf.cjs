// Independent Khronos glTF 2.0 validation; no network or external URI loading.
// npm install --prefix .nabla/gltf-validator gltf-validator@2.0.0-dev.3.10
// node tools/validate_gltf.cjs FILE.glb .nabla/gltf-validator
const fs = require('node:fs');
const path = require('node:path');
const [filename, prefix] = process.argv.slice(2);
if (!filename || !prefix) throw new Error('Expected GLB filename and validator installation prefix');
const validator = require(path.resolve(prefix, 'node_modules/gltf-validator'));
validator.validateBytes(new Uint8Array(fs.readFileSync(filename)), {
  uri: path.basename(filename), maxIssues: 100,
}).then(report => {
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');
  if (report.issues.numErrors || report.issues.numWarnings) process.exitCode = 1;
}).catch(error => { process.stderr.write(String(error) + '\n'); process.exitCode = 1; });
