# 2026-10-22 小组试用指南

> 当前版本请先看 [2026-10-29 试用说明](2026-10-29-trial-update.md)。本文保留初版安装和历史数量。

> 最新试用版本请先看 [2026-10-28 发布说明](2026-10-28-trial-update.md)。本文保留初版步骤与历史数量；当前库存为 1,000 套。

> 此指南保留首轮安装和试用步骤。2026-10-24 在同一分支更新代码，新增内容、配置及本轮验证请先看 [10 月 24 日更新](2026-10-24-trial-update.md)。下方 10 月 22 日数量属于历史验证，不代表本轮重跑。

本轮由 Anda 整合发布供组员试用，使用 **`codex/group-trial-20261022`** 分支，**不合并 main**。原始成员模块继续标为各成员实现；Anda 本轮贡献集中在真实数据、系统接入、前端、AI 交互及租后服务扩展。早期文档中的“尚未发布”属于当时记录，本指南说明本轮试用状态。

## 下载与启动

为保留每个人现有开发内容，建议克隆到新目录：

```sh
git clone --branch codex/group-trial-20261022 https://github.com/seven77-ops/elec5620-group3-rental-agent.git rental-group-trial
cd rental-group-trial
```

需要 Git、Python 3.11+、Node.js 22.23.1 或兼容的新版本及 npm。本轮实际版本和通过数量见 PR 的验证说明。macOS/Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-lock.txt
cd frontend
npm ci
cd ..
.venv/bin/python scripts/dev.py
```

Windows PowerShell（无需激活虚拟环境）：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server/requirements-lock.txt
cd frontend
npm ci
cd ..
.\.venv\Scripts\python.exe scripts/dev.py
```

打开 <http://127.0.0.1:5173>。如果端口已被其他项目占用，可给启动命令追加 `--web-port 5179 --api-port 8019`，再打开 5179。只在本机运行；退出时 Ctrl+C。运行数据保存在忽略的 `.runtime/` 中，不会随 GitHub 提供。

### 可选的真实模型

不配置 API 也可使用表单、房源查询、合同手工填写和租后页面。聊天及可选 AI 提取需要自己的已授权后端配置：复制根目录 `.env.example` 为 `.env`，填写 `RENTAL_AI_ENABLED=1`、完整 HTTPS `RENTAL_AI_URL`、`RENTAL_AI_MODEL`、`RENTAL_AI_API_KEY` 后重启。URL 使用兼容 OpenAI 的 Chat Completions 完整路径。每次外部处理仍需页面上的用户同意。密钥留在本机，勿发群或提交 GitHub。普通 500 条房源查询不需要 Domain/TfNSW 密钥。

## 请依次试用

1. **需求确认与 AI 助手**：新建案例，用表单填写预算口径、区域和房间条件；有模型配置时也可用自然语言。核对后明确确认，再生成推荐。修改偏好后检查版本变化，刷新页面检查记录恢复。
2. **真实房源**：查询、筛选、排序及翻页，打开详情和原广告链接；尝试图片预览、无图片状态、候选保存及报告导出。当前共 500 条广告、71 个区域；335 条有共 1,002 个来源图片链接。图片从原站加载，可能受网络或原站变化影响。
3. **选房后跟进**：保存候选后进入看房/询问记录，填写测试用的中介回复、租金口径与核实信息。核对广告快照和后续回复是否分开呈现，改变偏好后历史记录是否仍清楚。
4. **合同助手**：一条路径是填写双方与租期、租金等资料，核对后保存未签署草稿，预览/下载 PDF、修改保存新版本并检查历史；另一条路径是在单独同意合同处理后上传测试 TXT/DOCX/文本 PDF，检查提取、差异及复核。请用虚构姓名和联系资料测试。AI 提取是可选辅助，应用字段前仍需确认。
5. **租后服务**：明确确认实际租约资料后，尝试选择性带入联系人/地址，记录报修和未发送的英文邮件草稿、同一问题的连续跟进、供应商、搬家/清洁记录与附件。配置模型时检查聊天和页面是否同步更新，确认前是否保持原记录。
6. **退租与押金**：继续核对原 Agent4 的计划及押金操作。正式 Agent3 → Agent4 接收协议仍应由相关成员联调验收；本次试用不能代替该验收。
7. **异常与体验**：尝试取消确认、缺少必填信息、重复操作、刷新、修改偏好后的旧结果，以及手机宽度；反馈是否有难懂文字、重复步骤或跳转不清楚。

## 当前范围与限制

- 广告是带来源和时间的固定快照，在租状态、计价对象和部分事实仍需核实。缺失值不补造，广告金额不自动当作约定租金，未核实广告不自动通过合同交接。
- 合同生成是 NSW 普通整租住宅的**未签署草稿**，采用仓库记录的官方模板；未知信息待补，不自动签署。文本 PDF 复核上限 30 页，图片 OCR 上限 10 页且需要本机 OCR 工具。
- Qwen 等模型会有提取、上下文和表达不足。本轮提供的是可试用版本；仓库的六个用户情景是明确标注的虚构测试，不是真实用户研究或全部场景已通过的证明。
- 邮件、预约、供应商付款及通知均需用户自行处理；页面不会替你实际发送、下单或付款。
- 本次新快照验证不重复消耗真实模型 API；既有真实调用记录与本轮自动回归应分别阅读。

## 反馈与协作

**请先不要直接修改本轮集成代码、往试用分支提交或合并 main。** 在群里 @Anda 提建议，由 Anda 统一修改并更新版本。自己的模块开发仍可保留在自己的分支中，接入变更先在群里沟通。

反馈请附：`使用的系统/浏览器 → 页面和操作步骤 → 预期结果 → 实际结果 → 截图/错误提示`。截图不要带 API 密钥或真实个人资料。

## 本轮发布前验证

在独立冻结快照中新建虚拟环境，按锁定文件重新安装 Python/npm 依赖后验证。环境为 macOS、Python 3.13.2、Node 22.23.1、npm 10.9.8；Windows 命令已提供，但本轮没有 Windows 设备实测。

| 检查 | 本轮实际结果 |
|---|---|
| 根目录 `.venv/bin/python -m unittest discover -s server/tests -v` | 203/203 |
| 分别在 agent1/2/3/4 目录执行 `../.venv/bin/python -m unittest discover -s tests -v` | 52/52、89/89、40/40、57/57 |
| integration 目录执行同一 discover 命令 | 6/6 |
| frontend 目录 `npm run test:api` | 9/9 |
| frontend 目录 `node --experimental-strip-types --test tests/listingPresentation.test.ts` | 1/1 |
| frontend 目录 `npm run build` | TypeScript/Vite 通过，仍有既有 vendor 包体积提示 |
| `.venv/bin/python -m pip check` | 无依赖冲突 |

合计 447 项 Python 测试和 10 项前端单元测试。本轮 Chrome 使用独立案例验证实际表单确认 → Agent1 v1 → Rhodes 5 条真实推荐 → 图片与详情 → 明确保存候选 → 确认并保存未完成草稿 v1 → 内嵌 PDF 预览；另验证租后报修确认保存、未发送标识和待办。检查期间未见页面异常覆盖层或控制台 error/warn。不把历史浏览器套件或既有真实模型调用计入本轮重跑数量。代码复查未发现阻止小组试用的问题。完整共同验收仍待组员执行。

- [GitHub 仓库](https://github.com/seven77-ops/elec5620-group3-rental-agent)
- [试用分支](https://github.com/seven77-ops/elec5620-group3-rental-agent/tree/codex/group-trial-20261022)
- [SCRUM-35：统一前端与接口接入](https://breezebee64.atlassian.net/browse/SCRUM-35)
- [SCRUM-34：Agent2 真实房源与系统接入](https://breezebee64.atlassian.net/browse/SCRUM-34)
- [SCRUM-41：租后服务阶段](https://breezebee64.atlassian.net/browse/SCRUM-41)
- [SCRUM-42：资料接续与连续跟进阶段](https://breezebee64.atlassian.net/browse/SCRUM-42)
