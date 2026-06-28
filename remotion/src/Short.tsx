import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";

const fontFamily = "'Poppins', sans-serif";

export const shortSchema = z.object({
  title: z.string(),
  topicTitle: z.string(),
  accent: z.string(),
  // richer-visuals theme fields (all optional with safe defaults)
  accent2: z.string().default(""),
  pattern: z.enum(["grid", "dots", "rings", "diagonal"]).default("grid"),
  heroImage: z.string().default(""),
  audioSrc: z.string(),
  durationSeconds: z.number(),
  // word-level timings are optional / often empty from TTS — we no longer depend on them
  words: z
    .array(z.object({ text: z.string(), start: z.number(), end: z.number() }))
    .default([]),
  lines: z.array(z.string()).default([]),
  points: z
    .array(z.object({ heading: z.string(), detail: z.string() }))
    .default([]),
  flow: z.array(z.string()).default([]),
});

type Props = z.infer<typeof shortSchema>;

/* ----------------------------- color helpers ----------------------------- */
const hexToRgb = (h: string): [number, number, number] => {
  const n = parseInt(h.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const toHex = (rgb: number[]) =>
  "#" +
  rgb
    .map((x) => Math.round(Math.max(0, Math.min(255, x))).toString(16).padStart(2, "0"))
    .join("");

// rotate a hex color's hue by `deg` degrees (for a vibrant 2-tone gradient)
const shiftHue = (hex: string, deg: number): string => {
  let [r, g, b] = hexToRgb(hex).map((v) => v / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h /= 6;
  }
  h = (((h * 360 + deg) % 360) + 360) % 360 / 360;
  const hue2rgb = (p: number, q: number, t: number) => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  let r2 = l;
  let g2 = l;
  let b2 = l;
  if (s !== 0) {
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r2 = hue2rgb(p, q, h + 1 / 3);
    g2 = hue2rgb(p, q, h);
    b2 = hue2rgb(p, q, h - 1 / 3);
  }
  return toHex([r2 * 255, g2 * 255, b2 * 255]);
};

const sceneOpacity = (frame: number, start: number, end: number, fade = 10) =>
  interpolate(frame, [start, start + fade, end - fade, end], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

/* ------------------------------ background -------------------------------- */
// Per-topic pattern overlays (richer visuals).
const patternStyle = (pattern: string): React.CSSProperties => {
  switch (pattern) {
    case "dots":
      return {
        backgroundImage: "radial-gradient(rgba(255,255,255,0.10) 2px, transparent 2px)",
        backgroundSize: "60px 60px",
      };
    case "rings":
      return {
        backgroundImage: "repeating-radial-gradient(circle at 50% 40%, rgba(255,255,255,0.07) 0 2px, transparent 2px 70px)",
      };
    case "diagonal":
      return {
        backgroundImage: "repeating-linear-gradient(45deg, rgba(255,255,255,0.06) 0 2px, transparent 2px 46px)",
      };
    case "grid":
    default:
      return {
        backgroundImage:
          "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
        backgroundSize: "100px 100px",
      };
  }
};

const Background: React.FC<{ accent: string; accent2?: string; pattern?: string; heroImage?: string }> = ({
  accent,
  accent2,
  pattern = "grid",
  heroImage,
}) => {
  const frame = useCurrentFrame();
  const c1 = accent;
  const c2 = accent2 && accent2.startsWith("#") ? accent2 : shiftHue(accent, 55);
  const c3 = shiftHue(accent, -50);
  const angle = (frame * 0.7) % 360;
  const x1 = 50 + Math.sin(frame / 50) * 22;
  const x2 = 50 + Math.cos(frame / 65) * 22;
  return (
    <AbsoluteFill style={{ background: `linear-gradient(${angle}deg, ${c3}, #0b0d17 78%)` }}>
      <AbsoluteFill style={{ background: `radial-gradient(60% 42% at ${x1}% 20%, ${c1}dd, transparent 60%)` }} />
      <AbsoluteFill style={{ background: `radial-gradient(55% 38% at ${x2}% 82%, ${c2}bb, transparent 60%)` }} />
      <AbsoluteFill style={{ background: `radial-gradient(45% 30% at 82% 52%, ${c1}66, transparent 60%)` }} />
      {/* Optional hero image from the source article — native <img> so a broken
          URL can never fail the render; kept faint and behind all content. */}
      {heroImage ? (
        <AbsoluteFill style={{ maskImage: "radial-gradient(75% 60% at 50% 30%, black, transparent)" }}>
          <img
            src={heroImage}
            style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.16 }}
          />
        </AbsoluteFill>
      ) : null}
      <AbsoluteFill
        style={{
          ...patternStyle(pattern),
          maskImage: "radial-gradient(80% 70% at 50% 40%, black, transparent)",
        }}
      />
    </AbsoluteFill>
  );
};

const MAIN: React.CSSProperties = {
  position: "absolute",
  top: 300,
  left: 64,
  right: 64,
  bottom: 560,
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
};

/* ------------------------------ topic chip -------------------------------- */
const TopicChip: React.FC<{ label: string; accent: string }> = ({ label, accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 14 } });
  return (
    <div
      style={{
        position: "absolute",
        top: 150,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        transform: `translateY(${interpolate(s, [0, 1], [-40, 0])}px)`,
        opacity: s,
      }}
    >
      <div
        style={{
          padding: "16px 36px",
          borderRadius: 999,
          background: "rgba(255,255,255,0.10)",
          border: `2px solid ${accent}`,
          color: "#fff",
          fontSize: 40,
          fontWeight: 700,
          letterSpacing: 1,
          boxShadow: `0 0 30px ${accent}66`,
        }}
      >
        ● {label}
      </div>
    </div>
  );
};

/* -------------------------------- hook ------------------------------------ */
const Hook: React.FC<{ title: string; accent: string; start: number; end: number }> = ({
  title,
  accent,
  start,
  end,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - start, fps, config: { damping: 16 } });
  return (
    <div style={{ ...MAIN, opacity: sceneOpacity(frame, start, end, 12) }}>
      <div
        style={{
          transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)`,
          fontSize: 100,
          fontWeight: 900,
          color: "#fff",
          lineHeight: 1.04,
          textShadow: `0 8px 40px ${accent}aa`,
        }}
      >
        {title}
      </div>
    </div>
  );
};

/* ---------------------------- feature cards ------------------------------- */
const Cards: React.FC<{
  points: Props["points"];
  accent: string;
  start: number;
  end: number;
}> = ({ points, accent, start, end }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.max(1, points.length);
  const slot = (end - start) / n;
  const idx = Math.min(n - 1, Math.max(0, Math.floor((frame - start) / slot)));
  const localStart = start + idx * slot;
  const s = spring({ frame: frame - localStart, fps, config: { damping: 14, stiffness: 130 } });
  const p = points[idx] || { heading: "", detail: "" };
  return (
    <div style={{ ...MAIN, opacity: sceneOpacity(frame, start, end, 10) }}>
      <div style={{ display: "flex", gap: 14, marginBottom: 44 }}>
        {points.map((_, i) => (
          <div
            key={i}
            style={{
              width: i === idx ? 56 : 18,
              height: 18,
              borderRadius: 99,
              background: i === idx ? accent : "rgba(255,255,255,0.25)",
            }}
          />
        ))}
      </div>
      <div
        style={{
          transform: `translateY(${interpolate(s, [0, 1], [44, 0])}px) scale(${interpolate(
            s,
            [0, 1],
            [0.92, 1]
          )})`,
          background: "rgba(15,12,32,0.5)",
          border: `2px solid ${accent}80`,
          borderRadius: 44,
          padding: "56px 52px",
          boxShadow: `0 24px 80px rgba(0,0,0,0.45), 0 0 60px ${accent}40`,
        }}
      >
        <div
          style={{
            fontSize: 36,
            fontWeight: 800,
            color: accent,
            letterSpacing: 3,
            textTransform: "uppercase",
          }}
        >
          Highlight {idx + 1}
        </div>
        <div style={{ fontSize: 90, fontWeight: 900, color: "#fff", lineHeight: 1.05, margin: "16px 0 22px" }}>
          {p.heading}
        </div>
        <div style={{ fontSize: 52, fontWeight: 500, color: "rgba(255,255,255,0.9)", lineHeight: 1.25 }}>
          {p.detail}
        </div>
      </div>
    </div>
  );
};

/* ------------------------------ flow diagram ------------------------------ */
const Flow: React.FC<{ flow: string[]; accent: string; start: number; end: number }> = ({
  flow,
  accent,
  start,
  end,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = flow.length;
  const step = (end - start - 24) / Math.max(1, n);
  return (
    <div style={{ ...MAIN, alignItems: "center", opacity: sceneOpacity(frame, start, end, 10) }}>
      <div
        style={{
          fontSize: 40,
          fontWeight: 800,
          color: accent,
          letterSpacing: 3,
          textTransform: "uppercase",
          marginBottom: 36,
        }}
      >
        How it works
      </div>
      {flow.map((label, i) => {
        const s = spring({ frame: frame - (start + i * step), fps, config: { damping: 15 } });
        return (
          <React.Fragment key={i}>
            <div
              style={{
                opacity: s,
                transform: `translateY(${interpolate(s, [0, 1], [26, 0])}px) scale(${interpolate(
                  s,
                  [0, 1],
                  [0.9, 1]
                )})`,
                background: "rgba(15,12,32,0.6)",
                border: `3px solid ${accent}`,
                borderRadius: 28,
                padding: "30px 46px",
                minWidth: 520,
                textAlign: "center",
                fontSize: 56,
                fontWeight: 800,
                color: "#fff",
                boxShadow: `0 0 44px ${accent}55`,
              }}
            >
              {label}
            </div>
            {i < n - 1 && (
              <div style={{ opacity: s, fontSize: 60, lineHeight: 1, color: accent, margin: "8px 0" }}>↓</div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

/* --------------------------------- CTA ------------------------------------ */
const Cta: React.FC<{ accent: string; start: number; end: number }> = ({ accent, start, end }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - start, fps, config: { damping: 12, stiffness: 120 } });
  return (
    <div style={{ ...MAIN, alignItems: "center", textAlign: "center", opacity: sceneOpacity(frame, start, end, 12) }}>
      <div style={{ fontSize: 130, transform: `scale(${interpolate(s, [0, 1], [0.5, 1])})` }}>🔔</div>
      <div style={{ fontSize: 84, fontWeight: 900, color: "#fff", marginTop: 24, lineHeight: 1.1 }}>
        Follow for daily AI updates
      </div>
      <div style={{ fontSize: 50, fontWeight: 600, color: accent, marginTop: 18 }}>
        New Short every morning 🇮🇳
      </div>
    </div>
  );
};

/* ------------------------------ subtitles --------------------------------- */
const Subtitles: React.FC<{ lines: string[]; accent: string }> = ({ lines, accent }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  if (!lines.length) return null;

  // split the whole timeline across lines, weighted by character length
  const weights = lines.map((l) => Math.max(8, l.length));
  const sum = weights.reduce((a, b) => a + b, 0);
  let acc = 0;
  const wins = lines.map((l) => {
    const startF = (acc / sum) * durationInFrames;
    acc += Math.max(8, l.length);
    const endF = (acc / sum) * durationInFrames;
    return { l, startF, endF };
  });
  const cur = wins.find((w) => frame >= w.startF && frame < w.endF) || wins[wins.length - 1];
  const fade = Math.min(8, (cur.endF - cur.startF) / 3);
  const op = interpolate(
    frame,
    [cur.startF, cur.startF + fade, cur.endF - fade, cur.endF],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div style={{ position: "absolute", bottom: 210, left: 60, right: 60, textAlign: "center", opacity: op }}>
      <span
        style={{
          fontSize: 62,
          fontWeight: 800,
          color: "#fff",
          lineHeight: 1.25,
          textShadow: "0 4px 18px rgba(0,0,0,0.85)",
          background: "rgba(11,13,23,0.42)",
          borderRadius: 22,
          padding: "10px 22px",
          boxDecorationBreak: "clone",
          WebkitBoxDecorationBreak: "clone",
          borderBottom: `5px solid ${accent}`,
        }}
      >
        {cur.l}
      </span>
    </div>
  );
};

/* ------------------------------- progress --------------------------------- */
const Progress: React.FC<{ accent: string }> = ({ accent }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const pct = interpolate(frame, [0, durationInFrames], [0, 100], { extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", bottom: 80, left: 90, right: 90, height: 12, borderRadius: 8, background: "rgba(255,255,255,0.14)" }}>
      <div style={{ width: `${pct}%`, height: "100%", borderRadius: 8, background: accent, boxShadow: `0 0 18px ${accent}` }} />
    </div>
  );
};

/* ------------------------------ composition ------------------------------- */
export const Short: React.FC<Props> = ({
  title,
  topicTitle,
  accent,
  accent2,
  pattern,
  heroImage,
  audioSrc,
  lines,
  points,
  flow,
}) => {
  const { durationInFrames } = useVideoConfig();
  const D = durationInFrames;
  const hasFlow = flow.length >= 2;

  const introEnd = D * 0.15;
  const cardsEnd = hasFlow ? D * 0.62 : D * 0.85;
  const diagramEnd = D * 0.85;
  const ctaStart = D * 0.85;

  return (
    <AbsoluteFill style={{ fontFamily, backgroundColor: "#0b0d17" }}>
      <Background accent={accent} accent2={accent2} pattern={pattern} heroImage={heroImage} />
      <Audio src={audioSrc.startsWith("http") ? audioSrc : staticFile(audioSrc)} />
      <TopicChip label={topicTitle} accent={accent} />

      <Hook title={title} accent={accent} start={0} end={introEnd} />
      <Cards points={points} accent={accent} start={introEnd} end={cardsEnd} />
      {hasFlow && <Flow flow={flow} accent={accent} start={cardsEnd} end={diagramEnd} />}
      <Cta accent={accent} start={ctaStart} end={D} />

      <Subtitles lines={lines} accent={accent} />
      <Progress accent={accent} />
    </AbsoluteFill>
  );
};
