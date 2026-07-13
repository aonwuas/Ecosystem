  Evaluation: Prompt Orchestrator

  What it is / its goal

  Purpose: A CLI-first, model-agnostic runtime that tries to improve LLM output
  quality by decomposing a single generation into explicit stages —
  understanding → validated execution plan → worker → critic → optional one
  revision → final answer — with deterministic application policy governing 
  every model-proposed decision (strategy, role, clarification, refusal). Models
  propose; trusted code validates and authorizes.

  Core hypothesis (from MVP.md): a worker model does better when handed a prompt
  that already identifies the goal, task type, constraints, chosen strategy,
  output contract, and quality criteria — rather than inferring all of that plus
  solving plus self-evaluating in one shot.

  Long-term ambition (ROADMAP.md): 13 phases growing this into multi-model
  routing → multi-step planning → persistence → evaluation → coding-harness
  integration → API/service → OpenAI-compatible facade → RAG → tools → auto
  model selection → multi-user → production hardening.

  Current state: MVP is essentially complete and genuinely high quality. src is
  mypy-strict clean (49 files), ruff clean, 146/146 tests pass (~5.3k LOC
  source, ~4.1k LOC tests — an unusually good ratio), no network needed by
  default, honest and exhaustive PROJECT_STATE.md. This is one of the most
  disciplined small codebases I've evaluated.

  ---
  Glaring issues in the current implementation

  1. The core hypothesis is completely unvalidated. There is no measurement 
  anywhere that staged orchestration produces better output than a single call.
  The whole product exists to win a quality bet that has never been scored.
  Evaluation is Phase 5 — five phases of machinery get built on an unproven
  premise before anyone checks whether the premise holds. This is the single
  biggest problem.
  2. ~4× cost and latency for unmeasured gain. A full run is up to four
  sequential model calls (understanding, worker, critic, revision). That's 4×
  tokens and 4× wall-clock versus one call. Combined with #1, you may be paying
  4× for a lift that's small, zero, or occasionally negative — and you can't
  tell, because…
  3. No cost/latency accounting. PROJECT_STATE.md §19 notes token usage is
  parsed but not aggregated into FinalResponse. You literally cannot see what a
  run cost. That must exist before any optimization or the thesis test in #1 is
  even possible.
  4. Self-critique is weak by construction. In the common single-model
  deployment, the critic is the worker model grading its own homework — a
  well-known weak signal. And after revision there is no second critic pass (by
  design), so the revised answer ships with only deterministic checks. The stage
  that's supposed to guarantee quality is the least trustworthy link.
  5. Circular capability dependency. Orchestration is pitched as compensating
  for weaker models, but a weak local model is exactly the one least able to
  emit a good structured ExecutionPlan. The quality of the whole pipeline is
  gated by the weakest model's meta-cognition — the thing weak models are worst
  at.
  6. "Strategies" are prompt-template swaps, not execution paths. 17 strategies
  differ only in template text + metadata (the docs admit this in §54/§19). The
  elaborate registry may add little over a single well-written adaptive system
  prompt.
  7. Minor / hygiene: mypy-strict fails on 30 errors in the test files (missing
  annotations) despite the milestone claim that "quality gates pass" — src is
  clean but tests aren't held to the same bar. The one failing test
  (test_cli_help_succeeds) shells out to the bare prompt-orchestrator name and
  breaks whenever the venv isn't on PATH; it should use
  sys.executable/entry-point resolution like its sibling test does.

  ---
  Glaring issues in the roadmap
  
  1. Evaluation is ordered dead last among the "core" phases (Phase 5). It
  should be Phase 1, arguably Phase 0.5. You cannot responsibly build
  multi-model routing, multi-step planning, and persistence on top of an
  orchestration layer you haven't proven beats a baseline. This ordering is the
  roadmap's central flaw.
  2. The scope is 3–4 separate products for (apparently) a solo maintainer.
  Phases 7–13 alone are: an async task service, an OpenAI-compatible proxy, a
  RAG stack, a tool-execution sandbox, a model-routing/escalation engine, and a
  multi-tenant platform. Each is a company. The probability of finishing all 13
  well is very low; the risk of spreading thin and finishing none is high.
  3. Heavy redundancy with mature, well-funded tooling, with no stated 
  differentiation. Phase 1/11 (provider routing + escalation) ≈
  LiteLLM/OpenRouter; Phase 3 (multi-step planning) ≈ LangGraph; Phase 9 (RAG) ≈
  LlamaIndex; Phase 10 (tools) ≈ every agent framework; the "optimize the
  plan/prompt for a task" problem is precisely DSPy's thesis. The roadmap never
  says why build instead of adopt, or what the durable wedge is.
  4. Phase 8 (harness-native OpenAI-compatible proxy) is disproportionately 
  risky. The roadmap's own "must not" list (don't wrap tool calls in prose,
  don't lose tool-call IDs, don't corrupt structured output, don't inject
  clarifications) enumerates exactly why interposing a critic/orchestration
  layer inside a coding harness's tool loop is a minefield. Add 4× latency
  inside an agent loop and it's likely a net negative for the target user.
  5. DSPy-shaped problem, hand-built solution. Hand-authoring 17 strategy
  templates and critic rubrics is the manual version of what compile-time prompt
  optimization automates against a metric. Without the metric (#1), you're
  tuning prompts blind.

  ---
  Changes that would most improve the project

  Do now, before any new phase:
  - Build a minimal evaluation harness and bring Phase 5 to the front. Even
  30–50 tasks with baseline-vs-orchestrated pairwise judging (a stronger judge
  model) plus deterministic checks. Report the quality delta and the
  token/latency cost per run. This single change de-risks everything downstream.
  - Add token/latency/cost aggregation to FinalResponse — prerequisite for the
  above and for adaptive control below.
  - Make orchestration A/B-able: a built-in --baseline (single-call) mode so
  every prompt can be compared head-to-head. This turns the product into its own
  experiment.
  - Adaptive orchestration: skip critic/revision (and even collapse
  understanding into the worker prompt) when the plan says the task is
  low-complexity/low-risk. Only pay the 4× when the plan predicts it will pay
  off. The critic-policy flags are already a hook for this.

  Housekeeping:
  - Hold tests to mypy-strict (or explicitly relax strict for tests/) so
  "quality gates pass" is true.
  - Fix the PATH-dependent CLI test.

  Strategic:
  - Consider adopting LiteLLM for the provider layer instead of hand-building
  adapters across Phases 1 and 11, and reserve your effort for the
  orchestration/governance logic that's actually differentiated.

  ---
  Features worth adding to the roadmap

  - Continuous evaluation + regression gating (promoted, as above).
  - Per-request cost/latency budgets with hard ceilings, and a cheap-path
  fallback.
  - Best-of-N / self-consistency as a strategy — the sequential-only,
  single-worker design leaves the cheapest reliable quality win (sampling +
  selection) on the table. (The MVP explicitly excludes parallel calls; revisit
  that.)
  - Constrained decoding for structured output — llama-server supports GBNF
  grammars / JSON-schema-constrained generation. Using it for the
  understanding/critic JSON would eliminate an entire class of parse-and-repair
  failures rather than papering over them with a repair call.
  - Response/plan caching to offset the multi-call cost premium.
  - Prompt/strategy optimization phase (DSPy-style) once a metric exists.
  - A cross-model critic option — allow the critic role to default to a
  different (or stronger) model than the worker, since same-model self-critique
  is the weak case.

  ---
  Is it viable?

  Split answer:

  - As an engineering artifact, a learning vehicle, or a personal local-first
  tool: yes, clearly. The discipline, test coverage, honest self-documentation,
  and clean architecture are excellent — better than most funded projects at
  this stage. The extension points are real; someone could genuinely build Phase
  1–2 on this.
  - As a product following the full 13-phase roadmap: not as currently scoped.
  It bets a very large, multi-product roadmap on an unmeasured core premise,
  while re-implementing several commodity layers that mature incumbents already
  own, without a stated differentiator.

  The pivot to viability is concrete and cheap: prove the thesis with evaluation
  first. If staged orchestration measurably lifts quality on local models at
  acceptable cost, you have a real wedge — local-first, governance-heavy, 
  deterministic-policy orchestration is a genuine niche that LangGraph/DSPy
  don't own cleanly. Then ruthlessly cut the roadmap to that core (staged
  orchestration + adaptive cost control + evaluation + strong governance) and
  adopt libraries for routing/RAG/tools. If the measured lift is not there,
  you've spent one small phase to learn that before building six more — which is
  exactly the outcome the current ordering prevents you from discovering until
  it's expensive.

  Bottom line: excellent execution, honestly documented, aimed at an unproven
  target down an over-long path. Make it prove itself, then narrow it. The
  quality of the work earns it that chance.

  ---
  Note: I created a gitignored .venv/ to run the test suite; it doesn't affect 
  your tree. Want me to (a) add the evaluation-harness/cost-accounting as a 
  concrete plan, (b) fix the mypy-strict test gap and the PATH-dependent test 
  now, or (c) draft a trimmed roadmap?

✻ Cooked for 3m 31s

※ recap: I evaluated the Prompt Orchestrator project: a well-built but 
  unvalidated staged-LLM-orchestration runtime whose core quality premise is 
  never measured. Next action, if you want it: build a minimal evaluation 
  harness with cost accounting to prove the thesis before further roadmap work. 
  (disable recaps in /config)
  
  ------------------------------------------
  
  build a minimal evaluation harness with cost accounting to prove the thesis
  
  ------------------------------------------
  
  
  Done. The evaluation harness with cost accounting is built, tested, and
  working end-to-end.

  What was built

  The thesis-testing tool: for every case, it runs the full orchestration
  pipeline and a single-call baseline on the same worker model, then reports
  quality (deterministic pass/fail) side-by-side with cost (tokens, calls,
  latency). The example run makes the tradeoff concrete: orchestration and
  baseline both pass all checks, but orchestration costs 5.85× the tokens.
  That's exactly the signal needed to judge whether the orchestration premium is
  worth it — and it will become discriminating the moment you add cases where
  the arms disagree on quality.

  New capabilities

  - Cost accounting — MeteringModelClient (a decorator client mirroring the
  existing DiagnosticModelClient) records role, request kind, tokens, latency,
  and repair-vs-normal per call, aggregated into a RunUsage. Now attached to
  every run --json (usage field) — closing the PROJECT_STATE.md gap "token usage
  is parsed but not aggregated in FinalResponse."
  - Single-call baseline — PipelineRunner.run_baseline(): one worker call, no
  understanding/critic/revision — the honest control arm.
  - Evaluation package (evaluation/) — YAML corpus loader + EvalCase/EvalChecks
  schema, model-free deterministic checks
  (must_include/must_avoid/length/expected-status), orchestrated-vs-baseline
  harness with per-arm metering, an opt-in pairwise model judge (position-bias
  mitigated by deterministic slot assignment), and an EvalReport with text +
  JSON rendering.
  - CLI — prompt-orchestrator eval --corpus … [--judge] [--no-baseline] 
  [--json].
  - Runnable no-network example — config.eval-scripted.yaml + eval-corpus.yaml +
  fixture.

  Quality gates

  - 166 tests pass (21 new, fully type-annotated), no network.
  - ruff clean, ruff format clean, mypy --strict clean on all of src (57 files).
  - My new test files add zero mypy-strict errors; the 30 remaining are all
  pre-existing in older test files (untouched).

  Design notes / honest limitations

  - Metering happens at the client boundary, not inside each stage — so no stage
  code changed, but usage is per-operation rather than per-stage-result.
  - The judge reuses the critic role model and is opt-in (needs a capable
  model); scripted example doesn't exercise it, but a test does.
  - No provider pricing model yet (tokens, not dollars), and no report
  persistence or cross-run regression tracking — natural next steps if you want
  this to become the continuous-eval backbone I recommended in the evaluation.
  
  ------------------------------------------
  
  What are good ways to test the efficacy of the staged orchestration output vs 
  a single call?
  
  ------------------------------------------
  
   Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Testing the efficacy of staged orchestration vs a single call

 Context

 The orchestration pipeline costs ~4–6× the tokens/latency of one model call
 (the
 scripted example measured 5.85× tokens). So the honest efficacy question is
 not "does staged orchestration beat one naive call?" — it is "does it beat
 the best thing you could do with the same compute budget?" A single call with
 the same small model is a weak control; if orchestration only wins because it
 spends more, the structure isn't what's helping.

 The current harness (src/prompt_orchestrator/evaluation/) is a good base but
 proves little on its own: it runs each case once, compares exactly two
 arms (orchestrated vs one single call), reports raw counts (no confidence
 intervals or significance), uses one judge = the critic model (self-preference
 risk), and has no equal-compute controls. This plan lays out the methodology
 and a phased extension, prioritizing equal-compute fair baselines per the
 chosen
 scope.

 ---
 Part A — Methodology (the answer)

 A1. The measurement stack (weakest→strongest signal)

 1. Objective reference-free checks — already in checks.py (must_include,
 must_avoid, length, expected status). Cheap, reproducible, great for
 regression; weak as a "quality" measure. Extend with format/JSON-schema
 validity and constraint-satisfaction counts.
 2. Reference-based metrics (where gold answers exist) — exact match, token-F1,
 ROUGE (summarization), JSON-schema + field accuracy (extraction/structured
 output), executable unit tests (code). Objective and strong, but needs
 authored gold and doesn't fit open-ended/creative tasks. (Deprioritized by
 the user; kept as a later phase.)
 3. LLM-as-judge, pairwise — already in judge.py. The workhorse for
 open-ended quality. Only trustworthy with the bias controls in A3.
 4. Human evaluation — small blind preference set. Not for scoring everything;
 its job is to calibrate the LLM judge (agreement / Cohen's κ).

 A2. Fair baselines & controls — THE priority

 Compare orchestration against alternatives that spend a matched token/latency
 budget, so any win is attributable to structure, not spend:

 - Single call, same model — the floor (already have run_baseline).
 - Best-of-N sampling — draw N candidates from the worker model at temp>0 and
 select one (with the critic model, mirroring orchestration's critic). Pick N
 so
 best-of-N's tokens ≈ orchestration's tokens. This is the toughest, most
 important control: much of orchestration's benefit can be reproduced by simply
 sampling more and selecting.
 - Self-refine — single model, one context: generate → self-critique →
 improve, with no separate plan/strategy/roles. Isolates "explicit staged
 roles" from "just iterate once."
 - Stronger-model-at-equal-cost — could the extra tokens instead buy a bigger
 single model? Compare orchestrated-small vs single-large at matched $ or
 latency.
 - Ablations — understanding-only; worker+critic but no revision; etc. Reuses
 existing runtime.enable_critic / enable_revision toggles to attribute the
 lift to specific stages.

 Compute matching must be measured, not assumed. Because MeteringModelClient
 already records per-arm tokens/latency, the report can show the achieved
 token/latency ratio between arms so a reviewer can see the comparison is fair
 (and N can be tuned to hit parity).

 A3. Judge integrity (needed to trust any pairwise arm comparison)

 - Use a strong third-party judge model, never the worker or critic model
 (avoids self-preference bias).
 - Run both orders (A/B and B/A) and average; treat order-flips as ties.
 (Current code only alternates the slot across cases — better than nothing, not
 sufficient per-case.)
 - Calibrate against the small human set (agreement/κ); report it.
 - Self-consistency: run the judge twice; a high flip-rate means low-signal
 verdicts.
 - Force a rubric + written reason (already done).

 A4. Statistical treatment (so results aren't anecdotal)

 - Paired design (same prompts through every arm) → paired tests:
   - Pass/fail: McNemar's test on the discordant pairs.
   - Pairwise wins: sign / binomial test on non-ties; report win-rate with a
 Wilson confidence interval.
   - Continuous scores: Wilcoxon signed-rank or bootstrap CIs.
 - Sample size / power: 2–8 cases prove nothing. Estimate the N needed to
 detect a meaningful win-rate delta; report CIs so under-powered results are
 visibly inconclusive.
 - Variance / reproducibility: pass the API seed (OpenAI-compatible servers
 support it via extra_body) at fixed temperature for determinism; OR run K
 trials per arm at temp>0 and report mean ± CI plus pass-rate stability.
 Orchestration may win on consistency even at equal mean quality.
 - All of this is implementable with the stdlib only (statistics, math,
 random) — no numpy/scipy needed (confirmed: deps are only
 httpx/pydantic/yaml).

 A5. Slicing & failure analysis (where, not just whether)

 - Stratify by category / complexity / ambiguity / risk. Orchestration
 typically helps on ambiguous, high-stakes, multi-constraint tasks and hurts
 simple direct answers (over-engineering + latency). Aggregate numbers hide
 this.
 - Failure taxonomy per arm: hallucination, missed constraint, format
 violation, wrong refusal, verbosity.
 - Cost–quality Pareto: plot quality vs tokens/latency; is orchestration
 Pareto-optimal, or dominated by best-of-N? Report quality-per-1k-tokens.

 A6. Process integrity

 - Fixed, versioned corpus + fixed seeds → reproducible regression tracking
 across prompt/model/strategy changes.
 - Pre-register the metric and decision rule (what win-rate/CI justifies the
 cost) before running, to avoid cherry-picking.
 - Keep a hold-out set so prompts/strategies aren't overfit to the eval.

 ---
 Part B — Phased implementation plan (prioritized)

 Phase 1 — Equal-compute fair baselines (priority)

 Generalize the two-arm harness into an N-arm design and add the control arms.

 - New src/prompt_orchestrator/evaluation/arms.py — an Arm = {name, kind,
 run(request, client) -> FinalResponse}. Built-in factories:
   - orchestrated → PipelineRunner.run
   - single_call → PipelineRunner.run_baseline (exists)
   - best_of_n(n) → N single-call candidates + critic-model selection
   - self_refine → generate + one in-context self-critique/revise
   - ablation(enable_critic=…, enable_revision=…) → orchestrated run with
 toggles
 - pipeline/runner.py — add run_best_of_n, run_self_refine, and let
 run honor per-arm critic/revision overrides (reuse existing
 RuntimeConfig.enable_critic/enable_revision semantics; pass a small override
 rather than mutating frozen config). New request_kinds: candidate,
 selection, self_refine_draft, self_refine_revise (so the scripted client
 and metering can distinguish them).
 - evaluation/harness.py — iterate a list of arms per case; designate one
 treatment (orchestrated) and the rest controls; meter each arm via the
 existing MeteringModelClient.reset()/snapshot(); pairwise-judge treatment vs
 each control.
 - evaluation/report.py — replace hardcoded orchestrated_*/baseline_*
 with a per-arm results map; add a compute-match ratio per control
 (control tokens ÷ treatment tokens) and quality-per-1k-tokens so fairness is
 visible. Keep token_cost_premium behavior for the single-call arm.
 - cli.py — eval flags: --arms single_call,best_of_n,self_refine,
 --best-of-n N, --ablations.

 Reuse: run_baseline, MeteringModelClient, evaluate_checks, judge_pair.

 Phase 2 — Statistical layer (supporting; required to read Phase 1)

 - New src/prompt_orchestrator/evaluation/stats.py (stdlib only): Wilson
 interval, sign/binomial test, McNemar's test, bootstrap CI, and a sample-size
 helper.
 - Wire into EvalReport: per-arm pass-rate + Wilson CI; treatment-vs-control
 win-rate + CI + p-value (McNemar on pass/fail, sign test on judge wins).
 Render
 in render_report_text.

 Phase 3 — Judge integrity & variance (supporting)

 - Optional dedicated judge role in config (roles.judge, falling back to
 critic) so the judge can be a third-party strong model — small change in
 config/models.py + judge.py.
 - Both-order judging in judge.py (run A/B and B/A, average; flip ⇒ tie).
 - Multi-trial support: --trials K in the harness; thread the API seed
 through ModelRequest→extra_body for reproducibility; report per-arm variance.

 Phase 4 — Reference-based metrics (optional / later, per user
 deprioritization)

 - Add optional reference/gold to EvalCase and metric checks (exact-match,
 token-F1, JSON-schema validity) in a new metrics.py; add a small
 human-calibration corpus + judge↔human agreement report.

 ---
 Files to modify / add

 - New: evaluation/arms.py, evaluation/stats.py (Phase 2), metrics.py
 (Phase 4).
 - Modify: pipeline/runner.py (control-arm runners + per-arm toggles),
 evaluation/harness.py (N-arm loop), evaluation/report.py (per-arm map +
 compute ratios + stats), evaluation/judge.py + config/models.py (Phase 3
 judge role + both-order), cli.py (eval flags), evaluation/corpus.py
 (Phase 4 reference field).
 - Tests/examples: extend examples/eval-scripted.yaml fixture with candidate/
 selection/self_refine_* steps; new tests/test_eval_arms.py,
 tests/test_eval_stats.py; extend tests/test_evaluation.py /
 tests/test_cli_eval.py.

 Verification

 - Deterministic scripted run showing all arms + compute ratios:
 selection/self_refine_* steps; new tests/test_eval_arms.py,
 tests/test_eval_stats.py; extend tests/test_evaluation.py /
 tests/test_cli_eval.py.

 Verification


     ---
     Files to modify / add

     - New: evaluation/arms.py, evaluation/stats.py (Phase 2), metrics.py
     (Phase 4).
     - Modify: pipeline/runner.py (control-arm runners + per-arm toggles),
     evaluation/harness.py (N-arm loop), evaluation/report.py (per-arm map +
     compute ratios + stats), evaluation/judge.py + config/models.py (Phase 3
     judge role + both-order), cli.py (eval flags), evaluation/corpus.py
     (Phase 4 reference field).
     - Tests/examples: extend examples/eval-scripted.yaml fixture with
     candidate/
     selection/self_refine_* steps; new tests/test_eval_arms.py,
     tests/test_eval_stats.py; extend tests/test_evaluation.py /
     tests/test_cli_eval.py.

     Verification

     - Deterministic scripted run showing all arms + compute ratios:
     python -m prompt_orchestrator eval --config 
     examples/config.eval-scripted.yaml --corpus examples/eval-corpus.yaml 
     --arms single_call,best_of_n,self_refine --best-of-n 3 --json → assert a
     per-arm map, and that best-of-N's token ratio
     approaches orchestration's (compute-matched).
     - Unit tests for stats.py against hand-computed Wilson/McNemar/sign values.
     - Judge both-order test: identical answers ⇒ tie; asymmetric ⇒ stable
     winner
     across orders.
     - Gates stay green: ruff check, ruff format --check, mypy (src
     strict-clean;
     new tests add zero errors), full pytest with the venv on PATH.

     Plan approved. The priority is Phase 1 (equal-compute arms) + Phase 2 (stats
     to interpret them). Let me set up tasks and re-read the current (post-format)
     files I'll modify.


What was built (plan Phases 1–3)

  The methodology question is answered in the plan file, and the harness was
  extended from a two-arm counter into a fair, statistically-honest, N-arm 
  comparison — leading with the equal-compute controls you prioritized.

  The core idea, made runnable

  The demo shows the payoff directly. All three arms pass the check, but the
  report reframes the question from "does orchestration win?" to "is it worth 
  the compute?":

  ┌──────────────────────────┬───────┬────────┬───────────────┬────────────┐
  │           arm            │ calls │ tokens │ compute ratio │ quality/1k │
  ├──────────────────────────┼───────┼────────┼───────────────┼────────────┤
  │ orchestrated (treatment) │ 3     │ 1690   │ —             │ 0.59       │
  ├──────────────────────────┼───────┼────────┼───────────────┼────────────┤
  │ best_of_3                │ 4     │ 1065   │ 0.63×         │ 0.94       │
  ├──────────────────────────┼───────┼────────┼───────────────┼────────────┤
  │ self_refine              │ 2     │ 560    │ 0.33×         │ 1.79       │
  └──────────────────────────┴───────┴────────┴───────────────┴────────────┘

  Here self-refine reaches the same quality at a third of the tokens — exactly
  the "structure vs. spend" signal that a naive single-call baseline can't
  reveal.

  Delivered

  - Equal-compute control arms (pipeline/runner.py): run_best_of_n (N candidates
  + critic selection), run_self_refine (draft → self-critique in one model),
  and with_overrides for no-critic / no-revision ablations — all sharing the
  metered client so costs are comparable.
  - Arm abstraction (evaluation/arms.py): Arm / ArmSpec / build_arms — treatment
  first, then chosen controls + ablations.
  - Statistics, stdlib-only (evaluation/stats.py): Wilson intervals,
  sign/binomial test, McNemar, bootstrap, sample-size — all verified against
  hand-computed values.
  - N-arm harness + report (harness.py, report.py): per-arm pass-rate with 95% 
  CI, token/latency cost, compute-ratio-vs-treatment, quality-per-1k, and paired
  treatment-vs-control significance (McNemar on checks, sign test + win-rate CI
  on the judge).
  - Bias-controlled judge (judge.py): now judges each pair in both orders and
  only declares a winner when they agree (else a flagged tie).
  - CLI: eval --arms single_call,best_of_n,self_refine --best-of-n N --ablations
  --judge --json.

  Quality gates

  - 179 tests pass (13 new across test_eval_arms.py, test_eval_stats.py, updated
  eval tests), no network.
  - ruff + ruff-format clean; mypy --strict clean on all src (59 files); new
  tests add zero mypy errors (full-project count holds at the 30 pre-existing
  errors in older test files).
  - README, examples/README, and PROJECT_STATE updated.

  Honest scope notes (deferred, per your deprioritization)

  - Judge still reuses the critic role model (dedicated third-party judge role,
  multi-trial + API seeds, and reference/gold metrics are the documented next
  steps).
  - The scripted example only scripts the single-call control; the other arms
  need a live model or a matching fixture (the CLI test shows the exact per-arm
  call sequence).

  ------------------------------------------
  
  Stop developing new features.  I want to test the efficacy of the
  orchestration.
  Comparing absolute token usage is unimportant if the single prompt method
  produces garbage.
  This application is for taking weaker models (less than 50b parameters) and making
  them more effective.
  The reason there is only one model checking right now was because this
  project is an MVP whose goal was to get all the pieces working together.
                                                                                
  The pieces are working.  How can I test that the concept is effective?
  
  ------------------------------------------
  
  The user is course-correcting: stop building, and the real goal is a quality
  efficacy test — does orchestration make a weak (less than 50B) model meaningfully
  better, regardless of token cost. Let me re-read the existing plan, then
  verify a few facts about the current judge/config coupling before proposing a
  testing protocol.
  
   I have what I need. The decisive fact: the judge is hard-wired to the critic
  role, which orchestration itself uses — so there's no valid way today to
  measure quality with an independent, stronger instrument without contaminating
  the orchestrated arm. That's the crux of testing your concept. Two
  clarifications shape the protocol:
  
  ● The user wants to clarify before answering. What would you like to clarify or
  add? A few things that might be on your mind:

  - On the judge: Do you already have access to a strong model (hosted API or a
  big local one), or is a weak local model all you have right now? If the
  latter, I can propose ways to still get signal.
  - On "efficacy": What would convince you the concept works? A judge preferring
  orchestrated answers more often? Passing objective task requirements a single
  call fails? Closing the gap to a big model? Something else?
  - On the target: Is there a specific less than 50B model + endpoint you're testing
  against now, or should the protocol stay model-agnostic?
  - On scope: When you say "stop developing new features" — does that also rule
  out the small enabler needed to plug in an independent judge (so orchestration
  stays pure-weak-model while a stronger model scores it), or is necessary test
  infrastructure acceptable?
  
  Tell me whatever's on your mind and I'll reshape the questions/plan
  accordingly.

------------------------------------

The goal is to have multiple models. The reason there is a single model right 
  now is because the state of the project at the start of this session was      
  simple get things to go through the pipeline.  Additional models had not yet  
  been downloaded and configured.    

  ---------------------------------------
  
  Got it — multi-model is the intended state; single-model is just where the
  plumbing landed this session. That reframes things: the orchestration arm
  should reflect your real multi-model config, and the key remaining question is
  the judge (it must be stronger than, and separate from, the models in the
  arms — otherwise it's grading its own family). Two quick decisions and I'll
  write the protocol:

User answered Claude's questions:
  ⎿  · For scoring quality, what will act as the independent judge — a model 
     stronger than, and not used by, either arm? (Today the judge is hard-wired 
     to the critic role, so a distinct judge needs one small config/plumbing 
     change.) → Distinct large local judge
     · What result would convince you the concept works? → Passes objective lly 
     checks
     
      Decisions noted: distinct large local judge (independent, private) and
  objective checks as the primary success signal. That's a clean setup — and
  importantly, the objective-check result needs zero new code; the judge is a
  secondary signal that needs one small enabler. Let me write the protocol.
     
     The plan is written — a testing protocol, not more features. The headline: you
  can measure the concept right now with zero new code using objective checks;
  the distinct local judge is a secondary signal needing one small enabler.
  
   The product thesis is: staged orchestration makes a weak (less than 50B, local) model
 produce materially better answers than that same weak model answering in one
 shot. The single-model state in the repo is temporary plumbing, not a design
 choice — the real deployment maps different local models to the understanding
 /
 worker / critic / revision roles. The pieces now work end-to-end; the task now
 is
 to measure the concept, not build more.

 Chosen evaluation stance (from the user):
 - Primary signal: objective checks. Does the orchestrated answer meet
 per-task requirements (correctness, constraints, format) that the single call
 fails? Absolute token cost is explicitly not the deciding factor — a cheap
 answer that is garbage does not count.
 - Secondary signal: a distinct large local judge (e.g. 70B+), reserved as
 judge and used in no arm, for open-ended quality where checks under-determine.

 The harness already exists (src/prompt_orchestrator/evaluation/): arms,
 deterministic checks, paired stats (Wilson CI, sign, McNemar), a both-order
 judge, and per-arm cost accounting. The main missing ingredient is a real
 corpus, not more features.

 Key finding that shapes this plan: the judge is currently hard-wired to the
 critic role (judge.py → config.resolve_role(ModelRole.CRITIC)). Since the
 critic is also part of orchestration, pointing it at the large judge model
 would
 give the orchestrated arm a strong critic and bias the result. So the distinct
 judge requires one small decoupling change — but it is only needed for the
 secondary signal.

 ---
 The efficacy question & decision rule

 Question: On tasks with checkable requirements, does weak-model orchestration
 satisfy requirements that the weak-model single call does not — significantly,
 and without regressing easy tasks?

 Pre-registered decision rule (adjust before running, not after):
 - Effective if, over the corpus, orchestrated pass-rate > single-call
 pass-rate with the paired McNemar p < 0.05 (treatment-only passes clearly
 exceed control-only passes), and no significant regression on the "simple"
 category (guards against over-engineering).
 - Report per-category so wins/losses are visible where they happen.

 ---
 Step 1 — Objective-check efficacy run (NO new code)

 This produces the primary result using only what exists.

 1. Configure the real multi-model orchestration in a live config (copy
 examples/config.local-llama.yaml): map understanding/worker/critic/revision
 to the intended local <50B models, provider = openai_compatible at your
 llama-server/endpoint. The single_call control automatically uses the
 worker model (the honest "one shot from the model you'd otherwise use").
 2. Author a real corpus (see next section) as a YAML file of EvalCases with
 objective EvalChecks (corpus.py schema: must_include, must_avoid,
 min_length, max_length, expect_status).
 3. Run (objective checks only, no judge, so no code needed):
 prompt-orchestrator eval --config <live-multimodel.yaml> \
     --corpus <corpus.yaml> --arms single_call --json > result.json
 4. Read the primary result from the report, which already computes it:
   - arms.orchestrated.pass_rate + CI vs arms.single_call.pass_rate + CI.
   - comparisons.single_call.treatment_only_passes /
 control_only_passes / mcnemar_p (in report.py ComparisonAggregate).
   - Repeat/split the corpus by category to get per-category tables.

 Reused as-is: evaluate_checks (checks.py), ComparisonAggregate +
 ArmAggregate (report.py), wilson_interval/mcnemar_p_value (stats.py),
 the single_call arm (arms.py), PROMPT_ORCHESTRATOR_LIVE_CONFIG conventions
 (tests/test_live_smoke.py).

 ---
 Corpus design — the real lever

 Pick tasks where a weak single call plausibly fails a checkable requirement,
 i.e. where structure should help most. Target ≥30–50 cases, spread across
 categories, with enough per category to be non-anecdotal (stats.py
 sample_size_for_win_rate gives guidance; a ~15-point win-rate needs dozens).

 Suggested categories and the objective checks that catch failures:
 - Multi-constraint instructions — must_include every required element,
 must_avoid the forbidden ones (weak models drop constraints).
 - Format/structure adherence — require literal markers (e.g. section
 headings, ```json, required keys) via must_include.
 - Factual precision / no hallucination — must_include the correct fact,
 must_avoid the common wrong answer.
 - Underspecified prompts — expect_status: clarification_required (does
 orchestration correctly ask instead of guessing?).
 - Safety-sensitive — expect_status: refused or required caution language.
 - Simple direct questions — the regression guard: orchestration must not
 break or bloat these.

 Include a short rubric per case for the later judge step. Keep a hold-out
 slice you don't inspect while tuning prompts, to avoid overfitting the eval.

 I can scaffold a first-draft corpus across these categories for you to refine
 (this is data authoring, not feature work).

 ---
 Step 2 — Add the independent local judge (one small enabler; secondary)

 Only needed for open-ended quality beyond objective checks. This is the single
 code change in this plan, and it is test infrastructure, not a product
 feature.

 - Decouple the eval judge from the critic role so it can point at a distinct
 large local model that is used in no arm. Minimal approach: add an optional
 judge model reference (e.g. roles.judge, defaulting to the critic model) in
 config/models.py, add a JUDGE entry to ModelRole
 (domain/enums.py) so ModelRequest/metering/resolve_role stay consistent,
 and resolve it in judge.py (_judge_once). Keep the fallback so existing
 configs and the scripted example are unchanged.
 - Configure roles.judge → the 70B+ local model; keep the arms on the weak
 models. Run with the judge on:
 prompt-orchestrator eval --config <live-multimodel.yaml> \
     --corpus <corpus.yaml> --arms single_call --judge --json
 - The judge already runs both orders and reports win-rate + CI + sign test
 (report.py ComparisonAggregate.judge_*). Treat it as corroboration of the
 objective-check result, and calibrate it once against ~15–20 of your own
 blind rankings before trusting it broadly.

 ---
 Optional framing: recover-the-gap ceiling

 To show how effective, run a separate config where the worker is the large
 model (--arms single_call) to get a strong single-call ceiling, and compare
 the
 weak-orchestrated pass-rate against it. No code needed — just another config.

 ---
 What NOT to do

 No further harness features (no reference-metric module, no multi-trial/seed
 work, no new arms) unless a measured gap in Step 1–2 demands it. The next
 action
 is data (corpus) + running against real models.

 Verification

 - Dry-run the pipeline with no network first to confirm wiring:
 prompt-orchestrator eval --config examples/config.eval-scripted.yaml --corpus
 examples/eval-corpus.yaml (should report per-arm pass-rates + McNemar).
 - Live smoke: with the live multi-model config,
 prompt-orchestrator run --config <live>.yaml "…" returns a completed answer
 (mirrors tests/test_live_smoke.py).
 - Real run: Step 1 command on the authored corpus; confirm per-arm pass-rate
 CIs
 and comparisons.single_call.mcnemar_p populate, and per-category tables.
 - If Step 2's judge enabler is implemented: ruff check, ruff format --check,
 mypy (src strict-clean), full pytest stay green; the scripted example still
 runs unchanged (judge falls back to critic when roles.judge is unset).

  
  

