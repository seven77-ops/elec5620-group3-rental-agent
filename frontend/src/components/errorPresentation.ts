const messages: Record<string, { title: string; message: string }> = {
  unconfirmed_profile: {
    title: "先确认租房需求",
    message: "请先确认当前租房需求，再选择房源并准备合同。",
  },
  selection_required: {
    title: "先选择房源",
    message: "请先保存一套房源候选，再继续。",
  },
  real_selection_required: {
    title: "先选择房源",
    message: "请先保存一套房源候选，再继续。",
  },
  stale_selection: {
    title: "房源需要更新",
    message: "租房需求已改变，请重新选择符合当前需求的房源。",
  },
  needs_clarification: {
    title: "还需要补充资料",
    message: "请补齐所需资料后再继续。",
  },
  version_conflict: {
    title: "资料已更新",
    message: "请读取最新资料，核对当前输入后重新保存。",
  },
  stale_assistant_input: {
    title: "对话已更新",
    message: "请读取最新会话后重新发送。",
  },
  ai_not_configured: {
    title: "助手暂时无法连接",
    message: "请稍后重试，或联系项目管理员检查服务配置。",
  },
  ai_invalid_response: {
    title: "助手暂时未能完成回答",
    message: "请重试这条消息，已保存的对话会保留。",
  },
  ai_timeout: {
    title: "回答时间较长",
    message: "请重试这条消息，已保存的对话会保留。",
  },
};
export function userError(
  code: string | undefined,
  message: string,
): { title: string; message: string } {
  if (code && Object.hasOwn(messages, code)) return messages[code];
  return {
    title: "暂时无法完成",
    message: /[\u3400-\u9fff]/.test(message)
      ? message
      : "请稍后重试，或读取最新资料后继续。",
  };
}
