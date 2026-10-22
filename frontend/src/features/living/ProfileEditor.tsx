import { useState } from "react";
import {
  Button,
  Checkbox,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
} from "antd";
import type {
  LivingProfile,
  LivingRecord,
  LivingWrite,
} from "../../api/living";
const yesNo = [
  { value: "unknown", label: "尚未填写" },
  { value: "yes", label: "是" },
  { value: "no", label: "否" },
];
export default function ProfileEditor({
  record,
  busy,
  save,
}: {
  record: LivingRecord;
  busy: boolean;
  save: LivingWrite;
}) {
  const [open, setOpen] = useState(false),
    [confirmed, setConfirmed] = useState(false);
  const [snapshot, setSnapshot] = useState(record);
  const [form] = Form.useForm();
  const profile = record.profile;
  const start = () => {
    setSnapshot(record);
    setConfirmed(false);
    form.setFieldsValue({
      ...profile,
      lease_start_date: profile.lease_start_date ?? null,
      lease_end_date: profile.lease_end_date ?? null,
      ...Object.fromEntries(
        ["carpeted", "has_pets", "has_elevator"].map((key) => [
          key,
          profile[key as keyof LivingProfile] === null
            ? "unknown"
            : profile[key as keyof LivingProfile]
              ? "yes"
              : "no",
        ]),
      ),
    });
    setOpen(true);
  };
  const submit = async () => {
    if (!confirmed) return;
    try {
      const input = await form.validateFields();
      const values = {
        ...snapshot.profile,
        ...input,
        move_out_date: input.move_out_date || null,
        lease_start_date: input.lease_start_date || null,
        lease_end_date: input.lease_end_date || null,
      };
      for (const key of ["carpeted", "has_pets", "has_elevator"])
        values[key] = input[key] === "unknown" ? null : input[key] === "yes";
      for (const key of ["bedrooms", "bathrooms"])
        values[key] = input[key] ?? null;
      await save("/profile", values, snapshot.version, () => setOpen(false));
    } catch {
      /* Form field errors remain visible. */
    }
  };
  return (
    <>
      <section className="living-contact-strip">
        <div>
          <strong>{profile.address || "住处与联系人"}</strong>
          <Descriptions
            size="small"
            column={1}
            items={[
              {
                key: "agent",
                label: "中介 / 房东",
                children: profile.agent_name || "尚未填写",
              },
              {
                key: "email",
                label: "联系邮箱",
                children: profile.agent_email || "尚未填写",
              },
            ]}
          />
        </div>
        <Button id="living-contact-editor" onClick={start} disabled={busy}>
          编辑住处与联系人
        </Button>
      </section>
      <Modal
        forceRender
        title="住处与联系人"
        open={open}
        onCancel={() => !busy && setOpen(false)}
        onOk={submit}
        okText="确认保存资料"
        cancelText="取消"
        confirmLoading={busy}
        okButtonProps={{ disabled: !confirmed, "aria-label": "确认保存资料" }}
        cancelButtonProps={{ disabled: busy }}
        mask={{ closable: !busy }}
        closable={!busy}
        width={700}
      >
        <p className="muted">填写你确认的实际资料。未填写的条件保留为未知。</p>
        <Form
          name="living-profile"
          form={form}
          disabled={busy}
          layout="vertical"
          onValuesChange={() => setConfirmed(false)}
        >
          <Form.Item name="address" label="居住地址">
            <Input maxLength={1000} />
          </Form.Item>
          <div className="living-form-grid">
            <Form.Item name="suburb" label="区域">
              <Input />
            </Form.Item>
            <Form.Item name="postcode" label="邮编">
              <Input maxLength={10} />
            </Form.Item>
            <Form.Item name="agent_name" label="中介或房东姓名">
              <Input />
            </Form.Item>
            <Form.Item
              name="agent_email"
              label="联系邮箱"
              rules={[{ type: "email", message: "请填写有效邮箱" }]}
            >
              <Input type="email" />
            </Form.Item>
            <Form.Item name="agent_phone" label="联系电话">
              <Input type="tel" />
            </Form.Item>
            <Form.Item name="emergency_phone" label="紧急维修电话">
              <Input type="tel" />
            </Form.Item>
            <Form.Item name="lease_start_date" label="租约开始日期">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="lease_end_date" label="租约结束日期">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="move_out_date" label="预计退租日期">
              <Input type="date" />
            </Form.Item>
            <Form.Item name="moving_to" label="搬往地点">
              <Input />
            </Form.Item>
            <Form.Item name="bedrooms" label="卧室数量">
              <InputNumber min={0} max={100} precision={0} />
            </Form.Item>
            <Form.Item name="bathrooms" label="浴室数量">
              <InputNumber min={0} max={100} precision={0} />
            </Form.Item>
            <Form.Item name="carpeted" label="是否有地毯">
              <Select options={yesNo} />
            </Form.Item>
            <Form.Item name="has_pets" label="是否有宠物">
              <Select options={yesNo} />
            </Form.Item>
            <Form.Item name="has_elevator" label="是否有电梯">
              <Select options={yesNo} />
            </Form.Item>
          </div>
          <Form.Item name="own_furniture" label="自己的家具">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="landlord_furniture" label="房东提供的家具">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="notes" label="其他备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
        <Checkbox
          checked={confirmed}
          disabled={busy}
          onChange={(e) => setConfirmed(e.target.checked)}
        >
          我确认保存这些住处与联系人资料。
        </Checkbox>
        {record.version !== snapshot.version && (
          <p role="alert">资料已更新，请关闭窗口后重新核对最新资料。</p>
        )}
      </Modal>
    </>
  );
}
