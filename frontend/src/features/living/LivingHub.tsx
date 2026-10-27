import { useCallback, useEffect, useRef, useState } from "react";
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
import Aftercare from "../Aftercare";
import { Failure } from "../../components/Common";
import ProfileEditor from "./ProfileEditor";
import Repairs from "./Repairs";
import Utilities from "./Utilities";
import Services from "./Services";
import LivingFiles from "./LivingFiles";
import TenancySource from "./TenancySource";
import LivingTodos from "./LivingTodos";
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
  const openTodo = (target: string, repair?: string, booking?: string) => {
    setFocusVersion((value) => value + 1);
    setQuery({
      tab: target === "contacts" ? "repairs" : target,
      ...(repair ? { repair } : {}),
      ...(booking ? { booking } : {}),
      ...(target === "contacts" ? { section: "contacts" } : {}),
    });
    if (target === "contacts")
      requestAnimationFrame(() => {
        const button = document.getElementById("living-contact-editor");
        button?.focus({ preventScroll: true });
        button?.scrollIntoView({ behavior: "smooth", block: "center" });
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
  const save: LivingWrite = (path, values, expectedVersion, onSuccess) => {
    const requestId = newRequestId(),
      token = generation.current;
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
  const tab = ["repairs", "utilities", "services", "moveout", "bond"].includes(
    rawTab,
  )
    ? rawTab
    : "repairs";
  const ask = (message: string) =>
    navigate(
      `/cases/${encodeURIComponent(caseId)}/assistant?message=${encodeURIComponent(message)}`,
    );
  const error = loadError || action.error;
  if (!record || !directory)
    return (
      <section className="living-hub">
        <h1>租后生活服务</h1>
        {loading ? (
          <div className="living-loading" role="status">
            <Spin />
            <span>正在读取生活服务资料…</span>
          </div>
        ) : (
          <Failure error={error} retry={() => void load()} />
        )}
      </section>
    );
  const tabs = [
    {
      key: "repairs",
      label: "日常报修",
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
      label: "水电气网",
      children: (
        <Utilities
          record={record}
          providers={directory.providers}
          busy={action.busy || loading}
          save={save}
        />
      ),
    },
    {
      key: "services",
      label: "搬运与清洁",
      children: (
        <Services
          focusedId={tab === "services" ? query.get("booking") : null}
          focusVersion={focusVersion}
          record={record}
          providers={directory.providers}
          busy={action.busy || loading}
          save={save}
        />
      ),
    },
    {
      key: "moveout",
      label: "退租与押金",
      children: (
        <Aftercare
          key={tab === "bond" ? "bond" : "plan"}
          embedded
          initialMoveOutDate={record.profile.move_out_date || undefined}
          initialTab={tab === "bond" ? "bond" : "plan"}
        />
      ),
    },
  ];
  return (
    <section className="living-hub">
      <header className="living-heading">
        <div>
          <h1>租后生活服务</h1>
        </div>
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
          读取最新资料
        </Button>
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
      <LivingTodos
        record={record}
        providers={directory.providers}
        go={openTodo}
      />
      <TenancySource
        record={record}
        busy={action.busy || loading}
        onImported={load}
      />
      <ProfileEditor
        record={record}
        busy={action.busy || loading}
        save={save}
      />
      <Tabs
        activeKey={tab === "bond" ? "moveout" : tab}
        onChange={(key) => setQuery({ tab: key })}
        items={tabs}
      />
      <LivingFiles caseId={caseId} repairs={record.repairs} />
      {tab !== "moveout" && tab !== "bond" && (
        <div className="living-ai-help">
          <span>也可以先和租房助手聊聊</span>
          <Space wrap>
            {tab === "repairs" ? (
              <Button
                onClick={() =>
                  ask("我想准备一封给中介的报修邮件，请先问我问题详情。")
                }
              >
                聊聊报修问题
              </Button>
            ) : tab === "utilities" ? (
              <Button
                onClick={() =>
                  ask(
                    "我想整理水电气网供应商，请先根据我确认的资料帮我了解选择。",
                  )
                }
              >
                聊聊水电气网
              </Button>
            ) : (
              <>
                <Button
                  onClick={() =>
                    ask("我需要搬家服务，请帮我整理需要向搬运公司确认的问题。")
                  }
                >
                  聊聊搬家需求
                </Button>
                <Button
                  onClick={() =>
                    ask("我需要清洁服务，请帮我整理清洁范围和询价问题。")
                  }
                >
                  聊聊清洁需求
                </Button>
              </>
            )}
          </Space>
        </div>
      )}
    </section>
  );
}
