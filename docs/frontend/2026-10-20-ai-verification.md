# 本地 AI 接入验证记录

日期：2026-10-20（Australia/Sydney）。基线 `2e375bb`，本地分支 `codex/local-ai-integration`。所有新增代码、文档与测试只保存在本机；没有推送、创建或更新 PR、修改 Jira。

## 验证范围与来源

Agent 3 使用 GitHub main `4701fa1` 中已发布的代码（与前端基线内目录树一致）。新增候选提取模块和测试，原命令行、Schema、提取/复核流程保持兼容。Agent 2 新增辅助推荐解读模块，原资格、分数、排序与报告不被模型修改。

正式启动使用原 `server.app.main` 和独立本地存储 `.runtime/ai-local`。页面自动化另启动 `server.tests.ai_demo_app`，返回来源明确标为 `test_stub`，存储为 `.runtime/ai-browser`。测试替身只用于验证协议、展示与确认流程；本次没有真实 API 凭据，真实模型成功及输出质量尚未验证。

## 已执行验证

| 范围 | 结果 | 本地日志 |
| --- | --- | --- |
| Agent 1 原偏好服务 | 52 通过 | agent1-tests.log |
| Agent 2（含新增解读） | 89 通过 | agent2-final.log |
| Agent 3（含新增分析） | 40 通过 | agent3-final.log |
| Agent 4 原租后流程 | 57 通过 | agent4-tests.log |
| 服务端完整回归 | 57 通过 | server-final.log |
| 原跨 Agent 集成 | 6 通过 | integration-tests.log |
| 前端请求工具 | 9 通过 | frontend-api-final.log |
| 浏览器完整流程 | 19 通过 | browser-final.log |
| 生产构建上的 AI 流程 | 7 通过 | production-browser.log |
| TypeScript / Vite 构建 | 通过 | build-final.log |

Python 合计 301 项。前端请求测试使用 Node 内置 test runner，实际导入 TypeScript API 客户端；浏览器测试使用实际本地 HTTP 服务。服务端57项覆盖最新超时修复；Agent1/4与原跨Agent套件在本轮集成中执行，后续仅修改AI传输及前端边界时没有重复无关套件。

执行方式：各模块在自己的目录执行 `../.venv/bin/python -m unittest discover -s tests -v`；服务端在仓库根执行 `.venv/bin/python -m unittest discover -s server/tests -v`。前端执行 `npm --prefix frontend run test:api`、`npm --prefix frontend run build` 和 `WEB_TEST_BASE_URL=http://127.0.0.1:5183 npm --prefix frontend run test:e2e`；生产AI检查将地址改为4183并限定 `e2e/ai.spec.ts`。本机 Playwright 显式指定已安装 Chromium 路径。

额外实际页面检查：生产预览无 pageerror / console.error，360px时 document宽度360px。桌面/手机截图为 `contract-ai-production-desktop.png`、`contract-ai-production-mobile.png`，均来自显式 test_stub 测试服务。生产构建通过，仍有基线已有的1.14MB vendor包体积警告。

独立模块与集成复查已通过，复查发现的以下问题均有先失败、后通过的回归：总超时覆盖慢响应体及DNS executor等待、过期pending请求不重绑定变化后的输入、服务请求ID与响应ID区分、浏览器超时覆盖正文读取、JSON null与非法正文区分、迟到应用响应不覆盖其他合同或刷新已离开的案例。完整分支最终复查结论在收尾时补记。

Agent3单独补丁已在临时导出的GitHub基线 `2e375bb` 上执行 `git apply --check`，退出0。补丁路径见交接单。

所有日志与截图在忽略目录 `.runtime/ai-qa/`，不会提交为真实模型调用证据。浏览器插件不可用，本次使用仓库已有 Playwright 与本机 Chromium 实际运行页面。

## 核心检查

- 外部处理勾选默认关闭；未配置 API 时禁用 AI 生成，原流程可继续。
- 引文与原文行、金额/日期/枚举核对，未知、重复、伪造或缺失字段不能应用。
- 规则预览不改变正式复核；用户选字段并确认后才按原修正逻辑保存版本。
- AI 解释只关联已有发现/已保存合格推荐，不能更改评分、排名或人工审核门禁。
- 模型调用在数据库写事务外；撤销同意、改动复核或选房后，旧结果不可应用。
- 持久化请求收据、输入绑定、并发请求及旧请求晚返回时的最近结果顺序经过回归。
- 请求/响应 ID 分开记录，仅显示服务实际返回的用量；测试替身在页面显著标注。
- 失败保留原规则结果，重试保持原请求身份；取消外部处理勾选后不能继续模型重试。
- 切换分析会清除字段选择和确认；离开合同或切换复核后，旧应用响应不能覆盖当前页面。

## 仍需配置后的核对

1. 按 [运行配置](2026-10-20-ai-local-run.md) 在后端本机 `.env` 填写接口、模型和密钥，重启。
2. 使用合成合同真实调用，检查正常、租金冲突、无效引文与服务超时；确认供应商支持当前消息/JSON协议。
3. 模型解释的语义正确性仍需人工核对：引用存在及结构合法不能证明每句解释都由证据充分推出。
4. 已发送给外部服务的内容不能收回；进程崩溃恢复不承诺外部计费严格只发生一次。
5. 给 Agent 3 同学核对 [交接单](agent3-ai-handoff.md) 后，再决定如何同步，当前没有上传。
