// Runs the workflow's two Code nodes on the API's own response examples in ../fixtures. No key, no network.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url)));
const workflow = read('./oddsmatcher-to-google-sheets.json');
const code = (name) => workflow.nodes.find((n) => n.name === name).parameters.jsCode;
const SETTINGS = { commissionPercent: 2, minRating: 80, minLayAvailable: 0 };

// n8n runs a Code node's body as a function; these stand in for the helpers it uses. An empty sheet reaches the
// node as one empty item, because the sheet node is set to always output data.
const match = (board, sheet = [], settings = {}) =>
  new Function('$input', '$', code('Match against the sheet'))(
    { all: () => (sheet.length ? sheet : [{}]).map((json) => ({ json })) },
    (name) => ({ first: () => ({ json: name === 'Settings' ? { ...SETTINGS, ...settings } : board }) }),
  ).map((item) => item.json);
const explain = (json) => new Function('$input', code('Explain the failure'))({ first: () => ({ json }) })[0].json.message;

test('a back price beside the lay, rated with and without commission', () => {
  const board = read('../fixtures/v2-odds-type.standard_filtered.json');
  const ev = board.data[0];
  const outcome = ev.markets[0].outcomes[0].name;
  const out = match(board);
  assert.equal(out.length, 1);
  const [row] = out;
  assert.equal(row.row_key, `${ev.event_id}|h2h|${outcome}|william_hill`);
  assert.equal(row.event, `${ev.home_team} v ${ev.away_team}`);
  assert.equal(row.kick_off, '2026-09-17 04:00'); // 03:00 UTC is 04:00 in UK summer time
  assert.deepEqual([row.bookmaker, row.back, row.exchange, row.lay, row.lay_available], ['william_hill', 2.9, 'betfair_exchange', 3.45, 175]);
  assert.equal(row.rating, 84.06); // 2.9 / 3.45 x 100
  assert.equal(row.rating_after_commission, 82.86); // 2.9 x 0.98 / 3.43 x 100
  assert.deepEqual(match(board, [], { minRating: 90 }), []);
});

test('each bookmaker gets a row against the lowest lay with enough money at its price, and a race is named by its course', () => {
  const board = { data: read('../fixtures/v2-odds-type.bog_bare.json') };
  const rows = (settings) => match(board, [], { commissionPercent: 0, ...settings }).map((r) => [r.event, r.bookmaker, r.exchange, r.lay, r.rating]);
  assert.deepEqual(rows({}), [
    ['Ayr', 'ladbrokes', 'betfair_exchange', 4.3, 93.02],
    ['Ayr', 'betfred', 'betfair_exchange', 4.3, 93.02],
  ]);
  // the lowest lay has 17.26 at its price: with 20 needed, the next one up is used
  assert.deepEqual(rows({ minLayAvailable: 20 }), [
    ['Ayr', 'ladbrokes', 'smarkets', 4.4, 90.91],
    ['Ayr', 'betfred', 'smarkets', 4.4, 90.91],
  ]);
});

test('rows that left the board are removed from the bottom up, neighbouring rows in one run', () => {
  const board = read('../fixtures/v2-odds-type.standard_filtered.json');
  const [kept] = match(board);
  const sheet = [
    { row_number: 2, row_key: 'gone|1' },
    { row_number: 3, row_key: kept.row_key },
    { row_number: 4, row_key: 'gone|2' },
    { row_number: 5, row_key: 'gone|3' },
    { row_number: 6, row_key: '' }, // a row the workflow did not write: left alone
    { row_number: 7, row_key: 'gone|4' },
  ];
  assert.deepEqual(match(board, sheet), [
    { remove_from_row: 7, rows_to_remove: 1 },
    { remove_from_row: 4, rows_to_remove: 2 },
    { remove_from_row: 2, rows_to_remove: 1 },
    kept,
  ]);
  // nothing left on the board: every row it wrote goes, and nothing is added
  assert.deepEqual(match({ data: [] }, sheet.slice(1, 4)), [{ remove_from_row: 3, rows_to_remove: 3 }]);
});

test('an each-way board, whose lays are win and place, gives no rows', () => {
  assert.deepEqual(match(read('../fixtures/v2-odds-type.each_way.json')), []);
});

test('a failed call becomes one message with its status, code, request id and what to do', () => {
  const body = read('../fixtures/error-401.invalid_api_key.json');
  // the shape n8n's HTTP Request node gives a failed call on its error output
  const message = explain({ error: { status: 401, message: `401 - ${JSON.stringify(JSON.stringify(body))}` } });
  assert.match(message, /\(401, invalid_api_key, API key not recognised\., request id or_req_0+\)/);
  assert.match(message, /Check the API key in the Header Auth credential\.$/);
  assert.match(explain({ error: { status: 502, message: '502 - ""' } }), /\(502\)\. The next scheduled run tries again\.$/);
});
