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
  tenant_agent_notice_address: {
    prefix: "Tenant agent",
    suburb: "tenant_agent_notice_suburb",
    state: "tenant_agent_notice_state",
    postcode: "tenant_agent_notice_postcode",
  },
  corporation_address: {
    prefix: "Landlord company",
    suburb: "corporation_suburb",
    state: "corporation_state",
    postcode: "corporation_postcode",
  },
  address: {
    prefix: "Property",
    suburb: "suburb",
    state: "state",
    postcode: "postcode",
  },
  landlord_notice_address: {
    prefix: "Landlord",
    suburb: "landlord_notice_suburb",
    state: "landlord_notice_state",
    postcode: "landlord_notice_postcode",
  },
  tenant_notice_address: {
    prefix: "Tenant",
    suburb: "tenant_notice_suburb",
    state: "tenant_notice_state",
    postcode: "tenant_notice_postcode",
  },
  agent_notice_address: {
    prefix: "Landlord agent",
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
  requiredFields?: readonly (keyof LeaseFields)[];
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
      requiredFields={props.requiredFields}
    />
  );
}
function PropertyAddressFields({
  name,
  form,
  onEdited,
  source,
  requiredFields,
}: AddressProps) {
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
      <Form.Item
        name={name}
        label={leaseLabels[name]}
        required={requiredFields?.includes(name)}
        extra={source}
      >
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
                    ? `${item.suburb} · Select suburb`
                    : item.address}
                </strong>
                <small>
                  {item.suburb} · {item.state} {item.postcode}
                  {item.kind === "locality"
                    ? " · Continue with street address"
                    : ""}
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
                ? "Searching…"
                : failed
                  ? "Search unavailable; enter details manually"
                  : "No matches; enter details manually"
              : null
          }
        >
          <Input
            maxLength={200}
            aria-label={leaseLabels[name]}
            placeholder="Enter a suburb, street, or postcode, such as Redfern"
          />
        </AutoComplete>
      </Form.Item>
      <div className="lease-address-parts">
        <Form.Item
          name={group.suburb}
          label={`${group.prefix} suburb`}
          required={requiredFields?.includes(group.suburb)}
        >
          <Input maxLength={80} />
        </Form.Item>
        <Form.Item
          name={group.state}
          label={`${group.prefix} State`}
          required={requiredFields?.includes(group.state)}
        >
          <AutoComplete options={states}>
            <Input maxLength={40} />
          </AutoComplete>
        </Form.Item>
        <Form.Item
          name={group.postcode}
          required={requiredFields?.includes(group.postcode)}
          label={`${group.prefix} postcode`}
          rules={[
            { pattern: /^\d{4}$/, message: "Postcode must contain 4 digits." },
          ]}
        >
          <Input maxLength={4} inputMode="numeric" />
        </Form.Item>
      </div>
    </div>
  );
}
