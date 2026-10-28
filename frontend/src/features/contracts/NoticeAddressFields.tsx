import { useEffect, useState } from "react";
import { AutoComplete, Form, Input } from "antd";
import type { FormInstance } from "antd";
import { searchLeaseLocalities } from "../../api/leaseDraft";
import type { LeaseFields, LeaseLocality } from "../../api/leaseDraft";
import { leaseLabels } from "./leaseFields";

export const noticeStates = [
  "NSW",
  "VIC",
  "QLD",
  "ACT",
  "SA",
  "WA",
  "TAS",
  "NT",
].map((value) => ({ value }));
type Group = {
  prefix: string;
  suburb: keyof LeaseFields;
  state: keyof LeaseFields;
  postcode: keyof LeaseFields;
};

function useLocalities(query: string, state: string) {
  const [items, setItems] = useState<LeaseLocality[]>([]);
  const [status, setStatus] = useState("输入区域或邮编，可手动填写");
  useEffect(() => {
    let active = true;
    setItems([]);
    if (query.trim().length < 2)
      return () => {
        active = false;
      };
    setStatus("正在检索…");
    const timer = window.setTimeout(() => {
      searchLeaseLocalities(query.trim(), state)
        .then((result) => {
          if (active) {
            setItems(result.items);
            setStatus("暂无匹配，可手动填写");
          }
        })
        .catch(() => {
          if (active) setStatus("检索暂不可用，可手动填写");
        });
    }, 220);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query, state]);
  return { items, status };
}

export default function NoticeAddressFields({
  name,
  group,
  form,
  onEdited,
  requiredFields,
}: {
  name: keyof LeaseFields;
  group: Group;
  form: FormInstance<LeaseFields>;
  onEdited: () => void;
  requiredFields?: readonly (keyof LeaseFields)[];
}) {
  const state = String(
    Form.useWatch(group.state, { form, preserve: true }) ?? "",
  );
  const [suburbQuery, setSuburbQuery] = useState("");
  const [postcodeQuery, setPostcodeQuery] = useState("");
  const [openField, setOpenField] = useState<"suburb" | "postcode" | null>(
    null,
  );
  const suburbs = useLocalities(suburbQuery, state);
  const postcodes = useLocalities(postcodeQuery, state);
  const focusSearch = (field: "suburb" | "postcode") => {
    setOpenField(field);
    const value = String(
      form.getFieldValue(field === "suburb" ? group.suburb : group.postcode) ||
        (field === "postcode" ? form.getFieldValue(group.suburb) : "") ||
        "",
    );
    (field === "suburb" ? setSuburbQuery : setPostcodeQuery)(value);
  };
  const select = (id: string, items: LeaseLocality[]) => {
    const item = items.find((value) => value.id === id);
    if (!item) return;
    form.setFieldsValue({
      [group.suburb]: item.suburb,
      [group.state]: item.state,
      [group.postcode]: item.postcode,
    });
    setSuburbQuery("");
    setPostcodeQuery("");
    setOpenField(null);
    onEdited();
  };
  const options = (items: LeaseLocality[]) =>
    items.map((item) => ({
      value: item.id,
      label: (
        <span data-locality-option>
          {item.suburb} · {item.state} {item.postcode}
        </span>
      ),
    }));
  return (
    <div className="lease-address-fields lease-field-wide">
      <Form.Item
        name={name}
        label={leaseLabels[name]}
        required={requiredFields?.includes(name)}
      >
        <Input maxLength={200} placeholder="手动填写房号、门牌号和街道名" />
      </Form.Item>
      <div className="lease-address-parts">
        <Form.Item
          name={group.suburb}
          label={`${group.prefix}区域（Suburb）`}
          required={requiredFields?.includes(group.suburb)}
        >
          <AutoComplete
            options={options(suburbs.items)}
            virtual={false}
            filterOption={false}
            open={openField === "suburb"}
            onOpenChange={(open) =>
              open ? focusSearch("suburb") : setOpenField(null)
            }
            onSearch={(value) => {
              setSuburbQuery(value);
              setOpenField("suburb");
            }}
            onFocus={() => focusSearch("suburb")}
            onBlur={() => setOpenField(null)}
            onSelect={(id) => select(id, suburbs.items)}
            notFoundContent={suburbs.status}
          >
            <Input
              maxLength={80}
              placeholder="搜索选择或手动填写区域"
              onClick={() => focusSearch("suburb")}
            />
          </AutoComplete>
        </Form.Item>
        <Form.Item
          name={group.state}
          label={`${group.prefix} State`}
          required={requiredFields?.includes(group.state)}
        >
          <AutoComplete
            options={noticeStates}
            virtual={false}
            filterOption={(input, option) =>
              String(option?.value).includes(input.toUpperCase())
            }
          >
            <Input maxLength={40} placeholder="选择或手动填写" />
          </AutoComplete>
        </Form.Item>
        <Form.Item
          name={group.postcode}
          required={requiredFields?.includes(group.postcode)}
          label={`${group.prefix}邮编`}
          rules={[{ pattern: /^\d{4}$/, message: "邮编须为4位数字。" }]}
        >
          <AutoComplete
            options={options(postcodes.items)}
            virtual={false}
            filterOption={false}
            open={openField === "postcode"}
            onOpenChange={(open) =>
              open ? focusSearch("postcode") : setOpenField(null)
            }
            onSearch={(value) => {
              setPostcodeQuery(value);
              setOpenField("postcode");
            }}
            onFocus={() => focusSearch("postcode")}
            onBlur={() => setOpenField(null)}
            onSelect={(id) => select(id, postcodes.items)}
            notFoundContent={postcodes.status}
          >
            <Input
              maxLength={4}
              inputMode="numeric"
              placeholder="选择或输入4位邮编"
              onClick={() => focusSearch("postcode")}
            />
          </AutoComplete>
        </Form.Item>
      </div>
    </div>
  );
}
