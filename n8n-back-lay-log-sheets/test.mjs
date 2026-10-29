// Runs the workflow's two Code nodes on the API's own response examples in ../fixtures. No key, no network.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url)));
const workflow = read('./back-lay-log-to-google-sheets.json');
const code = (name) => workflow.nodes.find((n) => n.name === name).parameters.jsCode;
const SETTINGS = { commissionPercent: 2, minRating: 80, minLayAvailable: 20, minMovePercent: 0 };

// n8n runs a Code node's body as a function; these stand in for the helpers it uses. An empty sheet reaches the
// node as one empty item, because the sheet node is set to always output data.
const compare = (board, sheet = [], settings = {}) =>
  new Function('$input', '$', code('Compare with the log'))(
    { all: () => (sheet.length ? sheet : [{}]).map((json) => ({ json })) },
    (name) => ({ first: () => ({ json: name === 'Settings' ? { ...SETTINGS, ...settings } : board }) }),
  ).map((item) => item.json);
const explain = (json) => new Function('$input', code('Explain the failure'))({ first: () => ({ json }) })[0].json.message;

const board = (edit = () => {}) => {
  const b = read('../fixtures/v2-odds-type.standard_filtered.json');
  edit(b.data[0].markets[0].outcomes[0]);
  return b;
};

test('an empty sheet gets a new row for each pair at or above the rating', () => {
  const b = board();
  const ev = b.data[0];
  const [row, ...rest] = compare(b);
  assert.equal(rest.length, 0);
  assert.equal(row.pair_key, `${ev.event_id}|h2h|${ev.markets[0].outcomes[0].name}|william_hill`);
  assert.equal(row.kick_off, '2026-09-17 04:00'); // 03:00 UTC is 04:00 in UK summer time
  assert.match(row.checked_at, /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$/);
  assert.deepEqual([row.bookmaker, row.back, row.exchange, row.lay, row.lay_available], ['william_hill', 2.9, 'betfair_exchange', 3.45, 175]);
  assert.equal(row.rating, 84.06); // 2.9 / 3.45 x 100
  assert.equal(row.rating_after_commission, 82.86); // 2.9 x 0.98 / 3.43 x 100
  assert.deepEqual([row.change, row.back_before, row.lay_before], ['new', '', '']);
});

test('a pair is logged again only when a price has moved since its last row', () => {
  const [first] = compare(board());
  assert.deepEqual(compare(board(), [first]), []); // nothing moved: no duplicate

  const [moved] = compare(board((o) => (o.back[0].price = 3)), [first]);
  assert.deepEqual([moved.change, moved.back, moved.back_before, moved.lay, moved.lay_before], ['moved', 3, 2.9, 3.45, 3.45]);

  // 2.9 -> 3 is a 3.4% move: held back by a 5% minimum, while the lay's 3.45 -> 3.2 (-7.2%) is not
  assert.deepEqual(compare(board((o) => (o.back[0].price = 3)), [first], { minMovePercent: 5 }), []);
  const [lay] = compare(board((o) => (o.lay[0].price = 3.2)), [first], { minMovePercent: 5 });
  assert.deepEqual([lay.change, lay.lay, lay.lay_before], ['moved', 3.2, 3.45]);
});

test("the last row is the pair's latest checked_at, whatever order the sheet is in", () => {
  const [first] = compare(board());
  const older = { ...first, checked_at: '2026-09-17 01:00:00', back: 2.5 };
  const newer = { ...first, checked_at: '2026-09-17 02:00:00' };
  assert.deepEqual(compare(board(), [newer, older]), []);
  assert.equal(compare(board(), [older])[0].back_before, 2.5);
});

test('a lay with too little money at its price gives way to the next lowest, and pairs under the rating are left out', () => {
  const thin = (o) => o.lay.unshift({ ...o.lay[0], exchange: 'smarkets', price: 3.3, available: 5 });
  const [row] = compare(board(thin));
  assert.deepEqual([row.exchange, row.lay], ['betfair_exchange', 3.45]);
  assert.equal(compare(board(thin), [], { minLayAvailable: 0 })[0].exchange, 'smarkets');
  assert.deepEqual(compare(board(), [], { minLayAvailable: 200 }), []);
  assert.deepEqual(compare(board(), [], { minRating: 90 }), []);
});

test('an each-way board, whose lays are win and place, gives no rows', () => {
  assert.deepEqual(compare(read('../fixtures/v2-odds-type.each_way.json')), []);
});

test('a failed call becomes one message with its status, code, request id and what to do', () => {
  const body = read('../fixtures/error-401.invalid_api_key.json');
  // the shape n8n's HTTP Request node gives a failed call on its error output
  const message = explain({ error: { status: 401, message: `401 - ${JSON.stringify(JSON.stringify(body))}` } });
  assert.match(message, /\(401, invalid_api_key, API key not recognised\., request id or_req_0+\)/);
  assert.match(message, /Check the API key in the Header Auth credential\.$/);
  assert.match(explain({ error: { status: 502, message: '502 - ""' } }), /\(502\)\. The next scheduled run tries again\.$/);
  assert.match(explain({ error: { message: 'connect ECONNREFUSED' } }), /\(no reply\)\. The next scheduled run tries again\.$/);
});
