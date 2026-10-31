import { useEffect, useState } from "react";
import { Button, Space, Tag } from "antd";
import { useNavigate } from "react-router-dom";
import { useCase } from "../app/context";
import { api } from "../api/client";
import { Failure, Loading, PageTitle } from "../components/Common";

interface Step {
  key: string;
  agent: string;
  title: string;
  status: "done" | "in_progress" | "waiting" | "not_started";
  summary: string;
  refs: string[];
  page: string | null;
}
interface Progress {
  case_id: string;
  steps: Step[];
  note: string;
}
const statusTags: Record<Step["status"], [string, string]> = {
  done: ["cyan", "Completed"],
  in_progress: ["blue", "In progress"],
  waiting: ["gold", "Waiting"],
  not_started: ["default", "Not started"],
};

/** One view of the whole pipeline: which agent produced what and what each handoff carried. */
export default function CaseProgress() {
  const { current } = useCase();
  const navigate = useNavigate();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = () =>
    api<Progress>(`/cases/${encodeURIComponent(current.case_id)}/progress`)
      .then((value) => {
        setProgress(value);
        setError(null);
      })
      .catch(setError);
  useEffect(() => {
    void load();
    // Reload when the case changes elsewhere (selection, reviews, aftercare link).
  }, [
    current.case_id,
    current.selection,
    current.reviews,
    current.aftercare_case_id,
  ]);
  return (
    <>
      <PageTitle
        title="Case progress"
        description="The complete AI rental workflow: four agents handle different stages, human operators resolve disputes, and tenants confirm key decisions."
        extra={<Button onClick={() => void load()}>Refresh</Button>}
      />
      <Failure error={error} retry={() => void load()} />
      {!progress ? (
        !error && <Loading />
      ) : (
        <section className="panel case-progress">
          <ol className="progress-steps">
            {progress.steps.map((step, index) => {
              const [color, label] = statusTags[step.status];
              return (
                <li key={step.key} className={`progress-step ${step.status}`}>
                  <div className="progress-index" aria-hidden="true">
                    {index + 1}
                  </div>
                  <div className="progress-body">
                    <Space wrap>
                      <strong>{step.title}</strong>
                      <Tag>{step.agent}</Tag>
                      <Tag color={color}>{label}</Tag>
                    </Space>
                    <p>{step.summary}</p>
                    {step.refs.length > 0 && (
                      <p className="muted small">
                        Handoff references:{step.refs.join(" · ")}
                      </p>
                    )}
                    {step.page && (
                      <Button
                        size="small"
                        onClick={() =>
                          navigate(
                            step.page === "operator"
                              ? "/operator"
                              : `/cases/${current.case_id}/${step.page}`,
                          )
                        }
                      >
                        Go to
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
          <p className="muted small">{progress.note}</p>
        </section>
      )}
    </>
  );
}
