import { Image } from "antd";
import type { LivingAttachment } from "../../api/living";

export default function ReviewEvidence({
  files,
}: {
  files: LivingAttachment[];
}) {
  if (!files.length) return null;
  return (
    <div className="review-file-grid" aria-label="Evidence files">
      <Image.PreviewGroup>
        {files.map((file) => (
          <div className="review-file" key={file.attachment_id}>
            {file.mime_type.startsWith("image/") && (
              <Image src={file.download_url} alt={file.filename} width="100%" />
            )}
            {file.mime_type === "application/pdf" && (
              <div className="review-document">PDF document</div>
            )}
            <a href={file.download_url} target="_blank" rel="noreferrer">
              {file.filename}
            </a>
          </div>
        ))}
      </Image.PreviewGroup>
    </div>
  );
}
