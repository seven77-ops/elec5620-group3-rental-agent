import React from "react";
import ReactDOM from "react-dom/client";
import { App as AntApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { BrowserRouter } from "react-router-dom";
import App from "./app/App";
import "./styles/app.css";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#174EA6",
          colorSuccess: "#087F8C",
          colorText: "#172B4D",
          colorTextSecondary: "#65758B",
          colorBgLayout: "#F5F7FA",
          colorBorder: "#DCE4EE",
          borderRadius: 8,
          fontSize: 14,
          fontFamily:
            '-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif',
          controlHeight: 40,
        },
        components: {
          Layout: { headerBg: "#FFFFFF", siderBg: "#FFFFFF" },
          Button: { primaryShadow: "none" },
          Menu: {
            itemHeight: 48,
            itemSelectedBg: "#EAF1FC",
            itemSelectedColor: "#174EA6",
          },
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
);
