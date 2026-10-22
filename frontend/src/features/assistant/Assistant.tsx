import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  App,
  Button,
  Checkbox,
  Drawer,
  Input,
  Space,
  Spin,
  Tag,
} from "antd";
import {
  ArrowUpOutlined,
  CommentOutlined,
  HistoryOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import {
  applyAssistantProposal,
  createConversation,
  getConversation,
  listConversations,
  sendAssistantMessage,
  selectAssistantListing,
} from "../../api/assistant";
import type {
  AssistantAction,
  AssistantTurn,
  Conversation,
  ConversationSummary,
} from "../../api/assistant";
import type { HousingAd } from "../../api/catalog";
import { ApiError, newRequestId, post } from "../../api/client";
import { useCase, currentConfirmation } from "../../app/context";
import RentalNeeds from "./RentalNeeds";
import CandidateFollowup from "../candidate/CandidateFollowup";
import LivingCards from "./LivingCards";
import {
  conversationNeeds,
  needsMatch,
  listingMatches,
  pendingNeeds,
} from "./needs";

import ListingDetails from "../real-data/ListingDetails";
import { housingCopy } from "../real-data/listingPresentation";

const MAX_MESSAGE_LENGTH = 3000;
const MAX_COMPARISON_LISTINGS = 5;
const isInputError = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 422 ||
    error.code === "http_422" ||
    (error.code.startsWith("invalid_") && error.code !== "invalid_response"));

const suggestions = [
  {
    title: "帮我找房",
    text: "我想租房，帮我整理预算、区域和房屋条件。",
    note: "从需求开始",
  },
  {
    title: "比较房源",
    text: "我想比较几套房源，请先帮我找到合适的候选。",
    note: "看清差别",
  },
  {
    title: "复核合同",
    text: "我想复核租房合同，下一步怎么做？",
    note: "进入合同复核",
  },
  {
    title: "租后问题",
    text: "我遇到了租后问题，下一步怎么做？",
    note: "进入租后服务",
  },
];
const agentNames = {
  agent1: "租房需求",
  agent2: "房源顾问",
  agent3: "合同复核",
  agent4: "租后服务",
  assistant: "租房助手",
};

export default function Assistant() {
  const { current, refresh, go } = useCase();
  const { modal, message: toast } = App.useApp();
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [detail, setDetail] = useState<HousingAd | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  const [needsOpen, setNeedsOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const busyRef = useRef(false);
  const composing = useRef(false);
  const generation = useRef(0);
  const retryRef = useRef<(() => Promise<void>) | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  const caseId = current.case_id;
  const active = useRef<Conversation | null>(null);
  const confirmed = currentConfirmation(current);
  const needs = conversationNeeds(conversation, confirmed?.profile);
  const synced =
    needsMatch(needs, confirmed?.profile) && !pendingNeeds(conversation);
  useEffect(() => {
    const initialMessage = searchParams.get("message");
    if (initialMessage) {
      setText(initialMessage.slice(0, MAX_MESSAGE_LENGTH));
      setConsent(false);
      setSearchParams({}, { replace: true });
      return;
    }
    if (searchParams.get("needs") === "1") {
      setNeedsOpen(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  const update = (value: Conversation) => {
    active.current = value;
    setConversation(value);
    setItems((previous) => [
      {
        conversation_id: value.conversation_id,
        title: value.title,
        updated_at:
          value.messages.at(-1)?.created_at ?? new Date().toISOString(),
        message_count: value.messages.length,
      },
      ...previous.filter(
        (item) => item.conversation_id !== value.conversation_id,
      ),
    ]);
  };
  useEffect(() => {
    const token = ++generation.current;
    setLoading(true);
    listConversations(caseId)
      .then(async (result) => {
        if (generation.current !== token) return;
        setItems(result.items);
        if (result.items[0]) {
          const value = await getConversation(
            caseId,
            result.items[0].conversation_id,
          );
          if (generation.current === token) {
            active.current = value;
            setConversation(value);
          }
        }
      })
      .catch((e) => {
        if (generation.current === token)
          setError(e instanceof Error ? e.message : "会话读取失败。");
      })
      .finally(() => {
        if (generation.current === token) setLoading(false);
      });
    return () => {
      generation.current++;
    };
  }, [caseId]);
  useEffect(() => {
    transcript.current?.scrollTo({
      top: transcript.current.scrollHeight,
      behavior: "smooth",
    });
  }, [conversation, pending, busy]);

  const run = async (operation: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    setCanRetry(false);
    retryRef.current = operation;
    const token = generation.current;
    try {
      await operation();
      if (generation.current === token) {
        retryRef.current = null;
        setCanRetry(false);
        setPending(null);
      }
    } catch (e) {
      if (generation.current === token) {
        setError(e instanceof Error ? e.message : "请求未完成，请重试。");
        if (isInputError(e)) {
          retryRef.current = null;
          setCanRetry(false);
          setPending(null);
        } else setCanRetry(true);
      }
    } finally {
      busyRef.current = false;
      if (generation.current === token) setBusy(false);
    }
  };
  const read = async (id?: string) => {
    if (busyRef.current) return;
    const token = ++generation.current;
    setLoading(true);
    setError(null);
    setCanRetry(false);
    setPending(null);
    setSelected([]);
    retryRef.current = null;
    setHistoryOpen(false);
    try {
      const list = await listConversations(caseId);
      if (generation.current !== token) return;
      setItems(list.items);
      const selectedId =
        id ?? active.current?.conversation_id ?? list.items[0]?.conversation_id;
      const value = selectedId
        ? await getConversation(caseId, selectedId)
        : null;
      if (generation.current === token) {
        active.current = value;
        setConversation(value);
      }
    } catch (e) {
      if (generation.current === token)
        setError(e instanceof Error ? e.message : "会话读取失败。");
    } finally {
      if (generation.current === token) setLoading(false);
    }
  };
  const send = () => {
    const originalText = text;
    const input = text.trim();
    if (
      !input ||
      input.length > MAX_MESSAGE_LENGTH ||
      !consent ||
      busyRef.current ||
      loading ||
      canRetry
    )
      return;
    const token = generation.current;
    let target = active.current;
    let turn: AssistantTurn | null = null;
    setPending(input);
    setText("");
    setConsent(false);
    const listingIds = [...selected];
    void run(async () => {
      if (!target) {
        target = await createConversation(caseId);
        if (generation.current !== token) return;
        update(target);
      }
      turn ??= {
        request_id: newRequestId(),
        expected_revision: target.revision,
        message: input,
        allow_external_ai: true,
        ...(listingIds.length ? { listing_ids: listingIds } : {}),
      };
      let value: Conversation;
      try {
        value = await sendAssistantMessage(
          caseId,
          target.conversation_id,
          turn,
        );
      } catch (error) {
        if (generation.current === token && isInputError(error)) {
          setText(originalText);
          setSelected(listingIds);
        }
        throw error;
      }
      if (generation.current !== token) return;
      update(value);
      setPending(null);
      setSelected([]);
      await refresh();
    });
  };
  const act = (action: AssistantAction) => {
    if (busyRef.current || loading || canRetry || action.superseded) return;
    if (action.type === "suggestion" && action.message) {
      setText(action.message);
      setConsent(false);
      setSelected([]);
      return;
    }
    if (action.type === "navigate" && action.page) {
      go(action.page);
      return;
    }
    const token = generation.current;
    const requestId = newRequestId();
    if (
      action.type === "apply_living_services" &&
      action.proposal_id &&
      action.expected_version !== undefined
    ) {
      modal.confirm({
        title: "确认同步到租后服务？",
        content: (
          <>
            <p>核对以下信息，确认后保存到当前案例。邮件只生成草稿。</p>
            <ul className="assistant-proposal-summary">
              {action.summary?.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </>
        ),
        okText: "确认保存租后资料",
        cancelText: "继续修改",
        onOk: async () => {
          if (generation.current !== token) return;
          await run(async () => {
            await post(
              `/cases/${encodeURIComponent(caseId)}/living-services/proposals/${encodeURIComponent(action.proposal_id!)}/apply`,
              {
                request_id: requestId,
                expected_version: action.expected_version,
                confirmed: true,
              },
            );
            if (generation.current !== token || !active.current) return;
            const value = await getConversation(
              caseId,
              active.current.conversation_id,
            );
            if (generation.current !== token) return;
            update(value);
            toast.success("已同步到租后服务。");
          });
        },
      });
    } else if (action.type === "apply_preferences" && action.proposal_id) {
      modal.confirm({
        title: "确认同步租房需求？",
        content: (
          <>
            <p>将保存并确认新的偏好版本，按这些条件生成真实房源报告。</p>
            {action.summary?.length ? (
              <ul className="assistant-proposal-summary">
                {action.summary.map((line) => (
                  <li key={line}>{housingCopy(line)}</li>
                ))}
              </ul>
            ) : (
              <p>请先查看租房偏好，核对完整条件。</p>
            )}
          </>
        ),
        okText: "确认同步并生成推荐",
        okButtonProps: { disabled: !action.summary?.length },
        cancelText: "继续聊聊",
        onOk: async () => {
          if (generation.current !== token) return;
          await run(async () => {
            const value = await applyAssistantProposal(
              caseId,
              action.proposal_id!,
              requestId,
            );
            if (generation.current !== token) return;
            update(value.conversation);
            await refresh();
            if (generation.current === token)
              toast.success("租房需求与房源推荐已同步。");
          });
        },
      });
    } else if (
      action.type === "save_candidate" &&
      action.listing_id &&
      action.run_id
    ) {
      modal.confirm({
        title: "保存这条真实房源候选？",
        content: "保存房源及来源快照，在租状态、租金计价对象和租期仍需核实。",
        okText: "确认保存候选",
        cancelText: "取消",
        onOk: async () => {
          if (generation.current !== token) return;
          await run(async () => {
            await post(`/cases/${encodeURIComponent(caseId)}/selections`, {
              request_id: requestId,
              run_id: action.run_id,
              listing_id: action.listing_id,
              confirmed: true,
            });
            if (generation.current !== token) return;
            await refresh();
            if (generation.current === token)
              toast.success("真实房源候选已保存。");
          });
        },
      });
    }
  };
  const saveListing = (listing: HousingAd) => {
    if (busyRef.current || loading || canRetry) return;
    if (!confirmed || !synced || !listingMatches(listing, confirmed.profile)) {
      toast.info("请先核对并同步租房需求，再保存符合条件的候选。");
      setNeedsOpen(true);
      return;
    }
    const target = active.current;
    if (!target) return;
    const token = generation.current;
    const body = {
      request_id: newRequestId(),
      expected_revision: target.revision,
      expected_profile_fingerprint: current.draft.fingerprint,
      listing_id: listing.listing_id,
      confirmed: true as const,
    };
    modal.confirm({
      title: "保存这条真实房源候选？",
      content: (
        <>
          <p>
            {listing.address} · AUD {listing.weekly_rent}/周
          </p>
          <p>保存后会出现在房源推荐页；在租状态、账单与计价对象仍需核实。</p>
          {current.selection &&
            current.selection.listing_id !== listing.listing_id && (
              <p>将替换当前保存的候选房源。</p>
            )}
        </>
      ),
      okText: "确认保存候选",
      cancelText: "继续比较",
      onOk: async () => {
        if (generation.current !== token) return;
        await run(async () => {
          const result = await selectAssistantListing(
            caseId,
            target.conversation_id,
            body,
          );
          if (generation.current !== token) return;
          update(result.conversation);
          await refresh();
          toast.success("候选房源已同步到房源推荐。");
        });
      },
    });
  };
  const history = (
    <>
      <Button
        block
        icon={<PlusOutlined />}
        disabled={busy || loading || canRetry}
        onClick={() => {
          generation.current++;
          active.current = null;
          setConversation(null);
          setSelected([]);
          setText("");
          setConsent(false);
          setError(null);
          setPending(null);
          setHistoryOpen(false);
        }}
      >
        新会话
      </Button>
      <p className="assistant-history-label">最近会话</p>
      <nav aria-label="会话历史" className="assistant-history-list">
        {items.map((item) => (
          <Button
            type="text"
            key={item.conversation_id}
            disabled={busy || loading}
            className={
              conversation?.conversation_id === item.conversation_id
                ? "is-active"
                : ""
            }
            onClick={() => void read(item.conversation_id)}
          >
            {item.title || "租房新计划"}
          </Button>
        ))}
        {!items.length && <span className="muted small">会话会保存在这里</span>}
      </nav>
      <div className="assistant-history-foot">
        你的需求，你来决定。
        <br />
        修改偏好前会请你确认。
      </div>
    </>
  );
  return (
    <section className="assistant-shell" aria-label="AI租房助手">
      <aside className="assistant-history">{history}</aside>
      <Drawer
        title="会话历史"
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        size={280}
      >
        {history}
      </Drawer>
      <div className="assistant-workspace">
        <header className="assistant-heading">
          <div>
            <h1>AI租房助手</h1>
            <span>找房、比较、合同与租后，一起理清下一步</span>
          </div>
          <Space>
            <Button
              onClick={() => setNeedsOpen(true)}
              disabled={busy || loading}
            >
              我的租房需求
            </Button>
            <Button
              className="assistant-history-toggle"
              icon={<HistoryOutlined />}
              aria-label="历史会话"
              onClick={() => setHistoryOpen(true)}
            />
          </Space>
        </header>
        <div
          className="assistant-needs-strip"
          data-testid="assistant-needs-status"
        >
          <div>
            <Tag color={synced ? "blue" : "orange"}>
              {synced
                ? `已同步 v${confirmed?.version}`
                : confirmed
                  ? "需求有更新，待同步"
                  : "尚未同步需求"}
            </Tag>
            <span>
              {needs.suburb === undefined
                ? "区域待确认"
                : needs.suburb || "不限区域"}
              {needs.budget_amount !== undefined
                ? ` · 预算 ${needs.budget_amount} AUD${needs.budget_period === "week" ? "/周" : "（周期待确认）"}`
                : " · 可以边聊边整理需求"}
            </span>
          </div>
          <Button
            size="small"
            type="text"
            onClick={() => go("recommendations")}
          >
            查看房源推荐
          </Button>
        </div>
        <CandidateFollowup compact />
        <RentalNeeds
          open={needsOpen}
          onClose={() => setNeedsOpen(false)}
          conversation={conversation}
          onConversation={update}
          busy={busy}
          execute={run}
          error={error}
          canRetry={canRetry}
          onRetry={() => {
            if (retryRef.current) void run(retryRef.current);
          }}
          onReload={() => read(active.current?.conversation_id)}
          isCurrent={(id) => active.current?.conversation_id === id}
        />
        <div
          ref={transcript}
          className="assistant-transcript"
          role="log"
          aria-label="租房对话"
          aria-busy={busy || loading}
        >
          {loading ? (
            <div className="assistant-loading">
              <Spin />
              <span>正在读取会话…</span>
            </div>
          ) : (
            <>
              {!conversation?.messages.length && !pending && (
                <div className="assistant-welcome">
                  <div className="assistant-mark">
                    <CommentOutlined />
                  </div>
                  <span className="assistant-eyebrow">从一句话开始</span>
                  <h2>今天，想住在哪里？</h2>
                  <p>告诉我你的想法，我们一步步找到合适的家。</p>
                  <div className="assistant-suggestions">
                    {suggestions.map((suggestion) => (
                      <button
                        key={suggestion.title}
                        onClick={() => setText(suggestion.text)}
                        disabled={busy}
                      >
                        <strong>
                          {suggestion.title}
                          <span>↗</span>
                        </strong>
                        <small>{suggestion.note}</small>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {conversation?.messages.map((item) => (
                <article
                  key={item.message_id}
                  className={`assistant-message assistant-message-${item.role}`}
                >
                  <span className="assistant-message-author">
                    {item.role === "user" ? "你" : agentNames[item.agent]}
                  </span>
                  <div className="assistant-bubble">
                    {item.role === "assistant"
                      ? housingCopy(item.content)
                      : item.content}
                  </div>
                  {Boolean(item.providers?.length) && (
                    <LivingCards providers={item.providers!} />
                  )}
                  {item.listings.length > 0 && (
                    <div className="assistant-listings">
                      {item.listings.map((listing) => (
                        <article
                          key={listing.listing_id}
                          className="assistant-listing"
                          data-listing-id={listing.listing_id}
                        >
                          <div className="assistant-listing-top">
                            <Tag variant="filled">真实房源</Tag>
                            <Checkbox
                              aria-label={`选择比较 ${listing.address}`}
                              checked={selected.includes(listing.listing_id)}
                              disabled={
                                busy ||
                                canRetry ||
                                (selected.length >= MAX_COMPARISON_LISTINGS &&
                                  !selected.includes(listing.listing_id))
                              }
                              onChange={(e) =>
                                setSelected((ids) =>
                                  e.target.checked
                                    ? ids.includes(listing.listing_id) ||
                                      ids.length >= MAX_COMPARISON_LISTINGS
                                      ? ids
                                      : [...ids, listing.listing_id]
                                    : ids.filter(
                                        (id) => id !== listing.listing_id,
                                      ),
                                )
                              }
                            >
                              比较
                            </Checkbox>
                          </div>
                          <h3>{listing.address}</h3>
                          <p className="muted">
                            {listing.suburb} · {listing.postcode}
                          </p>
                          <strong className="assistant-rent">
                            AUD {listing.weekly_rent.toLocaleString()}
                            <small>/周 · 房源标价</small>
                          </strong>
                          <p className="assistant-listing-facts">
                            {listing.bedroom_label || `${listing.bedrooms} 卧`}{" "}
                            · {listing.bathrooms} 卫 · {listing.car_spaces} 车位
                          </p>
                          <Space>
                            <Button
                              size="small"
                              onClick={() => setDetail(listing)}
                            >
                              房源详情
                            </Button>
                            {current.selection?.listing_id ===
                              listing.listing_id &&
                            current.selection.profile_fingerprint ===
                              confirmed?.fingerprint ? (
                              <Tag color="blue">当前候选</Tag>
                            ) : (
                              <Button
                                size="small"
                                disabled={busy || canRetry}
                                onClick={() => saveListing(listing)}
                              >
                                保存为候选
                              </Button>
                            )}
                            <a
                              href={listing.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              原始房源 ↗
                            </a>
                          </Space>
                          <small className="muted">
                            在租状态、账单与计价对象待核实
                          </small>
                        </article>
                      ))}
                    </div>
                  )}
                  {item.actions
                    .filter(
                      (action) =>
                        (action.type === "apply_preferences" ||
                          action.type === "apply_living_services") &&
                        action.summary?.length,
                    )
                    .map((action, index) => {
                      const summary = (
                        <ul
                          className="assistant-proposal-summary"
                          key={`summary-${index}`}
                        >
                          {action.summary!.map((line) => (
                            <li key={line}>
                              {action.type === "apply_preferences"
                                ? housingCopy(line)
                                : line}
                            </li>
                          ))}
                        </ul>
                      );
                      return item.intent === "collect_preferences" ? (
                        <details key={`summary-${index}`}>
                          <summary>查看完整偏好（含其他已保存条件）</summary>
                          {summary}
                        </details>
                      ) : (
                        summary
                      );
                    })}
                  {item.actions.length > 0 && (
                    <Space wrap className="assistant-message-actions">
                      {item.actions.map((action, index) => (
                        <Button
                          key={`${action.type}-${index}`}
                          disabled={
                            busy ||
                            canRetry ||
                            action.applied ||
                            action.superseded
                          }
                          onClick={() => act(action)}
                        >
                          {action.applied || action.superseded
                            ? action.superseded
                              ? "已由后续修改替代"
                              : "已同步保存"
                            : action.type === "apply_preferences"
                              ? "确认并同步需求"
                              : action.label}
                        </Button>
                      ))}
                    </Space>
                  )}
                </article>
              ))}
              {pending && (
                <article className="assistant-message assistant-message-user">
                  <span className="assistant-message-author">你</span>
                  <div className="assistant-bubble">{pending}</div>
                </article>
              )}
              {busy && (
                <div className="assistant-thinking" role="status">
                  <Spin size="small" />
                  <span>正在整理你的需求…</span>
                </div>
              )}
            </>
          )}
        </div>
        <div className="assistant-composer-area">
          {error && (
            <Alert
              type="error"
              title="暂时未完成"
              description={error}
              action={
                <Space wrap>
                  {canRetry && (
                    <Button
                      size="small"
                      disabled={busy}
                      onClick={() =>
                        retryRef.current && void run(retryRef.current)
                      }
                    >
                      重试原操作
                    </Button>
                  )}
                  <Button
                    size="small"
                    disabled={busy}
                    onClick={() => void read()}
                  >
                    读取最新会话
                  </Button>
                </Space>
              }
            />
          )}
          {selected.length > 0 && (
            <div className="assistant-comparison">
              <span>
                已选 {selected.length}/{MAX_COMPARISON_LISTINGS} 套房源
              </span>
              <Button
                size="small"
                disabled={busy || canRetry}
                onClick={() =>
                  setText(
                    "请比较所选房源的周租、卧室、浴室和车位，并说明待核实项。",
                  )
                }
              >
                比较所选房源
              </Button>
              <Button
                size="small"
                type="text"
                disabled={busy}
                onClick={() => setSelected([])}
              >
                清空
              </Button>
            </div>
          )}
          <form
            className="assistant-composer"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <Input.TextArea
              aria-label="给租房助手的消息"
              placeholder="描述你的租房需求，或问一个问题…"
              value={text}
              disabled={busy || loading || canRetry}
              maxLength={MAX_MESSAGE_LENGTH}
              autoSize={{ minRows: 1, maxRows: 5 }}
              onChange={(e) => setText(e.target.value)}
              onCompositionStart={() => {
                composing.current = true;
              }}
              onCompositionEnd={() => {
                composing.current = false;
              }}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !composing.current &&
                  !e.nativeEvent.isComposing &&
                  e.keyCode !== 229
                ) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <Button
              type="primary"
              htmlType="submit"
              shape="circle"
              icon={<ArrowUpOutlined />}
              aria-label="发送消息"
              loading={busy}
              disabled={!text.trim() || !consent || loading || canRetry}
            />
          </form>
          <Checkbox
            className="assistant-consent"
            checked={consent}
            disabled={busy || loading || canRetry}
            onChange={(e) => setConsent(e.target.checked)}
          >
            同意本次将消息与相关租房、租后资料发送至外部 AI；请勿填写敏感信息。
          </Checkbox>
        </div>
      </div>
      <Drawer
        title="房源详情"
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        size="large"
      >
        {detail && <ListingDetails key={detail.listing_id} listing={detail} />}
      </Drawer>
    </section>
  );
}
