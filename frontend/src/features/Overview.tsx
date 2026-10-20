import { Button, Space, Steps } from "antd";
import { ArrowRightOutlined } from "@ant-design/icons";
import { useCase, currentConfirmation } from "../app/context";
import { PageTitle, Status } from "../components/Common";
export default function Overview() {
  const { current, go } = useCase();
  const confirmed = currentConfirmation(current);
  const review = current.reviews.at(-1);
  const selected = Boolean(confirmed && current.selection &&
    current.selection.profile_version === confirmed.version &&
    current.selection.profile_fingerprint === confirmed.fingerprint);
  const next = !confirmed
    ? "preferences"
    : !selected
      ? "recommendations"
      : !review
        ? "contract"
        : "aftercare";
  const index = !confirmed ? 0 : !selected ? 1 : !review ? 2 : 3;
  return (
    <>
      <PageTitle
        title="我的租房进度"
        description="每一步都有依据，每一次确认都由你决定。"
      />
      <section className="panel progress-panel">
        <Steps
          current={index}
          items={[
            {
              title: "确认偏好",
              content: confirmed
                ? `已确认 v${confirmed.version}`
                : "填写并明确确认",
            },
            {
              title: "选择房源",
              content: selected ? current.selection!.listing_id : "按当前偏好选择房源",
            },
            {
              title: "合同复核",
              content: review ? "查看复核结果" : "独立同意后处理",
            },
            {
              title: "租后服务",
              content: current.aftercare_case_id
                ? "租约资料已确认"
                : "补齐并确认租约",
            },
          ]}
        />
      </section>
      <section className="next-action">
        <div>
          <div className="section-caption">下一步</div>
          <h2>
            {next === "preferences"
              ? "确认你的租房偏好"
              : next === "recommendations"
                ? "寻找适合你的房源"
                : next === "contract"
                  ? "核对你选择的房源与合同"
                  : "确认租约资料，开始租后安排"}
          </h2>
          <p>已保存的版本和结果随时可以回看。</p>
        </div>
        <Button
          type="primary"
          icon={<ArrowRightOutlined />}
          onClick={() => go(next)}
        >
          继续当前流程
        </Button>
      </section>
      <div className="overview-grid">
        <section className="panel">
          <h2>当前有效资料</h2>
          <dl className="summary-list">
            <div>
              <dt>偏好</dt>
              <dd>
                {confirmed
                  ? `已确认版本 v${confirmed.version}`
                  : "当前草稿尚未确认"}
              </dd>
            </div>
            <div>
              <dt>推荐</dt>
              <dd>
                {current.evaluations.length
                  ? `${current.evaluations.length} 次已保存评估`
                  : "尚未生成"}
              </dd>
            </div>
            <div>
              <dt>所选房源</dt>
              <dd>{selected ? current.selection!.listing_id : current.selection ? "历史选择，需按当前偏好重新选择" : "尚未选择"}</dd>
            </div>
            <div>
              <dt>合同</dt>
              <dd>{review ? <Status value={review.status} /> : "尚未提交"}</dd>
            </div>
          </dl>
        </section>
        <section className="panel">
          <h2>已有租约？</h2>
          <p className="muted">
            可以直接填写并确认租约资料，进入退租计划和押金跟进。
          </p>
          <Space>
            <Button onClick={() => go("aftercare")}>直接填写租约资料</Button>
          </Space>
        </section>
      </div>
      <p className="page-footnote">
        全部房源、合同和服务记录均为合成演示。复核完成不代表签约批准。
      </p>
    </>
  );
}
