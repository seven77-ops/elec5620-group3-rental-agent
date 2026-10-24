import { useEffect, useRef, useState } from "react";
import { AutoComplete, Form, Input } from "antd";
import type { FormInstance } from "antd";
import { searchLeaseAddresses } from "../../api/leaseDraft";
import type { LeaseAddressSuggestion, LeaseFields } from "../../api/leaseDraft";
import { leaseLabels } from "./leaseFields";
import { isLocalityQuery } from "./leaseAddress";
import NoticeAddressFields from "./NoticeAddressFields";
import "./leaseAutofill.css";

export const addressGroups = {
  address: {
    prefix: "房屋",
    suburb: "suburb",
    state: "state",
    postcode: "postcode",
  },
  landlord_notice_address: {
    prefix: "出租方",
    suburb: "landlord_notice_suburb",
    state: "landlord_notice_state",
    postcode: "landlord_notice_postcode",
  },
  tenant_notice_address: {
    prefix: "租客",
    suburb: "tenant_notice_suburb",
    state: "tenant_notice_state",
    postcode: "tenant_notice_postcode",
  },
  agent_notice_address: {
    prefix: "代理",
    suburb: "agent_notice_suburb",
    state: "agent_notice_state",
    postcode: "agent_notice_postcode",
  },
} as const;
type AddressField = keyof typeof addressGroups;
const states = ["NSW", "VIC", "QLD", "ACT", "SA", "WA", "TAS", "NT"].map(
  (value) => ({ value }),
);
type AddressProps = {
  name: AddressField;
  form: FormInstance<LeaseFields>;
  onEdited: () => void;
  source?: string;
};
export default function LeaseAddressFields(props: AddressProps) {
  return props.name === "address" ? (
    <PropertyAddressFields {...props} />
  ) : (
    <NoticeAddressFields
      key={props.name}
      name={props.name}
      group={addressGroups[props.name]}
      form={props.form}
      onEdited={props.onEdited}
    />
  );
}
function PropertyAddressFields({ name, form, onEdited, source }: AddressProps) {
  const group = addressGroups[name];
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<LeaseAddressSuggestion[]>([]);
  const [searching, setSearching] = useState(false);
  const [failed, setFailed] = useState(false);
  const choice = useRef<"address" | "locality">("address");
  useEffect(() => {
    let valid = true;
    setItems([]);
    setFailed(false);
    if (query.trim().length < 2) {
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = window.setTimeout(() => {
      searchLeaseAddresses(query.trim())
        .then((result) => {
          if (valid) setItems(result.items);
        })
        .catch(() => {
          if (valid) setFailed(true);
        })
        .finally(() => {
          if (valid) setSearching(false);
        });
    }, 220);
    return () => {
      valid = false;
      window.clearTimeout(timer);
    };
  }, [query]);
  const select = (id: string) => {
    const item = items.find((value) => value.id === id);
    if (!item) return;
    choice.current = item.kind;
    const localityQuery = isLocalityQuery(query, item);
    form.setFieldsValue({
      [name]:
        item.kind === "locality" && !localityQuery
          ? query.trim()
          : item.address,
      [group.suburb]: item.suburb,
      [group.state]: item.state,
      [group.postcode]: item.postcode,
    });
    setQuery("");
    setItems([]);
    onEdited();
  };
  return (
    <div className="lease-address-fields lease-field-wide">
      <Form.Item name={name} label={leaseLabels[name]} extra={source}>
        <AutoComplete
          options={items.map((item) => ({
            value: item.id,
            label: (
              <div
                className="lease-address-option"
                data-address-kind={item.kind}
              >
                <strong>
                  {item.kind === "locality"
                    ? `${item.suburb} · 选择区域`
                    : item.address}
                </strong>
                <small>
                  {item.suburb} · {item.state} {item.postcode}
                  {item.kind === "locality" ? " · 继续填写街道门牌" : ""}
                </small>
              </div>
            ),
          }))}
          onSearch={setQuery}
          onSelect={select}
          filterOption={false}
          virtual={false}
          onChange={() => {
            if (choice.current === "address")
              form.setFieldsValue({
                [group.suburb]: "",
                [group.state]: "",
                [group.postcode]: "",
              });
          }}
          notFoundContent={
            query.length >= 2
              ? searching
                ? "正在检索…"
                : failed
                  ? "检索暂不可用，可手动填写"
                  : "暂无匹配，可手动填写"
              : null
          }
        >
          <Input
            maxLength={200}
            aria-label={leaseLabels[name]}
            placeholder="输入区域、街道或邮编，如 Redfern"
          />
        </AutoComplete>
      </Form.Item>
      <div className="lease-address-parts">
        <Form.Item name={group.suburb} label={`${group.prefix}区域（Suburb）`}>
          <Input maxLength={80} />
        </Form.Item>
        <Form.Item name={group.state} label={`${group.prefix} State`}>
          <AutoComplete options={states}>
            <Input maxLength={40} />
          </AutoComplete>
        </Form.Item>
        <Form.Item
          name={group.postcode}
          label={`${group.prefix}邮编`}
          rules={[{ pattern: /^\d{4}$/, message: "邮编须为4位数字。" }]}
        >
          <Input maxLength={4} inputMode="numeric" />
        </Form.Item>
      </div>
    </div>
  );
}
