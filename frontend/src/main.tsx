import React from "react";
import ReactDOM from "react-dom/client";
import { App as AntApp, ConfigProvider } from "antd";
import enGB from "antd/locale/en_GB";
import dayjs from "dayjs";
import "dayjs/locale/en-au";
import { BrowserRouter } from "react-router-dom";
import App from "./app/App";
import "./styles/app.css";
dayjs.locale("en-au");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={enGB}
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
          fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
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
