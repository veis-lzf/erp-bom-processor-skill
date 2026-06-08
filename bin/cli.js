#!/usr/bin/env node
/**
 * erp-bom CLI entry point
 * Wraps Python scripts for cross-platform compatibility
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const SCRIPTS_DIR = path.join(__dirname, '..', 'scripts');

function getPythonCommand() {
    const candidates = process.platform === 'win32'
        ? ['python', 'python3', 'py']
        : ['python3', 'python'];

    for (const cmd of candidates) {
        try {
            execSync(
                process.platform === 'win32'
                    ? `where ${cmd} 2>nul`
                    : `command -v ${cmd} 2>/dev/null`,
                { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }
            );
            return cmd;
        } catch (e) { /* ignore */ }
    }
    return null;
}

function runPython(scriptName, args) {
    const pythonCmd = getPythonCommand();
    if (!pythonCmd) {
        console.error('错误: 未找到 Python。请安装 Python 3.7+ 并确保在 PATH 中。');
        console.error('下载: https://www.python.org/downloads/');
        process.exit(1);
    }

    const scriptPath = path.join(SCRIPTS_DIR, scriptName);
    if (!fs.existsSync(scriptPath)) {
        console.error(`错误: 脚本不存在: ${scriptPath}`);
        process.exit(1);
    }

    const child = spawn(pythonCmd, [scriptPath, ...args], {
        stdio: 'inherit',
        cwd: process.cwd()
    });

    child.on('error', (err) => {
        console.error(`错误: 无法启动 ${pythonCmd}: ${err.message}`);
        process.exit(1);
    });

    child.on('close', (code) => {
        process.exit(code);
    });
}

function showHelp() {
    console.log(`
erp-bom <command> [options]

命令:
  process [bom-file]    处理 BOM 文件，将原理图BOM转换为格式化ERP BOM
                        无参数时批量处理 03_order/ 下所有文件
    
  diff [files...]       比对多份已处理BOM文件，生成差异清单
                        无参数时自动读取 04_output/ 下所有文件

  help                  显示此帮助信息

环境要求:
  - Node.js >= 14.0.0
  - Python 3.7+ (需安装 pandas, openpyxl)
    pip install pandas openpyxl

示例:
  erp-bom process
  erp-bom process my_bom.xlsx
  erp-bom diff
  erp-bom diff BOM_A_processed.xlsx BOM_B_processed.xlsx
`);
}

const args = process.argv.slice(2);
const command = args[0];

if (!command || command === 'help' || command === '--help' || command === '-h') {
    showHelp();
    process.exit(0);
}

switch (command) {
    case 'process':
        runPython('bom_processor.py', args.slice(1));
        break;
    case 'diff':
        runPython('bom_diff.py', args.slice(1));
        break;
    default:
        console.error(`未知命令: ${command}`);
        showHelp();
        process.exit(1);
}