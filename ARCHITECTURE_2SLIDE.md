<section class="slide cover">
<div class="eyebrow">YouTube AI Shorts Platform</div>
<h1>Automated Twice-Daily Content Engine</h1>
<p class="subtitle">From live topic discovery to published YouTube Short in a fully unattended pipeline</p>

<div class="pill-row">
  <span class="pill">09:00 IST</span>
  <span class="pill">21:00 IST</span>
  <span class="pill">Free Tooling</span>
  <span class="pill">No Manual Ops</span>
</div>

<div class="grid-2">
  <div class="card">
    <h3>What It Does</h3>
    <ul>
      <li>Selects topic (rotate or trending)</li>
      <li>Fetches latest relevant features</li>
      <li>Generates structured script with Gemini</li>
      <li>Synthesizes voice and captions</li>
      <li>Renders animated vertical video</li>
      <li>Uploads to YouTube with metadata and thumbnail</li>
    </ul>
  </div>
  <div class="card dark">
    <h3>Architecture Flow</h3>
    <pre>
GitHub Actions (15-min poll)
  -> Gate (IST slot + de-dup)
  -> Test (pytest)
  -> Publish Stages:
      1) Script   2) Voice
      3) Render   4) Upload
  -> history.json commit

External integrations:
- Gemini (google-genai)
- edge-tts
- Remotion + ffmpeg
- YouTube Data API v3
    </pre>
  </div>
</div>

<div class="footer-band">
  Business value: predictable publishing cadence, low operational cost, auditable automation.
</div>
</section>

<div class="page-break"></div>

<section class="slide">
<h2>Detailed Pipeline and Control Points</h2>

<div class="timeline">
  <div class="step"><span>1</span><b>Topic Strategy</b><em>Rotate or trending mode with cooldown.</em></div>
  <div class="step"><span>2</span><b>Feature Fetch</b><em>RSS + Google News, then freshness and relevance filtering.</em></div>
  <div class="step"><span>3</span><b>Script AI</b><em>Gemini generates strict JSON: title, lines, points, flow.</em></div>
  <div class="step"><span>4</span><b>Voice + Timing</b><em>edge-tts creates voice.mp3 and captions.</em></div>
  <div class="step"><span>5</span><b>Animation Render</b><em>Remotion renders vertical out.mp4 from typed props.</em></div>
  <div class="step"><span>6</span><b>YouTube Publish</b><em>Resumable upload with retry and metadata.</em></div>
</div>

<div class="grid-2 compact">
  <div class="card">
    <h3>Governance & Reliability</h3>
    <ul>
      <li>Gate windows: 09:00-12:00 and 21:00-00:00 IST</li>
      <li>Exactly one successful run per slot (de-dup)</li>
      <li>Stage separation improves observability</li>
      <li>Typed exceptions + retries for transient failures</li>
      <li>No database, auditable state in history.json</li>
    </ul>
  </div>
  <div class="card accent">
    <h3>Audience Outcomes</h3>
    <ul>
      <li><b>Senior Managers:</b> predictable output and cost control</li>
      <li><b>Enterprise Architects:</b> clear contracts and resilient orchestration</li>
      <li><b>Development Managers:</b> isolated stages and faster troubleshooting</li>
    </ul>
    <p class="kpi">End result: <b>twice-daily, fully automated Shorts publishing</b>.</p>
  </div>
</div>
</section>
