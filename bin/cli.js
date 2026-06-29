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
  init                  初始化项目目录结构（02_BOMfromSystem/03_order/04_output）

  process [bom-file]    处理 BOM 文件，将原理图BOM转换为格式化ERP BOM
                        无参数时批量处理 03_order/ 下所有文件
    
  diff [files...]       比对多份已处理BOM文件，生成差异清单
                        无参数时自动读取 04_output/ 下所有文件

  test                  运行单元测试，验证核心功能是否正常

  exp-to-bom <exp>       从 OrCAD EXP 文件提取 BOM，相同物料合并
  exp-lib-update <exp>   用元件库更新 EXP 中的描述和料号
  exp-bom-update <bom> <exp>  用 BOM+库 更新 EXP 文件

  help                  显示此帮助信息

环境要求:
  - Node.js >= 14.0.0
  - Python 3.7+ (需安装 pandas, openpyxl)
    pip install pandas openpyxl

示例:
  erp-bom init
  erp-bom process
  erp-bom process my_bom.xlsx
  erp-bom diff
  erp-bom diff BOM_A_processed.xlsx BOM_B_processed.xlsx
  erp-bom test
  erp-bom exp-to-bom my_design.EXP
  erp-bom exp-lib-update my_design.EXP
  erp-bom exp-bom-update my_bom.xlsx my_design.EXP
`);
}

const args = process.argv.slice(2);
const command = args[0];

if (!command || command === 'help' || command === '--help' || command === '-h') {
    showHelp();
    process.exit(0);
}

switch (command) {
    case 'init':
        initProject();
        break;
    case 'process':
        runPython('bom_processor.py', args.slice(1));
        break;
    case 'diff':
        runPython('bom_diff.py', args.slice(1));
        break;
    case 'test':
        runPython('test_runner.py', args.slice(1));
        break;
    case 'exp-to-bom':
        runPython('exp_processor.py', ['to-bom'].concat(args.slice(1)));
        break;
    case 'exp-lib-update':
        runPython('exp_processor.py', ['lib-update'].concat(args.slice(1)));
        break;
    case 'exp-bom-update':
        runPython('exp_processor.py', ['bom-update'].concat(args.slice(1)));
        break;
    default:
        console.error(`未知命令: ${command}`);
        showHelp();
        process.exit(1);
}

function initProject() {
    const cwd = process.cwd();
    const dirs = ['02_BOMfromSystem', '03_order', '04_output'];

    console.log(`初始化 erp-bom 项目结构: ${cwd}\n`);

    dirs.forEach(dir => {
        const fullPath = path.join(cwd, dir);
        if (fs.existsSync(fullPath)) {
            console.log(`  [跳过] ${dir}/ (已存在)`);
        } else {
            fs.mkdirSync(fullPath, { recursive: true });
            console.log(`  [创建] ${dir}/`);
        }
    });

    console.log('\n初始化完成！接下来请:');
    console.log('  1. 将元件库放入 02_BOMfromSystem/');
    console.log('  2. 将待处理BOM放入 03_order/');
    console.log('  3. 运行 erp-bom process 开始处理');
}