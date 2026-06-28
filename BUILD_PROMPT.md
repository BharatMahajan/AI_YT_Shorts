# Master Build Prompt — Daily AI YouTube Shorts Autopilot

This is a reusable **instruction set** you can hand to any capable AI coding agent (Claude Code, Cursor, etc.) to build this project from scratch. It deliberately contains **no code** — it describes *what* to build, *why*, and *in what order*. The agent should make its own implementation choices while honoring every requirement and guardrail below.

**What the agent must produce:** a fully-automatic pipeline that, once a day and unattended, picks a topic, researches fresh news, writes an original 50–60 second script, narrates it in an Indian-male voice, renders a sleek vertical motion-graphics video, uploads it to YouTube, and remembers what it did — all on free tools, on a schedule (default 9:00 AM IST, easily changeable).

---

## Table of Contents

1. [How to use this document](#1-how-to-use-this-document)
2. [The agent system prompt (paste first)](#2-the-agent-system-prompt-paste-first)
3. [Non-negotiable requirements](#3-non-negotiable-requirements)
4. [The free tool stack and why](#4-the-free-tool-stack-and-why)
5. [What to build, in order (the workflow)](#5-what-to-build-in-order-the-workflow)
6. [Cross-cutting rules every part must follow](#6-cross-cutting-rules-every-part-must-follow)
7. [The hand-off contract between the two layers](#7-the-hand-off-contract-between-the-two-layers)
8. [Credential and secret setup (human steps)](#8-credential-and-secret-setup-human-steps)
9. [Customization the owner will want](#9-customization-the-owner-will-want)
10. [Hard-won lessons — mistakes to design out](#10-hard-won-lessons--mistakes-to-design-out)
11. [Definition of done](#11-definition-of-done)

---

## 1. How to use this document

Give the agent Section 2 (the system prompt) plus Section 5 (the workflow) to execute. Keep Sections 3, 4, 6–11 open as the acceptance bar it must clear. The agent should work one stage at a time and validate each before moving on, because later stages depend on earlier ones.

---

## 2. The agent system prompt (paste first)

> You are a senior automation engineer. Build a production-grade, fully-automatic "daily AI YouTube Shorts" pipeline that runs unattended in the cloud and publishes one ~50–60 second vertical Short every day, rotating across four themes (AI news, GitHub Copilot, Claude, Cursor), using only free tools.
>
> Hold to these principles in everything you build:
> 1. **Free tools only.** No paid APIs or hosting. If a step would need money, stop and flag it rather than silently choosing a paid path.
> 2. **Fail loud, fail early.** Validate credentials and required programs before doing any slow work. Make each stage report a clear, typed failure. The runner should return distinct exit codes (success, configuration error, other failure) and send a best-effort alert — but an alert must never hide the original error.
> 3. **One small piece of durable state.** No database and no web server. The only thing that persists between runs is a single history file, saved back to the repository after each run. It powers anti-repetition and an optional learning loop.
> 4. **Keep content logic and animation separate.** The part that researches and writes should never touch the part that animates. They communicate only through one well-defined, validated data file.
> 5. **The audio decides the video length.** Measure the real length of the generated voice file itself; never trust the speech engine's word-timing events (they are frequently missing). Abort before rendering or uploading if the audio is suspiciously short.
> 6. **Be resilient.** Skip dead news sources silently, always keep a live search as a fallback, fall back across several model names if one is unavailable, and give every network call a timeout and automatic retries.
> 7. **Sound human and never repeat yourself.** Rotate opening styles, feed the writer the recent past titles to avoid, and write in a warm, energetic Indian-developer voice — not like an AI or a template.
> 8. **Test the logic and gate the release.** Cover the pure logic with automated tests that must pass in CI before the publishing step runs.
>
> Build stage by stage. After each stage, validate what the environment allows (import/compile checks for the logic; a compile/bundle check for the renderer). Be honest that a real video render and a real upload only happen in CI with real credentials — don't claim they work locally if the environment can't actually do them.
>
> Be honest about scope: this system produces and publishes videos. It cannot automate monetization — that requires meeting YouTube Partner Program thresholds, which no tool can bypass. Say so in the README.

---

## 3. Non-negotiable requirements

**Cadence and timing.** Exactly one Short per day. Default target time **9:00 AM IST**, and the run time must be changeable in one obvious place. (The reference build also supports an optional second slot in the evening — keep timing configuration centralized either way.)

**Topic rotation, in this exact order**, advancing one step per calendar day:
1. Latest tech updates in AI
2. Latest 1–2 features of GitHub / Microsoft Copilot
3. Latest 1–2 features of Claude (Anthropic)
4. Latest 1–2 features of Cursor

**Script quality.** Roughly 50–60 seconds of speech. It must feel human, energetic, and non-repetitive, achieved through an anti-repetition memory of recent titles plus rotating opening styles. The owner asked for a "developer review" feel — implement this as a toggle that, when on, publishes privately for manual approval, and when off, publishes fully automatically.

**Voice.** Indian male English by default, overridable per topic and via configuration.

**Visuals.** Quality animation with a sleek UI and friendly feel — vertical full-HD portrait, smooth scene-based motion graphics. No static slideshows and no code or terminal mockups.

**Free tools end to end**, and a single orchestrated pipeline with clean, independently-runnable stages (research/script, voice, render, upload) rather than many chatty sub-agents — this keeps it performant, cheap to test, and easy to retry.

---

## 4. The free tool stack and why

| Concern | Recommended free choice | Why |
|---|---|---|
| Scheduler / runtime | A CI scheduler with cron and secrets (e.g. GitHub Actions) | Free minutes, built-in cron and secrets, can commit state back, no server to maintain |
| News research | Public RSS feeds plus a public news-search RSS | No API key; the search acts as an always-available fallback |
| Script writing | A free-tier large language model with strong structured-output support | Free, reliable at returning structured data |
| Voiceover | A free text-to-speech engine that offers an Indian male voice | Free and natural-sounding |
| Audio length | A small audio-metadata library | Reads true audio length, unlike unreliable speech word-timings |
| Animation / render | A programmatic, code-driven motion-graphics renderer plus a standard video encoder | Open-source, produces polished MP4s without manual editing |
| Thumbnail | A standard image library | Free image generation |
| Upload | The official YouTube upload API with a long-lived refresh token | Free quota is enough for one upload a day |
| Failure alerts | Auto-created issues in the repo and/or a chat webhook | Free |

The agent should pin sensible versions and document them, but the choices above are what keep the whole thing free.

---

## 5. What to build, in order (the workflow)

Build these as separate, independently-runnable stages. Each entry says *what it must do* and *how you'll know it works* — not how to code it.

**Stage 0 — Foundations.** Establish one central configuration that holds all paths, voice settings, model preferences, video targets, behavior toggles, and the lists of which credentials each stage needs. Add a shared, typed set of error categories and a reusable retry-with-backoff helper, and one consistent logger. All writes to data files must be atomic so a reader never sees a half-written file. *Done when the configuration imports cleanly with no credentials present.*

**Stage 1 — Topic selection.** Define the four topics, each with its display title, a brand accent color, a one-line focus instruction for the writer, a curated set of news sources, several fallback search phrases, and (for the narrow topics) keywords that keep broad feeds on-subject. Provide a deterministic daily rotation as the default. Optionally provide a "trending" strategy that counts fresh items per topic and prefers the busiest one while avoiding any topic used in the last couple of runs. *Done when the topic advances by one each day and the cooldown logic is unit-tested.*

**Stage 2 — News research.** For the chosen topic, gather recent items from its sources plus a live search fallback. Give every fetch a timeout and a browser-like identifier; skip any individual source that fails without aborting. Clean the text, capture a best-effort image, filter out anything too old, sort newest first, remove duplicates, and keep only on-topic items (but fall back to the full pool rather than returning nothing). If genuinely nothing usable remains, fail clearly so the run stops. *Done when, against mocked feeds, it returns a clean on-topic list and an empty pool raises a clear error.*

**Stage 3 — Script generation.** Ask the language model to turn the 1–2 strongest real news items into a punchy spoken script. Pick a random opening style each time and tell the model the recent past titles to avoid. The prompt should request a warm, energetic, easy-to-pronounce Indian-developer voice of about 120–140 words ending in a "follow for daily updates" call to action, with no emojis in the spoken lines. Require a strict structured response containing: a short title, a couple of alternate titles (for A/B testing), a description with a few hashtags, a handful of search tags, the spoken lines, three to four on-screen highlight points (each a short heading plus a brief detail), and three to four tiny step labels for a simple flow diagram. Be tolerant when reading the model's response (it may wrap the data in formatting), validate that the essentials are present, fill safe defaults for the visual extras, and fall back across several model names if one is unavailable or out of free quota — with an actionable error if every option fails. Record the new title in the history memory. *Done when a mocked model yields a normalized result and malformed output raises a clear error.*

**Stage 4 — Voice and captions.** Convert the spoken lines into an audio file using the configured Indian male voice with a slightly faster, brighter delivery, retrying transient failures. Crucially, measure the real audio length from the file itself, and abort the whole run if it's implausibly short. Save the audio and a small captions record. *Done when synthesis yields a positive, real duration and empty audio raises a clear error.*

**Stage 5 — Prepare the visuals' inputs.** From the script and the measured audio length, assemble the single data file the renderer will consume, including the brand accent (and a derived second color for a gradient), the chosen topic's visual pattern, an optional faint background image, the spoken lines (which drive the on-screen captions), the highlight points, and the flow steps. Pick today's title variant for A/B testing. Separately, generate a branded thumbnail image with the topic label and wrapped title in two alternating layouts — but treat the thumbnail as best-effort, never letting it crash the run. *Done when the data file and thumbnail are produced and the thumbnail step survives a missing font.*

**Stage 6 — Render the video.** Build a portrait full-HD, smooth, scene-based animation: an animated gradient background with a subtle per-topic pattern, an opening hook with the title, a sequence of highlight cards, an optional simple flow diagram, and a closing call-to-action — with large, always-on captions across the bottom and a progress bar. The captions must be driven by the spoken lines spread across the timeline, never by word-timing data. The composition's total length must be computed from the real audio length so the video always matches the voice. The render step copies the audio in, runs the renderer, and verifies a non-empty video came out. *Done when the renderer compiles and bundles cleanly; the actual frame render happens in CI.*

**Stage 7 — Upload to YouTube.** Authenticate with the long-lived refresh token, confirm the video exists and isn't empty, and upload it as a resumable transfer that retries transient server and network errors with backoff. Set the title, description, tags, and the Science & Technology category, mark it not-made-for-kids, and choose visibility based on the review toggle (private for manual approval, otherwise the configured visibility). After uploading, attempt to set the custom thumbnail as a best-effort step that never fails the run. *Done when the retry behavior is unit-tested and missing credentials raise a clear error.*

**Stage 8 — Orchestrate and remember.** Wire the stages into one runner that can execute the whole chain or any single stage, with flags to skip rendering or uploading for cheap testing. Before each stage do a fast preflight that checks the needed credentials and programs and fails with an actionable message. Maintain a corruption-tolerant history file that records what was made (for anti-repetition) and, after upload, the video id and time (and later, performance). The runner maps each error category to its exit code and sends the failure alert. *Done when the full chain runs end to end given credentials, and each stage can be run on its own.*

**Stage 9 — Schedule it.** Set up the scheduled automation to target 9:00 AM IST (with an optional evening slot), allowing manual triggering too. Because CI cron timing drifts, poll more frequently and gate the actual publish to exactly one run per intended slot by checking whether a successful run already happened in that window. Run the test suite first and only publish if it passes. Install the needed system tools, cache the renderer's dependencies and its downloaded browser to keep runs fast, run the stages in order, and finally commit the updated history back to the repository. *Done when a manual trigger runs the whole chain and scheduled runs publish exactly once per slot.*

**Stage 10 — Harden it.** Add best-effort failure notifications (a chat webhook and/or an auto-opened repository issue) that never throw. Add a weekly health check that refreshes the upload token and makes a cheap authenticated model call, alerting if either is failing — so dead credentials surface before the daily run needs them. Provide a one-time local helper that walks the owner through granting upload permission and prints the values to store as secrets. Optionally add a learning loop that reads public view counts of past uploads and nudges both topic choice and writing style toward what performed well. Cover the pure logic with tests. *Done when the test suite is green, the health check validates credentials, and any stage failure produces an alert.*

---

## 6. Cross-cutting rules every part must follow

These apply across all stages and are part of the acceptance bar:

- Every file write is atomic; readers never see partial data.
- Every network call has a timeout, a polite identifier, and automatic retries with backoff.
- Failures are typed and mapped to clear exit codes; the orchestrator alerts on failure without masking the cause.
- The content layer and the animation layer share only one validated data file — no other coupling.
- The real audio length, measured from the file, is the single source of truth for video length.
- On-screen captions come from the spoken lines, never from speech word-timings.
- The thumbnail, analytics, and notification steps are best-effort and can never crash a run.
- Secrets live only in the CI secret store and a local ignored environment file — never committed.

---

## 7. The hand-off contract between the two layers

The research/writing layer hands the animation layer exactly one data file. Describe and validate it on the receiving side. It must carry: the active (A/B-selected) title; the topic's display label; the brand accent and a derived second color; the chosen visual pattern; an optional faint background image reference; the audio reference; the real audio length in seconds; the spoken lines (which drive the captions); the highlight points (each a short heading and brief detail); and the flow step labels. Word-timing data may be included but the visuals must not depend on it. Guarantee the spoken lines are never empty, since the captions and the script's validity both rely on them.

---

## 8. Credential and secret setup (human steps)

Document these clearly in the README, because the pipeline cannot do them for the owner:

- Create a free language-model API key from a **personal** account (corporate accounts often have zero free quota).
- In the cloud console, enable the YouTube upload API, create a desktop OAuth client, and **publish the consent screen to production** (test-mode tokens expire within about a week).
- Run the one-time local helper once to grant upload permission and obtain the long-lived refresh token, then store the client id, client secret, and refresh token as CI secrets.
- Optionally add an analytics API key and a chat webhook for alerts.
- Add the behavior toggles (visibility, review-before-publish, topic strategy, A/B testing, language, analytics) as CI variables.
- Trigger the workflow manually once to confirm the whole chain works before trusting the schedule.

---

## 9. Customization the owner will want

| To change… | Where it should live |
|---|---|
| Run time | One centralized timing setting (default 9:00 AM IST) |
| Topics and news sources | The topic definitions |
| Voice and language | Voice/language settings, with optional per-topic override |
| Manual review before publishing | The review toggle (publishes privately for approval) |
| Public / unlisted / private | The visibility setting |
| Smarter topic choice | The topic-strategy setting, optionally with the analytics loop on |
| Visual theme | The animation scenes and per-topic pattern/accent |
| Script length and style | The video-length target, word-count guidance, and opening styles |

---

## 10. Hard-won lessons — mistakes to design out

These are real failures the reference project hit; design them out from the start:

1. **One-second videos** happen when length is taken from speech word-timings that the engine sometimes omits. Measure the real audio length and abort if it's too short.
2. **A blank video** happens when on-screen content is gated on word-timings being present. Drive captions and scenes from the spoken lines instead.
3. **Use the current, supported model SDK**, not a deprecated one.
4. **Corporate accounts often have no free model quota.** Fall back across models and give an actionable "use a personal key" message.
5. **Test-mode upload tokens expire within about a week.** Publish the consent screen to production and run the weekly health check.
6. **Restricted sandboxes can't download the renderer's headless browser**, and committed dependencies may be built for the wrong OS. Validate by compiling and bundling; do the real render in CI on a clean install; cache the browser.
7. **CI cron drifts**, so poll often and gate to exactly one publish per intended slot.
8. **Thumbnail, analytics, and alerts must never crash the run** — keep them best-effort.
9. **Monetization can't be automated** and platforms demote repetitive, mass-produced AI content. Invest in genuine variety (anti-repetition memory, rotating hooks, real news) and set honest expectations.

---

## 11. Definition of done

- The test suite passes in CI, and CI gates publishing on it.
- The research/script stage produces a complete, structured script from real news given a model key.
- The voice stage produces audio of a sane length and the renderer's input file.
- The renderer compiles and bundles cleanly, and in CI produces a non-empty video whose length matches the audio.
- The upload stage publishes to YouTube and records the result in the history file.
- The schedule publishes exactly once per intended slot, and manual triggering works.
- The weekly health check validates the upload token and model key.
- Any stage failure returns a precise exit code and produces an alert.
- The README documents the free-tool stack, the secret setup, how to change the run time, and the honest monetization caveat.

---

*This is an instruction set, not an implementation. Hand Sections 2 and 5 to your coding agent to execute, and hold the result to Sections 3, 4, and 6–11.*
