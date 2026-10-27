import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Select, Space, Tag, Upload } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { getLivingAttachments, uploadLivingAttachment } from "../../api/living";
import type { LivingAttachment, LivingRecord } from "../../api/living";
import { newRequestId } from "../../api/client";
import { Failure } from "../../components/Common";
import { useAction } from "../../components/useAction";
const purposes: Record<LivingAttachment["purpose"], string> = {
  repair: "报修照片或资料",
  receipt: "收据",
  moveout: "退租资料",
};
const allowedTypes = new Set(["image/jpeg", "image/png", "application/pdf"]);
export default function LivingFiles({
  caseId,
  repairs,
}: {
  caseId: string;
  repairs: LivingRecord["repairs"];
}) {
  const [items, setItems] = useState<LivingAttachment[]>([]),
    [file, setFile] = useState<File | null>(null);
  const [purpose, setPurpose] = useState<LivingAttachment["purpose"]>("repair"),
    [repairId, setRepairId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState<unknown>(null);
  const generation = useRef(0),
    action = useAction();
  const load = useCallback(async () => {
    const token = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const result = await getLivingAttachments(caseId);
      if (generation.current === token) setItems(result.items);
    } catch (error) {
      if (generation.current === token) setError(error);
    } finally {
      if (generation.current === token) setLoading(false);
    }
  }, [caseId]);
  useEffect(() => {
    setFile(null);
    setRepairId(null);
    setPurpose("repair");
    setItems([]);
    action.clear();
    void load();
    return () => {
      generation.current++;
    };
  }, [load]);
  const upload = () => {
    if (!file || action.busy || loading || action.error) return;
    const token = generation.current,
      requestId = newRequestId(),
      chosen = file,
      chosenPurpose = purpose,
      chosenRepair = repairId;
    void action.run(async () => {
      try {
        await uploadLivingAttachment(
          caseId,
          chosen,
          chosenPurpose,
          chosenRepair,
          requestId,
        );
        if (generation.current !== token) return;
        const result = await getLivingAttachments(caseId);
        if (generation.current !== token) return;
        setItems(result.items);
        setFile(null);
        setError(null);
      } catch (error) {
        if (generation.current === token) throw error;
      }
    });
  };
  const frozen = action.busy || Boolean(action.error);
  return (
    <section
      className="living-files living-section"
      aria-label="照片与收据附件"
    >
      <div className="living-section-heading">
        <div>
          <h2>照片与收据</h2>
        </div>
        <Button
          aria-label="读取附件列表"
          loading={loading}
          disabled={action.busy}
          onClick={() => {
            action.clear();
            void load();
          }}
        >
          读取附件列表
        </Button>
      </div>
      {Boolean(error || action.error) && (
        <>
          <Failure error={error || action.error} />
          {Boolean(action.error) && (
            <Space wrap>
              <Button
                aria-label="重试原文件上传"
                loading={action.busy}
                onClick={() => void action.retry()}
              >
                重试原文件上传
              </Button>
              <Button disabled={action.busy} onClick={() => action.clear()}>
                取消本次上传
              </Button>
            </Space>
          )}
        </>
      )}
      <div className="living-file-controls">
        <label htmlFor="living-file-purpose">附件用途</label>
        <Select
          id="living-file-purpose"
          aria-label="附件用途"
          value={purpose}
          disabled={frozen}
          onChange={setPurpose}
          options={Object.entries(purposes).map(([value, label]) => ({
            value,
            label,
          }))}
        />
        <label htmlFor="living-file-repair">关联报修（可选）</label>
        <Select
          id="living-file-repair"
          aria-label="关联报修（可选）"
          value={repairId}
          disabled={frozen}
          allowClear
          placeholder="不关联特定报修"
          onChange={(id) => setRepairId(id || null)}
          options={repairs.map((repair) => ({
            value: repair.repair_id,
            label: repair.title,
          }))}
        />
      </div>
      <Space wrap>
        <Upload
          accept=".jpg,.jpeg,.png,.pdf"
          multiple={false}
          maxCount={1}
          showUploadList={false}
          disabled={frozen}
          beforeUpload={(candidate) => {
            if (!allowedTypes.has(candidate.type)) {
              setFile(null);
              setError("请选择 JPEG、PNG 图片或 PDF 文件。");
              return false;
            }
            if (candidate.size === 0 || candidate.size > 10 * 1024 * 1024) {
              setFile(null);
              setError("请选择非空且不超过10 MiB的文件。");
              return false;
            }
            setFile(candidate);
            setError(null);
            return false;
          }}
        >
          <Button
            aria-label="选择照片或PDF"
            icon={<UploadOutlined aria-hidden="true" />}
            disabled={frozen}
          >
            选择照片或PDF
          </Button>
        </Upload>
        <Button
          type="primary"
          aria-label="上传并保存附件"
          disabled={!file || frozen || loading}
          loading={action.busy}
          onClick={upload}
        >
          上传并保存附件
        </Button>
      </Space>
      {file && (
        <p className="living-file-picked">
          待上传：{file.name} · {(file.size / 1024).toFixed(1)} KiB{" "}
          <Button
            size="small"
            type="text"
            disabled={frozen}
            onClick={() => setFile(null)}
          >
            移除选中文件
          </Button>
        </p>
      )}
      <p className="living-note">
        支持 JPEG、PNG、PDF，每个文件最多10
        MiB。选择文件后需点击上传；不会发送给中介、供应商或 AI。
      </p>
      {!items.length && !loading && (
        <p className="muted small">还没有上传附件。</p>
      )}
      <div className="living-attachment-list">
        {items.map((item) => (
          <article key={item.attachment_id} className="living-attachment">
            <div>
              <a
                href={item.download_url}
                download={item.filename}
                aria-label={`下载 ${item.filename}`}
              >
                {item.filename}
              </a>
              <p>
                {purposes[item.purpose]} · {(item.size_bytes / 1024).toFixed(1)}{" "}
                KiB · {new Date(item.created_at).toLocaleString("zh-CN")}
              </p>
              {item.repair_id && (
                <small>
                  关联报修：
                  {repairs.find((repair) => repair.repair_id === item.repair_id)
                    ?.title || "报修记录"}
                </small>
              )}
            </div>
            <Tag>用户上传 · 未核实</Tag>
          </article>
        ))}
      </div>
    </section>
  );
}
