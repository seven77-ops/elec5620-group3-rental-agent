import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { api, ApiError } from "../src/api/client.ts";

const timers = new Set<ReturnType<typeof setTimeout>>();
beforeEach(() => {
  Object.assign(globalThis, {
    window: {
      setTimeout(callback: () => void, delay: number) {
        const timer = setTimeout(callback, delay);
        timers.add(timer);
        return timer;
      },
      clearTimeout(timer: ReturnType<typeof setTimeout>) {
        timers.delete(timer);
        clearTimeout(timer);
      },
    },
  });
});
afterEach(() => {
  const remaining = timers.size;
  for (const timer of timers) clearTimeout(timer);
  timers.clear();
  assert.equal(remaining, 0, "every completion must clean up its deadline");
});

for (const allowNull of [false, true]) {
  test(`deadline aborts a stalled response body (allowNull=${allowNull})`, async (t) => {
    let signal: AbortSignal | undefined;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    t.mock.method(globalThis, "fetch", async (_url, init) => {
      signal = init.signal;
      return new Response(
        new ReadableStream({
          start(stream) {
            signal!.addEventListener(
              "abort",
              () => stream.error(new DOMException("Aborted", "AbortError")),
              { once: true },
            );
            // Bound the RED run if the implementation prematurely clears its timer.
            watchdog = setTimeout(
              () => stream.error(new Error("body watchdog")),
              200,
            );
          },
        }),
      );
    });
    try {
      await assert.rejects(
        api("/stalled", undefined, { timeoutMs: 20, allowNull }),
        (error: unknown) =>
          error instanceof ApiError && error.code === "timeout",
      );
      assert.equal(signal?.aborted, true);
    } finally {
      clearTimeout(watchdog);
    }
  });

  test(`malformed JSON is invalid even when allowNull=${allowNull}`, async (t) => {
    t.mock.method(globalThis, "fetch", async () => new Response("{broken"));
    await assert.rejects(
      api("/malformed", undefined, { allowNull }),
      (error: unknown) =>
        error instanceof ApiError && error.code === "invalid_response",
    );
  });
}

test("a valid JSON null requires the explicit allowNull option", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("null"));
  await assert.rejects(
    api("/latest"),
    (error: unknown) =>
      error instanceof ApiError && error.code === "invalid_response",
  );
  assert.equal(await api("/latest", undefined, { allowNull: true }), null);
});

test("deadline also aborts before response headers arrive", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    (_url, init) =>
      new Promise((_resolve, reject) => {
        init.signal.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true },
        );
      }),
  );
  await assert.rejects(
    api("/slow", undefined, { timeoutMs: 20 }),
    (error: unknown) => error instanceof ApiError && error.code === "timeout",
  );
});

test("preserves HTTP semantic errors including request ID and fields", async (t) => {
  t.mock.method(globalThis, "fetch", async () =>
    Response.json(
      {
        error: {
          message: "Review changed",
          code: "version_conflict",
          request_id: "request-1",
          fields: { expected_version: 2 },
        },
      },
      { status: 409 },
    ),
  );
  await assert.rejects(api("/review"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.message, "Review changed");
    assert.equal(error.code, "version_conflict");
    assert.equal(error.requestId, "request-1");
    assert.deepEqual(error.fields, { expected_version: 2 });
    return true;
  });
});

test("malformed HTTP error bodies retain the status fallback", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("unavailable", { status: 503 }),
  );
  await assert.rejects(
    api("/unavailable"),
    (error: unknown) => error instanceof ApiError && error.code === "http_503",
  );
});

test("successful body and network failures both clean up the timer", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () =>
    Response.json({ version: 1 }),
  );
  assert.deepEqual(await api("/review"), { version: 1 });
  assert.equal(timers.size, 0);
  fetchMock.mock.mockImplementation(async () => {
    throw new TypeError("offline");
  });
  await assert.rejects(
    api("/offline"),
    (error: unknown) =>
      error instanceof ApiError && error.code === "network_error",
  );
});
