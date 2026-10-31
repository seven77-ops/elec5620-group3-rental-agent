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
import { Button, Drawer, Layout, Menu, Space } from "antd";
import {
  CheckSquareOutlined,
  AuditOutlined,
  NodeIndexOutlined,
  FileTextOutlined,
  FormOutlined,
  HomeOutlined,
  MenuOutlined,
  CommentOutlined,
} from "@ant-design/icons";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { api, post } from "../api/client";
import type { CaseState, DemoConfig } from "../api/types";
import { Failure, Loading } from "../components/Common";
import { useAction } from "../components/useAction";
import { CaseContext } from "./context";
const Assistant = lazy(() => import("../features/assistant/Assistant"));
const Preferences = lazy(() => import("../features/Preferences"));
const LegacyRecommendations = lazy(() => import("../features/Recommendations"));
const Recommendations = lazy(() => import("../features/RealRecommendations"));
import FavoritesProvider from "../features/favorites/FavoritesContext";
const Contract = lazy(() => import("../features/contracts/ContractAssistant"));
const Aftercare = lazy(() => import("../features/Aftercare"));
const LivingHub = lazy(() => import("../features/living/LivingHub"));
const Operator = lazy(() => import("../features/Operator"));
const CaseProgress = lazy(() => import("../features/CaseProgress"));

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
        <h1>This page is temporarily unavailable</h1>
        <p>
          Submitted data is saved in the local service. Refresh to load it
          again.
        </p>
        <Button onClick={() => location.reload()}>Reload case</Button>
      </div>
    ) : (
      this.props.children
    );
  }
}
const nav = [
  {
    key: "assistant",
    label: "AI rental assistant",
    icon: <CommentOutlined aria-hidden="true" />,
  },
  {
    key: "preferences",
    label: "Rental preferences",
    icon: <FormOutlined aria-hidden="true" />,
  },
  {
    key: "recommendations",
    label: "Housing recommendations",
    icon: <HomeOutlined aria-hidden="true" />,
  },
  {
    key: "contract",
    label: "Contract assistant",
    icon: <FileTextOutlined aria-hidden="true" />,
  },
  {
    key: "aftercare",
    label: "Aftercare services",
    icon: <CheckSquareOutlined aria-hidden="true" />,
  },
  {
    key: "progress",
    label: "Case progress",
    icon: <NodeIndexOutlined aria-hidden="true" />,
  },
  {
    key: "operator",
    label: "Human review",
    icon: <AuditOutlined aria-hidden="true" />,
  },
];
export default function App() {
  const [config, setConfig] = useState<DemoConfig | null>(null);
  const [current, setCurrent] = useState<CaseState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [mobile, setMobile] = useState(false);
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
    if (page === "preferences" && caseId && config?.mode === "real_listings")
      navigate(`/cases/${caseId}/assistant?needs=1`, { replace: true });
  }, [page, routePage, caseId, config?.mode, navigate]);
  const go = (target: string) => {
    setMobile(false);
    const destination =
      target === "preferences" && config?.mode === "real_listings"
        ? "assistant?needs=1"
        : target;
    navigate(
      destination === "operator"
        ? "/operator"
        : current
          ? `/cases/${current.case_id}/${destination}`
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
                    ? { ...item, label: "Contract assistant" }
                    : item,
                )
            : nav
        }
        onClick={({ key }) => go(key)}
      />
      <div
        className={`sidebar-bottom${config?.mode === "real_listings" ? " sidebar-bottom-mobile-only" : ""}`}
      >
        {current && (
          <Button
            className="mobile-new-case"
            onClick={create}
            loading={action.busy}
          >
            New demo case
          </Button>
        )}
        {config?.mode !== "real_listings" && (
          <Link to="/operator" onClick={() => setMobile(false)}>
            Local demo operator
          </Link>
        )}
      </div>
    </>
  );
  const pages: Record<string, ReactNode> = {
    assistant: <Assistant />,
    preferences:
      config?.mode === "real_listings" ? <Assistant /> : <Preferences />,
    recommendations:
      config?.mode === "real_listings" ? (
        <Recommendations />
      ) : (
        <LegacyRecommendations />
      ),
    contract: <Contract />,
    aftercare: config?.mode === "real_listings" ? <LivingHub /> : <Aftercare />,
    operator: <Operator />,
    progress: <CaseProgress />,
  };
  return (
    <ErrorBoundary>
      <Layout className="app-layout">
        <header className="app-header">
          <div className="brand">
            <HomeOutlined />
            <span>Rental Assistant</span>
          </div>
          <Space>
            <Button type="link" size="small" href="/api/v1/rag/product-guide" target="_blank" rel="noreferrer">
              User guide
            </Button>
            {current && (
              <Button
                className="new-case"
                size="small"
                onClick={create}
                loading={action.busy}
                aria-label="New case"
              >
                New case
              </Button>
            )}
            <Button
              className="mobile-menu"
              aria-label="Open navigation"
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
            title="Rental Assistant navigation"
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
              Skip to content
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
                    <h1>Find your next home</h1>
                    <p>
                      Start with a sentence and let Rental Assistant help you
                      clarify your needs.
                    </p>

                    <Button
                      type="primary"
                      size="large"
                      loading={action.busy}
                      onClick={create}
                      aria-label="New demo case"
                    >
                      New demo case
                    </Button>
                  </div>
                ) : (
                  <CaseContext.Provider
                    value={{ current, config, refresh, go }}
                  >
                    <FavoritesProvider key={current.case_id}>
                      <div id="page-content" key={`${current.case_id}:${page}`}>
                        <ErrorBoundary>
                          <Suspense fallback={<Loading />}>
                            {pages[page] ?? pages.assistant}
                          </Suspense>
                        </ErrorBoundary>
                      </div>
                    </FavoritesProvider>
                  </CaseContext.Provider>
                )}
              </>
            )}
          </main>
        </Layout>
      </Layout>
    </ErrorBoundary>
  );
}
