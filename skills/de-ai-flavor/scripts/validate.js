#!/usr/bin/env node

/**
 * 去AI味 - 文本质量验证脚本
 *
 * 用于检查改写后的文本是否符合人类写作特征
 *
 * 使用方法:
 *   node validate.js <text>
 *   node validate.js --file <path>
 *   cat state.json | node validate.js --stdin
 */

const fs = require('fs');
const path = require('path');

// 禁止词汇清单
const BAN_LIST = [
  '赋能', '痛点', '底层逻辑', '值得注意的是', '综上所述', '不仅如此',
  '与此同时', '在当今社会', '具有重要意义', '发挥着关键作用', '首先',
  '其次', '再次', '最后', '总而言之', '简而言之', '不言而喻', '不言而明',
  '从某种意义上来说', '从本质上来看', '本质上', '核心', '关键', '至关重要',
  '不可或缺', '深远意义', '显著提升', '生态', '闭环', '赛道', '破局',
  '值得注意的是', '值得强调的是', '必须指出', '引言', '摘要'
];

// 禁止句式
const BAN_PATTERNS = [
  /首先[，。].*其次[，。].*最后[，。]/,
  /第一[、\s].*第二[、\s].*第三/,
  /总[之]?结[来说述]/,
  /不是.*而是.*/g,
  /提出问题[，\s]分析问题[，\s]解决问题/
];

/**
 * 计算句子长度标准差
 */
function calculateSentenceVariance(text) {
  const sentences = text.split(/[。！？；\n]/).filter(s => s.trim().length > 0);
  if (sentences.length < 3) return 0;

  const lengths = sentences.map(s => s.length);
  const mean = lengths.reduce((a, b) => a + b, 0) / lengths.length;
  const variance = lengths.reduce((sum, len) => sum + Math.pow(len - mean, 2), 0) / lengths.length;

  return Math.sqrt(variance);
}

/**
 * 检查禁止词汇
 */
function checkBanList(text) {
  const found = [];
  for (const word of BAN_LIST) {
    if (text.includes(word)) {
      // 统计出现次数和位置
      let count = 0;
      let index = text.indexOf(word);
      while (index !== -1) {
        count++;
        found.push({
          word,
          count,
          position: index,
          context: text.substring(Math.max(0, index - 20), index + word.length + 20)
        });
        index = text.indexOf(word, index + 1);
      }
    }
  }
  return found;
}

/**
 * 检查禁止句式
 */
function checkBanPatterns(text) {
  const found = [];
  for (const pattern of BAN_PATTERNS) {
    if (typeof pattern === 'string') {
      if (text.includes(pattern)) {
        found.push({ pattern: pattern, match: 'literal' });
      }
    } else {
      const matches = text.match(pattern);
      if (matches) {
        found.push({ pattern: pattern.toString(), matches });
      }
    }
  }
  return found;
}

/**
 * 检查个人视角
 */
function checkPersonalVoice(text) {
  const iCount = (text.match(/我/g) || []).length;
  const weCount = (text.match(/我们/g) || []).length;
  const totalPersonal = iCount + weCount;

  return {
    i_count: iCount,
    we_count: weCount,
    total: totalPersonal,
    has_sufficient: totalPersonal >= 3
  };
}

/**
 * 检查句式均匀度
 */
function checkSentenceUniformity(text) {
  const variance = calculateSentenceVariance(text);
  return {
    variance: variance.toFixed(2),
    is_varied: variance > 3
  };
}

/**
 * 检查排比句
 */
function checkParallelism(text) {
  // 简单检测连续使用"的"的句子
  const sentences = text.split(/[。！？\n]/);
  let parallelCount = 0;
  let maxParallel = 0;
  let inParallel = false;

  for (const sentence of sentences) {
    const hasParallel = (sentence.match(/的/g) || []).length >= 3;
    if (hasParallel) {
      if (inParallel) {
        parallelCount++;
        maxParallel = Math.max(maxParallel, parallelCount);
      } else {
        inParallel = true;
        parallelCount = 1;
      }
    } else {
      inParallel = false;
      parallelCount = 0;
    }
  }

  return {
    max_parallel_count: maxParallel,
    is_acceptable: maxParallel <= 2
  };
}

/**
 * 主验证函数
 */
function validate(text) {
  const result = {
    timestamp: new Date().toISOString(),
    text_length: text.length,
    checks: {},
    summary: {
      passed: true,
      issues: []
    }
  };

  // 1. 禁止词汇检查
  const banListResults = checkBanList(text);
  result.checks.ban_list = {
    found: banListResults,
    passed: banListResults.length === 0
  };
  if (banListResults.length > 0) {
    result.summary.passed = false;
    result.summary.issues.push(`发现 ${banListResults.length} 处禁止词汇`);
  }

  // 2. 禁止句式检查
  const banPatternResults = checkBanPatterns(text);
  result.checks.ban_patterns = {
    found: banPatternResults,
    passed: banPatternResults.length === 0
  };
  if (banPatternResults.length > 0) {
    result.summary.passed = false;
    result.summary.issues.push(`发现 ${banPatternResults.length} 种禁止句式`);
  }

  // 3. 个人视角检查
  const personalVoiceResults = checkPersonalVoice(text);
  result.checks.personal_voice = personalVoiceResults;
  if (!personalVoiceResults.has_sufficient) {
    result.summary.passed = false;
    result.summary.issues.push('个人视角不足（需要至少3处"我"或"我们"）');
  }

  // 4. 句式均匀度检查
  const uniformityResults = checkSentenceUniformity(text);
  result.checks.sentence_uniformity = uniformityResults;
  if (!uniformityResults.is_varied) {
    result.summary.passed = false;
    result.summary.issues.push(`句式过于均匀（标准差${uniformityResults.variance}，需要>3）`);
  }

  // 5. 排比句检查
  const parallelismResults = checkParallelism(text);
  result.checks.parallelism = parallelismResults;
  if (!parallelismResults.is_acceptable) {
    result.summary.passed = false;
    result.summary.issues.push(`排比句过多（连续${parallelismResults.max_parallel_count}个）`);
  }

  return result;
}

/**
 * 格式化输出
 */
function formatResult(result) {
  const lines = [];
  lines.push('='.repeat(60));
  lines.push('去AI味 - 文本质量验证报告');
  lines.push('='.repeat(60));
  lines.push(`文本长度: ${result.text_length} 字符`);
  lines.push(`验证时间: ${result.timestamp}`);
  lines.push('');

  lines.push('【检查结果】');
  lines.push(`整体状态: ${result.summary.passed ? '✅ 通过' : '❌ 未通过'}`);
  lines.push('');

  // 禁止词汇
  const banCheck = result.checks.ban_list;
  lines.push(`1. 禁止词汇检查: ${banCheck.passed ? '✅ 通过' : '❌ 未通过'}`);
  if (banCheck.found.length > 0) {
    lines.push(`   发现 ${banCheck.found.length} 处:`);
    banCheck.found.slice(0, 5).forEach((item, i) => {
      lines.push(`   - "${item.word}" 出现 ${item.count} 次`);
    });
    if (banCheck.found.length > 5) {
      lines.push(`   ... 还有 ${banCheck.found.length - 5} 处`);
    }
  }

  // 个人视角
  const voiceCheck = result.checks.personal_voice;
  lines.push(`2. 个人视角检查: ${voiceCheck.has_sufficient ? '✅ 通过' : '❌ 未通过'}`);
  lines.push(`   "我"字 ${voiceCheck.i_count} 处，"我们" ${voiceCheck.we_count} 处`);

  // 句式变化
  const uniformCheck = result.checks.sentence_uniformity;
  lines.push(`3. 句式变化度: ${uniformCheck.is_varied ? '✅ 通过' : '❌ 未通过'}`);
  lines.push(`   句子长度标准差: ${uniformCheck.variance} (需要 > 3)`);

  // 排比句
  const paraCheck = result.checks.parallelism;
  lines.push(`4. 排比句检查: ${paraCheck.is_acceptable ? '✅ 通过' : '❌ 未通过'}`);
  lines.push(`   最大连续排比: ${paraCheck.max_parallel_count}`);

  lines.push('');

  // 问题汇总
  if (result.summary.issues.length > 0) {
    lines.push('【需要改进】');
    result.summary.issues.forEach((issue, i) => {
      lines.push(`${i + 1}. ${issue}`);
    });
  } else {
    lines.push('【总结】');
    lines.push('文本已符合人类写作风格！');
  }

  lines.push('');
  lines.push('='.repeat(60));

  return lines.join('\n');
}

// 命令行入口
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log('去AI味 - 文本质量验证工具');
    console.log('');
    console.log('使用方法:');
    console.log('  node validate.js <文本>');
    console.log('  node validate.js --file <文件路径>');
    console.log('  cat state.json | node validate.js --stdin');
    console.log('');
    console.log('示例:');
    console.log('  node validate.js "首先其次最后总之"');
    console.log('  node validate.js --file output/final_text.md');
    process.exit(0);
  }

  let text = '';

  if (args[0] === '--file' && args[1]) {
    // 从文件读取
    try {
      text = fs.readFileSync(args[1], 'utf8');
    } catch (err) {
      console.error(`无法读取文件: ${args[1]}`);
      process.exit(1);
    }
  } else if (args[0] === '--stdin') {
    // 从标准输入读取
    text = fs.readFileSync(0, 'utf8');
    // 如果是JSON，尝试解析
    try {
      const json = JSON.parse(text);
      text = json.final_text || json.original_text || text;
    } catch (e) {
      // 不是JSON，使用原文
    }
  } else {
    // 直接文本
    text = args.join(' ');
  }

  const result = validate(text);
  console.log(formatResult(result));

  // 输出JSON格式结果（用于程序调用）
  if (args.includes('--json')) {
    console.log(JSON.stringify(result, null, 2));
  }

  process.exit(result.summary.passed ? 0 : 1);
}

// 导出函数供模块使用
module.exports = {
  validate,
  checkBanList,
  checkBanPatterns,
  checkPersonalVoice,
  checkSentenceUniformity,
  checkParallelism,
  formatResult,
  BAN_LIST
};

// 如果是直接运行
if (require.main === module) {
  main();
}
