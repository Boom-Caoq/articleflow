# Changelog

所有版本变更都会记录在这里。版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [1.0.0] - 2026-09-10

### 新增
- 首发版本。
- `SKILL.md`：五步改写工作流（读配置 → 作者改写 → 质检员诊断 → 针对性修复 → 验收）。
- `config.json`：可配置 persona / style_level / allow_profanity / allow_humor / allow_interruptions / personal_experience / length_control / data_precision / max_revision_iterations / ban_words / output_format，内置 4 个预设（标准知识分享 / 技术博客 / 论坛问答 / 职场沟通）。
- `reference.md`：详细参考资料——AI 味识别维度、八大改写策略、质量检查清单、不同场景适配。
- `bin/cli.js`：`de-ai-flavor` 命令行工具，支持文本校验和 JSON 输出。
- `scripts/validate.js`：文本质量校验（禁用词、个人视角、句式变化度、排比句检测）。
- 内置核心原则：**不缩减原文内容**。改写的目标是改变风格，不是删减信息。
