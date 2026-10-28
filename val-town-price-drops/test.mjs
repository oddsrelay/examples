// Runs the val on the API's own raw-board example in ../fixtures, with Val Town's blob storage and email,
// Deno.env and fetch stood in for. No key, no network. Node 22.18 or later runs the TypeScript as it is.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { registerHooks } from 'node:module';
import test from 'node:test';

// Val Town's std/blob and std/email, served by the stand-ins in globalThis.valTown
const stand = {
  'https://esm.town/v/std/blob/main.ts': 'export const blob = globalThis.valTown.blob;',
  'https://esm.town/v/std/email': 'export const email = (message) => globalThis.valTown.email(message);',
};
registerHooks({
  resolve: (specifier, context, next) => specifier in stand
    ? { url: 'data:text/javascript,' + encodeURIComponent(stand[specifier]), shortCircuit: true }
    : next(specifier, context),
});

const store = new Map(); // blob storage
const sent = []; // emails
const calls = []; // every fetch: { url, init }
const env = { ODDSRELAY_KEY: 'test-key' };
let board; // what the API serves
let cost; // what a quote says
globalThis.valTown = {
  blob: { getJSON: async (k) => store.get(k), setJSON: async (k, v) => void store.set(k, structuredClone(v)) },
  email: async (message) => void sent.push(message),
};
globalThis.Deno = { env: { get: (name) => env[name] } };
globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url);
  calls.push({ url: u, init });
  if (u.origin !== 'https://api.oddsrelay.io') return new Response(null, { status: 204 }); // a webhook
  return Response.json(u.searchParams.get('quote') === 'true' ? { cost, remaining: 'unlimited', rate_card: 'x' } : board);
};
const { default: val } = await import('./alert.ts');

const run = async (page, price = 1) => {
  [board, cost, calls.length, sent.length] = [page, price, 0, 0];
  await val();
};
// The example's event has started by now: move it an hour ahead so the val keeps its prices
const page = (kickOff = Date.now() + 3600_000) => {
  const p = JSON.parse(readFileSync(new URL('../fixtures/v2-odds-raw.page.json', import.meta.url)));
  for (const ev of p.data) ev.commence_time = new Date(kickOff).toISOString();
  return p;
};
const outcome = (p, venue, market, i) =>
  p.data[0].bookmakers.find((b) => b.key === venue).markets.find((m) => m.key === market).outcomes[i];

test('the first run prices the read, makes it, stores the prices and says what it watches', async () => {
  store.clear();
  await run(page());
  const [quote, read] = calls.map((c) => c.url);
  assert.equal(calls.length, 2);
  assert.equal(quote.searchParams.get('quote'), 'true');
  quote.searchParams.delete('quote');
  assert.equal(quote.href, read.href); // the price checked is the read made
  assert.equal(read.pathname, '/v2/odds/raw');
  assert.equal(read.searchParams.get('region'), 'uk');
  for (const c of calls) assert.equal(c.init.headers.Authorization, 'Bearer test-key');
  assert.equal(sent.length, 1);
  assert.equal(sent[0].subject, 'Price-drop alert is on');
  assert.match(sent[0].text, /^Watching 8 prices on 1 event\. You will get a message when a price drops by 10% /);
  assert.ok(sent[0].text.endsWith(`Your filters match ${page().meta.total} events: each run reads the first 1, soonest first.`));
  assert.equal(Object.keys(store.get('prices')).length, 8);
});

test('later runs send the drops at or past the threshold, biggest first, and each drop once', async () => {
  store.clear();
  await run(page());
  await run(page());
  assert.equal(sent.length, 0);

  const moved = page();
  outcome(moved, 'bet600', 'h2h', 0).price = 1.5; // 1.7 -> 1.5, -11.8%
  outcome(moved, 'betgoodwin', 'h2h', 1).price = 1.9; // 2.0 -> 1.9, -5%: under the threshold
  outcome(moved, 'bet600', 'correct_score', 1).price = 3.5; // 4.75 -> 3.5, -26.3%
  outcome(moved, 'betgoodwin', 'correct_score', 0).price = 4; // 3.0 -> 4.0: a rise, not a drop
  await run(moved);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].subject, '2 price drops of 10% or more');
  const lines = sent[0].text.split('\n');
  assert.equal(lines[0], 'Prices down 10% or more since the last run:');
  assert.equal(lines[3], `Bet600, correct_score, ${outcome(moved, 'bet600', 'correct_score', 1).name}: 4.75 → 3.5 (-26.3%)`);
  assert.equal(lines[6], `Bet600, h2h, ${outcome(moved, 'bet600', 'h2h', 0).name}: 1.7 → 1.5 (-11.8%)`);
  assert.equal(lines.length, 7);

  await run(moved);
  assert.equal(sent.length, 0);
});

test('a read priced over the cap is not made, and the run fails with the price', async () => {
  store.clear();
  await assert.rejects(run(page(), 101), /costs 101 tokens, more than MAX_TOKENS_PER_RUN \(100\), so nothing was read/);
  assert.equal(calls.length, 1);
  assert.equal(store.size, 0);
});

test('with ALERT_WEBHOOK_URL set, the message is posted there and not emailed', async () => {
  store.clear();
  env.ALERT_WEBHOOK_URL = 'https://example.com/hook';
  try {
    await run(page());
  } finally {
    delete env.ALERT_WEBHOOK_URL;
  }
  assert.equal(sent.length, 0);
  assert.equal(calls.length, 3);
  assert.equal(calls[2].url.href, 'https://example.com/hook');
  const body = JSON.parse(calls[2].init.body);
  assert.equal(body.content, body.text);
  assert.match(body.text, /^Watching 8 prices on 1 event\./);
  assert.deepEqual(body.allowed_mentions, { parse: [] });
});

test('prices are forgotten once their event starts', async () => {
  store.clear();
  await run(page(Date.now() - 60_000));
  assert.deepEqual(store.get('prices'), {});
});
