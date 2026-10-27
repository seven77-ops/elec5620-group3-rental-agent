import type { AssistantMessage } from "../../api/assistant";
import "./commuteResults.css";

export default function TransitInfo({ message }: { message: AssistantMessage }) {
  const info = message.transit_information;
  if (!info) return null;
  return <section className="commute-results transit-information" aria-label="房源交通信息">
    <h3>{info.topic === "nearby" ? "附近车站" : "当前线路提醒"}</h3>
    <p className="small muted">{info.address}</p>
    {info.topic === "nearby" ? <ul className="transit-stop-list">
      {info.stops.map((stop) => <li key={stop.id}><span>{stop.name}</span><small>直线约 {stop.distance_m} 米</small></li>)}
    </ul> : <>
      {info.stop_name && <p className="small">站点：{info.stop_name}</p>}
      {info.alerts.length ? <ul>{info.alerts.map((alert, i) => <li key={i}>{alert.title} {alert.url && <a href={alert.url} target="_blank" rel="noopener noreferrer">查看详情 ↗</a>}</li>)}</ul>
        : <p className="small muted">暂未检索到该站当前公开提醒，出发前请再核对班次。</p>}
    </>}
    <a className="small" href={info.source_url} target="_blank" rel="noopener noreferrer">Transport for NSW ↗</a>
  </section>;
}
