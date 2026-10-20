import { useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
} from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { useCase } from "../app/context";
import { api } from "../api/client";
import type { Dict, Review } from "../api/types";
import { Failure, JsonDetails } from "../components/Common";
import { useAction } from "../components/useAction";
export default function TenancyForm({
  create,
  busy,
}: {
  create: (payload: Dict) => void;
  busy: boolean;
}) {
  const { current, config } = useCase();
  const [form] = Form.useForm();
  const [confirmed, setConfirmed] = useState(false);
  const action = useAction();
  const template = config.tenancy_template;
  const capabilities = config.capabilities as Dict;
  const prefill = () => {
    const id = current.reviews.at(-1)?.review_id;
    if (!id) return;
    void action.run(async () => {
      const r = await api<Review>(`/contract-reviews/${id}`);
      form.setFieldsValue({
        address: r.fields.address?.value,
        source_ref: `review:${r.review_id}@${r.version}#fields.address`,
        source_version: r.version,
      });
      setConfirmed(false);
    });
  };
  const submit = async () => {
    try {
      const values = await form.validateFields();
      create({
        tenancy: { ...template, ...values, confirmed: true },
        evidence: capabilities.aftercare_evidence_template ?? [],
      });
    } catch {
      /* Inline errors. */
    }
  };
  return (
    <section className="panel tenancy-form">
      <h2>确认租约资料</h2>
      <Alert
        type="info"
        showIcon
        title="以下为合成租约样例，请逐项核对"
        description="合同复核不代表租约已签订。只有你明确确认这些资料后，才创建租后服务案件。示例房间、家具和证据均可核对或编辑。"
      />
      <Failure error={action.error} retry={action.retry} />
      {current.reviews.length > 0 && (
        <Button
          onClick={prefill}
          loading={action.busy}
          aria-label="从最近合同复核预填地址与来源"
        >
          从最近合同复核预填地址与来源
        </Button>
      )}
      <Form
        form={form}
        initialValues={template}
        layout="vertical"
        onValuesChange={() => setConfirmed(false)}
      >
        <Form.Item
          name="address"
          label="租约地址"
          rules={[{ required: true, message: "填写确认的租约地址" }]}
        >
          <Input />
        </Form.Item>
        <div className="form-grid">
          <Form.Item name="jurisdiction" label="管辖地区">
            <Select options={[{ value: "NSW", label: "NSW" }]} />
          </Form.Item>
          <Form.Item name="tenancy_type" label="租约类型">
            <Select
              options={[
                { value: "standard_residential", label: "标准住宅租约" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="source_ref"
            label="资料来源引用"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="source_version"
            label="来源版本"
            rules={[{ required: true }]}
          >
            <InputNumber min={1} precision={0} />
          </Form.Item>
        </div>
        <div className="switch-group">
          <Form.Item name="carpeted" valuePropName="checked" label="有地毯">
            <Switch />
          </Form.Item>
          <Form.Item name="outdoor" valuePropName="checked" label="有室外区域">
            <Switch />
          </Form.Item>
          <Form.Item name="furnished" valuePropName="checked" label="带家具">
            <Switch />
          </Form.Item>
          <Form.Item
            name="inventory_confirmed"
            valuePropName="checked"
            label="家具清单已核对"
          >
            <Switch />
          </Form.Item>
        </div>
        <h3>房间</h3>
        <Form.List name="rooms">
          {(fields, { add, remove }) => (
            <>
              {fields.map((f) => (
                <div className="list-form-row" key={f.key}>
                  <Form.Item
                    name={[f.name, "id"]}
                    label="房间标识"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "name"]}
                    label="房间名称"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Button
                    aria-label="移除此房间"
                    icon={<MinusCircleOutlined />}
                    onClick={() => remove(f.name)}
                  />
                </div>
              ))}
              <Button
                icon={<PlusOutlined />}
                onClick={() => add({ id: "", name: "" })}
              >
                添加房间
              </Button>
            </>
          )}
        </Form.List>
        <h3>家具清单</h3>
        <Form.List name="inventory">
          {(fields, { add, remove }) => (
            <>
              {fields.map((f) => (
                <div className="list-form-row" key={f.key}>
                  <Form.Item
                    name={[f.name, "id"]}
                    label="家具标识"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "name"]}
                    label="家具名称"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    name={[f.name, "room_id"]}
                    label="所属房间标识"
                    rules={[{ required: true }]}
                  >
                    <Input />
                  </Form.Item>
                  <Button
                    aria-label="移除此家具"
                    icon={<MinusCircleOutlined />}
                    onClick={() => remove(f.name)}
                  />
                </div>
              ))}
              <Button
                icon={<PlusOutlined />}
                onClick={() => add({ id: "", name: "", room_id: "" })}
              >
                添加家具
              </Button>
            </>
          )}
        </Form.List>
        <Form.Item name="baseline_evidence_refs" label="入住基线证据引用">
          <Select
            mode="multiple"
            options={(
              (capabilities.aftercare_evidence_template ?? []) as Dict[]
            ).map((e) => ({
              value: String(e.evidence_id),
              label: String(e.evidence_id),
            }))}
          />
        </Form.Item>
      </Form>
      <Collapse
        ghost
        items={[
          {
            key: "evidence",
            label: "查看随合成样例提供的证据元数据",
            children: (
              <JsonDetails value={capabilities.aftercare_evidence_template} />
            ),
          },
        ]}
      />
      <Space orientation="vertical">
        <Checkbox
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        >
          我已核对并确认上述租约、房间、家具及资料来源。
        </Checkbox>
        <Button
          type="primary"
          disabled={!confirmed}
          loading={busy}
          onClick={submit}
          aria-label="确认资料并创建租后案件"
        >
          确认资料并创建租后案件
        </Button>
      </Space>
    </section>
  );
}
