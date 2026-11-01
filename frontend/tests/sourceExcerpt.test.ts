import test from "node:test";
import assert from "node:assert/strict";
import { sourceExcerptBlocks } from "../src/features/knowledge/sourceExcerpt.ts";

const words = (text: string) => text.replace(/\s+/g, " ").trim();

test("PDF sentence wraps stay within a reflowable block without changing source wording", () => {
  const quote = "You may incur costs from your own bank, but your landlord or agent cannot charge or pass on any additional costs \nincurred by them if you pay your rent by one of the above options. You also cannot be required to use a specific \nservice provider (such as an app) to make your payments.";
  const blocks = sourceExcerptBlocks(quote);
  assert.equal(blocks.length, 1);
  assert.equal(words(blocks.join("\n")), words(quote));
  assert.match(blocks[0], /specific \nservice provider/);
});

test("paragraphs, question headings, list items and wrapped list continuations remain distinct", () => {
  const quote = "First paragraph.\n\nCan rent change?\nCheck the agreement:\n• First item with a wrapped\ncontinuation\n• Second item\n\nFinal paragraph.";
  assert.deepEqual(sourceExcerptBlocks(quote), [
    "First paragraph.", "Can rent change?", "Check the agreement:",
    "• First item with a wrapped\ncontinuation", "• Second item", "Final paragraph.",
  ]);
  assert.equal(words(sourceExcerptBlocks(quote).join("\n")), words(quote));
});

test("CRLF, numbered lists and markdown headings preserve text and boundaries", () => {
  const quote = "## Details\r\n1. First entry\r\ncontinued\r\n2. Second entry\r\n\r\n<script>alert(1)</script>";
  assert.deepEqual(sourceExcerptBlocks(quote), [
    "## Details", "1. First entry\ncontinued", "2. Second entry", "<script>alert(1)</script>",
  ]);
  assert.deepEqual(sourceExcerptBlocks("\n \n"), []);
});
