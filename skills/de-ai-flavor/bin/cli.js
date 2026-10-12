#!/usr/bin/env node

/**
 * 去AI味 CLI 工具
 *
 * 命令行接口，用于快速测试文本改写效果
 */

const validate = require('../scripts/validate.js');

const args = process.argv.slice(2);

if (args.length === 0) {
  console.log(`
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           去AI味 (De-AI-Flavor) CLI 工具                   ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

使用方法:
  de-ai-flavor <文本>        验证文本质量
  de-ai-flavor --help        显示帮助

示例:
  de-ai-flavor "首先，其次，最后，综上所述"
  de-ai-flavor --file text.txt

检查项目:
  • 禁止词汇检测
  • 个人视角检查
  • 句式变化度
  • 排比句检测
`);
  process.exit(0);
}

if (args[0] === '--help' || args[0] === '-h') {
  console.log(`
去AI味 CLI 帮助

用法:
  de-ai-flavor [选项] [文本]

选项:
  -h, --help        显示帮助
  -v, --version     显示版本
  -f, --file <文件> 从文件读取文本
  -j, --json        输出JSON格式

示例:
  # 验证文本
  de-ai-flavor "首先，其次，最后，综上所述"

  # 从文件验证
  de-ai-flavor --file output.txt

  # JSON输出
  de-ai-flavor --json "文本内容"
`);
  process.exit(0);
}

if (args[0] === '--version' || args[0] === '-v') {
  console.log('de-ai-flavor v1.0.0');
  process.exit(0);
}

let text = '';

if (args[0] === '--file' || args[0] === '-f') {
  const fs = require('fs');
  const filePath = args[1];
  try {
    text = fs.readFileSync(filePath, 'utf8');
    console.log(`从文件读取: ${filePath}\n`);
  } catch (err) {
    console.error(`错误: 无法读取文件 ${filePath}`);
    process.exit(1);
  }
} else {
  text = args.join(' ');
}

const result = validate.validate(text);
console.log(validate.formatResult(result));

// 如果需要JSON输出
if (args.includes('--json') || args.includes('-j')) {
  console.log('\n--- JSON 输出 ---\n');
  console.log(JSON.stringify(result, null, 2));
}
