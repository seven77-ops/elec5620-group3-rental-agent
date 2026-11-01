import test from "node:test";
import assert from "node:assert/strict";
import {
  prepareEnquiry,
  listingContactUrl,
  enquiryMailto,
} from "../src/features/candidate/enquiryTemplate.ts";

test("enquiry uses selected address and only supplied optional details", () => {
  const plain = prepareEnquiry("1 Example Street, Sydney", {});
  assert.equal(plain.subject, "Inspection enquiry: 1 Example Street, Sydney");
  assert.match(plain.body, /^Hi,/);
  assert.match(plain.body, /1 Example Street, Sydney/);
  assert.doesNotMatch(plain.body, /available on|confirmed|booked|undefined/);
  const detailed = prepareEnquiry("1 Example Street", {
    agentName: " Alex Example ",
    preferredTime: " Saturday afternoon ",
    questions: "Is there bike storage?",
  });
  assert.match(detailed.body, /^Hi Alex Example,/);
  assert.match(detailed.body, /I’m available Saturday afternoon\./);
  assert.match(detailed.body, /Is there bike storage\?/);
});

test("only valid public-protocol listing URLs are linked", () => {
  assert.equal(
    listingContactUrl("https://example.com/listing?a=1"),
    "https://example.com/listing?a=1",
  );
  for (const value of [
    undefined,
    null,
    "",
    "undefined",
    "/relative",
    "javascript:alert(1)",
    "data:text/html,hi",
    "mailto:a@example.com",
    "https://user:password@example.com",
  ]) {
    assert.equal(listingContactUrl(value), null);
  }
});

test("email-client links require a single valid email and encode the edited draft", () => {
  for (const value of [
    "",
    "unknown",
    "a@example.com,b@example.com",
    "a@example.com\r\nBcc:b@example.com",
    "a@example.com?bcc=b@example.com",
  ]) {
    assert.equal(enquiryMailto(value, "Subject", "Body"), null);
  }
  assert.equal(
    enquiryMailto(
      " alex+test@example.com ",
      "Hello & request",
      "Line 1\nLine 2?",
    ),
    "mailto:alex+test@example.com?subject=Hello%20%26%20request&body=Line%201%0ALine%202%3F",
  );
  assert.equal(
    enquiryMailto("alex@example.com", "Hello\r\nBcc: x", "Body"),
    "mailto:alex@example.com?subject=Hello%20Bcc%3A%20x&body=Body",
  );
});

test("email recipient punctuation is encoded as part of the address", () => {
  assert.equal(
    enquiryMailto("alex#tag@example.com", "Hello", "Body"),
    "mailto:alex%23tag@example.com?subject=Hello&body=Body",
  );
});
