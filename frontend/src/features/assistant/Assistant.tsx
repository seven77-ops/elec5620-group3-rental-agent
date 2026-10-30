import { SoftPreferenceEvidence } from "./SoftPreferenceEvidence";
import KnowledgePanel from "../knowledge/KnowledgePanel";
import PublicKnowledgeReply from "../knowledge/PublicKnowledgeReply";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
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
import RepairDraftCard from "./RepairDraftCard";
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
const ChatContractReview = lazy(
  () => import("../contracts/ChatContractReview"),
);

const MAX_MESSAGE_LENGTH = 3000;
const MAX_COMPARISON_LISTINGS = 5;
const recommendationChangeValue = (field: string, value: unknown) => {
  if (value == null) return field === "suburb" ? "All areas" : "Not set";
  if (field === "commute_mode")
    return commuteModeLabels[String(value)] || String(value);
  if (field === "commute_max_minutes") return `${value} minutes`;
  return String(value);
};
const commuteModeLabels: Record<string, string> = {
  public_transport: "Public transport",
  train: "Train",
  metro: "Metro",
  bus: "Bus",
  drive: "Driving",
  bike: "Cycling",
  walk: "Walking",
};
const isInputError = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 422 ||
    error.code === "http_422" ||
    (error.code.startsWith("invalid_") && error.code !== "invalid_response"));

const suggestions = [
  {
    title: "Where should I live?",
    text: "I am new to Sydney and do not know which area suits me. Please recommend areas based on my budget, housing needs and commute to the University of Sydney main campus.",
    note: "Choose an area by commute",
  },
  {
    title: "Help me find a home",
    text: "I want to rent a home. Help me work through my budget, area and housing needs.",
    note: "Start with your needs",
  },
  {
    title: "Compare listings",
    text: "Compare listings against my rental needs, explain the matches and trade-offs, then prepare an inspection enquiry for the cheaper option.",
    note: "Understand the differences",
  },
  {
    title: "Prepare a lease",
    text: "Help me prepare a lease draft for my current candidate property. First, confirm which details are needed.",
    note: "Review before drafting",
  },
  {
    title: "Aftercare questions",
    text: "I have an aftercare issue. What should I do next?",
    note: "Open Aftercare services",
  },
];
const agentNames = {
  agent1: "Rental needs",
  agent2: "Housing adviser",
  agent3: "Contract assistant",
  agent4: "Aftercare services",
  assistant: "Rental Assistant",
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
          setError(
            e instanceof Error ? e.message : "Could not load the conversation.",
          );
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
          setError(
            e instanceof Error
              ? e.message
              : "The request did not finish. Please try again.",
          );
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
        setError(
          e instanceof Error ? e.message : "Could not load the conversation.",
        );
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
        title: "Confirm sync to Aftercare services?",
        content: (
          <>
            <p>
              Check the details below, then confirm to save them to this case.
              Emails are prepared as drafts.
            </p>
            <ul className="assistant-proposal-summary">
              {action.summary?.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </>
        ),
        okText: "Confirm and save aftercare details",
        cancelText: "Keep editing",
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
            toast.success("Synced to Aftercare services.");
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
        toast.success("Rental needs saved.");
      });
    } else if (
      action.type === "save_candidate" &&
      action.listing_id &&
      action.run_id
    ) {
      modal.confirm({
        title: "Select this property and start follow-up?",
        content:
          "Once selected, you can prepare an inspection and continue to the contract process.",
        okText: "Confirm selection and follow-up",
        cancelText: "Cancel",
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
              toast.success("Property selected. You can start follow-up.");
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
      toast.success(`Lease draft v${result.draft.version} synced.`);
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
        New conversation
      </Button>
      <p className="assistant-history-label">Recent conversations</p>
      <nav aria-label="Conversation history" className="assistant-history-list">
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
            {housingCopy(item.title || "New rental plan")}
          </Button>
        ))}
        {!items.length && (
          <span className="muted small">
            Your conversations will appear here
          </span>
        )}
      </nav>
    </>
  );
  return (
    <section className="assistant-shell" aria-label="AI rental assistant">
      <aside className="assistant-history">{history}</aside>
      <Drawer
        title="Conversation history"
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        size={280}
      >
        {history}
      </Drawer>
      <div className="assistant-workspace">
        <header className="assistant-heading">
          <div>
            <h1>AI rental assistant</h1>
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
              Polish repair email
            </Button>
            <Button
              className="assistant-needs-button"
              onClick={() => setNeedsOpen(true)}
              disabled={busy || loading}
            >
              My rental needs
            </Button>
            <KnowledgePanel />
            <Button
              className="assistant-history-toggle"
              icon={<HistoryOutlined />}
              aria-label="Past conversations"
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
          aria-label="Rental conversation"
          aria-busy={busy || loading}
        >
          {loading ? (
            <div className="assistant-loading">
              <Spin />
              <span>Loading conversation…</span>
            </div>
          ) : (
            <>
              {!conversation?.messages.length && !pending && (
                <div className="assistant-welcome">
                  <div className="assistant-mark">
                    <CommentOutlined />
                  </div>
                  <span className="assistant-eyebrow">
                    Start with a sentence
                  </span>
                  <h2>Where would you like to live?</h2>
                  <p>
                    Tell me what you have in mind. We will find a suitable home
                    step by step.
                  </p>
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
              {conversation?.messages.map((item, messageIndex) => (
                <article
                  key={item.message_id}
                  className={`assistant-message assistant-message-${item.role}`}
                >
                  <span className="assistant-message-author">
                    {item.role === "user" ? "You" : agentNames[item.agent]}
                  </span>
                  {!item.knowledge && (
                    <div className="assistant-bubble">
                      {item.role === "assistant"
                        ? item.task_steps?.length
                          ? "Here are the results of this task."
                          : item.comparison
                            ? "The housing comparison follows your current stated requirements."
                            : item.listings.length
                              ? recommendationCopy(item.content)
                              : housingCopy(item.content)
                        : item.content}
                    </div>
                  )}
                  {item.knowledge && (
                    <PublicKnowledgeReply
                      key={`${caseId}-${item.message_id}`}
                      caseId={caseId}
                      answer={item.knowledge}
                      question={
                        conversation.messages
                          .slice(0, messageIndex)
                          .reverse()
                          .find((message) => message.role === "user")
                          ?.content ?? ""
                      }
                    />
                  )}
                  {item.repair_email && (
                    <RepairDraftCard
                      draft={item.repair_email}
                      disabled={
                        busy ||
                        canRetry ||
                        item.message_id !==
                          conversation.messages.at(-1)?.message_id ||
                        item.actions.some((action) => action.superseded)
                      }
                      onSuggest={(suggestion) => {
                        setText(suggestion);
                        setSelected([]);
                      }}
                    />
                  )}
                  {item.intent === "contract" &&
                    !item.knowledge &&
                    item.message_id ===
                      conversation.messages.at(-1)?.message_id && (
                      <Suspense
                        fallback={
                          <p className="muted">Opening contract review…</p>
                        }
                      >
                        <ChatContractReview />
                      </Suspense>
                    )}
                  {item.soft_preferences && (
                    <SoftPreferenceEvidence report={item.soft_preferences} />
                  )}
                  {item.recommendation_change && (
                    <p
                      className="recommendation-change-summary"
                      role="status"
                      aria-label="Filter changes"
                    >
                      {item.recommendation_change.changes
                        .map(
                          (change) =>
                            `${change.label}: ${recommendationChangeValue(change.field, change.before)} → ${recommendationChangeValue(change.field, change.after)}`,
                        )
                        .join("; ")}
                      {` · Listings ${item.recommendation_change.before_count} → ${item.recommendation_change.after_count} properties`}
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
                              <Tag variant="filled">Live listing</Tag>
                              <Checkbox
                                aria-label={`Compare ${listing.address}`}
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
                                Compare
                              </Checkbox>
                            </div>
                            <h3>{listing.address}</h3>
                            <p className="muted">
                              {listing.suburb} · {listing.postcode}
                            </p>
                            <strong className="assistant-rent">
                              AUD {listing.weekly_rent.toLocaleString()}
                              <small>/week · advertised rent</small>
                            </strong>
                            <p className="assistant-listing-facts">
                              {listing.bedroom_label ||
                                `${listing.bedrooms} bed`}{" "}
                              · {listing.bathrooms} bath · {listing.car_spaces}{" "}
                              car spaces
                            </p>
                            <ListingReasons
                              listing={listing}
                              criteria={item.recommendation_criteria}
                              filters={item.recommendation_filters}
                            />
                            {item.soft_preferences && (
                              <SoftPreferenceEvidence
                                report={item.soft_preferences}
                                listingId={listing.listing_id}
                              />
                            )}
                            <Space>
                              <Button
                                size="small"
                                onClick={() => setDetail(listing)}
                              >
                                Listing details
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
                        action.summary?.length &&
                        !item.repair_email,
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
                          <summary>
                            View all preferences, including other saved needs
                          </summary>
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
                              ? "Replaced by a later change"
                              : "Synced and saved"
                            : action.type === "apply_preferences"
                              ? "Save rental needs"
                              : [
                                    "Record replies and inspection arrangements",
                                    "记录回复与看房安排",
                                  ].includes(action.label)
                                ? "View inspection enquiry checklist"
                                : housingCopy(action.label)}
                        </Button>
                      ))}
                    </Space>
                  )}
                </article>
              ))}
              {pending && (
                <article className="assistant-message assistant-message-user">
                  <span className="assistant-message-author">You</span>
                  <div className="assistant-bubble">{pending}</div>
                </article>
              )}
              {busy && (
                <div className="assistant-thinking" role="status">
                  <Spin size="small" />
                  <span>Working on it. Please wait…</span>
                </div>
              )}
            </>
          )}
        </div>
        <div className="assistant-composer-area">
          {selectionIssue && (
            <Alert
              type="warning"
              title="This listing does not match your current filters"
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
                    Adjust rental needs
                  </Button>
                  <Button size="small" onClick={() => setSelectionIssue(null)}>
                    Keep comparing
                  </Button>
                </Space>
              }
            />
          )}
          {error && (
            <Alert
              type="error"
              title="Could not finish"
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
                      Retry original action
                    </Button>
                  )}
                  <Button
                    size="small"
                    disabled={busy}
                    onClick={() => void read()}
                  >
                    Load latest conversation
                  </Button>
                </Space>
              }
            />
          )}
          {selected.length > 0 && (
            <div className="assistant-comparison">
              <span>
                Selected {selected.length}/{MAX_COMPARISON_LISTINGS} listings
              </span>
              <Button
                size="small"
                disabled={busy || canRetry}
                onClick={() =>
                  setText(
                    "Compare the weekly rent, bedrooms, bathrooms and car spaces of the selected listings.",
                  )
                }
              >
                Compare selected listings
              </Button>
              <Button
                size="small"
                type="text"
                disabled={busy}
                onClick={() => setSelected([])}
              >
                Clear
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
              aria-label="Message to Rental Assistant"
              placeholder="Describe your rental needs or ask a question…"
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
              aria-label="Send message"
              loading={busy}
              disabled={!text.trim() || loading || canRetry}
            />
          </form>
        </div>
      </div>
      <Drawer
        title="Listing details"
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
