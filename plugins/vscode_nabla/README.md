# Nabla Receipts

Preview local Nabla calculation receipts in VS Code and Positron.

Build and test:

```bash
npm ci
npm test
code --extensionDevelopmentPath "$PWD"
```

In the development host, open a trusted workspace and save a receipt as
`.nabla/receipts/<content_id>.json`. Hover over that 64-character hash in a file.
Use **Nabla: Open Receipt** to inspect another JSON receipt.

The extension reads local files up to 1 MiB and displays metadata. It does not
execute calculations or certify receipt integrity, proofs or scientific claims.

To build a distributable VSIX using the official VS Code packaging tool:

```bash
npx @vscode/vsce package --no-dependencies
```
