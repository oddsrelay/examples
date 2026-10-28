// Runs the workflow's Code node on the API's own raw-board example in ../fixtures. No key, no network.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url)));
const workflow = read('./price-moves-to-telegram.json');
const code = workflow.nodes.find((n) => n.type === 'n8n-nodes-base.code').parameters.jsCode;

// n8n runs a Code node's body as a function; these stand in for the three helpers it uses
const check = (page, store) =>
  new Function('$input', '$', '$getWorkflowStaticData', code)(
    { first: () => ({ json: page }) },
    () => ({ first: () => ({ json: { moveThresholdPercent: 10 } }) }),
    () => store,
  ).map((item) => item.json.text);

// The example's event has started by now: move it an hour ahead so the workflow keeps its prices
const page = (kickOff = Date.now() + 3600_000) => {
  const p = read('../fixtures/v2-odds-raw.page.json');
  for (const ev of p.data) ev.commence_time = new Date(kickOff).toISOString();
  return p;
};
const setPrice = (p, venue, market, outcome, price) => {
  const books = p.data[0].bookmakers.find((b) => b.key === venue);
  books.markets.find((m) => m.key === market).outcomes.find((o) => o.name === outcome).price = price;
  return p;
};

test('the first check stores the prices and says what it watches', () => {
  const store = {};
  const [text, ...rest] = check(page(), store);
  assert.equal(rest.length, 0);
  assert.match(text, /^Watching 8 prices on 1 event\. /);
  assert.match(text, /Your filters match 1312 events: each check reads the first 1 by kick-off\.$/);
  assert.equal(Object.keys(store.prices).length, 8);
});

test('later checks send the moves at or past the threshold, biggest first, and nothing when none', () => {
  const store = {};
  check(page(), store);
  assert.deepEqual(check(page(), store), []);

  const moved = setPrice(setPrice(page(), 'bet600', 'h2h', 'Natsuki Yoshimoto', 2.0), 'betgoodwin', 'h2h', 'Tiana Tian Deng', 2.1);
  setPrice(moved, 'bet600', 'correct_score', '1 - 2', 6.0);
  const [text, ...rest] = check(moved, store);
  assert.equal(rest.length, 0);
  const lines = text.split('\n');
  assert.equal(lines[0], 'Price moves of 10% or more:');
  assert.match(lines[3], /^Bet600 correct_score, 1 - 2: 4\.75 → 6 \(\+26\.3%\)$/);
  assert.match(lines[6], /^Bet600 h2h, Natsuki Yoshimoto: 1\.7 → 2 \(\+17\.6%\)$/);
  assert.doesNotMatch(text, /BetGoodwin/); // its 5% move stays under the threshold
  assert.deepEqual(check(moved, store), []); // a move is sent once
});

test('prices are forgotten once their event starts', () => {
  const store = {};
  check(page(Date.now() - 60_000), store);
  assert.deepEqual(store.prices, {});
});
