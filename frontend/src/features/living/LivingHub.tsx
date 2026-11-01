import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Button, Space, Spin, Tabs } from "antd";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  getLivingProviders,
  getLivingServices,
  writeLivingServices,
} from "../../api/living";
import type {
  LivingRecord,
  LivingWrite,
  ProviderDirectory,
} from "../../api/living";
import { newRequestId } from "../../api/client";
import { useCase } from "../../app/context";
import { useAction } from "../../components/useAction";
import IssueReport from "../aftercare/IssueReport";
import { Failure } from "../../components/Common";
import HomeDrawer from "./HomeDrawer";
import InProgressDrawer from "./InProgressDrawer";
import { inProgressItems } from "./inProgress";
import Repairs from "./Repairs";
import Utilities from "./Utilities";
import Services from "./Services";
import "./living.css";

export default function LivingHub() {
  const { current } = useCase();
  const [query, setQuery] = useSearchParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState<LivingRecord | null>(null),
    [directory, setDirectory] = useState<ProviderDirectory | null>(null);
  const [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState<unknown>(null);
  const action = useAction();
  const generation = useRef(0);
  const busyRef = useRef(false);
  busyRef.current = action.busy || loading;
  const caseId = current.case_id;
  const [focusVersion, setFocusVersion] = useState(0);
  const [homeOpen, setHomeOpen] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const openTodo = (target: string, repair?: string, booking?: string) => {
    setFocusVersion((value) => value + 1);
    setQuery({
      tab: target === "contacts" ? "repairs" : target,
      ...(repair ? { repair } : {}),
      ...(booking ? { booking } : {}),
      ...(target === "contacts" ? { section: "contacts" } : {}),
    });
  };
  const load = useCallback(async () => {
    const token = ++generation.current;
    setLoading(true);
    setLoadError(null);
    try {
      const [value, providers] = await Promise.all([
        getLivingServices(caseId),
        getLivingProviders(),
      ]);
      if (generation.current === token) {
        setRecord(value);
        setDirectory(providers);
      }
    } catch (e) {
      if (generation.current === token) setLoadError(e);
    } finally {
      if (generation.current === token) setLoading(false);
    }
  }, [caseId]);
  useEffect(() => {
    void load();
    return () => {
      generation.current++;
    };
  }, [load]);
  const save: LivingWrite = (
    path,
    values,
    expectedVersion,
    onSuccess,
    requestId = newRequestId(),
  ) => {
    const token = generation.current;
    const body = structuredClone(values);
    return action.run(async () => {
      const result = await writeLivingServices(
        caseId,
        path,
        body,
        expectedVersion,
        requestId,
      );
      if (generation.current !== token) return;
      setRecord(result);
      onSuccess?.();
    });
  };
  const rawTab = query.get("tab") || "repairs";
  const tab = [
    "repairs",
    "utilities",
    "services",
    "moveout",
    "bond",
    "issues",
  ].includes(rawTab)
    ? rawTab
    : "repairs";
  const ask = (message: string) =>
    navigate(
      `/cases/${encodeURIComponent(caseId)}/assistant?message=${encodeURIComponent(message)}`,
    );
  const error = loadError || action.error;
  const progressItems = record
    ? inProgressItems(record, directory?.providers ?? [])
    : [];
  const toolbar = (
    <Space wrap>
      <Button onClick={() => setHomeOpen(true)} disabled={action.busy}>
        My home
      </Button>
      <Button
        onClick={() => setProgressOpen(true)}
        disabled={!record || action.busy}
      >
        In progress ({progressItems.length})
      </Button>
      <Button
        disabled={action.busy}
        loading={loading}
        onClick={() => {
          if (!busyRef.current) {
            action.clear();
            void load();
          }
        }}
      >
        Load latest information
      </Button>
    </Space>
  );
  const drawers = (
    <Fragment key="home-toolbar-drawers">
      <HomeDrawer
        caseId={caseId}
        providers={directory?.providers ?? []}
        onOpenService={(target) => {
          setHomeOpen(false);
          openTodo(target.tab, undefined, target.booking);
        }}
        open={homeOpen}
        onClose={() => setHomeOpen(false)}
        onSaved={(value) => {
          setRecord(value);
          void load();
        }}
      />
      <InProgressDrawer
        open={progressOpen}
        onClose={() => setProgressOpen(false)}
        items={progressItems}
        onOpen={(item) => {
          setProgressOpen(false);
          openTodo(item.tab, item.repair, item.booking);
        }}
      />
    </Fragment>
  );

  if (["issues", "moveout", "bond"].includes(tab))
    return (
      <section className="living-hub">
        <header className="living-heading">
          <h1>Issue report</h1>
          {toolbar}
        </header>
        <Tabs
          activeKey="issues"
          onChange={(key) => setQuery({ tab: key })}
          items={[
            { key: "repairs", label: "Repairs" },
            { key: "utilities", label: "Utilities" },
            { key: "services", label: "Moving and cleaning" },
            { key: "issues", label: "Issue report", children: <IssueReport /> },
          ]}
        />
        {drawers}
      </section>
    );
  if (!record || !directory)
    return (
      <section className="living-hub">
        <header className="living-heading">
          <h1>Living and aftercare services</h1>
          {toolbar}
        </header>
        {drawers}
        {loading ? (
          <div className="living-loading" role="status">
            <Spin />
            <span>Loading living service information…</span>
          </div>
        ) : (
          <Failure error={error} retry={() => void load()} />
        )}
      </section>
    );
  const tabs = [
    {
      key: "repairs",
      label: "Repairs",
      children: (
        <Repairs
          record={record}
          busy={action.busy || loading}
          save={save}
          focusedId={tab === "repairs" ? query.get("repair") : null}
          focusVersion={focusVersion}
          onChat={ask}
        />
      ),
    },
    {
      key: "utilities",
      label: "Utilities",
      children: (
        <Utilities
          onViewHome={() => setHomeOpen(true)}
          record={record}
          providers={directory.providers}
          busy={action.busy || loading}
          save={save}
        />
      ),
    },
    {
      key: "services",
      label: "Moving and cleaning",
      children: (
        <Services
          onViewHome={() => setHomeOpen(true)}
          focusedId={tab === "services" ? query.get("booking") : null}
          focusVersion={focusVersion}
          record={record}
          providers={directory.providers}
          busy={action.busy || loading}
          save={save}
        />
      ),
    },
    { key: "issues", label: "Issue report", children: <IssueReport /> },
  ];
  return (
    <section className="living-hub">
      <header className="living-heading">
        <div>
          <h1>Living and aftercare services</h1>
        </div>
        {toolbar}
      </header>
      <Failure
        error={error}
        retry={
          action.error
            ? action.retry
            : () => {
                action.clear();
                void load();
              }
        }
      />
      <Tabs
        activeKey={tab}
        onChange={(key) => setQuery({ tab: key })}
        items={tabs}
      />
      {tab !== "moveout" && tab !== "bond" && (
        <div className="living-ai-help">
          <span>You can also start with Rental Assistant</span>
          <Space wrap>
            {tab === "repairs" ? (
              <Button
                onClick={() =>
                  ask(
                    "I want to prepare a repair email to my agent. Please ask me about the issue first.",
                  )
                }
              >
                Discuss a repair
              </Button>
            ) : tab === "utilities" ? (
              <Button
                onClick={() =>
                  ask(
                    "I want to organise my utility providers. Please explain the options using my confirmed information first.",
                  )
                }
              >
                Discuss utilities
              </Button>
            ) : (
              <>
                <Button
                  onClick={() =>
                    ask(
                      "I need moving services. Please help me prepare questions to confirm with a removalist.",
                    )
                  }
                >
                  Discuss moving needs
                </Button>
                <Button
                  onClick={() =>
                    ask(
                      "I need cleaning services. Please help me clarify the scope and questions for a quote.",
                    )
                  }
                >
                  Discuss cleaning needs
                </Button>
              </>
            )}
          </Space>
        </div>
      )}
      {drawers}
    </section>
  );
}
