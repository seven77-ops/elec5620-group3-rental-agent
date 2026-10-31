import { useEffect, useState } from "react";
import { Tabs } from "antd";
import { api } from "../../api/client";
import type { Point, RealConfig } from "../../api/realData";
import { Failure, Loading } from "../../components/Common";
import MarketPanel from "./MarketPanel";
import ListingPanel from "./ListingPanel";
import { DomainPanel, TripPanel } from "./ProviderPanels";

export default function RecommendationTools() {
  const [config, setConfig] = useState<RealConfig | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState("market");
  const [origin, setOrigin] = useState<Point | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let valid = true;
    api<RealConfig>("/real-data/config")
      .then((value) => {
        if (valid) {
          setConfig(value);
          setError(null);
        }
      })
      .catch((e) => {
        if (valid) setError(e);
      });
    return () => {
      valid = false;
    };
  }, [revision]);
  const onPoint = (p: Point) => {
    setOrigin(p);
    setTab("trips");
  };
  return (
    <>
      <Failure error={error} retry={() => setRevision((v) => v + 1)} />
      {!config ? (
        !error && <Loading />
      ) : (
        <Tabs
          activeKey={tab}
          onChange={setTab}
          destroyOnHidden
          items={[
            {
              key: "market",
              label: "Rent reference",
              children: <MarketPanel />,
            },
            {
              key: "listings",
              label: "Live listing",
              children: (
                <>
                  <ListingPanel onPoint={onPoint} />
                  <DomainPanel
                    config={config.providers.domain}
                    onPoint={onPoint}
                  />
                </>
              ),
            },
            {
              key: "trips",
              label: "Commute search",
              children: (
                <TripPanel
                  key={
                    origin
                      ? `${origin.latitude}: ${origin.longitude}`
                      : "manual"
                  }
                  config={config.providers.tfnsw}
                  origin={origin}
                />
              ),
            },
          ]}
        />
      )}
    </>
  );
}
