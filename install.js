#!/usr/bin/env node
/**
 * Post-install script ─ Registers the Trae IDE SKILL
 */

const fs = require('fs');
const path = require('path');

const HOME = process.env.HOME || process.env.USERPROFILE;
if (!HOME) {
    console.log('跳过: 无法确定用户主目录');
    process.exit(0);
}

const SKILLS_DIR = path.join(HOME, '.trae', 'skills', 'erp-bom-processor');
const SOURCE_SKILL = path.join(__dirname, 'SKILL.md');

if (!fs.existsSync(SOURCE_SKILL)) {
    console.log('跳过: 未找到 SKILL.md');
    process.exit(0);
}

try {
    if (!fs.existsSync(SKILLS_DIR)) {
        fs.mkdirSync(SKILLS_DIR, { recursive: true });
    }

    fs.copyFileSync(SOURCE_SKILL, path.join(SKILLS_DIR, 'SKILL.md'));
    console.log('erp-bom-processor SKILL 已注册到 Trae IDE');
} catch (e) {
    console.log('提示: 请手动将 SKILL.md 复制到 ' + SKILLS_DIR);
    console.log('  错误详情: ' + e.message);
}