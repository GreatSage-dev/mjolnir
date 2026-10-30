import os
from playwright.sync_api import sync_playwright

HTML_HERO_3_2 = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');
  
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1800px;
    height: 1200px;
    background: #07090c;
    color: #e6edf3;
    font-family: 'Plus Jakarta Sans', sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }

  /* Ambient Grid & Glow */
  .grid-bg {
    position: absolute;
    inset: 0;
    background-image: 
      linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px);
    background-size: 60px 60px;
    opacity: 0.8;
  }

  .radial-glow {
    position: absolute;
    top: 40%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 900px;
    height: 700px;
    background: radial-gradient(circle, rgba(118, 185, 0, 0.16) 0%, rgba(0, 230, 118, 0.08) 35%, transparent 70%);
    filter: blur(80px);
    pointer-events: none;
  }

  .top-badge {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(118, 185, 0, 0.08);
    border: 1px solid rgba(118, 185, 0, 0.35);
    padding: 10px 24px;
    border-radius: 9999px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    color: #76b900;
    margin-bottom: 48px;
    box-shadow: 0 0 30px rgba(118, 185, 0, 0.15);
    z-index: 2;
  }

  .top-badge .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #00ff88;
    box-shadow: 0 0 10px #00ff88;
  }

  /* Emblem / Logo Icon */
  .logo-symbol {
    position: relative;
    width: 220px;
    height: 220px;
    margin-bottom: 44px;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .brand-title {
    font-size: 104px;
    font-weight: 900;
    letter-spacing: -2.5px;
    color: #ffffff;
    line-height: 1;
    margin-bottom: 20px;
    z-index: 2;
    text-shadow: 0 4px 40px rgba(0,0,0,0.8);
  }

  .brand-title span {
    background: linear-gradient(135deg, #76b900 0%, #00ff88 60%, #a8ff78 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .brand-tagline {
    font-size: 30px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: #94a3b8;
    margin-bottom: 50px;
    z-index: 2;
    text-align: center;
  }

  .tech-pills {
    display: flex;
    align-items: center;
    gap: 20px;
    z-index: 2;
  }

  .pill {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(18, 22, 28, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 12px 24px;
    border-radius: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 16px;
    color: #cbd5e1;
    backdrop-filter: blur(10px);
  }

  .pill strong {
    color: #ffffff;
  }

  .bottom-telemetry {
    position: absolute;
    bottom: 40px;
    display: flex;
    gap: 40px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    color: #475569;
    letter-spacing: 1.5px;
    z-index: 2;
  }

  .bottom-telemetry span {
    color: #76b900;
    font-weight: 600;
  }
</style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="radial-glow"></div>

  <div class="top-badge">
    <div class="dot"></div>
    Autonomous Agent Reliability Architecture
  </div>

  <div class="logo-symbol">
    <svg width="220" height="220" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="hammerGrad" x1="20" y1="20" x2="180" y2="180" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#76B900" />
          <stop offset="50%" stop-color="#00E676" />
          <stop offset="100%" stop-color="#00897B" />
        </linearGradient>
        <linearGradient id="innerPrism" x1="50" y1="50" x2="150" y2="150" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.9" />
          <stop offset="100%" stop-color="#76B900" stop-opacity="0.3" />
        </linearGradient>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="10" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      
      <!-- Outer Hex/Prism Shield -->
      <polygon points="100,14 176,58 176,142 100,186 24,142 24,58" 
               stroke="url(#hammerGrad)" stroke-width="4.5" fill="rgba(10, 14, 20, 0.75)" filter="url(#glow)" />
      
      <!-- Geometric Stylized Mjolnir Hammer Head -->
      <path d="M56 62 H144 V92 H124 V84 H76 V92 H56 V62 Z" fill="url(#hammerGrad)" />
      <!-- Hammer Core Plate -->
      <rect x="68" y="70" width="64" height="14" rx="2" fill="#0A0E14" />
      <circle cx="100" cy="77" r="3.5" fill="#00FF88" />

      <!-- Convergence Shaft (Escalation Path) -->
      <path d="M93 92 H107 V146 L100 156 L93 146 Z" fill="url(#hammerGrad)" />
      
      <!-- Precision Crosshairs / Coordinate Reticle -->
      <circle cx="100" cy="115" r="26" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" stroke-dasharray="3 3" />
      <line x1="66" y1="115" x2="134" y2="115" stroke="rgba(118, 185, 0, 0.5)" stroke-width="1.5" />
      <line x1="100" y1="84" x2="100" y2="148" stroke="rgba(118, 185, 0, 0.5)" stroke-width="1.5" />
    </svg>
  </div>

  <h1 class="brand-title">MJ<span>Ö</span>LNIR</h1>
  <p class="brand-tagline">The 2D Escalation Engine for High-Stakes AI Agents</p>

  <div class="tech-pills">
    <div class="pill"><span>Model:</span> <strong>NVIDIA Nemotron 3 Super / Ultra</strong></div>
    <div class="pill"><span>Inference:</span> <strong>Nebius Token Factory</strong></div>
    <div class="pill"><span>Grounding:</span> <strong>Tavily Search API</strong></div>
    <div class="pill"><span>Success:</span> <strong style="color: #00ff88;">88.0% Deterministic</strong></div>
  </div>

  <div class="bottom-telemetry">
    <div>CONFIDENCE &times; CONSENSUS ESCALATION</div>
    <div>&bull;</div>
    <div>ZERO-MOCK VERIFICATION</div>
    <div>&bull;</div>
    <div><span>88% PASS RATE</span> (VS 37% VANILLA)</div>
  </div>
</body>
</html>
"""

HTML_LOGO_SQUARE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@800;900&family=JetBrains+Mono:wght@700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1024px;
    height: 1024px;
    background: #07090c;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    font-family: 'Plus Jakarta Sans', sans-serif;
  }
  .grid-bg {
    position: absolute;
    inset: 0;
    background-image: 
      linear-gradient(to right, rgba(255,255,255,0.035) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255,255,255,0.035) 1px, transparent 1px);
    background-size: 40px 40px;
  }
  .glow {
    position: absolute;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle, rgba(118, 185, 0, 0.22) 0%, rgba(0, 230, 118, 0.08) 45%, transparent 75%);
    filter: blur(60px);
  }
  .icon-wrap {
    position: relative;
    z-index: 2;
    margin-bottom: 24px;
  }
  .brand-text {
    font-size: 78px;
    font-weight: 900;
    letter-spacing: -2px;
    color: #ffffff;
    z-index: 2;
  }
  .brand-text span {
    background: linear-gradient(135deg, #76b900 0%, #00ff88 60%, #a8ff78 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .sub-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    letter-spacing: 5px;
    color: #76b900;
    text-transform: uppercase;
    margin-top: 8px;
    z-index: 2;
  }
</style>
</head>
<body>
  <div class="grid-bg"></div>
  <div class="glow"></div>
  <div class="icon-wrap">
    <svg width="340" height="340" viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="hammerGradSq" x1="20" y1="20" x2="180" y2="180" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#76B900" />
          <stop offset="50%" stop-color="#00E676" />
          <stop offset="100%" stop-color="#00897B" />
        </linearGradient>
        <filter id="glowSq" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="8" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      <polygon points="100,14 176,58 176,142 100,186 24,142 24,58" 
               stroke="url(#hammerGradSq)" stroke-width="4.5" fill="rgba(10, 14, 20, 0.85)" filter="url(#glowSq)" />
      <path d="M56 62 H144 V92 H124 V84 H76 V92 H56 V62 Z" fill="url(#hammerGradSq)" />
      <rect x="68" y="70" width="64" height="14" rx="2" fill="#07090C" />
      <circle cx="100" cy="77" r="3.5" fill="#00FF88" />
      <path d="M93 92 H107 V146 L100 156 L93 146 Z" fill="url(#hammerGradSq)" />
      <circle cx="100" cy="115" r="26" stroke="rgba(255,255,255,0.25)" stroke-width="1.5" stroke-dasharray="3 3" />
      <line x1="66" y1="115" x2="134" y2="115" stroke="rgba(118, 185, 0, 0.6)" stroke-width="1.5" />
      <line x1="100" y1="84" x2="100" y2="148" stroke="rgba(118, 185, 0, 0.6)" stroke-width="1.5" />
    </svg>
  </div>
  <div class="brand-text">MJ<span>Ö</span>LNIR</div>
  <div class="sub-text">2D Escalation Engine</div>
</body>
</html>
"""

def generate():
    os.makedirs("artifacts", exist_ok=True)
    os.makedirs("static/assets", exist_ok=True)

    with open("artifacts/temp_card_3_2.html", "w", encoding="utf-8") as f:
        f.write(HTML_HERO_3_2)
    with open("artifacts/temp_logo_sq.html", "w", encoding="utf-8") as f:
        f.write(HTML_LOGO_SQUARE)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        # 1. 3:2 Hero Card (1800x1200) for Devpost Media Gallery
        page1 = browser.new_page(viewport={"width": 1800, "height": 1200})
        page1.goto(f"file:///{os.path.abspath('artifacts/temp_card_3_2.html')}")
        page1.wait_for_timeout(1000)
        hero_card_path = "artifacts/mjolnir_hero_card_3x2.png"
        page1.screenshot(path=hero_card_path, full_page=True)
        print(f"Rendered: {hero_card_path}")
        page1.close()

        # 2. Square Logo (1024x1024) for Avatars/GitHub
        page2 = browser.new_page(viewport={"width": 1024, "height": 1024})
        page2.goto(f"file:///{os.path.abspath('artifacts/temp_logo_sq.html')}")
        page2.wait_for_timeout(1000)
        sq_logo_path = "artifacts/mjolnir_logo_square.png"
        page2.screenshot(path=sq_logo_path, full_page=True)
        print(f"Rendered: {sq_logo_path}")
        page2.close()

        browser.close()

    # Clean up temp html
    if os.path.exists("artifacts/temp_card_3_2.html"):
        os.remove("artifacts/temp_card_3_2.html")
    if os.path.exists("artifacts/temp_logo_sq.html"):
        os.remove("artifacts/temp_logo_sq.html")

if __name__ == "__main__":
    generate()
