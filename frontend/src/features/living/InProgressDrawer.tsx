import { Button, Drawer, Empty, Tag } from "antd";
import type { ProgressItem } from "./inProgress";
export default function InProgressDrawer({
  open,
  onClose,
  items,
  onOpen,
}: {
  open: boolean;
  onClose: () => void;
  items: ProgressItem[];
  onOpen: (item: ProgressItem) => void;
}) {
  return (
    <Drawer title="In progress" open={open} onClose={onClose} width={480}>
      {items.length ? (
        items.map((item) => (
          <div className="home-progress-item" key={item.id}>
            <div>
              <strong>{item.title}</strong>
              <p>
                <Tag>{item.status}</Tag>
              </p>
            </div>
            <Button
              onClick={() => onOpen(item)}
              aria-label={`Open ${item.title}`}
            >
              Open
            </Button>
          </div>
        ))
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="No items in progress"
        />
      )}
    </Drawer>
  );
}
