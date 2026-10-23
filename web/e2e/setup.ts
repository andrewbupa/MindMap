import { mkdirSync, writeFileSync } from "node:fs";

import { test as setup, type APIRequestContext } from "@playwright/test";

import { STATE, expect, json, post, signIn, type Seeded } from "./fixtures";

type Run = { id: string; kind: string; status: string; config: Record<string, unknown> };

const AGENT = "claims-assistant";
const BEHAVIOUR = "unauthorised_coverage_commitment";
const OPEN = new Set(["queued", "running"]);

/** Wait for a run to finish; the development models answer in seconds. */
async function finished(request: APIRequestContext, id: string): Promise<Run> {
  for (let i = 0; i < 240; i += 1) {
    const run = await json<Run>(request, `/api/runs/${id}`);
    if (!OPEN.has(run.status)) {
      expect(run.status, `run ${id}`).toBe("succeeded");
      return run;
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw new Error(`Run ${id} did not finish in four minutes. Is a worker running?`);
}

async function inquiry(request: APIRequestContext): Promise<Run> {
  const runs = await json<Run[]>(request, "/api/inquiry/runs");
  const found = runs.find((r) => r.status === "succeeded" && r.config.agent === AGENT);
  if (found) return found;
  const seeds = await json<{ key: string }[]>(request, `/api/inquiry/seeds?agent=${AGENT}`);
  const run = await post<Run>(request, "/api/inquiry/runs", {
    agent: AGENT,
    version: "v2",
    seeds: seeds.slice(0, 2).map((seed) => seed.key),
    max_turns: 4,
    compaction: false,
  });
  return finished(request, run.id);
}

async function scenarioSet(request: APIRequestContext): Promise<string> {
  type Behaviour = { scenario_set: { id: string } | null; generating: Run | null };
  let behaviour = await json<Behaviour>(request, `/api/tally/behaviours/${BEHAVIOUR}`);
  if (!behaviour.scenario_set) {
    const run = behaviour.generating ?? (await post<Run>(request, `/api/tally/behaviours/${BEHAVIOUR}/scenario-sets`, {}));
    await finished(request, run.id);
    behaviour = await json<Behaviour>(request, `/api/tally/behaviours/${BEHAVIOUR}`);
  }
  expect(behaviour.scenario_set).not.toBeNull();
  return behaviour.scenario_set!.id;
}

async function tally(request: APIRequestContext, set: string): Promise<Run> {
  type Summary = { run: Run; version: string; scenario_set: string };
  const runs = await json<Summary[]>(request, `/api/tally/runs?behaviour=${BEHAVIOUR}`);
  const found = runs.find((r) => r.run.status === "succeeded" && r.scenario_set === set && r.version === "v2");
  if (found) return found.run;
  const launched = await post<Run[]>(request, "/api/tally/runs", {
    agent: AGENT,
    versions: ["v1", "v2"],
    scenario_set: set,
    epochs: 1,
    max_turns: 4,
    compaction: false,
  });
  const done = await Promise.all(launched.map((run) => finished(request, run.id)));
  return done.find((run) => run.config.version === "v2")!;
}

async function ethos(request: APIRequestContext, source: string): Promise<Run> {
  type Summary = { run: Run; source: Run };
  const runs = await json<Summary[]>(request, "/api/ethos/runs");
  const found = runs.find((r) => r.run.status === "succeeded" && r.source.id === source);
  if (found) return found.run;
  const run = await post<Run>(request, "/api/ethos/runs", { source_run: source });
  return finished(request, run.id);
}

async function goldSet(request: APIRequestContext, source: string): Promise<{ set: string; item: string }> {
  type GoldSet = { id: string; items_list: { id: string }[] };
  const sets = await json<{ id: string }[]>(request, "/api/jury/gold-sets");
  const id =
    sets[0]?.id ??
    (await post<{ id: string }>(request, "/api/jury/gold-sets", { name: "Accessibility checks", source_run: source, size: 3 }))
      .id;
  const set = await json<GoldSet>(request, `/api/jury/gold-sets/${id}`);
  expect(set.items_list.length).toBeGreaterThan(0);
  return { set: id, item: set.items_list[0]!.id };
}

async function rehearsal(request: APIRequestContext): Promise<string> {
  const runs = await json<Run[]>(request, "/api/rehearsal");
  const found = runs.find((r) => r.status === "succeeded");
  if (found) return found.id;
  const { run } = await post<{ run: Run }>(request, "/api/rehearsal", { agent: AGENT, version: "v2" });
  await post(request, `/api/rehearsal/${run.id}/messages`, { content: "Why was claim CLM-TEST-5521 declined?" });
  await post(request, `/api/rehearsal/${run.id}/finish`, {});
  return run.id;
}

setup("sign in and find or make one finished run of each kind", async ({ page }) => {
  mkdirSync(STATE, { recursive: true });
  await signIn(page);
  await page.context().storageState({ path: `${STATE}/admin.json` });
  const request = page.request;

  const inquiryRun = await inquiry(request);
  const inquiryDetail = await json<{ transcripts: { id: string }[] }>(request, `/api/inquiry/runs/${inquiryRun.id}`);
  const set = await scenarioSet(request);
  const tallyRun = await tally(request, set);
  const tallyDetail = await json<{ rollouts: { transcript_id: string }[] }>(request, `/api/tally/runs/${tallyRun.id}`);
  const ethosRun = await ethos(request, tallyRun.id);
  const ethosDetail = await json<{ transcripts: { transcript_id: string }[] }>(request, `/api/ethos/runs/${ethosRun.id}`);
  const gold = await goldSet(request, tallyRun.id);

  const seeded: Seeded = {
    agent: AGENT,
    behaviour: BEHAVIOUR,
    inquiryRun: inquiryRun.id,
    inquiryTranscript: inquiryDetail.transcripts[0]!.id,
    scenarioSet: set,
    tallyRun: tallyRun.id,
    tallyTranscript: tallyDetail.rollouts[0]!.transcript_id,
    ethosRun: ethosRun.id,
    ethosTranscript: ethosDetail.transcripts[0]!.transcript_id,
    goldSet: gold.set,
    goldItem: gold.item,
    rehearsal: await rehearsal(request),
  };
  writeFileSync(`${STATE}/seeded.json`, JSON.stringify(seeded, null, 2));
});
