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
