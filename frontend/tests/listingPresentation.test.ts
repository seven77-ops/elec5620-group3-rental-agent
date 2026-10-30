import test from "node:test";
import assert from "node:assert/strict";
import {
  propertyFeatures,
  recommendationCopy,
} from "../src/features/real-data/listingPresentation.ts";

test("source feature noise and inherited property names cannot become facilities", () => {
  const source = [
    "Balcony",
    "Balcony / Deck*",
    "Gas",
    "Unverified feature",
    "Apartments & units for rent in Bexley #### Domain",
    "constructor",
    "__proto__",
    "Gas",
  ];
  assert.deepEqual(propertyFeatures(source), [
    "Balcony",
    "Balcony / deck",
    "Gas connection",
  ]);
  assert.equal(source.length, 8);
});

test("historical listing replies omit canned verification footers while keeping the housing facts", () => {
  const text =
    "按这些条件找到 13 条房源，先给你看 5 条。Burwood，至少2卧，房源周租上限900澳元。\n这是房源标价预览，偏好尚未修改；在租状态、账单和计价对象仍需核实。";
  assert.equal(
    recommendationCopy(text),
    "按这些条件找到 13 条房源。Burwood，至少2卧，房源周租上限900澳元。",
  );
  assert.ok(text.includes("待核实") || text.includes("仍需核实"));
});

test("explicit budget and billing questions are preserved instead of deleting every mention of bills", () => {
  const text =
    "每周预算 AUD 900 · 整套 · 不含账单。这个每周预算是整套、每个房间，还是每人承担的金额？";
  assert.equal(recommendationCopy(text), text);
  assert.equal(
    recommendationCopy("周租 AUD 700 在上限900内；个人费用待核实"),
    "周租 AUD 700 在上限900内",
  );
});

test("historical next-step notices do not advertise the retired reply form", () => {
  const old = "已选定 Example Road，可以准备看房、记录中介回复或生成租约草稿。";
  assert.equal(
    recommendationCopy(old),
    "已选定 Example Road，Prepare an inspection or generate a lease draft。",
  );
  assert.equal(
    recommendationCopy(
      "可在房源跟进里记录中介回复；已有合同可直接复核。这份清单尚未发送给中介。",
    ),
    "View the inspection enquiry checklist or go straight to lease drafting and review.这份清单尚未发送给中介。",
  );
  assert.equal(
    recommendationCopy("中介回复：每周900澳元。"),
    "中介回复：每周900澳元。",
  );
});
