import { Alert, Button, Collapse } from "antd";
import { ApiError } from "../../api/client";
import { Failure, JsonDetails } from "../../components/Common";
import { clarificationMessages } from "./presentation";

export default function AftercareFailure({
  error,
  retry,
  onResolve,
  resolveLabel,
}: {
  error: unknown;
  retry?: () => void;
  onResolve?: () => void;
  resolveLabel?: string;
}) {
  if (!(error instanceof ApiError) || error.code !== "needs_clarification")
    return <Failure error={error} retry={retry} />;
  return (
    <section className="aftercare-guidance" aria-label="操作提示">
      <Alert
        type="warning"
        showIcon
        title="资料还需补充"
        description={
          <>
            <ul>
              {clarificationMessages(error.message).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {onResolve && (
              <Button type="primary" onClick={onResolve}>
                {resolveLabel || "补充资料"}
              </Button>
            )}
          </>
        }
      />
      <Collapse
        ghost
        size="small"
        items={[
          {
            key: "details",
            label: "查看错误详情",
            children: (
              <JsonDetails
                value={{
                  code: error.code,
                  message: error.message,
                  request_id: error.requestId,
                }}
              />
            ),
          },
        ]}
      />
    </section>
  );
}
