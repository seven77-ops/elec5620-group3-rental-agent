import { useEffect, useState } from "react";
import { Button, Modal, Spin } from "antd";
import { downloadUrl } from "../../api/client";
import { leaseRoot } from "../../api/leaseDraft";
import type { LeaseDraft } from "../../api/leaseDraft";
import { Failure } from "../../components/Common";

/** Displays one immutable saved version; opening a preview never saves fields. */
export default function LeasePdfPreview({
  draft,
  onClose,
}: {
  draft: LeaseDraft;
  onClose: () => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const endpoint = downloadUrl(
    leaseRoot(draft.case_id) +
      `/${encodeURIComponent(draft.draft_id)}/pdf?version=${draft.version}`,
  );
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let resource: string | undefined;
    setUrl(null);
    setError(null);
    setLoading(true);
    const deadline = window.setTimeout(() => controller.abort(), 30_000);
    void (async () => {
      try {
        const response = await fetch(endpoint, { signal: controller.signal });
        if (!response.ok) {
          const body = await response.json().catch(() => null);
          throw new Error(
            body?.error?.message ?? "合同预览暂时无法读取，请重试。",
          );
        }
        const blob = await response.blob();
        if (
          !response.headers.get("content-type")?.includes("application/pdf") ||
          (await blob.slice(0, 5).text()) !== "%PDF-"
        )
          throw new Error("返回的文件不是有效 PDF，请重新加载预览。");
        if (active) {
          resource = URL.createObjectURL(blob);
          setUrl(resource);
        }
      } catch (e) {
        if (active)
          setError(
            controller.signal.aborted
              ? new Error("合同预览加载超时，请重试。")
              : e,
          );
      } finally {
        window.clearTimeout(deadline);
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(deadline);
      if (resource) URL.revokeObjectURL(resource);
    };
  }, [endpoint, attempt]);
  return (
    <Modal
      open
      title={`合同预览 · v${draft.version}`}
      onCancel={onClose}
      width={1040}
      className="lease-pdf-modal"
      footer={[
        <Button key="back" onClick={onClose}>
          返回填写
        </Button>,
        <Button key="download" type="primary" href={endpoint}>
          下载此版本 PDF
        </Button>,
      ]}
    >
      <p className="muted small">
        已将确认的信息填入 NSW 官方模板；未填项与签字栏保持空白。
      </p>
      <Failure error={error} />
      {Boolean(error) && (
        <Button onClick={() => setAttempt((v) => v + 1)}>重新加载预览</Button>
      )}
      {loading && (
        <div className="lease-pdf-loading" role="status">
          <Spin />
          <span>正在填写并加载合同…</span>
        </div>
      )}
      {url && (
        <iframe
          src={`${url}#view=FitH`}
          title={`已填写的合同草稿 v${draft.version}`}
          className="lease-pdf-frame"
        />
      )}
      <p className="muted small">
        未签署草稿 · 如浏览器无法显示，可下载 PDF 查看。
      </p>
    </Modal>
  );
}
