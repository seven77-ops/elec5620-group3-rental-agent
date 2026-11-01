# Issue report 两页签简化

## 页面

将 Aftercare services 的 Move-out and bond 替换为 **Issue report**，旧 moveout/bond 链接仍兼容。此页仅有 **Report issue** 与 **History**：

- 表单：Issue type、Issue description、可选证据文件、Submit report。日期由服务器提交时自动记录。
- 类型：租金/押金、家具、维修、租住期间、搬出、搬出之后、其他。
- 不显示租约资料、病例编号、计划、押金激活、提醒、额外标题或诉求字段。不要求先创建或确认租约；其他 Repairs / Utilities / Moving and cleaning 页签保留。
- History 汇总本地新旧报告、日期、文件、状态和人工建议。旧报告额外的金额、诉求和来源引用可在 Original report details 中展开，数据未删除。

复用已验证的本地 JPG/PNG/PDF 上传、预览、下载与冻结请求重试。隐藏系统原生文件选择文本，改用英文 Upload files 按钮，避免中文操作系统把表单控件显示为中文。

## 数据与审核

新增独立 issue_report 保存对象，直接提交无需虚构“已确认租约”。保留原始描述、受限类型、服务器时间、幂等请求、版本冲突及病例归属文件校验。旧 Agent4 记录继续读取，不迁移或覆写。

- POST /cases/{case_id}/issue-reports：request_id/category/description/attachment_ids。
- GET /issue-reports：按实际时间排序的新旧报告历史。
- POST /issue-reports/{report_id}/advice：request_id/expected_version/note。

Human review 同时显示旧报告和新问题，保存建议后回显到 History；原报告不被改写。Case progress 同步计入新问题的待处理/已完成状态。报告和附件不会自动发送给外部 AI。

## 验证

- 相关后端 56 项通过，包含直接上报、所有类型、自动日期、无租约、重试、原文保留、跨病例文件拒绝、旧报告、建议版本与持久化、进度和用户指南。
- 前端单元 70 项通过；TypeScript/Vite 构建、Prettier 和 git diff --check 通过。
- 五个独立浏览器场景通过：表单→文件→人工审核→历史建议；移动端丢失上传和提交响应重试；旧报告及原详情保留；无密钥审核队列；合同引用和建议长度。最后的旧报告详情检查补齐 Collapse 导入后定向重跑通过。
- 被移除的旧计划/押金/弹窗 UI 测试保留源代码并显式标记为历史覆盖，当前 UI 覆盖由 issue-report.spec.ts 取代；Agent4 底层规则与状态测试继续保留。
- README、用户指南、canonical documents、API 契约已同步。公共 RAG 仅更新产品帮助，其他文档、关键词及向量的摘要不变，更新前已备份。
- 本地服务按当前实际环境重新加载，保留 Jev active；重启前后五个数据库逻辑摘要一致。验证使用临时虚构数据，没有向既有用户报告/合同中写测试内容。

日志：/tmp/flat-issue-*.log；截图：/tmp/flat-issue-report.png、/tmp/flat-issue-history.png、/tmp/flat-issue-mobile.png；重载记录：/tmp/flat-issue-reload-result.json。
