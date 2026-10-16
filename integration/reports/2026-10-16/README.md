# 2026-10-16 跨 Agent 本地验证记录

执行日期：2026-10-16（Australia/Sydney）。临时干净虚拟环境，Python 3.13.2；按双方 requirements.txt 安装 jsonschema 4.25.1、pypdf 6.21.0，完整解析版本见 dependencies.txt。本记录由本地实际运行生成，不代表 Yirui / Chenyang 共同验收、真人批准或网络投递。

|检查|预期|实际与证据|
|---|---|---|
|Agent 3 README 工作目录|从 agent3/ 可以启动模块|整理前 No module named contract_agent；整理后退出0，见 directory-fix.json 和 handoff-tests.txt|
|目录整理完整性|35个移动文件内容不变|逐文件与上游原始内容比较，全部一致；只有文档另行补入口说明|
|Agent 1 交接样例|偏好正文符合Schema；外层搜索、版本、指纹一致；案例ID与搜索ID分开|通过；仅模拟确认，不代表实现确认服务|
|Agent 2 原有测试|71项通过|71/71，见 agent2-tests.txt|
|Agent 3 原有测试|25项通过|25/25，无跳过，见 agent3-tests.txt|
|仓库交接检查|6项通过|6/6，见 handoff-tests.txt；覆盖目录入口、样例映射、现场选房包/重试、无合同同意、租金冲突门禁、同ID不同输入拒绝|
|编译检查|双方模块和测试可编译|退出0，见 execution.json|
|正常文件交接|合成偏好→新选房包→合同复核，保留批次/版本/选择引用|Reviewed，见 selection.json、selection.selection.json、review.json / .md|
|同内容请求重试|同一review_id及完整结果，不重复创建|review.json 与 retry.json 完全一致，见 handoff-results.json|
|合同租金从500改为650|识别与房源原始租金冲突，等待人工|Awaiting Human Review，含 rent_difference，见 conflict-agreement.txt、conflict.json / .md|
|人工决定前生成问题|拒绝，不生成问题包|退出2，见 blocked-questions.txt；本次未冒充人工批准|

复现命令和输入字段见 [联调说明](../../README.md)。各项退出码见 execution.json / handoff-results.json；SHA-256 清单见 sha256.json。receive 的 SQLite 收据仅用于临时验证，没有提交数据库。

固定房源快照/选择时点为2026-09-17，合同规则参考日期为2026-10-15。这是同一组合成测试数据的交接验证；不代表房源已在2026-10-16重新核实。报告中的生成时间和review UUID随首次调用变化；同一请求的持久收据可保证重试返回原结果。

仍待完成：Agent 1 真实对话、确认与版本持久化及调用适配；Chenyang 对接口约定的共同确认；跨机器投递、身份验证和UI接入。此记录不关闭这些待办。
