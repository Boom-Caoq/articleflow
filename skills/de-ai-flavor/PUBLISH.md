# npm 发布指南

这份文档面向贡献者，说明如何把 `de-ai-flavor` 发布到 npm。

> ⚠️ **发布 npm 涉及账号登录，需要发布者本人执行。** 本文档只提供完整命令清单。

---

## 发布前检查清单

在 `npm publish` 之前，逐项确认：

- [ ] 已注册 npm 账号：<https://www.npmjs.com/signup>
- [ ] 已在 `package.json` 替换所有 `<your-username>` 占位符为真实 GitHub 用户名（已完成：Boom-Caoq）
- [ ] `package.json` 的 `version` 字段正确（语义化版本）
- [ ] `npm pack --dry-run` 检查发布包内容无误
- [ ] 本地 `npm install -g .` 测试包可正常安装并运行 CLI
- [ ] 单元测试通过（如果有）：`npm test`
- [ ] `CHANGELOG.md` 已更新本次变更
- [ ] GitHub 仓库已创建（如果需要）

### 替换占位符

```bash
# 把所有 <your-username> 替换为你的 GitHub 用户名
# （在 PowerShell 里）：
Get-ChildItem -Recurse -Include *.json,*.md | ForEach-Object {
  (Get-Content $_.FullName) -replace '<your-username>', '你的真实用户名' | Set-Content $_.FullName
}

# 或在 Linux/macOS：
grep -rl '<your-username>' --include='*.json' --include='*.md' . | xargs sed -i 's/<your-username>/你的真实用户名/g'
```

---

## 第一次发布

### 1. 登录 npm

```bash
npm login
```

按提示输入：

- Username（npm 用户名）
- Password
- Email
- One-time password（如开启了两步验证）

验证登录状态：

```bash
npm whoami
```

应该输出你的 npm 用户名。

### 2. 检查包名是否被占用

```bash
npm view de-ai-flavor
```

- 如果返回 404：包名可用，继续下一步
- 如果返回版本信息：包名已被占用，需要换名（如 `@你的用户名/de-ai-flavor` 走 scoped 包）

如果需要换名，编辑 `package.json`：

```json
{
  "name": "@你的用户名/de-ai-flavor",
  "publishConfig": {
    "access": "public"
  }
}
```

### 3. 预览发布包

```bash
npm pack --dry-run
```

输出会列出哪些文件会被打包。应该包含：

```
package.json
README.md
LICENSE
CHANGELOG.md
PUBLISH.md
SKILL.md
reference.md
config.json
bin/cli.js
scripts/validate.js
```

不应该包含：

```
node_modules/
output/
.output/
*.log
```

如果不对，检查 `.npmignore`。

### 4. 实际打包预览（可选）

```bash
npm pack
```

会生成 `de-ai-flavor-1.0.0.tgz`。可以解开看看：

```bash
tar -xzf de-ai-flavor-1.0.0.tgz
ls package/
```

确认无误后删除：

```bash
rm -rf package/ de-ai-flavor-1.0.0.tgz
```

### 5. 发布

```bash
npm publish
```

发布成功后会输出：

```
+ de-ai-flavor@1.0.0
```

### 6. 验证发布结果

```bash
# 在 npm 网站查看
open https://www.npmjs.com/package/de-ai-flavor

# 或在本地从 npm 安装测试
npm install -g de-ai-flavor
de-ai-flavor --version
```

---

## 升级版本发布

每次发布新版：

### 1. 更新版本号

```bash
# 补丁版本（bug 修复）：1.0.0 → 1.0.1
npm version patch

# 次版本（新功能，向后兼容）：1.0.0 → 1.1.0
npm version minor

# 主版本（破坏性变更）：1.0.0 → 2.0.0
npm version major
```

这会自动：

- 更新 `package.json` 的 `version`
- 创建一个 git tag（`v1.0.1` 等）
- 在 `git tag` 上运行 `npm version` 钩子

### 2. 更新 CHANGELOG.md

在 `CHANGELOG.md` 顶部加上新版本段落：

```markdown
## [1.0.1] - 2026-09-XX

### 修复
- 修复了某个 bug
```

### 3. 提交 + 推送

```bash
git add .
git commit -m "chore: release v1.0.1"
git push origin main --tags
```

### 4. 重新发布

```bash
npm publish
```

---

## 常见错误处理

### `npm ERR! 403 Forbidden`

原因：包名被占用了，或没有 publish 权限。

解决：

- 换名（用 scoped：`@你的用户名/de-ai-flavor`）
- 或联系当前维护者转让包名

### `npm ERR! 402 Payment Required`

原因：包名是 private，需要付费账户。

解决：检查 `package.json` 没有 `"private": true`。

### `npm ERR! EOTP`

原因：开启了两步验证，需要一次性密码。

解决：

```bash
npm login --otp=123456
# 或发布时
npm publish --otp=123456
```

### `npm ERR! You do not have permission to publish`

原因：你不是包的所有者，或尝试发布到别人的包。

解决：

- 确认包名属于你：`npm owner ls de-ai-flavor`
- 改用 scoped 包名

### README 在 npm 上显示不对

原因：npm 用它自己的渲染器。

解决：在 <https://www.npmjs.com/package/de-ai-flavor> 直接查看渲染效果。如果不对：

1. 检查 `package.json` 的 `description` 字段是否正确
2. 检查 `repository.url` 是否指向真实仓库
3. README 必须 UTF-8 编码

---

## 发布后必做清单

- [ ] 在 npm 网站确认包页面正常：<https://www.npmjs.com/package/de-ai-flavor>
- [ ] 在 GitHub 创建一个 Release（tag 对应版本）
- [ ] 测试 `npm install -g de-ai-flavor` 能正常安装
- [ ] 测试 CLI：`de-ai-flavor "首先其次最后"`
- [ ] 在 README 加上 npm badge：
  ```markdown
  [![npm version](https://img.shields.io/npm/v/de-ai-flavor.svg)](https://www.npmjs.com/package/de-ai-flavor)
  ```
- [ ] 通知社区（如果有的话）

---

## 撤销发布

如果发布后发现严重问题（72 小时内）：

```bash
npm unpublish de-ai-flavor@1.0.0 --force
```

> ⚠️ **npm 不建议撤销发布**。更推荐的做法：发布一个新版本修复问题，而不是撤销旧版本。

---

## 自动化（GitHub Actions）

如果你想让发布自动化，可以创建 `.github/workflows/publish.yml`：

```yaml
name: Publish to npm

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'
      - run: npm ci
      - run: npm test
      - run: npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

需要在 GitHub 仓库设置里添加 `NPM_TOKEN` secret（从 npm 网站生成）。

---

## 工具对照

发布命令速查：

| 场景 | 命令 |
|------|------|
| 登录 | `npm login` |
| 查看当前用户 | `npm whoami` |
| 检查包名 | `npm view de-ai-flavor` |
| 预览发布包 | `npm pack --dry-run` |
| 实际打包 | `npm pack` |
| 发布 | `npm publish` |
| 带 OTP 发布 | `npm publish --otp=123456` |
| 升级补丁版 | `npm version patch` |
| 升级次版 | `npm version minor` |
| 升级主版 | `npm version major` |
| 撤销（限 72h） | `npm unpublish <pkg>@<ver> --force` |
| 全局安装 | `npm install -g de-ai-flavor` |
| 项目安装 | `npm install de-ai-flavor` |

---

## 参考链接

- npm 官方文档：<https://docs.npmjs.com/>
- 创建 npm 账号：<https://www.npmjs.com/signup>
- 包名查询：<https://www.npmjs.com/search?q=de-ai-flavor>
- 语义化版本：<https://semver.org/lang/zh-CN/>
