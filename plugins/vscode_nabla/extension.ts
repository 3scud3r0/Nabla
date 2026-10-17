import * as vscode from 'vscode';
import { parseReceipt } from './receipt';

export function activate(context: vscode.ExtensionContext): void {
    context.subscriptions.push(vscode.languages.registerHoverProvider({scheme: 'file'}, {
        async provideHover(document, position): Promise<vscode.Hover | undefined> {
            if (!vscode.workspace.isTrusted) return;
            const range = document.getWordRangeAtPosition(position, /\b[0-9a-f]{64}\b/);
            const folder = vscode.workspace.getWorkspaceFolder(document.uri);
            if (!range || !folder) return;
            const id = document.getText(range);
            const uri = vscode.Uri.joinPath(folder.uri, '.nabla', 'receipts', `${id}.json`);
            try {
                const stat = await vscode.workspace.fs.stat(uri);
                if (stat.size > 1024 * 1024) return;
                const data = parseReceipt(await vscode.workspace.fs.readFile(uri), id);
                const markdown = new vscode.MarkdownString();
                markdown.isTrusted = false;
                markdown.appendText('Nabla receipt — declared metadata; integrity and mathematics not verified by this preview.\n');
                markdown.appendCodeblock(JSON.stringify(data, null, 2).slice(0, 16000), 'json');
                return new vscode.Hover(markdown, range);
            } catch { return; }
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('nabla.showReceipt', async () => {
        if (!vscode.workspace.isTrusted) return;
        const selection = await vscode.window.showOpenDialog({canSelectMany: false, filters: {'Nabla receipt': ['json']}});
        if (!selection) return;
        try {
            const stat = await vscode.workspace.fs.stat(selection[0]);
            if (stat.size > 1024 * 1024) throw new Error('Receipt exceeds 1 MiB preview budget');
            const data = parseReceipt(await vscode.workspace.fs.readFile(selection[0]));
            const document = await vscode.workspace.openTextDocument({language: 'json', content: JSON.stringify(data, null, 2)});
            await vscode.window.showTextDocument(document);
        } catch (error) { void vscode.window.showErrorMessage(`Nabla: ${String(error)}`); }
    }));
}

export function deactivate(): void { /* subscriptions are disposed by the extension host */ }
