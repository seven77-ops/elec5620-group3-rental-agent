import { Alert, Collapse, Tag } from "antd";
import type { KnowledgeAnswer } from "../../api/knowledge";
import "./knowledge.css";
const sourceLabels = {
  official_guidance: "NSW Government",
  official_template: "NSW Government · Official template",
  student_guidance: "University of Sydney",
  product_guide: "Rental assistant guide",
  user_contract: "Uploaded contract",
};
export default function KnowledgeEvidence({
  answer,
  showAnswer = false,
}: {
  answer: KnowledgeAnswer;
  showAnswer?: boolean;
}) {
  return (
    <section className="knowledge-evidence" aria-label="Knowledge evidence">
      <div className="knowledge-evidence-heading">
        {(answer.scope === "product" || answer.scope === "contract") && (
          <strong>
            {answer.scope === "product"
              ? "Product usage guide"
              : "Contract and reference sources"}
          </strong>
        )}
        <Tag color={answer.status === "answered" ? "blue" : "default"}>
          {answer.status === "answered"
            ? "Cited answer"
            : answer.status === "sources_only"
              ? "Sources only"
              : "More information needed"}
        </Tag>
      </div>
      {showAnswer && <p className="knowledge-answer">{answer.answer}</p>}
      {!!answer.citations.length && (
        <Collapse
          items={[
            {
              key: "sources",
              label: "Read source excerpts",
              children: answer.citations.map((source, index) => (
                <article
                  className="knowledge-source"
                  key={`${source.evidence_id}-${index}`}
                >
                  <a href={source.source_url} target="_blank" rel="noreferrer">
                    [{index + 1}] {source.title} ·{" "}
                    {source.source_type ? sourceLabels[source.source_type] : "Reference source"}{" "}
                    ↗
                  </a>
                  <p className="muted small">
                    {source.source_type === "user_contract"
                      ? `Page ${source.page} · ${source.section} · Review v${source.review_version}`
                      : `${source.page ? `Page ${source.page} · ` : ""}${source.section} · Checked ${source.checked_at}`}
                  </p>
                  <blockquote>{source.quote}</blockquote>
                </article>
              )),
            },
          ]}
        />
      )}
      {!!answer.unknowns.length && (
        <Alert
          type="info"
          title="Still to clarify"
          description={answer.unknowns.join(" ")}
          showIcon
        />
      )}
      {!!answer.warnings.length && (
        <details className="knowledge-limitations">
          <summary>Answer limitations</summary>
          <ul>
            {answer.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
