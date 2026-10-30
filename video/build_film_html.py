import json, os

VIDEO_DIR = r"c:\Users\HP LAPTOP\Documents\NVIDIA\video"
AUDIO_JSON = os.path.join(VIDEO_DIR, "assets", "audio", "voiceover_data.json")
OUT_HTML = os.path.join(VIDEO_DIR, "film.html")

with open(AUDIO_JSON, "r", encoding="utf-8") as f:
    vo_data = json.load(f)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MJOLNIR — Launch & Judge Film</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    width: 1920px;
    height: 1080px;
    overflow: hidden;
    background: #f7f7f7;
    -webkit-font-smoothing: antialiased;
  }
  canvas {
    display: block;
    width: 1920px;
    height: 1080px;
  }
</style>
</head>
<body>
<canvas id="stage" width="1920" height="1080"></canvas>
<script>
const VO = __VO_DATA__;
const CUES = VO.cues;
const W = 1920, H = 1080;

const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d', { alpha: false });
const subCanvas = document.createElement('canvas');
subCanvas.width = W;
subCanvas.height = H;
const sctx = subCanvas.getContext('2d', { alpha: false });

// Brand Palette (Matches static/index.html & static/app.html)
const COL = {
  paper: '#f7f7f7',
  ground: '#eef1ee',
  dot: '#d9e0db',
  ink: '#0d2a1c',
  muted: '#4f5d55',
  volt: '#f6e016',
  emerald: '#157347',
  mint: '#34d399',
  mintBg: '#dcfae5',
  crimson: '#c81e1e',
  crimsonBg: '#fee2e2',
  cyan: '#0ea5e9',
  forestDark: '#091f15',
  forestCard: '#113323',
  forestLine: '#214d38'
};

// Preload 2x Retina UI Screenshots
const IMG_PATHS = {
  landing: 'assets/ui/landing_hero.png',
  appDefault: 'assets/ui/app_default.png',
  appVerified: 'assets/ui/app_verified_result.png',
  appScrolled: 'assets/ui/app_diff_scrolled.png'
};
const IMGS = {};

// Math & Closed-Form Spring Helpers (Pure functions of time — zero state between frames)
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, u) => a + (b - a) * u;
const logLerp = (z0, z1, u) => Math.exp(lerp(Math.log(z0), Math.log(z1), u));
const easeOutCubic = u => { u = clamp(u, 0, 1); return 1 - Math.pow(1 - u, 3); };
const easeInOutCubic = u => { u = clamp(u, 0, 1); return u < 0.5 ? 4*u*u*u : 1 - Math.pow(-2*u + 2, 3)/2; };
const easeInCubic = u => { u = clamp(u, 0, 1); return u*u*u; };
const smoothstep = (t0, t1, t) => easeInOutCubic(clamp((t - t0) / Math.max(0.0001, t1 - t0), 0, 1));
const easeOutWindow = (t0, dur, t) => easeOutCubic(clamp((t - t0) / Math.max(0.0001, dur), 0, 1));

function spring(dt, freq = 14.0, zeta = 0.76) {
  if (dt <= 0) return 0;
  if (dt > 2.5) return 1;
  if (zeta < 1.0) {
    const wd = freq * Math.sqrt(1 - zeta * zeta);
    return 1 - Math.exp(-zeta * freq * dt) * (Math.cos(wd * dt) + (zeta / Math.sqrt(1 - zeta * zeta)) * Math.sin(wd * dt));
  }
  return 1 - Math.exp(-freq * dt) * (1 + freq * dt);
}

// Deterministic seeded hash
function hash01(i) {
  let x = Math.sin(i * 127.1 + 311.7) * 43758.5453123;
  return x - Math.floor(x);
}

// Draw minimalist geometric person/agent icon (Circle Head + Rounded-Square Body)
function drawFigure(c, x, y, scale, fill, strokeCol = null, alpha = 1.0, tiltRad = 0, badge = null) {
  if (alpha <= 0.01 || scale <= 0.01) return;
  c.save();
  c.globalAlpha *= alpha;
  c.translate(x, y);
  if (tiltRad !== 0) c.rotate(tiltRad);
  c.scale(scale, scale);

  // Head (circle)
  c.fillStyle = fill;
  c.beginPath();
  c.arc(0, -19, 8.2, 0, Math.PI * 2);
  c.fill();
  if (strokeCol) {
    c.strokeStyle = strokeCol;
    c.lineWidth = 1.6;
    c.stroke();
  }

  // Body (rounded square torso)
  c.beginPath();
  c.roundRect(-12, -8, 24, 25, 6);
  c.fill();
  if (strokeCol) {
    c.stroke();
  }

  // Optional crisp status symbol on chest ('x' or 'check' or 'bolt')
  if (badge === 'x') {
    c.strokeStyle = '#ffffff';
    c.lineWidth = 2.2;
    c.lineCap = 'round';
    c.beginPath();
    c.moveTo(-4, 0.5); c.lineTo(4, 8.5);
    c.moveTo(4, 0.5); c.lineTo(-4, 8.5);
    c.stroke();
  } else if (badge === 'check') {
    c.strokeStyle = '#091f15';
    c.lineWidth = 2.4;
    c.lineCap = 'round';
    c.lineJoin = 'round';
    c.beginPath();
    c.moveTo(-4.5, 4.5); c.lineTo(-1, 8.2); c.lineTo(5, 0.5);
    c.stroke();
  }
  c.restore();
}

// Draw masked kinetic line of text (rises cleanly from baseline clip, zero fade-slop)
function drawMaskedText(c, text, x, y, progress, opts = {}) {
  if (progress <= 0.001) return;
  const font = opts.font || '600 54px "Hanken Grotesk"';
  const color = opts.color || COL.ink;
  const align = opts.align || 'left';
  const height = opts.clipH || 76;
  c.save();
  c.font = font;
  c.textAlign = align;
  c.textBaseline = 'alphabetic';
  c.beginPath();
  c.rect(x - (align === 'center' ? 960 : align === 'right' ? 1400 : 20), y - height + 14, 1920, height + 10);
  c.clip();
  const yOff = (1 - progress) * (height * 0.92);
  c.fillStyle = color;
  c.fillText(text, x, y + yOff);
  c.restore();
}

// Draw crisp macOS vector cursor (scales with camera, rotates gently into motion)
function drawCursor(c, x, y, scale = 1.0, press = 0.0, rotRad = 0.0) {
  c.save();
  c.translate(x, y);
  c.rotate(rotRad);
  const s = scale * (1 - 0.16 * press);
  c.scale(s, s);
  // Fast offset drop shadow (avoids CPU shadowBlur)
  c.save();
  c.translate(2, 5);
  c.beginPath();
  c.moveTo(0, 0); c.lineTo(0, 31); c.lineTo(8.2, 23.5); c.lineTo(14.5, 36);
  c.lineTo(19.5, 33.5); c.lineTo(13.2, 21.2); c.lineTo(23.5, 21.2); c.closePath();
  c.fillStyle = 'rgba(0,0,0,0.22)';
  c.fill();
  c.restore();

  c.beginPath();
  c.moveTo(0, 0);
  c.lineTo(0, 31);
  c.lineTo(8.2, 23.5);
  c.lineTo(14.5, 36);
  c.lineTo(19.5, 33.5);
  c.lineTo(13.2, 21.2);
  c.lineTo(23.5, 21.2);
  c.closePath();
  c.fillStyle = '#0d2a1c';
  c.fill();
  c.lineWidth = 2.4;
  c.strokeStyle = '#ffffff';
  c.stroke();
  c.restore();
}

// Draw studio dot grid in world space
function drawDotGrid(c, spacing, dotColor, xMin, xMax, yMin, yMax) {
  c.fillStyle = dotColor;
  for (let gx = xMin; gx <= xMax; gx += spacing) {
    for (let gy = yMin; gy <= yMax; gy += spacing) {
      c.fillRect(gx - 1.2, gy - 1.2, 2.4, 2.4);
    }
  }
}

// Draw 3D perspective tilted image (1880px telephoto horizontal strip projection — zero WebGL context loss)
function drawTiltedSheet(c, img, cx, cy, drawW, drawH, pitchDeg, shadowAlpha = 0.18) {
  if (!img || !img.complete) return;
  const rad = pitchDeg * Math.PI / 180;
  const focal = 1880;
  const strips = 96;

  // Fast GPU-friendly layered soft studio floor shadow (avoids slow CPU ctx.filter blur)
  c.save();
  const botScale = focal / (focal - (drawH * 0.5) * Math.sin(rad));
  const sw = drawW * botScale * 0.98;
  const sh0 = drawH * Math.cos(rad) * 0.96;
  for (let layer = 3; layer >= 1; layer--) {
    const pad = layer * 14;
    c.fillStyle = `rgba(13, 42, 28, ${(shadowAlpha * 0.34).toFixed(3)})`;
    c.beginPath();
    c.roundRect(
      cx - sw * 0.5 - pad * 0.6,
      cy - sh0 * 0.46 + 22 + layer * 5,
      sw + pad * 1.2,
      sh0 + pad * 0.7,
      22 + pad * 0.5
    );
    c.fill();
  }
  c.restore();

  // Perspective horizontal slices
  for (let i = 0; i < strips; i++) {
    const v0 = i / strips;
    const v1 = (i + 1.35) / strips;
    const ly0 = (v0 - 0.5) * drawH;
    const ly1 = (min1(v1) - 0.5) * drawH;

    // Top tilts away (+z), bottom comes toward lens (-z)
    const z0 = (0.5 - v0) * drawH * Math.sin(rad);
    const z1 = (0.5 - min1(v1)) * drawH * Math.sin(rad);
    const p0 = focal / (focal + z0);
    const p1 = focal / (focal + z1);

    const sy0 = cy + ly0 * Math.cos(rad) * p0;
    const sy1 = cy + ly1 * Math.cos(rad) * p1;
    const wMid = drawW * 0.5 * (p0 + p1);
    const sh = Math.max(1, sy1 - sy0);

    c.drawImage(
      img,
      0, v0 * img.naturalHeight, img.naturalWidth, (min1(v1) - v0) * img.naturalHeight,
      cx - wMid * 0.5, sy0, wMid, sh
    );
  }
}
const min1 = x => x > 1 ? 1 : x;

// =========================================================================
// ACT 1 + ACT 2: WARM STUDIO WORLD (100 Figures -> Whip-Pan -> Two-Way Fork)
// =========================================================================
function renderActs1And2(c, t) {
  c.fillStyle = COL.paper;
  c.fillRect(0, 0, W, H);

  // Camera trajectory across World Zone 1 (center 960, 445) -> Whip-pan to Zone 2 (center 2960, 445)
  const whipStart = CUES.act2_why - 0.16;
  const whipProg = smoothstep(whipStart, whipStart + 0.52, t);

  let camX = lerp(960, 2960, whipProg);
  let camY = 445;
  let zoom = 1.0;

  if (t < whipStart) {
    // Act 1 camera: 1.28 -> 1.00 intro settle, then push 1.00 -> 1.12 on 15x cost, subtle pull to 1.04 on 70 fail
    const introU = easeOutCubic(clamp(t / 1.35, 0, 1));
    const baseZ = logLerp(1.26, 1.00, introU);
    const costPush = smoothstep(CUES.cost_15x - 0.25, CUES.cost_15x + 1.1, t);
    const failSettle = smoothstep(CUES.seventy_fail, CUES.seventy_fail + 0.9, t);
    zoom = baseZ * logLerp(1.0, 1.11, costPush) * logLerp(1.0, 0.95, failSettle) * (1 + 0.004 * t);
    camX = 960 + costPush * 36 - failSettle * 20;
  } else {
    // Act 2 camera: pan gently left on API fork, right on Math fork, pull back on web pollution
    const apiPan = smoothstep(CUES.fork_api - 0.2, CUES.fork_api + 0.7, t);
    const mathPan = smoothstep(CUES.fork_math - 0.2, CUES.fork_math + 0.7, t);
    const widePull = smoothstep(CUES.web_pollute - 0.2, CUES.web_pollute + 0.6, t);
    camX = 2960 - 150 * apiPan + 300 * mathPan - 150 * widePull;
    camY = 445 + 14 * apiPan - 14 * widePull;
    zoom = logLerp(1.02, 1.13, apiPan) * logLerp(1.0, 0.91, widePull) * (1 + 0.003 * (t - CUES.act2_why));
  }

  c.save();
  c.translate(W / 2, 445);
  c.scale(zoom, zoom);
  c.translate(-camX, -camY);

  // Studio dot grid spanning both zones
  drawDotGrid(c, 56, COL.dot, -200, 4200, -200, 1100);

  // ---------------- ZONE 1: THE 100 GEOMETRIC FIGURES (x ~ 960) ----------------
  if (camX < 2350) {
    const gridX0 = 260, gridY0 = 215;
    const stepX = 64, stepY = 58;

    // Header badge + Kinetic title above grid
    const hProg = spring(t - 0.06, 15, 0.82);
    drawMaskedText(c, '100 REAL CODING TASKS  ·  550B MODEL ALONE', gridX0 - 12, 148, hProg, {
      font: '600 26px "IBM Plex Mono"', color: COL.muted
    });

    // Scanning beam during first 4.2s
    if (t > 0.5 && t < CUES.seventy_fail + 0.3) {
      const scanY = gridY0 - 25 + ((t * 195) % (10 * stepY + 20));
      const grad = c.createLinearGradient(0, scanY - 36, 0, scanY + 12);
      grad.addColorStop(0, 'rgba(246, 224, 22, 0)');
      grad.addColorStop(1, 'rgba(246, 224, 22, 0.28)');
      c.fillStyle = grad;
      c.fillRect(gridX0 - 32, scanY - 36, 9 * stepX + 64, 48);
    }

    // Draw the 10 x 10 = 100 minimalist figures!
    let passedCount = 100;
    let failedCount = 0;

    for (let row = 0; row < 10; row++) {
      for (let col = 0; col < 10; col++) {
        const idx = row * 10 + col;
        const enterDelay = 0.04 + (row * 0.032 + col * 0.022);
        const popS = spring(t - enterDelay, 16, 0.72);
        if (popS <= 0.01) continue;

        let fx = gridX0 + col * stepX;
        let fy = gridY0 + row * stepY;

        // Subtle organic idle breathe so nothing is ever frozen
        const breathe = Math.sin(t * 3.4 + idx * 0.43) * 2.0;
        fy += breathe;

        // Cost pulse ripple when "fifteen times more" hits
        const costDt = t - (CUES.cost_15x + (col + row) * 0.025);
        let fill = COL.ink;
        let tilt = 0;
        let badge = null;
        let figScale = 0.88 * popS;

        if (costDt > 0 && t < CUES.seventy_fail + (row * 0.04)) {
          const pulse = Math.exp(-costDt * 2.8);
          figScale *= (1 + 0.14 * pulse);
          if (pulse > 0.25) fill = '#9a6b00';
        }

        // At CUES.seventy_fail (6.44s): bottom 7 rows (70 figures!) fail on 2026 API update!
        const isFailing = idx >= 30;
        const failDt = t - (CUES.seventy_fail + (row - 3) * 0.055 + hash01(idx) * 0.09);

        if (t >= CUES.seventy_fail) {
          if (isFailing && failDt > 0) {
            failedCount++;
            passedCount--;
            const dropP = spring(failDt, 13, 0.68);
            fill = COL.crimson;
            const dir = (idx % 2 === 0 ? 1 : -1);
            tilt = dir * (0.28 + 0.22 * hash01(idx + 7)) * dropP;
            fy += 13 * dropP;
            figScale *= (1 - 0.08 * dropP);
            badge = 'x';
          } else if (!isFailing && t > CUES.seventy_fail + 0.25) {
            fill = COL.emerald;
          }
        }

        drawFigure(c, fx, fy, figScale, fill, null, 1.0, tilt, badge);
      }
    }

    // Right-Side Dynamic Visual Telemetry (Zero rectangular static cards — pure kinetic rings & counters!)
    const rightX = 1360;
    const costP = smoothstep(CUES.cost_15x - 0.15, CUES.cost_15x + 0.85, t);
    const failP = smoothstep(CUES.seventy_fail, CUES.seventy_fail + 0.75, t);

    // Animated Orbital Cost Ring (1x -> 15x COST)
    const ringY = 335;
    const ringR = 96;
    c.save();
    c.translate(rightX, ringY);
    c.strokeStyle = '#dce2de';
    c.lineWidth = 14;
    c.beginPath();
    c.arc(0, 0, ringR, 0, Math.PI * 2);
    c.stroke();

    const sweepAngle = lerp(0.18, 1.0, costP) * Math.PI * 2;
    c.strokeStyle = costP > 0.1 ? '#d97706' : COL.ink;
    c.lineCap = 'round';
    c.beginPath();
    c.arc(0, 0, ringR, -Math.PI / 2, -Math.PI / 2 + sweepAngle);
    c.stroke();

    // Multiplier readout inside ring
    const multVal = lerp(1.0, 15.0, costP);
    c.fillStyle = COL.ink;
    c.font = '700 52px "Hanken Grotesk"';
    c.textAlign = 'center';
    c.textBaseline = 'middle';
    c.fillText(`${multVal.toFixed(costP > 0.92 ? 0 : 1)}x`, 0, -6);
    c.font = '500 18px "IBM Plex Mono"';
    c.fillStyle = COL.muted;
    c.fillText('TOKEN COST', 0, 34);
    c.restore();

    // Live Failing vs Standing Counter below ring
    if (t > CUES.seventy_fail - 0.1) {
      const sPop = spring(t - CUES.seventy_fail, 14, 0.78);
      c.save();
      c.translate(rightX, 585);
      c.scale(0.85 + 0.15 * sPop, 0.85 + 0.15 * sPop);
      c.globalAlpha = clamp(sPop * 1.3, 0, 1);

      c.fillStyle = COL.crimson;
      c.font = '700 84px "Hanken Grotesk"';
      c.textAlign = 'center';
      c.fillText(`${failedCount} / 100`, 0, 0);

      c.font = '600 22px "IBM Plex Mono"';
      c.fillText('FAILED ON 2026 API UPDATES', 0, 38);

      // Pill tag
      c.fillStyle = COL.crimsonBg;
      c.beginPath();
      c.roundRect(-195, 62, 390, 42, 21);
      c.fill();
      c.fillStyle = COL.crimson;
      c.font = '600 18px "IBM Plex Mono"';
      c.fillText('Nemotron-Ultra Bare: 0/6 on new APIs', 0, 89);
      c.restore();
    } else if (t > 1.0) {
      c.save();
      c.fillStyle = COL.muted;
      c.font = '500 22px "IBM Plex Mono"';
      c.textAlign = 'center';
      c.fillText('Sending all 100 tasks to 550B...', rightX, 560);
      c.restore();
    }
  }

  // ---------------- ZONE 2: TWO FAILURE MODES FORK (x ~ 2960) ----------------
  if (camX > 1650) {
    const zx = 2960;
    const t2 = t - CUES.act2_why;
    const titleP = spring(t2 - 0.1, 14, 0.82);
    drawMaskedText(c, 'TWO COMPLETELY DIFFERENT BUGS', zx, 136, titleP, {
      font: '700 50px "Hanken Grotesk"', color: COL.ink, align: 'center'
    });

    const splitP = smoothstep(CUES.fork_api - 0.55, CUES.fork_api + 0.35, t);
    const leftX = lerp(zx, zx - 430, splitP);
    const rightX = lerp(zx, zx + 430, splitP);
    const baseY = 470;

    // Connecting rail fork lines
    c.strokeStyle = '#cbd5cf';
    c.lineWidth = 4;
    c.setLineDash([10, 10]);
    c.beginPath();
    c.moveTo(zx, 210);
    c.bezierCurveTo(zx, 310, leftX, 290, leftX, 370);
    c.moveTo(zx, 210);
    c.bezierCurveTo(zx, 310, rightX, 290, rightX, 370);
    c.stroke();
    c.setLineDash([]);

    // --- LEFT RAIL: BRAND-NEW API CHANGED (Plug mismatch animation) ---
    const apiP = spring(t - CUES.fork_api + 0.1, 13, 0.76);
    drawFigure(c, leftX, baseY + Math.sin(t * 4) * 3, 2.85, COL.cyan, null, 1.0, -0.05 * Math.sin(t * 5));

    if (apiP > 0.02) {
      c.save();
      c.translate(leftX, baseY - 145);
      c.globalAlpha = clamp(apiP, 0, 1);

      // Animated Plug vs Reshaped 2026 Socket bouncing back!
      const attempt = Math.abs(Math.sin((t - CUES.fork_api) * 3.8));
      const plugGap = 18 + 34 * attempt;

      // Old 2-prong plug (.dict())
      c.fillStyle = COL.ink;
      c.beginPath();
      c.roundRect(-125 - plugGap * 0.5, -22, 74, 44, 8);
      c.fill();
      c.fillRect(-51 - plugGap * 0.5, -14, 18, 8);
      c.fillRect(-51 - plugGap * 0.5, 6, 18, 8);
      c.fillStyle = '#ffffff';
      c.font = '600 15px "IBM Plex Mono"';
      c.textAlign = 'center';
      c.fillText('.dict()', -88 - plugGap * 0.5, 5);

      // New 2026 3-slot socket (.model_dump)
      c.fillStyle = COL.cyan;
      c.beginPath();
      c.roundRect(45 + plugGap * 0.5, -26, 118, 52, 8);
      c.fill();
      c.fillStyle = '#ffffff';
      c.fillText('2026 API v3', 104 + plugGap * 0.5, 5);

      // Spark symbol on collision
      if (attempt < 0.28) {
        c.strokeStyle = COL.crimson;
        c.lineWidth = 3.5;
        for (let a = 0; a < 6; a++) {
          const ang = (a / 6) * Math.PI * 2;
          c.beginPath();
          c.moveTo(Math.cos(ang) * 8, Math.sin(ang) * 8);
          c.lineTo(Math.cos(ang) * 22, Math.sin(ang) * 22);
          c.stroke();
        }
      }
      c.restore();

      drawMaskedText(c, '1. NEW API CHANGED', leftX, baseY + 135, clamp(apiP, 0, 1), {
        font: '700 34px "Hanken Grotesk"', color: COL.ink, align: 'center'
      });
      drawMaskedText(c, 'Model never saw 2026 docs', leftX, baseY + 174, clamp(apiP, 0, 1), {
        font: '500 21px "IBM Plex Mono"', color: COL.muted, align: 'center'
      });
    }

    // --- RIGHT RAIL: HARD MATH LOGIC + WEB SEARCH POLLUTION ---
    const mathP = spring(t - CUES.fork_math + 0.25, 13, 0.78);
    const pollP = smoothstep(CUES.web_pollute, CUES.web_pollute + 0.8, t);
    const shieldP = spring(t - (CUES.web_pollute + 1.85), 15, 0.78);

    // Wobble balance beam when web clutter hits, then level cleanly when shield snaps in!
    const clutterActive = pollP * (1 - clamp(shieldP, 0, 1));
    const beamTilt = clutterActive * (-0.34 + 0.08 * Math.sin(t * 14));

    drawFigure(
      c, rightX, baseY + Math.sin(t * 4 + 1.5) * 3,
      2.85, clutterActive > 0.35 ? COL.crimson : COL.emerald,
      null, splitP > 0.05 ? 1.0 : 0.0, beamTilt * 0.35
    );

    if (mathP > 0.02) {
      c.save();
      c.translate(rightX, baseY - 135);
      c.rotate(beamTilt);
      c.globalAlpha = clamp(mathP, 0, 1);

      // Precision geometric balance beam + graph nodes
      c.strokeStyle = clutterActive > 0.35 ? COL.crimson : COL.ink;
      c.lineWidth = 5;
      c.beginPath();
      c.moveTo(-120, 0);
      c.lineTo(120, 0);
      c.stroke();

      for (const nx of [-110, 0, 110]) {
        c.fillStyle = nx === 0 ? COL.volt : (clutterActive > 0.35 ? COL.crimson : COL.emerald);
        c.beginPath();
        c.arc(nx, 0, 15, 0, Math.PI * 2);
        c.fill();
        c.strokeStyle = COL.ink;
        c.lineWidth = 2.5;
        c.stroke();
      }
      c.restore();

      drawMaskedText(c, '2. HARD MATH LOGIC', rightX, baseY + 135, clamp(mathP, 0, 1), {
        font: '700 34px "Hanken Grotesk"', color: COL.ink, align: 'center'
      });
      drawMaskedText(
        c,
        pollP > 0.2 ? (shieldP > 0.4 ? 'Shielded: 0 web clutter!' : 'Blind web search pollutes math (-39%)') : 'Needs deeper reasoning, not search',
        rightX, baseY + 174, clamp(mathP, 0, 1),
        { font: '600 20px "IBM Plex Mono"', color: clutterActive > 0.3 ? COL.crimson : COL.emerald, align: 'center' }
      );
    }

    // Falling noisy red web-snippet fragments during pollution window
    if (pollP > 0.02) {
      const tags = ['<blog>', '404 HTML', 'stale stackoverflow', 'ad-noise', 'wrong v1 doc'];
      for (let k = 0; k < 5; k++) {
        const dropCycle = ((t - CUES.web_pollute) * 1.45 + k * 0.21) % 1.0;
        const fragX = rightX - 130 + k * 64;
        let fragY = 180 + dropCycle * 195;
        let fragA = pollP;
        if (shieldP > 0.2 && fragY > 255) {
          fragA *= Math.max(0, 1 - shieldP * 1.5);
          fragY = Math.min(fragY, 255);
        }
        if (fragA > 0.04) {
          c.save();
          c.globalAlpha = fragA;
          c.font = '600 12px "IBM Plex Mono"';
          c.textAlign = 'center';
          const tw = c.measureText(tags[k]).width + 24;
          c.fillStyle = COL.crimsonBg;
          c.strokeStyle = COL.crimson;
          c.lineWidth = 1.5;
          c.beginPath();
          c.roundRect(fragX - tw / 2, fragY - 14, tw, 28, 6);
          c.fill(); c.stroke();
          c.fillStyle = COL.crimson;
          c.fillText(tags[k], fragX, fragY + 4);
          c.restore();
        }
      }

      // Deterministic Shield Bar snapping across above Right Figure
      if (shieldP > 0.02) {
        c.save();
        const sw = 310 * clamp(shieldP, 0, 1);
        c.fillStyle = COL.ink;
        c.beginPath();
        c.roundRect(rightX - sw / 2, 252, sw, 32, 16);
        c.fill();
        if (shieldP > 0.55) {
          c.fillStyle = COL.volt;
          c.font = '600 14px "IBM Plex Mono"';
          c.textAlign = 'center';
          c.fillText('SKIP SEARCH · ZERO POLLUTION', rightX, 273);
        }
        c.restore();
      }
    }
  }

  c.restore();
}

// =========================================================================
// ACT 3: MEET MJOLNIR — LIVING 2D ESCALATION RAILWAY (Dark Forest Stage)
// =========================================================================
function renderAct3(c, t) {
  c.fillStyle = COL.forestDark;
  c.fillRect(0, 0, W, H);

  const localT = t - CUES.act3_mjolnir;
  // Camera tracks gently along the 2D Escalation Track
  const lockFocus = smoothstep(CUES.sandbox_lock - 0.4, CUES.sandbox_lock + 0.5, t);
  const tavFocus = smoothstep(CUES.tavily_3stage - 0.3, CUES.tavily_3stage + 0.7, t);
  const supFocus = smoothstep(CUES.escalate_super - 0.3, CUES.escalate_super + 0.7, t);

  const camX = 960 - 90 * (1 - lockFocus) + 110 * tavFocus + 40 * supFocus;
  const camY = 455 - 45 * tavFocus + 90 * supFocus;
  const zoom = logLerp(1.06, 1.02, clamp(localT / 2.0, 0, 1)) * logLerp(1.0, 1.08, tavFocus) * logLerp(1.0, 0.96, supFocus);

  c.save();
  c.translate(W / 2, 450);
  c.scale(zoom, zoom);
  c.translate(-camX, -camY);

  drawDotGrid(c, 60, '#163828', 0, 2200, 0, 1000);

  // --- RAILWAY TRACKS ---
  const yMid = 470, yTop = 275, yBot = 665;
  const xIn = 140, xNano = 430, xLock = 790, xOut = 1760;

  // Base tracks
  c.lineWidth = 8;
  c.lineCap = 'round';
  // Express center green lane
  c.strokeStyle = '#1d4d35';
  c.beginPath(); c.moveTo(xIn, yMid); c.lineTo(xOut, yMid); c.stroke();

  // Upper Knowledge Axis (Tavily 3-Stage)
  c.strokeStyle = tavFocus > 0.05 ? COL.cyan : '#183c3c';
  c.beginPath();
  c.moveTo(xLock, yMid);
  c.bezierCurveTo(xLock + 110, yMid, xLock + 110, yTop, xLock + 230, yTop);
  c.lineTo(1540, yTop);
  c.bezierCurveTo(1640, yTop, 1650, yMid, xOut, yMid);
  c.stroke();

  // Lower Reasoning Axis (Super 120B -> Ultra 550B)
  c.strokeStyle = supFocus > 0.05 ? COL.volt : '#2a3d24';
  c.beginPath();
  c.moveTo(xLock, yMid);
  c.bezierCurveTo(xLock + 110, yMid, xLock + 110, yBot, xLock + 250, yBot);
  c.lineTo(1540, yBot);
  c.bezierCurveTo(1640, yBot, 1650, yMid, xOut, yMid);
  c.stroke();

  // --- STATION 1: NVIDIA NEMOTRON NANO (NEBIUS) ---
  const nanoP = spring(localT - 0.35, 14, 0.76);
  c.save();
  c.translate(xNano, yMid);
  c.scale(nanoP, nanoP);
  c.fillStyle = COL.forestCard;
  c.strokeStyle = COL.mint;
  c.lineWidth = 3;
  c.beginPath(); c.arc(0, 0, 74, 0, Math.PI * 2); c.fill(); c.stroke();
  // Spinning turbine arc
  c.strokeStyle = COL.volt;
  c.lineWidth = 4;
  c.beginPath(); c.arc(0, 0, 84, t * 4.2, t * 4.2 + 1.9); c.stroke();
  c.fillStyle = '#ffffff';
  c.font = '700 22px "Hanken Grotesk"';
  c.textAlign = 'center';
  c.fillText('Nemotron', 0, -8);
  c.fillStyle = COL.mint;
  c.fillText('Nano', 0, 18);
  c.font = '500 13px "IBM Plex Mono"';
  c.fillStyle = '#9cc5b0';
  c.fillText('NEBIUS FAST PROBE', 0, 108);
  c.restore();

  // --- STATION 2: LOCKED SHA-256 SANDBOX GATE ---
  const lockSnap = spring(t - (CUES.sandbox_lock - 0.2), 16, 0.72);
  c.save();
  c.translate(xLock, yMid);
  // Shackle (closes down on lockSnap!)
  const shackleLift = (1 - clamp(lockSnap, 0, 1)) * 22;
  c.strokeStyle = lockSnap > 0.2 ? COL.volt : '#8fb5a1';
  c.lineWidth = 7;
  c.beginPath();
  c.arc(0, -34 - shackleLift, 24, Math.PI, 0);
  c.lineTo(24, -14);
  c.moveTo(-24, -34 - shackleLift);
  c.lineTo(-24, -14);
  c.stroke();

  // Lock body
  c.fillStyle = lockSnap > 0.2 ? COL.volt : '#e2ece6';
  c.beginPath();
  c.roundRect(-42, -18, 84, 70, 14);
  c.fill();
  c.fillStyle = COL.forestDark;
  c.font = '700 16px "IBM Plex Mono"';
  c.textAlign = 'center';
  c.fillText('LOCKED', 0, 12);
  c.fillText('SHA-256', 0, 34);
  c.fillStyle = '#9cc5b0';
  c.font = '500 13px "IBM Plex Mono"';
  c.fillText('UN-CHEATABLE TEST', 0, 78);
  c.restore();

  // --- UPPER BRANCH: TAVILY 3-STAGE LIVE DOCS (/search -> /extract -> /map) ---
  const stages = ['/search', '/extract', '/map'];
  for (let s = 0; s < 3; s++) {
    const sx = 1070 + s * 195;
    const sp = spring(t - (CUES.tavily_3stage + s * 0.42), 14, 0.75);
    c.save();
    c.translate(sx, yTop);
    const active = sp > 0.1;
    c.fillStyle = active ? '#0c384a' : '#102920';
    c.strokeStyle = active ? COL.cyan : '#274d3d';
    c.lineWidth = active ? 3.5 : 2;
    const sc = 0.88 + 0.12 * clamp(sp, 0, 1);
    c.scale(sc, sc);
    c.beginPath();
    c.roundRect(-72, -34, 144, 68, 34);
    c.fill(); c.stroke();
    c.fillStyle = active ? '#ffffff' : '#6e9483';
    c.font = '600 20px "IBM Plex Mono"';
    c.textAlign = 'center';
    c.fillText(stages[s], 0, 7);
    if (s === 1) {
      c.fillStyle = COL.cyan;
      c.font = '600 15px "IBM Plex Mono"';
      c.fillText('TAVILY LIVE 2026 DOCS', 0, -86);
    }
    c.restore();
  }

  // --- LOWER BRANCH: SKIP SEARCH -> SUPER 120B -> ULTRA 550B ---
  const rungs = [
    { label: 'SKIP SEARCH', sub: '0 Web Noise', x: 1065, col: '#9cc5b0' },
    { label: 'Super 120B', sub: 'Mid Escalation', x: 1275, col: COL.volt },
    { label: 'Ultra 550B', sub: 'Deep Math Reserve', x: 1485, col: COL.mint }
  ];
  for (let r = 0; r < 3; r++) {
    const rp = spring(t - (CUES.escalate_super + r * 0.38), 14, 0.76);
    const rg = rungs[r];
    c.save();
    c.translate(rg.x, yBot);
    const active = rp > 0.1;
    const sc = 0.88 + 0.12 * clamp(rp, 0, 1);
    c.scale(sc, sc);
    c.fillStyle = active ? '#1a3c28' : '#102920';
    c.strokeStyle = active ? rg.col : '#274d3d';
    c.lineWidth = active ? 3.5 : 2;
    c.beginPath();
    c.roundRect(-80, -36, 160, 72, 16);
    c.fill(); c.stroke();
    c.fillStyle = active ? '#ffffff' : '#6e9483';
    c.font = '700 20px "Hanken Grotesk"';
    c.textAlign = 'center';
    c.fillText(rg.label, 0, -2);
    c.fillStyle = active ? rg.col : '#567868';
    c.font = '500 13px "IBM Plex Mono"';
    c.fillText(rg.sub, 0, 20);
    c.restore();
  }

  // EXIT 0 VERIFIED GOAL GATE on far right
  c.save();
  c.translate(xOut, yMid);
  c.fillStyle = COL.mint;
  c.beginPath();
  c.roundRect(-64, -44, 128, 88, 20);
  c.fill();
  c.fillStyle = COL.forestDark;
  c.font = '700 22px "IBM Plex Mono"';
  c.textAlign = 'center';
  c.fillText('EXIT 0', 0, -4);
  c.font = '600 14px "IBM Plex Mono"';
  c.fillText('VERIFIED', 0, 20);
  c.restore();

  // --- ANIMATED GEOMETRIC TASK FIGURES RIDING THE TRACKS! ---
  // 1) Fast green express tasks continuously clearing Nano -> Exit 0
  for (let k = 0; k < 3; k++) {
    const u = ((localT * 0.34 + k * 0.33) % 1.0);
    const fx = lerp(xIn, xOut - 75, u);
    const col = fx > xLock ? COL.mint : '#e2ece6';
    drawFigure(c, fx, yMid - 4, 0.92, col, null, 0.95, 0, fx > xLock ? 'check' : null);
  }

  // 2) API-Gap Hero Figure riding Upper Tavily Branch during tavily_3stage
  if (t >= CUES.tavily_3stage - 0.6) {
    const u = clamp((t - (CUES.tavily_3stage - 0.5)) / 3.6, 0, 1);
    let fx, fy;
    const yTopRide = yTop - 58;
    if (u < 0.22) {
      const k = u / 0.22;
      fx = lerp(xLock, 1020, k);
      fy = lerp(yMid, yTopRide, easeInOutCubic(k));
    } else if (u < 0.80) {
      const k = (u - 0.22) / 0.58;
      fx = lerp(1020, 1520, k);
      fy = yTopRide;
    } else {
      const k = (u - 0.80) / 0.20;
      fx = lerp(1520, xOut - 70, k);
      fy = lerp(yTopRide, yMid, easeInOutCubic(k));
    }
    const fixed = u > 0.72;
    drawFigure(c, fx, fy, 1.22, fixed ? COL.mint : COL.cyan, '#ffffff', 1.0, 0, fixed ? 'check' : null);
  }

  // 3) Hard-Logic Hero Figure riding Lower Super/Ultra Branch during escalate_super
  if (t >= CUES.escalate_super - 0.5) {
    const u = clamp((t - (CUES.escalate_super - 0.4)) / 3.6, 0, 1);
    let fx, fy;
    const yBotRide = yBot - 62;
    if (u < 0.22) {
      const k = u / 0.22;
      fx = lerp(xLock, 1040, k);
      fy = lerp(yMid, yBotRide, easeInOutCubic(k));
    } else if (u < 0.82) {
      const k = (u - 0.22) / 0.60;
      fx = lerp(1040, 1520, k);
      fy = yBotRide;
    } else {
      const k = (u - 0.82) / 0.18;
      fx = lerp(1520, xOut - 70, k);
      fy = lerp(yBotRide, yMid, easeInOutCubic(k));
    }
    const fixed = u > 0.72;
    drawFigure(c, fx, fy, 1.22, fixed ? COL.mint : COL.volt, COL.forestDark, 1.0, 0, fixed ? 'check' : null);
  }

  c.restore();

  // Screen-pinned Top-Left MJOLNIR Banner so camera pan never clips a single letter!
  const brandP = spring(localT - 0.12, 14, 0.8);
  c.save();
  c.fillStyle = COL.volt;
  c.beginPath();
  c.roundRect(88, 66, 44 * clamp(brandP, 0, 1), 44, 11);
  c.fill();
  if (brandP > 0.5) {
    c.fillStyle = COL.forestDark;
    c.beginPath();
    c.roundRect(98, 76, 24, 9, 2.5);
    c.roundRect(106, 85, 8, 15, 2);
    c.fill();
  }
  c.restore();
  drawMaskedText(c, 'MJOLNIR  ·  2D ESCALATION ENGINE', 148, 100, brandP, {
    font: '700 38px "Hanken Grotesk"', color: '#f7f7f7'
  });
}

// =========================================================================
// ACT 4: REAL UI WALKTHROUGH (52° -> 0° 3D Entrance + Cursor-Coupled Log-Zoom)
// =========================================================================
function renderAct4(c, t) {
  c.fillStyle = COL.ground;
  c.fillRect(0, 0, W, H);
  drawDotGrid(c, 52, '#d5ddd7', 0, W, 0, H);

  const inWorkbench = t >= CUES.open_workbench + 0.32;

  if (!inWorkbench) {
    // Phase 4A: Landing Page enters at 52° 3D studio angle -> settles toward frontal, cursor clicks "Open the workbench ->"
    const dt = t - CUES.act4_testing;
    const enterP = easeOutCubic(clamp(dt / 1.35, 0, 1));
    const pitch = lerp(50, 6, enterP);
    const clickHoverP = smoothstep(CUES.open_workbench - 0.9, CUES.open_workbench - 0.05, t);
    const clickPress = (t > CUES.open_workbench && t < CUES.open_workbench + 0.24)
      ? Math.sin(((t - CUES.open_workbench) / 0.24) * Math.PI)
      : 0;

    // Log-zoom into the yellow CTA button on the left of landing_hero.png
    const z = logLerp(0.96, 1.36, clickHoverP);
    const focusX = lerp(960, 520, clickHoverP);
    const focusY = lerp(455, 600, clickHoverP);

    c.save();
    c.translate(W / 2, 445);
    c.scale(z, z);
    c.translate(-focusX, -focusY);

    drawTiltedSheet(c, IMGS.landing, 960, 455, 1360, 850, pitch, 0.22);

    // Cursor glides in onto "Open the workbench ->" button (logical ~ x:445, y:565 in 1360x850 centered at 960,455)
    const ctaX = 960 - 680 + 162;
    const ctaY = 455 - 425 + 528;
    const curU = easeInOutCubic(clamp((dt - 0.45) / (CUES.open_workbench - CUES.act4_testing - 0.45), 0, 1));
    const curX = lerp(1220, ctaX, curU);
    const curY = lerp(310, ctaY, curU);

    // Click ripple on press
    if (t >= CUES.open_workbench) {
      const rp = clamp((t - CUES.open_workbench) / 0.32, 0, 1);
      c.strokeStyle = COL.ink;
      c.lineWidth = 4 * (1 - rp);
      c.beginPath();
      c.arc(ctaX, ctaY, 16 + 75 * rp, 0, Math.PI * 2);
      c.stroke();
    }

    drawCursor(c, curX, curY, 1.15 + 0.2 * clickHoverP, clickPress, -0.08 * (1 - curU));
    c.restore();
  } else {
    // Phase 4B: Real Mjolnir Workbench (2880x1800 Retina) with Screen-Studio Cursor-Coupled Log-Zoom!
    const sheetW = 1440, sheetH = 900;
    const sheetLeft = (W - sheetW) / 2;   // 240
    const sheetTop = 28;

    // 4 smooth camera stops inside the real UI:
    // Stop 1 (44.3 -> 46.2s): Task selector top-left (x: 493, y: 36 in sheet)
    // Stop 2 (46.2 -> 47.7s): "Run split-screen assay" button top-right (x: 1324, y: 89 in sheet)
    // Stop 3 (47.8 -> 51.8s): Split-Screen Assay comparison (x: 590, y: 545 in sheet)
    // Stop 4 (51.9 -> 54.6s): Unified Git Diff & Verified Cost Receipt (x: 1115, y: 595 in sheet)
    const uToRun = smoothstep(CUES.click_run - 1.05, CUES.click_run - 0.08, t);
    const uToTrace = smoothstep(CUES.watch_trace - 0.1, CUES.watch_trace + 1.0, t);
    const uToDiff = smoothstep(CUES.diff_receipt - 1.1, CUES.diff_receipt - 0.05, t);

    let targetX = sheetLeft + 520;
    let targetY = sheetTop + 125;
    let targetZ = 1.62;

    targetX = lerp(targetX, sheetLeft + 1180, uToRun);
    targetY = lerp(targetY, sheetTop + 115, uToRun);
    targetZ = logLerp(targetZ, 1.72, uToRun);

    targetX = lerp(targetX, sheetLeft + 595, uToTrace);
    targetY = lerp(targetY, sheetTop + 535, uToTrace);
    targetZ = logLerp(targetZ, 1.66, uToTrace);

    targetX = lerp(targetX, sheetLeft + 1095, uToDiff);
    targetY = lerp(targetY, sheetTop + 560, uToDiff);
    targetZ = logLerp(targetZ, 1.82, uToDiff);

    // Subtle entrance zoom settle
    const wbEnter = spring(t - (CUES.open_workbench + 0.32), 14, 0.82);
    const curZ = logLerp(1.05, targetZ, clamp(wbEnter, 0, 1));

    c.save();
    c.translate(W / 2, 435);
    c.scale(curZ, curZ);
    c.translate(-targetX, -targetY);

    // Fast layered soft shadow + crisp browser sheet border
    c.save();
    for (let sl = 3; sl >= 1; sl--) {
      const sp = sl * 8;
      c.fillStyle = 'rgba(13, 42, 28, 0.055)';
      c.beginPath();
      c.roundRect(sheetLeft - sp, sheetTop - sp * 0.4 + sl * 6, sheetW + sp * 2, sheetH + sp * 1.5, 16 + sp * 0.4);
      c.fill();
    }
    c.fillStyle = '#ffffff';
    c.beginPath();
    c.roundRect(sheetLeft, sheetTop, sheetW, sheetH, 16);
    c.fill();
    c.clip();

    const uiImg = (t < CUES.click_run + 0.14) ? (IMGS.appDefault || IMGS.appVerified) : IMGS.appVerified;
    if (uiImg && uiImg.complete) {
      c.drawImage(uiImg, sheetLeft, sheetTop, sheetW, sheetH);
    }

    // Active spotlight callout rings so judges track the exact proof instantly!
    if (uToTrace > 0.35 && uToDiff < 0.65) {
      const a = Math.min(uToTrace, 1 - uToDiff * 0.8);
      c.strokeStyle = `rgba(21, 115, 71, ${0.85 * a})`;
      c.lineWidth = 3.5;
      c.beginPath();
      c.roundRect(sheetLeft + 594, sheetTop + 418, 306, 352, 10);
      c.stroke();
    }
    if (uToDiff > 0.35) {
      c.strokeStyle = `rgba(21, 115, 71, ${0.9 * uToDiff})`;
      c.lineWidth = 3.5;
      c.beginPath();
      c.roundRect(sheetLeft + 948, sheetTop + 585, 438, 175, 10);
      c.stroke();
    }
    c.restore();

    // Cursor path across the Workbench
    let cx = sheetLeft + 493, cy = sheetTop + 26;
    cx = lerp(cx, sheetLeft + 1324, uToRun);
    cy = lerp(cy, sheetTop + 89, uToRun);
    cx = lerp(cx, sheetLeft + 748, uToTrace);
    cy = lerp(cy, sheetTop + 615, uToTrace);
    cx = lerp(cx, sheetLeft + 1140, uToDiff);
    cy = lerp(cy, sheetTop + 705, uToDiff);

    const runClickPress = (t > CUES.click_run - 0.04 && t < CUES.click_run + 0.22)
      ? Math.sin(((t - (CUES.click_run - 0.04)) / 0.26) * Math.PI)
      : 0;

    if (t >= CUES.click_run && t < CUES.click_run + 0.42) {
      const rp = (t - CUES.click_run) / 0.42;
      c.strokeStyle = COL.emerald;
      c.lineWidth = 4 * (1 - rp);
      c.beginPath();
      c.arc(sheetLeft + 1324, sheetTop + 89, 12 + 68 * rp, 0, Math.PI * 2);
      c.stroke();
    }

    drawCursor(c, cx, cy, 0.92, runClickPress, 0);
    c.restore();

    // Soft studio lower-third cushion gradient so zoomed UI never competes with subtitles
    const btmGrad = c.createLinearGradient(0, 885, 0, 1080);
    btmGrad.addColorStop(0, 'rgba(238, 241, 238, 0)');
    btmGrad.addColorStop(0.55, 'rgba(238, 241, 238, 0.86)');
    btmGrad.addColorStop(1, 'rgba(238, 241, 238, 0.98)');
    c.fillStyle = btmGrad;
    c.fillRect(0, 885, W, 195);
  }
}

// =========================================================================
// ACT 5: 100/100 FULL-CIRCLE PAYOFF & MJOLNIR CONVERGENCE FINALE
// =========================================================================
function renderAct5(c, t) {
  c.fillStyle = COL.forestDark;
  c.fillRect(0, 0, W, H);

  const localT = t - CUES.act5_ten_of_ten;
  const pillarsP = smoothstep(CUES.summary_pillars - 0.25, CUES.summary_pillars + 0.55, t);
  const convP = smoothstep(CUES.final_mjolnir - 0.35, CUES.final_mjolnir + 0.65, t);

  // Subtle continuous camera micro-push (1.00 -> 1.05)
  const zoom = 1.0 + 0.0045 * Math.max(0, localT);
  c.save();
  c.translate(W / 2, 445);
  c.scale(zoom, zoom);
  c.translate(-W / 2, -445);

  drawDotGrid(c, 58, '#143324', 0, W, 0, H);

  const gridX0 = 220, gridY0 = 185, stepX = 62, stepY = 56;

  // All 100 Geometric Figures: spring upright -> form luminous ring on pillars -> converge into MJOLNIR mark!
  for (let row = 0; row < 10; row++) {
    for (let col = 0; col < 10; col++) {
      const idx = row * 10 + col;
      const gx = gridX0 + col * stepX;
      const gy = gridY0 + row * stepY;

      // Wave rising all 100 figures to standing emerald!
      const riseDt = localT - (row * 0.045 + col * 0.032);
      const standP = clamp(spring(riseDt, 15, 0.72), 0, 1.15);

      // Ring position during summary pillars
      const angle = (idx / 100) * Math.PI * 2 + t * 0.28;
      const ringRadius = 355 + (idx % 2) * 34;
      const rx = 960 + Math.cos(angle) * ringRadius;
      const ry = 445 + Math.sin(angle) * (ringRadius * 0.78);

      // Converged emblem position at CUES.final_mjolnir
      const cx = 960, cy = 340;

      let x = lerp(gx, rx, pillarsP);
      let y = lerp(gy + (1 - Math.min(1, standP)) * 18, ry, pillarsP);
      x = lerp(x, cx, easeInOutCubic(convP));
      y = lerp(y, cy, easeInOutCubic(convP));

      const colFill = standP > 0.35 ? (idx % 10 === 0 ? COL.volt : COL.mint) : '#385c4a';
      const tilt = (1 - Math.min(1, standP)) * 0.32 * (idx % 2 === 0 ? 1 : -1);
      const sc = 0.86 * (1 - 0.85 * easeInCubic(convP));
      const alpha = 1 - easeInCubic(clamp((convP - 0.55) / 0.45, 0, 1));

      drawFigure(c, x, y, sc, colFill, null, alpha, tilt, (standP > 0.7 && pillarsP < 0.3) ? 'check' : null);
    }
  }

  // Phase 5A Metrics (10 / 10 LIVE SOLVED & -70% COST) beside the 100 standing figures
  if (pillarsP < 0.85) {
    const fadeOut = 1 - smoothstep(0.15, 0.75, pillarsP);
    c.save();
    c.globalAlpha = fadeOut;
    const rx = 1365;

    const p10 = spring(localT - 0.15, 14, 0.78);
    drawMaskedText(c, '10 / 10', rx, 345, p10, {
      font: '700 108px "Hanken Grotesk"', color: COL.mint, align: 'center', clipH: 120
    });
    drawMaskedText(c, '100% VERIFIED FIXES LIVE', rx, 392, p10, {
      font: '600 22px "IBM Plex Mono"', color: '#cfe8da', align: 'center'
    });

    const p70 = spring(t - CUES.cost_minus_70 + 0.1, 14, 0.78);
    if (p70 > 0.01) {
      drawMaskedText(c, '-70%', rx, 565, p70, {
        font: '700 104px "Hanken Grotesk"', color: COL.volt, align: 'center', clipH: 120
      });
      drawMaskedText(c, 'LOWER COST  ($0.00157 / FIX)', rx, 612, p70, {
        font: '600 22px "IBM Plex Mono"', color: '#cfe8da', align: 'center'
      });
    }
    c.restore();
  }

  // Phase 5B Three Kinetic Pillars inside the orbital 100-figure halo
  if (pillarsP > 0.15 && convP < 0.85) {
    const pFade = 1 - smoothstep(0.15, 0.75, convP);
    c.save();
    c.globalAlpha = pFade;
    const tFast = spring(t - CUES.summary_pillars, 15, 0.8);
    const tApi = spring(t - (CUES.summary_pillars + 1.15), 15, 0.8);
    const tSmart = spring(t - (CUES.summary_pillars + 2.55), 15, 0.8);

    drawMaskedText(c, 'Fast first.', 960, 365, tFast, {
      font: '700 64px "Hanken Grotesk"', color: '#ffffff', align: 'center', clipH: 80
    });
    drawMaskedText(c, 'Grounded on new APIs.', 960, 455, tApi, {
      font: '700 64px "Hanken Grotesk"', color: COL.cyan, align: 'center', clipH: 80
    });
    drawMaskedText(c, 'Smart on deep logic.', 960, 545, tSmart, {
      font: '700 64px "Hanken Grotesk"', color: COL.volt, align: 'center', clipH: 80
    });
    c.restore();
  }

  // Phase 5C Final MJOLNIR Brand Lockup emerging from the 100-figure convergence!
  if (convP > 0.25) {
    const endP = spring(t - CUES.final_mjolnir, 13, 0.78);
    c.save();
    c.translate(960, 340);
    const badgeS = clamp(endP, 0, 1.1);
    c.scale(badgeS, badgeS);
    // Volt geometric hammer/anvil mark
    c.fillStyle = COL.volt;
    c.beginPath();
    c.roundRect(-48, -48, 96, 96, 24);
    c.fill();
    // Clean geometric T-hammer inside
    c.fillStyle = COL.forestDark;
    c.beginPath();
    c.roundRect(-28, -24, 56, 20, 5);
    c.roundRect(-9, -4, 18, 32, 4);
    c.fill();
    c.restore();

    drawMaskedText(c, 'MJOLNIR', 960, 515, clamp(endP, 0, 1), {
      font: '700 112px "Hanken Grotesk"', color: '#ffffff', align: 'center', clipH: 130
    });
    drawMaskedText(
      c,
      'Nebius Token Factory   ·   NVIDIA Nemotron 3   ·   Tavily Live Docs',
      960, 582, clamp(spring(t - (CUES.final_mjolnir + 0.22), 14, 0.84), 0, 1),
      { font: '500 24px "IBM Plex Mono"', color: COL.mint, align: 'center', clipH: 48 }
    );
  }

  c.restore();
}

// =========================================================================
// CORNER-OVERSCALED SHAPE FLOOD TRANSITIONS (0.36s, zero crossfades!)
// =========================================================================
function renderSceneAt(c, t) {
  const tFlood1 = CUES.act3_mjolnir - 0.18; // Light -> Dark Forest (Act 2 -> Act 3)
  const tFlood2 = CUES.act4_testing - 0.18; // Dark Forest -> Light UI (Act 3 -> Act 4)
  const tFlood3 = CUES.act5_ten_of_ten - 0.18; // Light UI -> Dark Forest Finale (Act 4 -> Act 5)
  const dur = 0.36;
  const maxR = 1320;

  if (t < tFlood1) {
    renderActs1And2(c, t);
  } else if (t < tFlood1 + dur) {
    renderActs1And2(c, t);
    const u = easeInOutCubic((t - tFlood1) / dur);
    c.save();
    c.beginPath();
    c.arc(960, 460, u * maxR, 0, Math.PI * 2);
    c.clip();
    renderAct3(c, t);
    c.strokeStyle = COL.volt;
    c.lineWidth = 14 * (1 - u);
    c.stroke();
    c.restore();
  } else if (t < tFlood2) {
    renderAct3(c, t);
  } else if (t < tFlood2 + dur) {
    renderAct3(c, t);
    const u = easeInOutCubic((t - tFlood2) / dur);
    c.save();
    c.beginPath();
    c.arc(960, 460, u * maxR, 0, Math.PI * 2);
    c.clip();
    renderAct4(c, t);
    c.strokeStyle = COL.volt;
    c.lineWidth = 14 * (1 - u);
    c.stroke();
    c.restore();
  } else if (t < tFlood3) {
    renderAct4(c, t);
  } else if (t < tFlood3 + dur) {
    renderAct4(c, t);
    const u = easeInOutCubic((t - tFlood3) / dur);
    c.save();
    c.beginPath();
    c.arc(960, 460, u * maxR, 0, Math.PI * 2);
    c.clip();
    renderAct5(c, t);
    c.strokeStyle = COL.mint;
    c.lineWidth = 14 * (1 - u);
    c.stroke();
    c.restore();
  } else {
    renderAct5(c, t);
  }
}

// =========================================================================
// BALANCED LOWER-THIRD VOICE-SYNCED SUBTITLES (y = 948..1026, Never Overlaps!)
// =========================================================================
function renderBalancedSubtitles(c, t) {
  // Find active or slightly pre/post-buffered phrase
  let activePhrase = null;
  let alpha = 0;

  for (let i = 0; i < VO.phrases.length; i++) {
    const p = VO.phrases[i];
    const leadIn = 0.06;
    const tailOut = (i + 1 < VO.phrases.length)
      ? Math.min(0.22, Math.max(0.05, VO.phrases[i + 1].start - p.end - 0.01))
      : 0.55;
    if (t >= p.start - leadIn && t <= p.end + tailOut) {
      activePhrase = p;
      const inA = clamp((t - (p.start - leadIn)) / 0.08, 0, 1);
      const outA = clamp(((p.end + tailOut) - t) / Math.max(0.08, tailOut), 0, 1);
      alpha = Math.min(inA, outA);
      break;
    }
  }
  if (!activePhrase || alpha <= 0.02) return;

  // Determine if background is currently Dark Forest or Light Studio for balanced contrast
  const isDarkStage = (t >= CUES.act3_mjolnir && t < CUES.act4_testing) || (t >= CUES.act5_ten_of_ten);

  c.save();
  c.globalAlpha = alpha;
  c.font = '600 30px "Hanken Grotesk"';
  c.textBaseline = 'middle';

  const gap = 10;
  const wordMetrics = activePhrase.words.map(w => ({
    ...w,
    width: c.measureText(w.word).width
  }));
  const totalTextW = wordMetrics.reduce((s, w) => s + w.width, 0) + gap * (wordMetrics.length - 1);

  const padX = 34, pillH = 64;
  const pillW = totalTextW + padX * 2;
  const pillX = (W - pillW) / 2;
  const pillY = 958;

  // Crisp frosted capsule pill in dedicated lower-third safe zone (fast layered shadow)
  c.fillStyle = 'rgba(0, 0, 0, 0.14)';
  c.beginPath();
  c.roundRect(pillX - 3, pillY + 6, pillW + 6, pillH + 4, 34);
  c.fill();
  c.fillStyle = isDarkStage ? 'rgba(247, 249, 248, 0.95)' : 'rgba(11, 35, 23, 0.94)';
  c.beginPath();
  c.roundRect(pillX, pillY, pillW, pillH, 32);
  c.fill();

  c.strokeStyle = isDarkStage ? 'rgba(255,255,255,0.4)' : 'rgba(246, 224, 22, 0.32)';
  c.lineWidth = 1.5;
  c.stroke();

  // Draw each word with millisecond-exact active highlight!
  let curX = pillX + padX;
  const midY = pillY + pillH / 2 + 1;

  for (const wm of wordMetrics) {
    const isCurrent = (t >= wm.start - 0.03 && t <= wm.end + 0.10);
    const isSpoken = t > wm.end + 0.10;

    if (isCurrent) {
      // Subtle active highlight pill behind the exact word being spoken right now!
      c.fillStyle = isDarkStage ? COL.volt : COL.volt;
      c.beginPath();
      c.roundRect(curX - 7, midY - 20, wm.width + 14, 38, 10);
      c.fill();
      c.fillStyle = COL.ink;
    } else if (isSpoken) {
      c.fillStyle = isDarkStage ? COL.ink : '#ffffff';
    } else {
      c.fillStyle = isDarkStage ? 'rgba(13, 42, 28, 0.46)' : 'rgba(255, 255, 255, 0.50)';
    }

    c.textAlign = 'left';
    c.fillText(wm.word, curX, midY);
    curX += wm.width + gap;
  }

  c.restore();
}

// =========================================================================
// DETERMINISTIC WINDOW.SEEK(T) WITH TEMPORAL SUBFRAME MOTION BLUR
// =========================================================================
window.seek = function(t, subframes = 3) {
  ctx.globalAlpha = 1.0;
  if (subframes <= 1) {
    renderSceneAt(ctx, t);
  } else {
    const shutter = (1 / 60) * 0.65;
    for (let s = 0; s < subframes; s++) {
      const offset = ((s / (subframes - 1)) - 0.5) * shutter;
      const st = clamp(t + offset, 0, VO.total_duration);
      renderSceneAt(sctx, st);
      ctx.globalAlpha = 1 / (s + 1);
      ctx.drawImage(subCanvas, 0, 0);
    }
    ctx.globalAlpha = 1.0;
  }
  // Subtitles sit razor-sharp atop motion-blurred world!
  renderBalancedSubtitles(ctx, t);
};

// Preload all fonts & images before signaling ready
async function boot() {
  await document.fonts.ready;
  const loads = Object.entries(IMG_PATHS).map(([k, src]) => new Promise(resolve => {
    const img = new Image();
    img.onload = () => { IMGS[k] = img; resolve(); };
    img.onerror = () => { resolve(); };
    img.src = src;
  }));
  await Promise.all(loads);
  window.__READY = true;
  window.seek(1.5, 1);
}
boot();
</script>
</body>
</html>
"""

html_out = HTML_TEMPLATE.replace("__VO_DATA__", json.dumps(vo_data))
with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_out)

print(f"[OK] Built deterministic film.html ({len(html_out)} bytes) -> {OUT_HTML}")
