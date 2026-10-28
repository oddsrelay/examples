// Runs the workflow's Code node on the API's own response examples in ../fixtures. No key, no network.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url)));
const workflow = read('./oddsmatcher-to-google-sheets.json');
const code = workflow.nodes.find((n) => n.type === 'n8n-nodes-base.code').parameters.jsCode;

// n8n runs a Code node's body as a function; these stand in for the two helpers it uses
const rows = (body, settings) =>
  new Function('$input', '$', code)({ first: () => ({ json: body }) }, () => ({ first: () => ({ json: settings }) }))
    .map((item) => item.json);

test('a back price beside the lay, rated with and without commission', () => {
  const board = read('../fixtures/v2-odds-type.standard_filtered.json');
  const ev = board.data[0];
  const outcome = ev.markets[0].outcomes[0].name;
  const out = rows(board, { commissionPercent: 2 });
  assert.equal(out.length, 1);
  const [row] = out;
  assert.equal(row.row_key, `${ev.event_id}|h2h|${outcome}|william_hill`);
  assert.equal(row.event, `${ev.home_team} v ${ev.away_team}`);
  assert.equal(row.kick_off, '2026-09-17 04:00'); // 03:00 UTC is 04:00 in UK summer time
  assert.deepEqual([row.bookmaker, row.back, row.exchange, row.lay, row.lay_available], ['william_hill', 2.9, 'betfair_exchange', 3.45, 175]);
  assert.equal(row.rating, 84.06); // 2.9 / 3.45 x 100
  assert.equal(row.rating_after_commission, 82.86); // 2.9 x 0.98 / 3.43 x 100
});

test('each bookmaker gets a row against the lowest lay, and a race is named by its course', () => {
  const out = rows({ data: read('../fixtures/v2-odds-type.bog_bare.json') }, { commissionPercent: 0 });
  assert.deepEqual(out.map((r) => [r.event, r.bookmaker, r.exchange, r.lay, r.rating, r.rating_after_commission]), [
    ['Ayr', 'ladbrokes', 'betfair_exchange', 4.3, 93.02, 93.02],
    ['Ayr', 'betfred', 'betfair_exchange', 4.3, 93.02, 93.02],
  ]);
  assert.equal(new Set(out.map((r) => r.row_key)).size, 2);
});

test('an each-way board, whose lays are win and place, gives no rows', () => {
  assert.deepEqual(rows(read('../fixtures/v2-odds-type.each_way.json'), { commissionPercent: 2 }), []);
});
