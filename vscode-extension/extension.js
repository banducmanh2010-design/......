const vscode = require('vscode');
const https = require('https');

function activate(context) {
  const config = vscode.workspace.getConfiguration('ducmanh');
  context.subscriptions.push(vscode.commands.registerCommand('ducmanh.connect', async () => {
    const endpoint = await vscode.window.showInputBox({prompt:'DUCMANH AI API endpoint', value:config.get('endpoint','https://zalo-gemini-bot-73m6.onrender.com')});
    if (endpoint) await config.update('endpoint', endpoint.replace(/\/$/,''), vscode.ConfigurationTarget.Global);
    vscode.window.showInformationMessage('Đã lưu endpoint. Hãy cấu hình API token trong VS Code SecretStorage ở bản phát hành bảo mật.');
  }));
  context.subscriptions.push(vscode.commands.registerCommand('ducmanh.ask', async () => {
    const editor = vscode.window.activeTextEditor;
    const selection = editor ? editor.document.getText(editor.selection) : '';
    const prompt = await vscode.window.showInputBox({prompt:'Bạn muốn DUCMANH AI làm gì với đoạn code/workspace?'});
    if (!prompt) return;
    const safeContext = selection || (editor ? editor.document.getText().slice(0,12000) : '');
    vscode.window.showInformationMessage('Connector skeleton đã nhận yêu cầu. Cần cấu hình endpoint và xác thực API trước khi gửi dữ liệu.');
    console.log('DUCMANH request prepared', {prompt, contextLength:safeContext.length});
  }));
}
function deactivate() {}
module.exports = {activate,deactivate};
