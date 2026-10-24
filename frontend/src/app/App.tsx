import {
  Component,
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { Alert, Button, Drawer, Layout, Menu, Space } from "antd";
import {
  CheckSquareOutlined,
  FileTextOutlined,
  FormOutlined,
  HomeOutlined,
  InfoCircleOutlined,
  MenuOutlined,
  CommentOutlined,
} from "@ant-design/icons";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { api, post } from "../api/client";
import type { CaseState, DemoConfig } from "../api/types";
import {
  EvidenceDrawer,
  Failure,
  JsonDetails,
  Loading,
} from "../components/Common";
import { useAction } from "../components/useAction";
import { CaseContext } from "./context";
const Assistant = lazy(() => import("../features/assistant/Assistant"));
const Preferences = lazy(() => import("../features/Preferences"));
const LegacyRecommendations = lazy(() => import("../features/Recommendations"));
const Recommendations = lazy(() => import("../features/RealRecommendations"));
const Contract = lazy(() => import("../features/contracts/ContractAssistant"));
const Aftercare = lazy(() => import("../features/Aftercare"));
const LivingHub = lazy(() => import("../features/living/LivingHub"));
const Operator = lazy(() => import("../features/Operator"));

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    return this.state.error ? (
      <div className="panel">
        <h1>页面暂时无法显示</h1>
        <p>已提交的数据保存在本地服务中。刷新后可以重新读取。</p>
        <Button onClick={() => location.reload()}>重新读取案例</Button>
      </div>
    ) : (
      this.props.children
    );
  }
}
const nav = [
  {
    key: "assistant",
    label: "AI租房助手",
    icon: <CommentOutlined aria-hidden="true" />,
  },
  {
    key: "preferences",
    label: "租房偏好",
    icon: <FormOutlined aria-hidden="true" />,
  },
  {
    key: "recommendations",
    label: "房源推荐",
    icon: <HomeOutlined aria-hidden="true" />,
  },
  {
    key: "contract",
    label: "合同复核",
    icon: <FileTextOutlined aria-hidden="true" />,
  },
  {
    key: "aftercare",
    label: "租后服务",
    icon: <CheckSquareOutlined aria-hidden="true" />,
  },
];
export default function App() {
  const [config, setConfig] = useState<DemoConfig | null>(null);
  const [current, setCurrent] = useState<CaseState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [mobile, setMobile] = useState(false);
  const [evidence, setEvidence] = useState(false);
  const action = useAction();
  const navigate = useNavigate();
  const location = useLocation();
  const parts = location.pathname.split("/");
  const routeCase = parts[1] === "cases" ? parts[2] : null;
  const caseId = routeCase ?? localStorage.getItem("rental-case-v1");
  const idRef = useRef(caseId);
  idRef.current = caseId;
  const routePage =
    parts[1] === "operator" ? "operator" : (parts[3] ?? "assistant");
  const page = routePage === "overview" ? "assistant" : routePage;
  useEffect(() => {
    let valid = true;
    setLoading(true);
    setError(null);
    setCurrent((saved) => (saved?.case_id === caseId ? saved : null));
    Promise.all([
      api<DemoConfig>("/demo-config"),
      caseId
        ? api<CaseState>(`/cases/${encodeURIComponent(caseId)}`)
        : Promise.resolve(null),
    ])
      .then(([cfg, c]) => {
        if (valid) {
          setConfig(cfg);
          setCurrent(c);
          if (c) localStorage.setItem("rental-case-v1", c.case_id);
        }
      })
      .catch((e) => {
        if (valid) setError(e);
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [caseId]);
  const refresh = useCallback(async () => {
    const id = idRef.current;
    if (!id) return;
    const c = await api<CaseState>(`/cases/${encodeURIComponent(id)}`);
    if (idRef.current === id) setCurrent(c);
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if (routePage === "overview" && caseId)
      navigate(`/cases/${caseId}/assistant`, { replace: true });
    if (page === "real-data" && caseId)
      navigate(`/cases/${caseId}/recommendations`, { replace: true });
  }, [page, routePage, caseId, navigate]);
  const go = (target: string) => {
    setMobile(false);
    navigate(
      target === "operator"
        ? "/operator"
        : current
          ? `/cases/${current.case_id}/${target}`
          : "/",
    );
  };
  const create = () =>
    void action.run(async () => {
      const c = await post<CaseState>("/cases", {});
      localStorage.setItem("rental-case-v1", c.case_id);
      setCurrent(c);
      navigate(`/cases/${c.case_id}/assistant`);
    });
  const navigation = (
    <>
      <Menu
        mode="inline"
        selectedKeys={[page]}
        items={
          config?.mode === "real_listings"
            ? nav
                .filter((item) => item.key !== "preferences")
                .map((item) =>
                  item.key === "contract"
                    ? { ...item, label: "合同助手" }
                    : item,
                )
            : nav
        }
        onClick={({ key }) => go(key)}
      />
      <div className="sidebar-bottom">
        {current && (
          <Button
            className="mobile-new-case"
            onClick={create}
            loading={action.busy}
          >
            新建演示案例
          </Button>
        )}
        <Button
          type="text"
          icon={<InfoCircleOutlined />}
          onClick={() => {
            setMobile(false);
            setEvidence(true);
          }}
        >
          演示与证据
        </Button>
        <Link to="/operator" onClick={() => setMobile(false)}>
          本地演示操作员
        </Link>
      </div>
    </>
  );
  const pages: Record<string, ReactNode> = {
    assistant: <Assistant />,
    preferences: <Preferences />,
    recommendations:
      config?.mode === "real_listings" ? (
        <Recommendations />
      ) : (
        <LegacyRecommendations />
      ),
    contract: <Contract />,
    aftercare: config?.mode === "real_listings" ? <LivingHub /> : <Aftercare />,
    operator: <Operator />,
  };
  return (
    <ErrorBoundary>
      <Layout className="app-layout">
        <header className="app-header">
          <div className="brand">
            <HomeOutlined />
            <span>租房助手</span>
          </div>
          <Space>
            <span className="demo-label">
              {config?.mode === "real_listings"
                ? "真实房源 · 参考快照"
                : "合成数据演示"}
            </span>
            {current && (
              <Button
                className="new-case"
                size="small"
                onClick={create}
                loading={action.busy}
                aria-label="新建案例"
              >
                新建案例
              </Button>
            )}
            <Button
              className="mobile-menu"
              aria-label="打开导航"
              icon={<MenuOutlined />}
              onClick={() => setMobile(true)}
            />
          </Space>
        </header>
        <Layout>
          <Layout.Sider width={208} className="desktop-sidebar">
            {navigation}
          </Layout.Sider>
          <Drawer
            title="租房助手导航"
            placement="left"
            open={mobile}
            onClose={() => setMobile(false)}
          >
            {navigation}
          </Drawer>
          <main
            id="main-content"
            className={`main-content ${page === "assistant" ? "assistant-page" : ""}`}
          >
            <a className="skip-link" href="#page-content">
              跳至内容
            </a>
            {loading ? (
              <Loading />
            ) : (
              <>
                <Failure
                  error={error || action.error}
                  retry={
                    error
                      ? () => location && window.location.reload()
                      : action.retry
                  }
                />
                {!current || !config || current.case_id !== caseId ? (
                  <div className="welcome panel">
                    <HomeOutlined className="welcome-icon" />
                    <h1>找到适合你的下一个家</h1>
                    <p>从一句话开始，让租房助手陪你理清需求。</p>

                    <Button
                      type="primary"
                      size="large"
                      loading={action.busy}
                      onClick={create}
                      aria-label="新建演示案例"
                    >
                      新建演示案例
                    </Button>
                  </div>
                ) : (
                  <CaseContext.Provider
                    value={{ current, config, refresh, go }}
                  >
                    {page !== "assistant" && (
                      <div className="case-caption">
                        当前案例 <span>{current.case_id}</span>
                        <span>
                          {page === "operator"
                            ? "本地演示操作员视图"
                            : "本地演示身份 · 租客"}
                        </span>
                      </div>
                    )}
                    <div id="page-content" key={`${current.case_id}:${page}`}>
                      <ErrorBoundary>
                        <Suspense fallback={<Loading />}>
                          {pages[page] ?? pages.assistant}
                        </Suspense>
                      </ErrorBoundary>
                    </div>
                  </CaseContext.Provider>
                )}
              </>
            )}
          </main>
        </Layout>
        <EvidenceDrawer
          title="演示与证据"
          open={evidence}
          onClose={() => setEvidence(false)}
        >
          <Alert
            type="info"
            title="真实房源与业务能力"
            description="Agent1 保存偏好，Agent2 使用真实房源库进行事实筛选和候选保存；是否仍在租、费用与租期尚待核实。可记录看房与中介回复，由 Agent3 生成未签署租约草稿，或独立同意上传真实合同后提取与比对。房源和用户记录不视为已核实交接证明；Agent4 需要另行确认租约资料。不会向房东或中介发送消息。"
            showIcon
          />
          <h3>独立的业务参考时间</h3>
          <JsonDetails value={config?.clocks} />
          <h3>当前案例与版本引用</h3>
          <JsonDetails
            value={
              current
                ? {
                    case_id: current.case_id,
                    search_id: current.search_id,
                    agent1: current.agent1,
                    draft_revision: current.draft.revision,
                    confirmations: current.confirmations.map((c) => ({
                      version: c.version,
                      fingerprint: c.fingerprint,
                    })),
                    evaluations: current.evaluations,
                    selection: current.selection,
                    reviews: current.reviews,
                    aftercare_case_id: current.aftercare_case_id,
                  }
                : null
            }
          />
        </EvidenceDrawer>
      </Layout>
    </ErrorBoundary>
  );
}
