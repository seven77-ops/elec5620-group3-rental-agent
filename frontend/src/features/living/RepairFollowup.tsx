import { useState } from "react";
import { Alert, App, Button, Form, Input, Modal, Select, Space } from "antd";
import type {
  LivingWrite,
  RepairEntry,
  RepairStatus,
  RepairTone,
  RepairUpdateValues,
} from "../../api/living";
const statuses: Record<RepairStatus, string> = {
  prepared: "草稿已准备",
  contacted: "已自行联系",
  resolved: "问题已解决",
};
const tones: Record<RepairTone, string> = {
  standard: "标准",
  polite: "更礼貌",
  concise: "更简洁",
};
export default function RepairFollowup({
  repair,
  version,
  busy,
  save,
}: {
  repair: RepairEntry;
  version: number;
  busy: boolean;
  save: LivingWrite;
}) {
  const [open, setOpen] = useState(false),
    [snapshot, setSnapshot] = useState({ repair, version }),
    [failed, setFailed] = useState(false);
  const [form] = Form.useForm<{
    status: RepairStatus;
    note: string;
    email_tone: RepairTone;
  }>();
  const { modal, message } = App.useApp();
  const start = () => {
    setSnapshot({ repair, version });
    setFailed(false);
    form.setFieldsValue({
      status: repair.status,
      note: "",
      email_tone: repair.email_tone || "standard",
    });
    setOpen(true);
  };
  const confirm = async () => {
    try {
      const input = await form.validateFields();
      const values: RepairUpdateValues = {};
      if (input.status !== snapshot.repair.status) values.status = input.status;
      if (input.note?.trim()) values.note = input.note;
      if (input.email_tone !== (snapshot.repair.email_tone || "standard"))
        values.email_tone = input.email_tone;
      if (!Object.keys(values).length) {
        message.info("请填写后续记录、修改状态或选择不同语气。");
        return;
      }
      modal.confirm({
        title: "确认保存这条报修的后续？",
        content: (
          <>
            <p>{snapshot.repair.title}</p>
            {values.note && <p className="living-prewrap">{values.note}</p>}
            {values.status && <p>状态：{statuses[values.status]}</p>}
            {values.email_tone && <p>草稿语气：{tones[values.email_tone]}</p>}
            <p>只更新这一条报修，不新建问题或发送邮件。</p>
          </>
        ),
        okText: "确认保存报修后续",
        cancelText: "继续编辑",
        onOk: async () => {
          const saved = await save(
            `/repairs/${encodeURIComponent(snapshot.repair.repair_id)}`,
            values,
            snapshot.version,
            () => setOpen(false),
          );
          if (!saved) setFailed(true);
        },
      });
    } catch {
      /* Inline form validation. */
    }
  };
  return (
    <>
      <Space wrap>
        <Button disabled={busy} onClick={start}>
          记录后续
        </Button>
        <Button disabled={busy} onClick={start}>
          调整邮件语气
        </Button>
      </Space>
      <Modal
        forceRender
        title="记录报修后续"
        open={open}
        onCancel={() => !busy && setOpen(false)}
        onOk={() => void confirm()}
        okText="核对并保存后续"
        cancelText="取消"
        confirmLoading={busy}
        okButtonProps={{ "aria-label": "核对并保存后续" }}
        cancelButtonProps={{ disabled: busy }}
        closable={!busy}
        mask={{ closable: !busy }}
      >
        <p>
          <strong>{snapshot.repair.title}</strong>
        </p>
        {failed && (
          <Alert
            type="error"
            title="尚未保存。输入已保留；请关闭窗口查看页面错误，必要时读取最新资料后重新核对。"
          />
        )}
        <Form
          name={`repair-followup-${repair.repair_id}`}
          form={form}
          layout="vertical"
          disabled={busy}
        >
          <Form.Item name="note" label="对方回复或我的记录">
            <Input.TextArea
              aria-label="对方回复或我的记录"
              rows={3}
              maxLength={3000}
            />
          </Form.Item>
          <Form.Item name="status" label="报修状态">
            <Select
              options={Object.entries(statuses).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item name="email_tone" label="邮件语气">
            <Select
              options={Object.entries(tones).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
        </Form>
        <p className="living-note">
          只调整邮件草稿措辞，原始问题和收件人保持不变。没有确定的预约时间请直接注明尚未确定。
        </p>
      </Modal>
    </>
  );
}
