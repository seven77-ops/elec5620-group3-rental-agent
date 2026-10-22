import { useEffect, useRef, useState } from "react";
import { Alert, App, Button, Checkbox, Space } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useCase, currentConfirmation } from "../app/context";
import { api, downloadUrl, newRequestId, post } from "../api/client";
import type { Review } from "../api/types";
import { Failure } from "../components/Common";
import { useAction } from "../components/useAction";
export default function ContractUpload({
  onReview,
  onConsentChange,
  revision,
}: {
  onReview: (r: Review) => void;
  onConsentChange: () => void;
  revision: number;
}) {
  const { current, config, refresh } = useCase();
  const { message } = App.useApp();
  const action = useAction();
  const [consentCheck, setConsentCheck] = useState(false);
  const [consent, setConsent] = useState<string | null>(null);
  const [synthetic, setSynthetic] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const input = useRef<HTMLInputElement>(null);
  const real = current.selection?.data_mode === "real_listings";
  const selectionCurrent = Boolean(
    current.selection &&
    current.selection.profile_version === currentConfirmation(current)?.version,
  );
  useEffect(() => {
    let valid = true;
    setLoading(true);
    api<{
      consents: {
        consent_id: string;
        active: boolean;
        selection_current: boolean;
      }[];
    }>(`/cases/${current.case_id}/contract-consents`)
      .then((r) => {
        if (valid) {
          setConsent(
            r.consents.filter((c) => c.active && c.selection_current).at(-1)
              ?.consent_id ?? null,
          );
          setLoadError(null);
        }
      })
      .catch((e) => {
        if (valid) setLoadError(e);
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [current.case_id, current.selection, revision]);
  const agree = () =>
    void action.run(async () => {
      const r = await post<{ consent_id: string }>(
        `/cases/${current.case_id}/contract-consents`,
        { confirmed: true },
      );
      setConsent(r.consent_id);
      onConsentChange();
      message.success(
        real
          ? "合同处理同意已记录，现在可以选择合同。"
          : "合同处理同意已记录，现在可以选择合成合同。",
      );
    });
  const revoke = () => {
    const id = consent;
    void action.run(async () => {
      await post(`/cases/${current.case_id}/contract-consents`, {
        confirmed: false,
        consent_id: id,
      });
      setConsent(null);
      setConsentCheck(false);
      setFile(null);
      if (input.current) input.current.value = "";
      onConsentChange();
      message.success("已撤销后续合同处理同意。");
    });
  };
  const upload = () => {
    if (!file || !consent) return;
    const chosen = file,
      consentId = consent,
      requestId = newRequestId();
    void action.run(async () => {
      const r = await api<{ review: Review; newly_created: boolean }>(
        `/cases/${current.case_id}/contract-reviews`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-Consent-Id": consentId,
            "X-Request-Id": requestId,
            "X-Filename": encodeURIComponent(chosen.name),
          },
          body: chosen,
        },
      );
      onReview(r.review);
      await refresh();
      onConsentChange();
      message.success(
        r.newly_created ? "合同复核结果已保存。" : "已恢复原请求的复核结果。",
      );
    });
  };
  return (
    <section className="panel upload-panel">
      <h2>独立同意与合同上传</h2>
      <p className="muted">
        {real
          ? "上传后先在本地提取字段，并与当前房源和补充记录比对。"
          : "仅处理合成合同，上传后先在本地提取字段并核对。"}
        AI 辅助分析需另行同意。
      </p>
      <Failure
        error={action.error || loadError}
        retry={loadError ? onConsentChange : action.retry}
      />
      {loading ? (
        <p role="status">正在核对已保存的同意记录…</p>
      ) : !consent ? (
        <>
          <Checkbox
            checked={consentCheck}
            onChange={(e) => setConsentCheck(e.target.checked)}
          >
            我同意为本次复核处理此合同，理解此同意独立于选房确认。
          </Checkbox>
          <div className="consent-actions">
            <Button
              type="primary"
              aria-label="同意处理此合同"
              disabled={
                !consentCheck || !selectionCurrent || Boolean(loadError)
              }
              loading={action.busy}
              onClick={agree}
            >
              同意处理此合同
            </Button>
          </div>
        </>
      ) : (
        <>
          <Alert
            type="success"
            showIcon
            title="合同处理同意已记录"
            action={
              <Button size="small" disabled={action.busy} onClick={revoke}>
                撤销同意
              </Button>
            }
          />
          <div className="upload-controls">
            <input
              ref={input}
              type="file"
              aria-label={real ? "选择合同" : "选择合成合同"}
              accept=".txt,.docx,.pdf"
              disabled={action.busy}
              onChange={(e) => {
                const chosen = e.target.files?.[0] ?? null;
                if (chosen && chosen.size > 2_000_000) {
                  message.error(
                    "文件超过 2,000,000 字节，请提供较小的合同文件。",
                  );
                  e.target.value = "";
                  return;
                }
                setFile(chosen);
              }}
            />
            <Button
              aria-label={real ? "选择合同文件" : "选择合成合同文件"}
              icon={<UploadOutlined />}
              onClick={() => input.current?.click()}
              disabled={action.busy}
            >
              {real ? "选择合同" : "选择合成合同"}
            </Button>
            <span className="break-word">{file?.name ?? "尚未选择文件"}</span>
          </div>
          <Checkbox
            checked={synthetic}
            onChange={(e) => setSynthetic(e.target.checked)}
          >
            {real
              ? "我确认有权提交此合同用于本次复核。"
              : "我确认上传的是合成演示合同。"}
          </Checkbox>
          <div className="consent-actions">
            <Button
              type="primary"
              aria-label="上传并复核"
              disabled={!file || !synthetic || !selectionCurrent}
              onClick={upload}
              loading={action.busy}
            >
              上传并复核
            </Button>
          </div>
        </>
      )}
      <p className="muted small">
        TXT / DOCX / PDF，最多 2,000,000 字节，文字 PDF 最多 {real ? 30 : 10}{" "}
        页，扫描 PDF 最多 10 页。扫描文件需要本机 OCR 能力。
      </p>
      {!real && (
        <Space wrap>
          <span className="muted">下载合成样例：</span>
          {config.agreement_examples.map((e) => (
            <a key={e.id} href={downloadUrl(`/demo-agreements/${e.id}`)}>
              {e.id === "normal" ? "正常合同" : "租金冲突合同"}
            </a>
          ))}
        </Space>
      )}
      <p className="muted small">
        {real
          ? "以实际复核日期检查规则时效；字段无法可靠提取时，可核对原文后修正或另行使用 AI 分析。"
          : `合同规则参考日期：${config.clocks.contract}，与房源快照日期独立。`}
      </p>
    </section>
  );
}
