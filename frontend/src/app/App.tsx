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
  AuditOutlined,
  CheckSquareOutlined,
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
    key: "progress",
    label: "案例进度",
    icon: <NodeIndexOutlined aria-hidden="true" />,
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
  {
    // The founder/operator's SR02 review queue; still requires the local operator key.
    key: "operator",
    label: "人工审核（运营者）",
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
                    ? { ...item, label: "合同助手" }
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
            新建演示案例
          </Button>
        )}
        {config?.mode !== "real_listings" && (
          <Link to="/operator" onClick={() => setMobile(false)}>
            本地演示操作员
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
            <span>租房助手</span>
          </div>
          <Space>
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
