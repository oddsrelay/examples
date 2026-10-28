// UK price-drop alert: a Val Town cron val. Each run reads UK and Irish bookmaker prices from the OddsRelay API
// and sends you every price that has dropped by DROP_PERCENT or more since the last run, by email or to a
// webhook. Set up in the README: the key goes in this val's environment variables, never in this file.
import { blob } from "https://esm.town/v/std/blob/main.ts";
import { email } from "https://esm.town/v/std/email";

// Your settings. The keys are the ones the API's /v2/sports and /v2/bookmakers list.
const SPORTS = "soccer_english_premier_league"; // sport or competition keys, comma-separated
const MARKETS = "h2h"; // market keys, comma-separated: h2h is the match result
const BOOKMAKERS = "william_hill,paddy_power,sky_bet"; // bookmaker keys, comma-separated
const DROP_PERCENT = 10; // the smallest drop sent, as a percentage of the price at the last run
const MAX_TOKENS_PER_RUN = 100; // a run whose read is priced above this reads nothing and fails with the price

const API = "https://api.oddsrelay.io";

// The last price of each outcome, kept in this val's blob storage: "event|bookmaker|market|outcome" -> price, kick-off
type Seen = Record<string, [price: number, kickOff: number]>;

export default async function () {
  const filters = {
    region: "uk",
    sports: SPORTS,
    markets: MARKETS,
    bookmakers: BOOKMAKERS,
    commenceTimeFrom: new Date().toISOString(), // events that have not started
  };
  // The token cap: price the read first (quote=true costs nothing), and read only within MAX_TOKENS_PER_RUN
  const { cost } = await get("/v2/odds/raw", { ...filters, quote: "true" });
  if (cost > MAX_TOKENS_PER_RUN) {
    throw new Error(
      `This run's read costs ${cost} tokens, more than MAX_TOKENS_PER_RUN (${MAX_TOKENS_PER_RUN}), so nothing was ` +
        "read. Narrow SPORTS, MARKETS or BOOKMAKERS, or raise the cap.",
    );
  }
  const page = await get("/v2/odds/raw", filters); // up to 250 events, soonest kick-off first

  const last: Seen | undefined = await blob.getJSON("prices");
  const seen: Seen = { ...last };
  const drops = [];
  let watched = 0;
  for (const event of page.data) {
    const kickOff = Date.parse(event.commence_time);
    const name = event.home_team && event.away_team ? `${event.home_team} v ${event.away_team}` : event.sport_title;
    for (const book of event.bookmakers) {
      for (const market of book.markets) {
        for (const outcome of market.outcomes) {
          const price = outcome.price; // bookmakers send price; exchanges send back and lay prices, left out here
          if (!(price > 1)) continue;
          watched++;
          const key = [event.id, book.key, market.key, outcome.name].join("|");
          const was = seen[key]?.[0];
          seen[key] = [price, kickOff];
          const drop = was ? ((was - price) / was) * 100 : 0;
          if (drop >= DROP_PERCENT) {
            drops.push({ name, kickOff, book: book.title, market: market.key, outcome: outcome.name, was, price, drop });
          }
        }
      }
    }
  }
  for (const [key, [, kickOff]] of Object.entries(seen)) if (!(kickOff > Date.now())) delete seen[key]; // started
  await blob.setJSON("prices", seen);

  const count = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
  if (!last) { // the first run only stores the prices and says so, which also tests your email or webhook
    const what = page.data.length
      ? `Watching ${count(watched, "price")} on ${count(page.data.length, "event")}.`
      : "No events match your filters right now.";
    const more = page.meta.next_cursor
      ? ` Your filters match ${count(page.meta.total, "event")}: each run reads the first ${page.data.length}, ` +
        "soonest first."
      : "";
    return await send(
      "Price-drop alert is on",
      `${what} You will get a message when a price drops by ${DROP_PERCENT}% or more.${more}`,
    );
  }
  if (!drops.length) return console.log(`No drop of ${DROP_PERCENT}% or more among ${count(watched, "price")}`);

  drops.sort((a, b) => b.drop - a.drop);
  const when = (ms: number) =>
    new Date(ms).toLocaleString("en-GB", {
      timeZone: "Europe/London",
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  let text = `Prices down ${DROP_PERCENT}% or more since the last run:`;
  for (const [i, d] of drops.entries()) {
    const line = `\n\n${d.name}, ${when(d.kickOff)}\n${d.book}, ${d.market}, ${d.outcome}: ${d.was} → ${d.price} ` +
      `(-${d.drop.toFixed(1)}%)`;
    const rest = `\n\nAnd ${drops.length - i} more.`;
    if (text.length + line.length + rest.length > 1900) { // a Discord message holds 2,000 characters at most
      text += rest;
      break;
    }
    text += line;
  }
  await send(`${count(drops.length, "price drop")} of ${DROP_PERCENT}% or more`, text);
}

// One GET on the API. The key is read from ODDSRELAY_KEY and only ever goes in the Authorization header. fetch
// asks for gzip, which the boards require, and unzips the reply.
async function get(path: string, params: Record<string, string>) {
  const key = Deno.env.get("ODDSRELAY_KEY")?.trim();
  if (!key) throw new Error("Set ODDSRELAY_KEY in this val's environment variables");
  for (let tries = 1;; tries++) {
    const res = await fetch(`${API}${path}?${new URLSearchParams(params)}`, {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (res.status === 429 && tries < 3) { // rate-limited: wait as long as the reply says, then try again
      await res.body?.cancel();
      await new Promise((done) => setTimeout(done, 1000 * (Number(res.headers.get("Retry-After")) || 1)));
      continue;
    }
    const body = await res.json().catch(() => ({})); // a 429 comes with an empty body
    if (res.ok) return body;
    const error = body.error ?? {};
    throw new Error(
      `OddsRelay answered HTTP ${res.status} ${error.code ?? ""}: ${error.message ?? ""} ` +
        `(request id ${error.request_id ?? "-"})`,
    );
  }
}

// Email goes to your Val Town account's own address. With ALERT_WEBHOOK_URL set, the message is posted there instead.
async function send(subject: string, text: string) {
  const hook = Deno.env.get("ALERT_WEBHOOK_URL")?.trim();
  if (!hook) return await email({ subject, text });
  // Discord reads content and Slack reads text; allowed_mentions stops an @ in a name pinging anyone on Discord
  const res = await fetch(hook, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: text, text, allowed_mentions: { parse: [] } }),
  });
  // The error never shows the webhook's address: anyone who has it can post to your channel
  if (!res.ok) throw new Error(`The webhook refused the message: HTTP ${res.status} ${(await res.text()).slice(0, 200)}`);
}
