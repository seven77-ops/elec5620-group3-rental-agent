# 官方语料采集只读集成复查

复查日期：2026-10-30。范围：官方采集 brief/report、`capture.py`、`sources.py`、`index.py`、`official-expansion.json` 及其公开 PDF 原件。仅创建隔离临时索引和 PDF 预览；未读取真实案例、合同上传或运行时私有数据，未修改共享代码、发布索引或重启服务。

## 两项结论

- **范围符合：通过。** 八份新增官方/学校文档齐全，分类与当前快照正确；两份 PDF 的全部 30 页正文、原始字节哈希和版本一致，标准租约确为空白模板。当前快照没有发现失败页被冒充正文。
- **代码质量：修复后通过。** 首轮发现的两项 P2 校验缺口已修正并通过独立复查：Reader 失败页会被拒绝，索引绑定注册来源身份/类型，并验证固定本地公开 PDF 原件、正文与完整元数据。最终 20 项相关测试通过，12 项原始攻击探针及 4 项补充边界探针通过。`source_types` 的关键词与向量过滤逻辑本身通过复查。下方保留首轮问题及复现，末节记录关闭证据。

## 首轮实质问题（已修复，保留审计记录）

### [P2] HTTP 200 包装的常见网关/服务失败页仍会被发布为官方正文

位置：`server/app/rag/capture.py:18`、`:46`、`:64`。

`ERROR` 覆盖了 403、特定 404、若干拒绝/挑战页面，以及以 `Error`、`Forbidden` 等开头的 `Title:`，但没有覆盖常见的 `Title: 503 Service Unavailable`、`Title: 502 Bad Gateway`，正文标题 `# 503 Service Unavailable` 也不会匹配。只要 Reader 返回 HTTP 200、官方 URL envelope 正确、错误说明超过 300 字符，`parse_source` 就会给错误页生成正常的 `document_version` / `content_hash` 并返回官方知识记录。`capture()` 只检查 Reader 自身 HTTP 状态，因此同样会受到影响。

离线复现采用已注册 `condition-reports` 来源，没有任何网络调用：

```python
from server.app.rag.capture import parse_source
from server.app.rag.sources import SOURCES

source = next(s for s in SOURCES if s[0] == 'condition-reports')
body = (
    'The requested service is temporarily unavailable. The server is temporarily '
    'unable to service your request due to maintenance downtime or capacity '
    'problems. Please try again later. If this problem persists, contact the '
    'website administrator. Your requested content could not be retrieved at '
    'this time. This page is a generated error response and is not the document '
    'you requested.'
)
raw = ('Title: 503 Service Unavailable\nURL Source: ' + source[2]
       + '\nMarkdown Content:\n# 503 Service Unavailable\n\n' + body)
doc = parse_source(source, raw, checked_at='2026-10-30')
print(doc['document_id'], len(doc['text']))
# 当前结果：condition-reports 407；应抛 ValueError。
```

另一份 `Title: 502 Bad Gateway` 的合理长度错误说明也被接受，正文 406 字符。建议针对 envelope 标题/状态信号和正文错误标题增加明确拒绝规则，并补充“HTTP 200 代理包装错误”的回归测试；拒绝必须发生在生成文档记录之前。当前八份快照正文未出现这些失败标记，问题影响未来重新采集的可靠性。

### [P2] 索引只信任主机类别，未绑定已注册来源身份/类型与 PDF 哈希

位置：`server/app/rag/index.py:88`–`:98`。

采集入口 `_source()` 严格要求完整注册 tuple，且 `parse_pdf()` 固定 PDF 哈希，这两层是正确的；但 `KnowledgeIndex.prepare()` 不使用 `SOURCES`、`SOURCE_TYPES`、`PDF_DOWNLOADS` 或 `PDF_SHA256` 验证官方输入。它只检查来源类型集合、NSW jurisdiction、HTTPS 主机，以及可选 `page_count`。因此本地导入/刷新集成一旦提供了错误记录，发布层不会发现：

- 已注册 `standard-lease` 可以使用其正确官方 landing URL，却被标成 `official_guidance`，没有 PDF provenance，正文和版本随意，然后成功发布检索。模板与正式指引的区分会失效。
- 任意未审核的 NSW 官方主机路径，加上 `source_type=official_template`、任意 `download_url` 和 `page_count=1`，即使 `document_version` / `content_hash` 是 `not-real`，也能作为模板发布。无需提供已审核 PDF 哈希或真正的 PDF。

离线临时目录探针结果：

```text
ACCEPTED_INDEX_PROBE misclassified_lease
  document_id=standard-lease
  source_type=official_guidance
  source_url=<正确的已注册标准租约 landing URL>
  document_version=not-real

ACCEPTED_INDEX_PROBE unreviewed_government_template
  document_id=made-up-template
  source_type=official_template
  source_url=https://www.nsw.gov.au/not-reviewed
  download_url=https://www.nsw.gov.au/user-content/synthetic-filled-contract.pdf
  document_version=not-real
```

探针正文仅为 `Synthetic trusted-public review probe.`，没有私人内容，也未读取这些 URL。这不是已发现的公开写入接口漏洞；它是发布边界不能兑现“仅审核过来源/空白原件”的一致性保证。建议至少将已注册 ID 的 URL 和 `SOURCE_TYPES` 绑定，要求 `official_template` 对应审核过的 PDF URL/哈希，对 PDF 页面和正文哈希作一致性验证；增加上述错误分类、错误哈希及未审核模板的回归测试。若保留测试/其他可信官方来源兼容入口，应与正式审核语料入口明确区分。

## 符合项与证据

### 八份文档完整性

`official-expansion.json` 恰为八条，ID、标题、`source_url` 都与注册表 tuple 一致；`language=en`、`scope=public`、`jurisdiction=NSW`；每条正文 SHA-256 都等于 `content_hash`，HTML 文档的 `document_version` 也等于正文哈希。

| ID | 分类 | 正文字符 | 审计结果 |
| --- | --- | ---: | --- |
| standard-lease | official_template | 62,752 | 全部 20 页，与保存 PDF 重新提取结果逐字符相同 |
| tenant-information | official_guidance | 34,202 | 全部 10 页，与保存 PDF 重新提取结果逐字符相同 |
| condition-reports | official_guidance | 6,564 | 正文、标题与责任/搬入搬出章节保留 |
| shared-housing | official_guidance | 10,949 | 转租、转让、同住人、同住押金与退出相关限定保留 |
| student-off-campus | student_guidance | 4,716 | University of Sydney 来源，未归类成 NSW Government |
| rent-increases | official_guidance | 7,571 | 增租、续租/替换租约、社会住房、争议等章节保留 |
| wear-and-damage | official_guidance | 6,575 | 双方责任、家暴限定与分类示例保留 |
| landlord-access | official_guidance | 4,901 | 通知日计数、紧急例外、检查维修、管理营销等限定保留 |

六份网页正文未独立联网重新采集，因此本结论限于快照结构/内容和采集报告的一致性，不声称重新核对了现时网页的逐字完整性。快照仍有少量 “Listen” / “On this page” 导航及源站文字重复，不影响本次已识别的实质段落；不列为阻断项。

### PDF provenance 与空白模板

- `standard-lease-2026-09-21.pdf`：568,096 字节，SHA-256 `5addb961d6864a794f1f5e44a74e21e5216e762eeeac9e176ec088c004480c64`。与 `PDF_SHA256`、快照 `document_sha256` / `document_version` 及既有批准空白模板的原始字节完全一致。`## Page N` 为连续 1–20，重新提取全文逐字符一致，最短页 680 字符。
- `tenant-information-2026-10-08.pdf`：244,290 字节，SHA-256 `a4e0eb3924f1813bab83a75c4e97ae62ec9098be11d41e8abce9f2ede1213dce`。与固定哈希和元数据一致；连续 1–10 页全文逐字符一致，最短页 2,653 字符。
- 标准模板有 127 个 AcroForm 字段、137 个 widget；字段及全部 annotation 的 `/V` 均为空/关闭。使用 Poppler 渲染并目检第 1、19、20 页：身份、日期、通知地址及各方签名区域为空；没有已填写人名或签名。完整 PDF 字节与批准空白原件相同，进一步排除了未检查页被替换。
- `parse_pdf()` 在正文提取前检查固定原始字节哈希、加密/页数、标准模板的字段及 annotation 值；提取后拒绝短/不可提取页。页面 chunk 的 `page` 与 PDF `#page=N` 链接由已知页标题派生，实际快照页数正确。

PDF 原件（未修改）：

- `data/knowledge/en/files/standard-lease-2026-09-21.pdf`
- `data/knowledge/en/files/tenant-information-2026-10-08.pdf`

### 正确的信任与过滤边界

- `capture._source()` 在发起请求前拒绝任意/修改 tuple；没有用户控制的任意抓取 URL。
- 抓取使用固定 Reader URL 和 PDF 映射、不跟随重定向、流式大小限制；原始连接失败、非 2xx、错误媒体类型、错误官方 landing 链接及 PDF 哈希变化会被拒绝。
- `student_guidance` 索引只允许学校主机；`official_guidance` / `official_template` 只允许政府主机，能拦截把学校 URL 标成政府来源的简单伪造。局部产品指南的固定本地身份校验更严格。
- `source_types` 关键词过滤在 SQL 的 `LIMIT` 之前，向量过滤在评分/截断之前；25 条其他类型结果不会挤掉 limit=1 的学校来源结果，空 tuple 返回空结果，作用域没有发现交叉泄漏。
- 在临时 SQLite 中发布当前八份快照得到 90 个 chunks：6 份官方指引 59 个、1 份模板 20 个、1 份学校指引 11 个。类型与页级来源保留。

## 运行的验证

```text
.venv/bin/python -m unittest \
  server.tests.test_rag_capture \
  server.tests.test_rag_expansion.ExpansionIndexTests \
  server.tests.test_product_guide -v

Ran 17 tests
OK
```

另运行两个只读 Python 审计：八份元数据/正文哈希/本地公开 PDF 精确再提取/页码/空白值检查全部通过；两个失败 envelope 和两个发布身份探针复现上述缺口。没有调用 cloud embeddings、真实服务或用户案例 API。

复查时 `scripts/rag_index.py` 和服务初始 snapshot 装载仍处于父任务待完成集成范围；本报告未把这项已分配的进行中工作当作额外缺陷。最终仍应由父任务完成合并/发布/路由的整体验证。

## 修复后的独立复查与问题关闭

父任务及采集作者修复后，重新阅读 `capture.py`、新增 `provenance.py`、`index.py` 和回归测试。原两项 P2 均关闭，没有新增阻断问题。

- `capture._http_error_page()` 在 Reader envelope 标题及正文前导错误标题检查常见 4xx/5xx 标签，裁剪导航后再次检查。HTTP 200 包装的 502/503/504/500 错误页回归测试覆盖 `parse_source()` 和 `capture()`；正常正文讨论服务错误不会被误拒。
- `provenance.validate_registered_identity()` 对已注册 ID 绑定 canonical URL 和 `SOURCE_TYPES`，对已注册 URL 反向绑定 ID，拒绝把标准租约换 alias ID 后伪装成普通指引。未注册的模板、学校指引和 PDF 下载都被拒绝。
- `standard-lease` 和 `tenant-information` 均从固定本地公开原件路径读取 bytes，先核对固定 SHA-256，再使用全页提取结果核对 `text`、`document_version`、`document_sha256`、`download_url`、`page_count`、`content_hash`。缓存键包括原始 bytes，固定文件改变不会绕开哈希检查。
- 调用者的 `original_file` 只作为未采用的输入元数据，不决定读文件路径。补充探针设置其为 `/not/read/synthetic-private-contract.pdf`，并用只读方法调用跟踪确认实际只读取固定 `data/knowledge/en/files/standard-lease-2026-09-21.pdf`，没有尝试读取调用者路径。
- 为既有合成测试保留的未注册普通政府主机 `official_guidance` 兼容入口仍存在；它不能复用任何已注册 canonical URL、不能声明模板/学校类型或附带未注册 PDF 下载。这是明确的兼容边界，不是公开用户文档导入接口。

原 12 项离线探针结果：

```text
REJECTED lease_as_guidance
REJECTED lease_wrong_url
REJECTED school_as_government
REJECTED lease_wrong_download
REJECTED lease_bad_original_hash
REJECTED lease_bad_version
REJECTED lease_bad_body
REJECTED lease_bad_page_count
REJECTED statement_bad_original_hash
REJECTED unregistered_template
REJECTED 503 Service Unavailable
REJECTED 502 Bad Gateway
BOUNDARY RECHECK PASS 12 probes
```

额外三项拒绝探针通过：注册租约 URL 换 alias ID、未注册学校指引、未注册普通指引附 PDF 下载；第四项路径跟踪通过。当前八份原始快照仍能正常发布为 90 chunks。

最终重新运行相同相关测试命令（新增回归测试后）：

```text
Ran 20 tests in 0.472s
OK
```

以上均使用临时 SQLite 或纯函数/公开本地 PDF，没有访问实际案例或外部服务，也没有修改共享实现。
