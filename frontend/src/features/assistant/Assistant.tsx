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
  applyAssistantLease,
  createConversation,
  getConversation,
  listConversations,
  sendAssistantMessage,
} from "../../api/assistant";
import type {
  AssistantAction,
  AssistantTurn,
  Conversation,
  ConversationSummary,
} from "../../api/assistant";
import type { HousingAd } from "../../api/catalog";
import { ApiError, newRequestId, post } from "../../api/client";
import { useCase } from "../../app/context";
import RentalNeeds from "./RentalNeeds";
import CandidateFollowup from "../candidate/CandidateFollowup";
import LivingCards from "./LivingCards";
import TaskResults from "./TaskResults";
import LeaseProposalCard from "./LeaseProposalCard";
import CommuteResults from "./CommuteResults";
import TransitInfo from "./TransitInfo";
import AreaAdvice from "./AreaAdvice";

import ListingDetails from "../real-data/ListingDetails";
import {
  housingCopy,
  recommendationCopy,
} from "../real-data/listingPresentation";
import ListingResults from "./ListingResults";
import ListingActions from "../favorites/ListingActions";
import { useFavorites } from "../favorites/FavoritesContext";
import RecommendationControls from "./RecommendationControls";
import ListingReasons from "./ListingReasons";
import { adjustRecommendation } from "../../api/assistant";
import type {
  RecommendationPatch,
  RecommendationContext,
} from "../../api/assistant";
import FavoritesDrawer from "../favorites/FavoritesDrawer";

const MAX_MESSAGE_LENGTH = 3000;
const MAX_COMPARISON_LISTINGS = 5;
const recommendationChangeValue = (field: string, value: unknown) => {
  if (value == null) return field === "suburb" ? "全部区域" : "未设置";
  if (field === "commute_mode")
    return commuteModeLabels[String(value)] || String(value);
  if (field === "commute_max_minutes") return `${value} 分钟`;
  return briefValueLabels[String(value)] ?? String(value);
};
const briefValueLabels: Record<string, string> = {
  week: "每周",
  month: "每月",
  whole_property: "整套",
  per_room: "每个房间",
  per_person: "每人",
  private_room: "独立单间",
  shared_room: "共享房间",
  student_accommodation: "学生公寓",
};
const commuteModeLabels: Record<string, string> = {
  public_transport: "公共交通",
  train: "火车",
  metro: "地铁",
  bus: "公交车",
  drive: "开车",
  bike: "骑行",
  walk: "步行",
};
// AI switched off is not transient: retrying can never succeed, so it must not lock the forms.
const isInputError = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 422 ||
    error.code === "http_422" ||
    error.code === "ai_disabled" ||
    error.code === "ai_not_configured" ||
    (error.code.startsWith("invalid_") && error.code !== "invalid_response"));

const suggestions = [
  {
    title: "不知道住哪里",
    text: "我刚来悉尼，不知道哪个区适合我，请根据预算、户型和到悉大主校区的通勤帮我推荐。",
    note: "按通勤选区域",
  },
  {
    title: "帮我找房",
    text: "我想租房，帮我整理预算、区域和房屋条件。",
    note: "从需求开始",
  },
  {
    title: "比较房源",
    text: "请按我的租房需求比较房源，说明符合哪些要求、需要取舍什么，再为更便宜的一套准备看房询问。",
    note: "看清差别",
  },
  {
    title: "准备合同",
    text: "帮我整理当前候选房源的租约草稿，先确认需要哪些信息。",
    note: "核对后填入合同",
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
  agent3: "合同助手",
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
  const [selectionIssue, setSelectionIssue] = useState<string | null>(null);
  const [text, setText] = useState("");
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
  const favorites = useFavorites();
  useEffect(() => {
    const initialMessage = searchParams.get("message");
    if (initialMessage) {
      setText(initialMessage.slice(0, MAX_MESSAGE_LENGTH));
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
        const requestedConversation = searchParams.get("conversation");
        const initialId =
          result.items.find(
            (item) => item.conversation_id === requestedConversation,
          )?.conversation_id ?? result.items[0]?.conversation_id;
        if (initialId) {
          const value = await getConversation(caseId, initialId);
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
    setSelectionIssue(null);
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
        if (
          e instanceof ApiError &&
          e.code === "listing_outside_requirements"
        ) {
          setError(null);
          setSelectionIssue(e.message);
          retryRef.current = null;
          setCanRetry(false);
          setPending(null);
        } else {
          setError(e instanceof Error ? e.message : "请求未完成，请重试。");
          if (isInputError(e)) {
            retryRef.current = null;
            setCanRetry(false);
            setPending(null);
          } else setCanRetry(true);
        }
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
    setSelectionIssue(null);
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
        allow_external_data: true,
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
  const applyRecommendation = async (
    patch: RecommendationPatch,
    context: RecommendationContext,
  ) => {
    if (!active.current || busyRef.current || loading || canRetry) return false;
    const target = active.current.conversation_id,
      token = generation.current;
    const body = {
      request_id: newRequestId(),
      expected_revision: context.revision,
      expected_profile_fingerprint: current.draft.fingerprint,
      catalog_fingerprint: context.catalog_fingerprint,
      confirmed: true as const,
      patch: structuredClone(patch),
    };
    let success = false;
    await run(async () => {
      const value = await adjustRecommendation(caseId, target, body);
      if (
        generation.current !== token ||
        active.current?.conversation_id !== target
      )
        return;
      update(value);
      setSelected([]);
      success = true;
    });
    return success;
  };
  const act = (action: AssistantAction) => {
    if (busyRef.current || loading || canRetry || action.superseded) return;
    if (action.type === "suggestion" && action.message) {
      setText(action.message);
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
      void run(async () => {
        const value = await applyAssistantProposal(
          caseId,
          action.proposal_id!,
          requestId,
        );
        if (generation.current !== token) return;
        update(value.conversation);
        await refresh();
        toast.success("找房条件已保存。");
      });
    } else if (
      action.type === "save_candidate" &&
      action.listing_id &&
      action.run_id
    ) {
      modal.confirm({
        title: "选定这套房并开始跟进？",
        content: "选定后可准备看房、记录中介回复，并进入合同流程。",
        okText: "确认选定并跟进",
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
              toast.success("已选定房源，可开始跟进。");
          });
        },
      });
    }
  };
  const confirmLease = async (proposalId: string) => {
    const target = active.current;
    if (!target || busyRef.current || loading || canRetry) return false;
    const token = generation.current;
    const body = {
      request_id: newRequestId(),
      expected_revision: target.revision,
      confirmed: true as const,
      applicability_confirmed: true as const,
    };
    let applied = false;
    await run(async () => {
      const result = await applyAssistantLease(
        caseId,
        target.conversation_id,
        proposalId,
        body,
      );
      if (generation.current !== token) return;
      update(result.conversation);
      applied = true;
      toast.success(`合同草稿 v${result.draft.version} 已同步。`);
    });
    return applied;
  };
  const saveListing = (listing: HousingAd) => {
    if (busyRef.current || loading || canRetry || !active.current) return;
    const target = active.current.conversation_id;
    favorites.choose(listing, { conversation_id: target }, (result) => {
      if (active.current?.conversation_id === target && result.conversation)
        update(result.conversation);
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
          </div>
          <Space wrap>
            <FavoritesDrawer
              selectionSource={
                conversation
                  ? { conversation_id: conversation.conversation_id }
                  : undefined
              }
              onSelected={(result) => {
                if (
                  result.conversation &&
                  result.conversation.conversation_id ===
                    active.current?.conversation_id
                )
                  update(result.conversation);
              }}
              commuteMode={conversation?.rental_brief?.commute_mode}
            />
            <Button
              onClick={() => go("aftercare?tab=repairs")}
              disabled={busy || loading}
            >
              润色报修邮件
            </Button>
            <Button
              className="assistant-needs-button"
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
        <RecommendationControls
          key={`${caseId}-${conversation?.conversation_id || "new"}`}
          caseId={caseId}
          conversationId={conversation?.conversation_id || null}
          revision={conversation?.revision || 0}
          busy={busy || loading}
          disabled={canRetry}
          onReload={() => void read()}
          error={error}
          onApply={applyRecommendation}
        />
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
                      ? item.task_steps?.length
                        ? "本次任务的处理结果如下。"
                        : item.comparison
                          ? "已按你当前明确的要求整理房源比较。"
                          : item.listings.length
                            ? recommendationCopy(item.content)
                            : housingCopy(item.content)
                      : item.content}
                  </div>
                  {item.recommendation_change && (
                    <p
                      className="recommendation-change-summary"
                      role="status"
                      aria-label="本次筛选变化"
                    >
                      {item.recommendation_change.changes
                        .map(
                          (change) =>
                            `${change.label}：${recommendationChangeValue(change.field, change.before)} → ${recommendationChangeValue(change.field, change.after)}`,
                        )
                        .join("；")}
                      {` · 房源 ${item.recommendation_change.before_count} → ${item.recommendation_change.after_count} 套`}
                    </p>
                  )}
                  {item.role === "assistant" && (
                    <AreaAdvice
                      report={item.area_advice}
                      disabled={busy || loading || canRetry}
                      onSuggest={(value) => {
                        setText(value);
                        setSelected([]);
                      }}
                    />
                  )}
                  {item.role === "assistant" && (
                    <CommuteResults
                      message={item}
                      onView={setDetail}
                      onSave={saveListing}
                      disabled={busy || loading || canRetry}
                      onSuggest={(value) => {
                        setText(value);
                        setSelected([]);
                      }}
                    />
                  )}
                  {item.role === "assistant" && <TransitInfo message={item} />}
                  {item.role === "assistant" && (
                    <TaskResults
                      message={item}
                      onView={setDetail}
                      onSave={saveListing}
                      disabled={busy || canRetry}
                    />
                  )}
                  {item.lease_proposal && (
                    <LeaseProposalCard
                      proposal={item.lease_proposal}
                      disabled={busy || loading || canRetry}
                      onConfirm={confirmLease}
                      onOpenContract={() => go("contract?mode=draft")}
                    />
                  )}
                  {Boolean(item.providers?.length) && (
                    <LivingCards providers={item.providers!} />
                  )}
                  {!item.commute_recommendation &&
                    item.listings.some(
                      (listing) =>
                        !item.comparison?.items.some(
                          (compared) =>
                            compared.listing_id === listing.listing_id,
                        ),
                    ) && (
                      <ListingResults
                        listings={item.listings.filter(
                          (listing) =>
                            !item.comparison?.items.some(
                              (compared) =>
                                compared.listing_id === listing.listing_id,
                            ),
                        )}
                      >
                        {(listing) => (
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
                              {listing.bedroom_label ||
                                `${listing.bedrooms} 卧`}{" "}
                              · {listing.bathrooms} 卫 · {listing.car_spaces}{" "}
                              车位
                            </p>
                            <ListingReasons
                              listing={listing}
                              criteria={item.recommendation_criteria}
                              filters={item.recommendation_filters}
                            />
                            <Space>
                              <Button
                                size="small"
                                onClick={() => setDetail(listing)}
                              >
                                房源详情
                              </Button>
                              <ListingActions
                                listing={listing}
                                onSelect={saveListing}
                                disabled={busy || canRetry}
                              />
                            </Space>
                          </article>
                        )}
                      </ListingResults>
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
                              ? "保存找房条件"
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
                  <span>正在处理，请稍候…</span>
                </div>
              )}
            </>
          )}
        </div>
        <div className="assistant-composer-area">
          {selectionIssue && (
            <Alert
              type="warning"
              title="这套房源不符合当前筛选条件"
              description={selectionIssue}
              action={
                <Space wrap>
                  <Button
                    size="small"
                    onClick={() => {
                      setSelectionIssue(null);
                      setNeedsOpen(true);
                    }}
                  >
                    调整租房需求
                  </Button>
                  <Button size="small" onClick={() => setSelectionIssue(null)}>
                    继续比较
                  </Button>
                </Space>
              }
            />
          )}
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
                  setText("请比较所选房源的周租、卧室、浴室和车位。")
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
              disabled={!text.trim() || loading || canRetry}
            />
          </form>
        </div>
      </div>
      <Drawer
        title="房源详情"
        rootClassName="usyd-listing-drawer"
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        size="large"
      >
        {detail && <ListingDetails key={detail.listing_id} listing={detail} />}
      </Drawer>
    </section>
  );
}
