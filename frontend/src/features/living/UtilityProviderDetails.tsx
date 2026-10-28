import { Button, Modal, Space } from "antd";
import {
  EnvironmentOutlined,
  GlobalOutlined,
  PhoneOutlined,
} from "@ant-design/icons";
import type { LivingProvider, ProviderCategory } from "../../api/living";
import UtilityPlanBrowser from "./UtilityPlanBrowser";

const categoryLabels: Record<ProviderCategory, string> = {
  electricity: "电力",
  gas: "燃气",
  internet: "网络",
  water: "供水",
  removalist: "搬运",
  cleaner: "清洁",
};
export const providerCategories = (provider: LivingProvider) =>
  provider.categories.map((category) => categoryLabels[category]).join(" · ");

export default function UtilityProviderDetails({
  provider,
  onClose,
}: {
  provider?: LivingProvider;
  onClose: () => void;
}) {
  return (
    <Modal
      title={provider ? `${provider.name} · 供应商详情` : "供应商详情"}
      open={!!provider}
      className="utility-provider-modal"
      onCancel={onClose}
      width={1000}
      destroyOnHidden
      styles={{
        body: {
          maxHeight: "68dvh",
          overflowY: "auto",
          overflowWrap: "anywhere",
        },
      }}
      footer={<Button onClick={onClose}>关闭详情</Button>}
    >
      {provider && (
        <div className="living-provider-details" key={provider.id}>
          <div className="provider-overview">
            <div className="provider-overview-info">
              <span className="provider-category-badge">
                {providerCategories(provider)}
              </span>
              <p className="provider-coverage">
                <EnvironmentOutlined /> {provider.coverage}
              </p>
            </div>
            <Space wrap className="provider-contact-actions">
              <Button
                href={provider.website}
                aria-label="官方网站"
                target="_blank"
                rel="noopener noreferrer"
                icon={<GlobalOutlined />}
              >
                官方网站
              </Button>
              <Button
                href={provider.contact_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                联系页面
              </Button>
              {provider.phone && (
                <Button
                  href={`tel:${provider.phone}`}
                  aria-label={provider.phone}
                  icon={<PhoneOutlined />}
                >
                  {provider.phone}
                </Button>
              )}
            </Space>
          </div>
          <div className="provider-facts-note">
            {provider.notes || "服务范围请按实际地址向供应商确认。"}
          </div>
          {provider.plans?.length ? (
            <UtilityPlanBrowser plans={provider.plans} />
          ) : (
            <p className="muted">可通过上方官网或联系页面查看服务。</p>
          )}
          <p className="muted living-provider-source">
            {provider.plans?.length ? "联系信息来源：" : "来源："}
            <a
              href={provider.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              官方页面
            </a>
            {" · "}
            {provider.plans?.length ? "联系信息核对日期" : "核对日期"}{" "}
            {provider.checked_on}
          </p>
        </div>
      )}
    </Modal>
  );
}
