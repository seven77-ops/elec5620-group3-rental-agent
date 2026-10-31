import { Button, Modal, Space } from "antd";
import {
  EnvironmentOutlined,
  GlobalOutlined,
  PhoneOutlined,
} from "@ant-design/icons";
import type { LivingProvider, ProviderCategory } from "../../api/living";
import UtilityPlanBrowser from "./UtilityPlanBrowser";

const categoryLabels: Record<ProviderCategory, string> = {
  electricity: "Electricity",
  gas: "Gas",
  internet: "Internet",
  water: "Water",
  removalist: "Moving",
  cleaner: "Cleaning",
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
      title={
        provider ? `${provider.name} · Provider details` : "Provider details"
      }
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
      footer={<Button onClick={onClose}>Close details</Button>}
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
                aria-label="Official website"
                target="_blank"
                rel="noopener noreferrer"
                icon={<GlobalOutlined />}
              >
                Official website
              </Button>
              <Button
                href={provider.contact_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Contact page
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
            {provider.notes ||
              "Confirm service coverage for your actual address with the provider."}
          </div>
          {provider.plans?.length ? (
            <UtilityPlanBrowser plans={provider.plans} />
          ) : (
            <p className="muted">
              View services through the official website or contact page above.
            </p>
          )}
          <p className="muted living-provider-source">
            {provider.plans?.length ? "Contact information source:" : "Source:"}
            <a
              href={provider.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Official page
            </a>
            {" · "}
            {provider.plans?.length
              ? "Contact information checked on"
              : "Checked on"}{" "}
            {provider.checked_on}
          </p>
        </div>
      )}
    </Modal>
  );
}
