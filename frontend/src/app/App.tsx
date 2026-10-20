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
  AppstoreOutlined,
  CheckSquareOutlined,
  FileTextOutlined,
  FormOutlined,
  HomeOutlined,
  InfoCircleOutlined,
  MenuOutlined,
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
import Overview from "../features/Overview";
const Preferences = lazy(() => import("../features/Preferences"));
const Recommendations = lazy(() => import("../features/Recommendations"));
const Contract = lazy(() => import("../features/Contract"));
const Aftercare = lazy(() => import("../features/Aftercare"));
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
  { key: "overview", label: "我的进度", icon: <AppstoreOutlined /> },
  { key: "preferences", label: "租房偏好", icon: <FormOutlined /> },
  { key: "recommendations", label: "房源推荐", icon: <HomeOutlined /> },
  { key: "contract", label: "合同复核", icon: <FileTextOutlined /> },
  { key: "aftercare", label: "租后服务", icon: <CheckSquareOutlined /> },
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
  const page = parts[1] === "operator" ? "operator" : (parts[3] ?? "overview");
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
      navigate(`/cases/${c.case_id}/preferences`);
    });
  const navigation = (
    <>
      <Menu
        mode="inline"
        selectedKeys={[page]}
        items={nav}
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
    overview: <Overview />,
    preferences: <Preferences />,
    recommendations: <Recommendations />,
    contract: <Contract />,
    aftercare: <Aftercare />,
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
            <span className="demo-label">合成数据演示</span>
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
          <main id="main-content" className="main-content">
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
                    <h1>从你的租房偏好开始</h1>
                    <p>确认需求、查看推荐依据，再由你决定下一步。</p>
                    <p className="muted">
                      本地课程演示使用合成数据，表单通过 Agent1
                      保存并确认偏好版本。
                    </p>
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
                    <div className="case-caption">
                      当前案例 <span>{current.case_id}</span>
                      <span>
                        {page === "operator"
                          ? "本地演示操作员视图"
                          : "本地演示身份 · 租客"}
                      </span>
                    </div>
                    <div id="page-content" key={`${current.case_id}:${page}`}>
                      <ErrorBoundary>
                        <Suspense fallback={<Loading />}>
                          {pages[page] ?? pages.overview}
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
            title="本地合成场景回放"
            description="Agent1、2、3、4 均调用原 Python 业务实现。Agent1 当前使用表单输入，未启用 LLM 对话提取；房源和合同仍为合成数据，不会向房东或中介发送消息。Agent2 推荐解读和 Agent3 AI 候选分析需单独同意并配置后端模型；调用记录会明确显示真实或测试来源。"
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
