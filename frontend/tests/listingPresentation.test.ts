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
    "阳台",
    "阳台 / 露台",
    "燃气设施",
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
