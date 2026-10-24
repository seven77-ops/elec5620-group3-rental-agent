import test from "node:test";
import assert from "node:assert/strict";
import {
  missingTenancyDetails,
  tenancySource,
  evidenceKind,
} from "../src/features/aftercare/presentation.ts";
test("unknown values remain pending and false values are complete", () => {
  assert.deepEqual(
    missingTenancyDetails({
      rooms: null,
      carpeted: null,
      outdoor: null,
      furnished: null,
    }),
    ["房间信息", "是否有地毯", "是否有室外区域", "是否带家具"],
  );
  assert.deepEqual(
    missingTenancyDetails({
      rooms: [{ id: "room-1", name: "卧室" }],
      carpeted: false,
      outdoor: false,
      furnished: false,
    }),
    [],
  );
});
test("an empty furnished inventory is not labelled complete even if checked", () => {
  assert.deepEqual(
    missingTenancyDetails({
      rooms: [{}],
      carpeted: true,
      outdoor: false,
      furnished: true,
      inventory: null,
      inventory_confirmed: true,
    }),
    ["家具清单"],
  );
  assert.deepEqual(
    missingTenancyDetails({
      rooms: [{}],
      carpeted: true,
      outdoor: false,
      furnished: true,
      inventory: [{ name: "床" }],
      inventory_confirmed: false,
    }),
    ["家具清单核对"],
  );
});
test("sources and evidence have user-facing names without exposing internal references", () => {
  assert.equal(tenancySource("user-entered:tenant-confirmation"), "用户填写");
  assert.equal(
    tenancySource("review:review-123@1#fields.address"),
    "合同复核预填",
  );
  assert.equal(evidenceKind("deposit_record"), "押金凭证");
  assert.equal(evidenceKind("other"), "其他资料");
  assert.equal(evidenceKind("constructor"), "其他资料");
});
