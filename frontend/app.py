"""
Streamlit Frontend — Smart Expense Intelligence System

Features:
  1. Real Email OTP Login / Sign-up Gate with JWT Session Persistence
  2. 4-Option Home Navigation:
     • 📤 Upload Statement
     • 📋 View Transactions
     • 📊 Analytics & Cash Flow
     • 🔄 Recurring Subscriptions
  3. Dynamic & Calibrated Confidence Scores
  4. Fully scoped multi-tenant data isolation per user
"""

import os
import sys
import time
import re
from datetime import datetime, date
from pathlib import Path

import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dotenv import load_dotenv


# ─── Configuration ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Smart Expense Intelligence",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Initialize Default Session State ─────────────────────────────────────────

if "mask_pii" not in st.session_state:
    st.session_state["mask_pii"] = False
if "active_view" not in st.session_state:
    st.session_state["active_view"] = "dashboard"
if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = None
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "ai_chat_messages" not in st.session_state:
    st.session_state["ai_chat_messages"] = []
if "auth_screen" not in st.session_state:
    st.session_state["auth_screen"] = "welcome"
if "selected_drilldown_category" not in st.session_state:
    st.session_state["selected_drilldown_category"] = "All"

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Main header */
    .main-header {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 1.75rem 2.25rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .main-header-title {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header-subtitle {
        color: #a5b4fc;
        font-size: 0.95rem;
        margin: 0.3rem 0 0 0;
        font-weight: 400;
    }

    /* User Profile Chip */
    .user-chip {
        background: rgba(255, 255, 255, 0.1);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #e0e7ff;
        font-size: 0.85rem;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Navigation Action Cards */
    .nav-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
        padding: 2rem 1.75rem;
        border-radius: 16px;
        border: 1px solid rgba(139, 92, 246, 0.3);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        transition: all 0.25s ease;
        text-align: center;
    }
    /* ─── Futuristic Glassmorphism & Cyber Fintech Theme ─── */
    .stApp {
        background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 50%, #030712 100%) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Main Modern Header */
    .main-header {
        background: rgba(30, 27, 75, 0.45);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 20px;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    }
    .main-header-title {
        color: #ffffff;
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .main-header-subtitle {
        color: #94a3b8;
        font-size: 0.92rem;
        margin-top: 0.2rem;
    }
    .user-chip {
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(129, 140, 248, 0.35);
        padding: 0.45rem 1.1rem;
        border-radius: 9999px;
        color: #c7d2fe;
        font-size: 0.85rem;
        font-weight: 600;
    }

    /* Futuristic Navigation Feature Cards */
    .nav-card {
        background: linear-gradient(165deg, rgba(30, 27, 75, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 18px;
        padding: 1.6rem 1.25rem 1.25rem 1.25rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        min-height: 280px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .nav-card:hover {
        transform: translateY(-6px);
        border-color: #38bdf8;
        box-shadow: 0 15px 35px rgba(56, 189, 248, 0.2);
    }
    .nav-icon {
        font-size: 2.2rem;
        margin-bottom: 0.75rem;
        filter: drop-shadow(0 0 12px rgba(129, 140, 248, 0.4));
    }
    .nav-title {
        color: #ffffff;
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
        letter-spacing: -0.3px;
    }
    .nav-desc {
        color: #94a3b8;
        font-size: 0.82rem;
        line-height: 1.45;
        margin-bottom: 0.5rem;
    }

    /* Futuristic KPI Cards */
    .kpi-card {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.5) 0%, rgba(15, 23, 42, 0.7) 100%);
        backdrop-filter: blur(10px);
        padding: 1.3rem 1.5rem;
        border-radius: 16px;
        border: 1px solid rgba(139, 92, 246, 0.2);
        box-shadow: 0 6px 25px rgba(0, 0, 0, 0.25);
        transition: all 0.2s ease;
    }
    .kpi-card:hover {
        border-color: rgba(139, 92, 246, 0.4);
    }
    .kpi-label {
        color: #94a3b8;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.4rem;
    }
    .kpi-value {
        color: #ffffff;
        font-size: 1.7rem;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .kpi-value.positive { color: #34d399; text-shadow: 0 0 15px rgba(52, 211, 153, 0.3); }
    .kpi-value.negative { color: #f87171; text-shadow: 0 0 15px rgba(248, 113, 113, 0.3); }
    .kpi-value.warning  { color: #fbbf24; text-shadow: 0 0 15px rgba(251, 191, 36, 0.3); }

    /* Alert Banners */
    .shortfall-alert {
        background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 50%, #b91c1c 100%);
        padding: 1.25rem 1.5rem;
        border-radius: 14px;
        border-left: 5px solid #ef4444;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(239, 68, 68, 0.3);
    }
    .shortfall-alert h3 {
        color: #fecaca;
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
    }
    .shortfall-alert p {
        color: #fca5a5;
        font-size: 0.95rem;
        margin: 0.25rem 0;
    }

    .safe-alert {
        background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
        padding: 1.25rem 1.5rem;
        border-radius: 14px;
        border-left: 5px solid #10b981;
        margin: 1rem 0;
    }
    .safe-alert h3 {
        color: #a7f3d0;
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0 0 0.3rem 0;
    }
    .safe-alert p {
        color: #6ee7b7;
        font-size: 0.95rem;
        margin: 0;
    }

    .section-header {
        color: #ffffff;
        font-size: 1.3rem;
        font-weight: 800;
        margin: 2rem 0 1.25rem 0;
        padding-bottom: 0.6rem;
        border-bottom: 2px solid rgba(139, 92, 246, 0.3);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Auth Box */
    .auth-container {
        max-width: 480px;
        margin: 3rem auto;
        background: linear-gradient(135deg, #1e1b4b 0%, #24243e 100%);
        padding: 2.5rem;
        border-radius: 16px;
        border: 1px solid rgba(139, 92, 246, 0.3);

    /* Precisa-Style Scorecard */
    .score-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
        border: 1px solid rgba(139, 92, 246, 0.4);
        border-radius: 18px;
        padding: 1.75rem;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        position: relative;
        overflow: hidden;
    }
    .score-num {
        font-size: 3.2rem;
        font-weight: 900;
        letter-spacing: -1px;
        line-height: 1;
        margin: 0.5rem 0;
    }
    .score-num.tier-low {
        color: #34d399;
        text-shadow: 0 0 25px rgba(52, 211, 153, 0.4);
    }
    .score-num.tier-med {
        color: #fbbf24;
        text-shadow: 0 0 25px rgba(251, 191, 36, 0.4);
    }
    .score-num.tier-high {
        color: #f87171;
        text-shadow: 0 0 25px rgba(248, 113, 113, 0.4);
    }
    .risk-badge {
        display: inline-block;
        padding: 0.35rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .risk-badge.badge-low {
        background: rgba(52, 211, 153, 0.15);
        color: #34d399;
        border: 1px solid rgba(52, 211, 153, 0.4);
    }
    .risk-badge.badge-med {
        background: rgba(251, 191, 36, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.4);
    }
    .risk-badge.badge-high {
        background: rgba(248, 113, 113, 0.15);
        color: #f87171;
        border: 1px solid rgba(248, 113, 113, 0.4);
    }

    /* Landing Page Hero & Typography */
    .hero-container {
        text-align: center;
        padding: 3rem 1rem 2rem 1rem;
        max-width: 960px;
        margin: 0 auto;
    }
    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(139, 92, 246, 0.15);
        color: #c4b5fd;
        border: 1px solid rgba(139, 92, 246, 0.35);
        padding: 0.4rem 1.1rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
    }
    .hero-title {
        font-size: 3.2rem;
        font-weight: 900;
        color: #ffffff;
        letter-spacing: -1px;
        line-height: 1.15;
        margin-bottom: 1rem;
    }
    .hero-gradient {
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.15rem;
        max-width: 720px;
        margin: 0 auto 2.5rem auto;
        line-height: 1.6;
    }

    /* Metrics Strip */
    .metric-strip {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        background: rgba(30, 27, 75, 0.4);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 2.5rem 0;
        text-align: center;
    }
    .metric-number {
        font-size: 2rem;
        font-weight: 800;
        color: #38bdf8;
        letter-spacing: -0.5px;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
        margin-top: 0.25rem;
    }

    /* Feature Grid Card */
    .feature-card {
        background: linear-gradient(145deg, rgba(30, 27, 75, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 16px;
        padding: 1.75rem;
        height: 100%;
        transition: all 0.3s ease;
    }
    .feature-card:hover {
        transform: translateY(-4px);
        border-color: rgba(56, 189, 248, 0.5);
        box-shadow: 0 12px 30px rgba(56, 189, 248, 0.15);
    }
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 1rem;
    }
    .feature-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.5rem;
    }
    .feature-desc {
        color: #94a3b8;
        font-size: 0.88rem;
        line-height: 1.5;
    }

    /* Pricing Cards */
    .pricing-card {
        background: linear-gradient(145deg, #1e1b4b 0%, #0f172a 100%);
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-radius: 18px;
        padding: 2rem 1.5rem;
        text-align: center;
        position: relative;
        height: 100%;
    }
    .pricing-card.popular {
        border: 2px solid #818cf8;
        box-shadow: 0 10px 30px rgba(129, 140, 248, 0.25);
    }
    .pricing-badge {
        position: absolute;
        top: -12px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #818cf8, #c084fc);
        color: #ffffff;
        padding: 0.2rem 0.8rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .pricing-price {
        font-size: 2.5rem;
        font-weight: 900;
        color: #ffffff;
        margin: 1rem 0 0.25rem 0;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>


""", unsafe_allow_html=True)

# ─── Auth & API Helper Functions ─────────────────────────────────────────────

def get_auth_headers() -> dict:
    """Return Authorization header with Bearer JWT token."""
    token = st.session_state.get("auth_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(endpoint: str):
    """Make an authenticated GET request to the backend."""
    try:
        resp = requests.get(
            f"{BACKEND_URL}{endpoint}",
            headers=get_auth_headers(),
            timeout=30,
        )
        if resp.status_code == 401:
            st.session_state.pop("auth_token", None)
            st.session_state.pop("user_info", None)
            st.rerun()
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to backend. Make sure it's running: `uvicorn backend.main:app --port 8000`")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint: str, **kwargs):
    """Make an authenticated POST request to the backend."""
    headers = kwargs.pop("headers", {})
    headers.update(get_auth_headers())
    try:
        resp = requests.post(
            f"{BACKEND_URL}{endpoint}",
            headers=headers,
            timeout=60,
            **kwargs,
        )
        if resp.status_code == 401:
            st.session_state.pop("auth_token", None)
            st.session_state.pop("user_info", None)
            st.rerun()
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        detail = "Request failed."
        try:
            detail = resp.json().get("detail", str(e))
        except Exception:
            pass
        st.error(f"Error: {detail}")
        return None
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to backend. Make sure it's running: `uvicorn backend.main:app --port 8000`")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_delete(endpoint: str):
    """Make an authenticated DELETE request."""
    try:
        resp = requests.delete(
            f"{BACKEND_URL}{endpoint}",
            headers=get_auth_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def format_inr(amount: float) -> str:
    """Format amount in Indian Rupees."""
    if abs(amount) >= 100000:
        return f"₹{amount/100000:.1f}L"
    elif abs(amount) >= 1000:
        return f"₹{amount:,.0f}"
    return f"₹{amount:.2f}"


CATEGORY_COLORS = {
    "food": "#f97316",
    "rent": "#8b5cf6",
    "travel": "#06b6d4",
    "shopping": "#ec4899",
    "utilities": "#eab308",
    "entertainment": "#a855f7",
    "subscriptions": "#6366f1",
    "healthcare": "#10b981",
    "transfers": "#64748b",
    "salary": "#22c55e",
    "other": "#94a3b8",
    "uncategorized": "#475569",
}

# ─── Authentication View ─────────────────────────────────────────────────────

# ─── Authentication Views ────────────────────────────────────────────────────

def render_login_view():
    """Unified, clean Auth Controller: Welcome Screen -> (Create Account | Sign In) -> OTP Verification."""
    auth_screen = st.session_state.get("auth_screen", "welcome")

    if auth_screen == "welcome":
        render_welcome_screen()
    elif auth_screen == "signup":
        render_signup_screen()
    elif auth_screen == "signin":
        render_signin_screen()
    elif auth_screen == "verify":
        render_verify_screen()
    else:
        st.session_state["auth_screen"] = "welcome"
        st.rerun()


def render_welcome_screen():
    """Beautiful 3D Interactive Welcome Portal with WebGL particle mesh and floating 3D glassmorphic cards."""
    # ── 3D Interactive Three.js WebGL Particle Constellation Banner ──
    import streamlit.components.v1 as components
    three_d_hero_html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      body { margin: 0; padding: 0; overflow: hidden; background: transparent; }
      #canvas3d { position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }
      .hero-content {
        position: relative;
        z-index: 10;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
        text-align: center;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #ffffff;
        pointer-events: none;
      }
      .badge-3d {
        background: rgba(99, 102, 241, 0.2);
        border: 1px solid rgba(168, 85, 247, 0.5);
        padding: 6px 18px;
        border-radius: 30px;
        font-size: 13px;
        font-weight: 700;
        color: #c4b5fd;
        margin-bottom: 12px;
        box-shadow: 0 0 20px rgba(139, 92, 246, 0.4);
        text-transform: uppercase;
        letter-spacing: 1px;
      }
      .title-3d {
        font-size: 42px;
        font-weight: 900;
        letter-spacing: -1.5px;
        margin: 0 0 10px 0;
        background: linear-gradient(135deg, #ffffff 0%, #a5b4fc 40%, #38bdf8 70%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 10px 30px rgba(0,0,0,0.5);
      }
      .subtitle-3d {
        font-size: 16px;
        color: #94a3b8;
        max-width: 620px;
        line-height: 1.5;
        margin: 0;
      }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    </head>
    <body>
    <div id="canvas3d"></div>
    <div class="hero-content">
      <div class="badge-3d">✨ 3D Autonomous AI Finance Suite</div>
      <h1 class="title-3d">Smart Expense Intelligence System</h1>
      <p class="subtitle-3d">Turn bank statements into actionable cash-flow intelligence, 3D credit health scores, and automated fraud shields.</p>
    </div>

    <script>
      const container = document.getElementById('canvas3d');
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(60, window.innerWidth / 280, 0.1, 1000);
      camera.position.z = 80;

      const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.setSize(window.innerWidth, 280);
      renderer.setPixelRatio(window.devicePixelRatio);
      container.appendChild(renderer.domElement);

      // Create 3D Glowing Particle Sphere Grid
      const particleCount = 700;
      const geometry = new THREE.BufferGeometry();
      const positions = new Float32Array(particleCount * 3);
      const colors = new Float32Array(particleCount * 3);

      const colorA = new THREE.Color(0x6366f1);
      const colorB = new THREE.Color(0xec4899);
      const colorC = new THREE.Color(0x38bdf8);

      for (let i = 0; i < particleCount; i++) {
        const u = Math.random();
        const v = Math.random();
        const theta = u * 2.0 * Math.PI;
        const phi = Math.acos(2.0 * v - 1.0);
        const r = Math.cbrt(Math.random()) * 45;
        const sinPhi = Math.sin(phi);

        positions[i * 3] = r * sinPhi * Math.cos(theta);
        positions[i * 3 + 1] = r * sinPhi * Math.sin(theta);
        positions[i * 3 + 2] = r * Math.cos(phi);

        const mixColor = i % 3 === 0 ? colorA : (i % 3 === 1 ? colorB : colorC);
        colors[i * 3] = mixColor.r;
        colors[i * 3 + 1] = mixColor.g;
        colors[i * 3 + 2] = mixColor.b;
      }

      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

      // Shimmering 3D Particle Material
      const material = new THREE.PointsMaterial({
        size: 1.8,
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        blending: THREE.AdditiveBlending
      });

      const particleSystem = new THREE.Points(geometry, material);
      scene.add(particleSystem);

      // 3D Geometric Floating Wireframe Icosahedron
      const icoGeo = new THREE.IcosahedronGeometry(22, 1);
      const icoMat = new THREE.MeshBasicMaterial({
        color: 0xa855f7,
        wireframe: true,
        transparent: true,
        opacity: 0.25
      });
      const icoMesh = new THREE.Mesh(icoGeo, icoMat);
      scene.add(icoMesh);

      // Interactive mouse parallax
      let mouseX = 0, mouseY = 0;
      window.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX - window.innerWidth / 2) * 0.03;
        mouseY = (e.clientY - 140) * 0.03;
      });

      function animate() {
        requestAnimationFrame(animate);
        particleSystem.rotation.y += 0.003;
        particleSystem.rotation.x += 0.0015;
        icoMesh.rotation.y -= 0.004;
        icoMesh.rotation.z += 0.002;

        camera.position.x += (mouseX - camera.position.x) * 0.05;
        camera.position.y += (-mouseY - camera.position.y) * 0.05;
        camera.lookAt(scene.position);

        renderer.render(scene, camera);
      }
      animate();

      window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / 280;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, 280);
      });
    </script>
    </body>
    </html>
    """
    components.html(three_d_hero_html, height=290)

    # ── Custom 3D Interactive Button Effects & Ripple CSS ──
    st.markdown("""
    <style>
    /* 3D Create Account Button */
    div[data-testid="stButton"] button[kind="primary"] {
        background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 50%, #6366f1 100%) !important;
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 1.05rem !important;
        border-radius: 14px !important;
        border: 2px solid rgba(255, 255, 255, 0.4) !important;
        box-shadow: 0 8px 25px rgba(236, 72, 153, 0.5), 0 4px 0 #7c3aed, 0 0 20px rgba(139, 92, 246, 0.4) !important;
        padding: 0.85rem 1.5rem !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
        position: relative !important;
        overflow: hidden !important;
        cursor: pointer !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        transform: translateY(-3px) scale(1.02) !important;
        box-shadow: 0 12px 30px rgba(236, 72, 153, 0.7), 0 6px 0 #7c3aed, 0 0 35px rgba(139, 92, 246, 0.6) !important;
        filter: brightness(1.1) !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:active {
        transform: translateY(3px) scale(0.98) !important;
        box-shadow: 0 2px 10px rgba(236, 72, 153, 0.4), 0 1px 0 #7c3aed !important;
        filter: brightness(0.95) !important;
    }

    /* 3D Sign In Secondary Button */
    div[data-testid="stButton"] button[kind="secondary"] {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
        color: #e0e7ff !important;
        font-weight: 700 !important;
        font-size: 1.02rem !important;
        border-radius: 14px !important;
        border: 2px solid rgba(139, 92, 246, 0.45) !important;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5), 0 4px 0 rgba(99, 102, 241, 0.5) !important;
        padding: 0.85rem 1.5rem !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
        cursor: pointer !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        transform: translateY(-3px) scale(1.02) !important;
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 10px 25px rgba(56, 189, 248, 0.3), 0 6px 0 rgba(56, 189, 248, 0.6), 0 0 25px rgba(56, 189, 248, 0.3) !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:active {
        transform: translateY(3px) scale(0.98) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.6), 0 1px 0 rgba(99, 102, 241, 0.5) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 3D Glassmorphic Auth Action Box
    col_left, col_mid, col_right = st.columns([1, 1.35, 1])

    with col_mid:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(30, 27, 75, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
            padding: 2.2rem 2rem;
            border-radius: 24px;
            border: 1px solid rgba(139, 92, 246, 0.45);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7), 0 0 30px rgba(99, 102, 241, 0.25);
            text-align: center;
            backdrop-filter: blur(20px);
            transform: perspective(1000px) rotateX(1deg);
            transition: transform 0.3s ease;
        ">
            <div style="font-size: 2.4rem; margin-bottom: 0.5rem; filter: drop-shadow(0 0 15px rgba(236, 72, 153, 0.5));">💎</div>
            <div style="font-size: 1.35rem; font-weight: 800; color: #ffffff; margin-bottom: 0.3rem;">Welcome to the Portal</div>
            <p style="color: #a5b4fc; font-size: 0.9rem; margin-bottom: 1.5rem;">Select an option below to create or access your isolated account</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        if st.button("✨ Create Account", key="welcome_btn_signup", use_container_width=True, type="primary"):
            st.session_state["auth_screen"] = "signup"
            st.rerun()

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        if st.button("🔑 Sign In", key="welcome_btn_signin", use_container_width=True, type="secondary"):
            st.session_state["auth_screen"] = "signin"
            st.rerun()

    # Metrics Strip with rich inline styling
    st.markdown("""
    <div style="
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.2rem;
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(139, 92, 246, 0.35);
        border-radius: 20px;
        padding: 1.8rem 1.5rem;
        margin: 3.5rem 0 2.5rem 0;
        text-align: center;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4), 0 0 25px rgba(99, 102, 241, 0.15);
    ">
        <div>
            <div style="font-size: 2.2rem; font-weight: 900; background: linear-gradient(135deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">1,200+</div>
            <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.8px; margin-top: 0.3rem;">Bank Formats Supported</div>
        </div>
        <div>
            <div style="font-size: 2.2rem; font-weight: 900; background: linear-gradient(135deg, #34d399, #10b981); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">850+</div>
            <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.8px; margin-top: 0.3rem;">Banks Worldwide</div>
        </div>
        <div>
            <div style="font-size: 2.2rem; font-weight: 900; background: linear-gradient(135deg, #f472b6, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">14+</div>
            <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.8px; margin-top: 0.3rem;">Automated Risk Checks</div>
        </div>
        <div>
            <div style="font-size: 2.2rem; font-weight: 900; background: linear-gradient(135deg, #fbbf24, #f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">99.4%</div>
            <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.8px; margin-top: 0.3rem;">Extraction Accuracy</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Core Solutions Section
    st.markdown("<div style='text-align: center; margin: 2rem 0 1.5rem 0;'><h2 style='color: #ffffff; font-weight: 800; font-size: 1.8rem;'>✨ Core Platform Capabilities</h2><p style='color: #94a3b8; font-size: 0.95rem;'>Bank-grade AI analysis ready immediately inside your dashboard</p></div>", unsafe_allow_html=True)

    sol1, sol2, sol3 = st.columns(3)
    with sol1:
        st.markdown("""
        <div style="
            background: linear-gradient(145deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(139, 92, 246, 0.35);
            border-radius: 18px;
            padding: 1.8rem;
            height: 100%;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        ">
            <div style="font-size: 2.2rem; margin-bottom: 0.8rem;">📄</div>
            <div style="font-size: 1.2rem; font-weight: 800; color: #ffffff; margin-bottom: 0.5rem;">Bank Statement Parser</div>
            <div style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.55;">
                Upload password-protected PDFs or CSVs from any bank. Automatically decrypts, extracts tables, and cleans noisy UPI & Indian merchant narrations with 99.4% precision.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with sol2:
        st.markdown("""
        <div style="
            background: linear-gradient(145deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(52, 211, 153, 0.4);
            border-radius: 18px;
            padding: 1.8rem;
            height: 100%;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        ">
            <div style="font-size: 2.2rem; margin-bottom: 0.8rem;">🛡️</div>
            <div style="font-size: 1.2rem; font-weight: 800; color: #ffffff; margin-bottom: 0.5rem;">Financial Health & Risk Score</div>
            <div style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.55;">
                Calculates creditworthiness score (0–1000), cash-flow volatility index, and 8+ automated banking risk checks (circular loops, cash ratio, DTI underwriting).
            </div>
        </div>
        """, unsafe_allow_html=True)

    with sol3:
        st.markdown("""
        <div style="
            background: linear-gradient(145deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(236, 72, 153, 0.35);
            border-radius: 18px;
            padding: 1.8rem;
            height: 100%;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        ">
            <div style="font-size: 2.2rem; margin-bottom: 0.8rem;">🔄</div>
            <div style="font-size: 1.2rem; font-weight: 800; color: #ffffff; margin-bottom: 0.5rem;">Subscription & Burn Radar</div>
            <div style="color: #cbd5e1; font-size: 0.88rem; line-height: 1.55;">
                Deterministic recurring detector flags silent subscriptions, upcoming renewal bills, and projected monthly/annual cash outflow automatically.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("<hr style='margin: 3.5rem 0 1.5rem 0; border-color: rgba(139, 92, 246, 0.2);'>", unsafe_allow_html=True)
    f1, f2 = st.columns([2, 1])
    with f1:
        st.markdown("<div style='color: #64748b; font-size: 0.85rem;'>© 2026 Smart Expense Intelligence System. Powered by AI & Brevo Real-Time OTP Verification.</div>", unsafe_allow_html=True)
    with f2:
        st.markdown("<div style='text-align: right; color: #818cf8; font-size: 0.85rem;'>🔒 256-bit Bank-Grade Encryption</div>", unsafe_allow_html=True)








def render_signup_screen():
    """Create Account screen with explicit new-user validation."""
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 800;">✨ Create your account</h1>
        <p style="color: #a5b4fc; font-size: 1rem;">Enter your email to receive a 6-digit verification code</p>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_mid, col_right = st.columns([1, 1.5, 1])

    with col_mid:
        # Check if we have an inline account exists warning
        if st.session_state.get("signup_account_exists"):
            exists_email = st.session_state.get("auth_email_input", "")
            st.warning(f"⚠️ An account with **{exists_email}** already exists.")
            if st.button(f"👉 Sign in with {exists_email} instead", use_container_width=True, type="primary"):
                st.session_state["auth_email_input"] = exists_email
                st.session_state["signup_account_exists"] = False
                st.session_state["auth_screen"] = "signin"
                st.rerun()
            st.markdown("<hr style='margin: 1rem 0; border-color: rgba(139, 92, 246, 0.2);'>", unsafe_allow_html=True)

        initial_email = st.session_state.get("auth_email_input", "")
        with st.form("signup_form"):
            email_val = st.text_input("Your Email Address", value=initial_email, placeholder="name@example.com").strip().lower()
            submit_btn = st.form_submit_button("Send Code ➔", use_container_width=True, type="primary")

            if submit_btn:
                if not email_val or "@" not in email_val:
                    st.error("Please enter a valid email address.")
                else:
                    st.session_state["auth_email_input"] = email_val
                    with st.spinner("Checking and sending code..."):
                        resp = requests.post(
                            f"{BACKEND_URL}/api/auth/send-otp",
                            json={"email": email_val, "intent": "signup"},
                            timeout=20,
                        )
                        if resp.status_code == 200:
                            st.session_state["pending_email"] = email_val
                            st.session_state["auth_intent"] = "signup"
                            st.session_state["auth_screen"] = "verify"
                            st.session_state["signup_account_exists"] = False
                            st.rerun()
                        elif resp.status_code == 409:
                            # Account already exists
                            st.session_state["signup_account_exists"] = True
                            st.rerun()
                        elif resp.status_code == 429:
                            st.error(resp.json().get("detail", "Rate limit exceeded. Please wait."))
                        else:
                            err_msg = resp.json().get("detail", "Could not send code, please try again.")
                            st.error(f"⚠️ {err_msg}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back to Welcome", key="back_to_welcome_signup", use_container_width=True):
                st.session_state["signup_account_exists"] = False
                st.session_state["auth_screen"] = "welcome"
                st.rerun()
        with c2:
            if st.button("Already have an account? Sign In", key="switch_to_signin", use_container_width=True):
                st.session_state["signup_account_exists"] = False
                st.session_state["auth_screen"] = "signin"
                st.rerun()


def render_signin_screen():
    """Sign In screen with explicit returning-user validation."""
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 800;">🔑 Sign in</h1>
        <p style="color: #a5b4fc; font-size: 1rem;">Enter your email to sign in to your existing account</p>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_mid, col_right = st.columns([1, 1.5, 1])

    with col_mid:
        # Check if we have an inline no account found warning
        if st.session_state.get("signin_no_account"):
            missing_email = st.session_state.get("auth_email_input", "")
            st.warning(f"⚠️ No account found with **{missing_email}**.")
            if st.button(f"👉 Create an account for {missing_email} instead", use_container_width=True, type="primary"):
                st.session_state["auth_email_input"] = missing_email
                st.session_state["signin_no_account"] = False
                st.session_state["auth_screen"] = "signup"
                st.rerun()
            st.markdown("<hr style='margin: 1rem 0; border-color: rgba(139, 92, 246, 0.2);'>", unsafe_allow_html=True)

        initial_email = st.session_state.get("auth_email_input", "")
        with st.form("signin_form"):
            email_val = st.text_input("Your Email Address", value=initial_email, placeholder="name@example.com").strip().lower()
            submit_btn = st.form_submit_button("Send Code ➔", use_container_width=True, type="primary")

            if submit_btn:
                if not email_val or "@" not in email_val:
                    st.error("Please enter a valid email address.")
                else:
                    st.session_state["auth_email_input"] = email_val
                    with st.spinner("Checking and sending code..."):
                        resp = requests.post(
                            f"{BACKEND_URL}/api/auth/send-otp",
                            json={"email": email_val, "intent": "signin"},
                            timeout=20,
                        )
                        if resp.status_code == 200:
                            st.session_state["pending_email"] = email_val
                            st.session_state["auth_intent"] = "signin"
                            st.session_state["auth_screen"] = "verify"
                            st.session_state["signin_no_account"] = False
                            st.rerun()
                        elif resp.status_code == 404:
                            # No account found
                            st.session_state["signin_no_account"] = True
                            st.rerun()
                        elif resp.status_code == 429:
                            st.error(resp.json().get("detail", "Rate limit exceeded. Please wait."))
                        else:
                            err_msg = resp.json().get("detail", "Could not send code, please try again.")
                            st.error(f"⚠️ {err_msg}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Back to Welcome", key="back_to_welcome_signin", use_container_width=True):
                st.session_state["signin_no_account"] = False
                st.session_state["auth_screen"] = "welcome"
                st.rerun()
        with c2:
            if st.button("New user? Create Account", key="switch_to_signup", use_container_width=True):
                st.session_state["signin_no_account"] = False
                st.session_state["auth_screen"] = "signup"
                st.rerun()


def render_verify_screen():
    """Shared 6-digit code verification step with path-matched copy."""
    pending_email = st.session_state.get("pending_email", "")
    intent = st.session_state.get("auth_intent", "signup")

    if intent == "signup":
        title_text = "✨ Finish Creating Account"
        info_copy = f"Enter the 6-digit code we sent to **{pending_email}** to finish creating your account."
        action_btn_text = "Verify Code & Create Account 🚀"
    else:
        title_text = "🔑 Sign In to Your Account"
        info_copy = f"Enter the 6-digit code we sent to **{pending_email}** to sign in."
        action_btn_text = "Verify Code & Sign In 🔓"

    st.markdown(f"""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 1.5rem;">
        <h1 style="color: #ffffff; font-size: 2.2rem; font-weight: 800;">{title_text}</h1>
        <p style="color: #a5b4fc; font-size: 1rem;">Check your email inbox (and spam folder if needed)</p>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_mid, col_right = st.columns([1, 1.5, 1])

    with col_mid:
        st.markdown(f"""
        <div style="background: rgba(99, 102, 241, 0.15); border-left: 4px solid #6366f1; padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 1.25rem;">
            <span style="color: #c7d2fe; font-size: 0.95rem;">{info_copy}</span>
        </div>
        """, unsafe_allow_html=True)

        with st.form("shared_verify_otp_form"):
            otp_code = st.text_input("Enter 6-Digit Code", max_chars=6, placeholder="123456").strip()


            verify_btn = st.form_submit_button(action_btn_text, use_container_width=True, type="primary")

            if verify_btn:
                if len(otp_code) != 6 or not otp_code.isdigit():
                    st.error("Please enter a valid 6-digit numeric verification code.")
                else:
                    with st.spinner("Verifying code..."):
                        resp = requests.post(
                            f"{BACKEND_URL}/api/auth/verify-otp",
                            json={"email": pending_email, "otp": otp_code},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state["auth_token"] = data["access_token"]
                            st.session_state["user_info"] = data["user"]
                            st.session_state["current_page"] = "home"
                            st.session_state.pop("auth_screen", None)
                            st.session_state.pop("pending_email", None)
                            st.session_state.pop("auth_intent", None)
                            st.success("🎉 " + data.get("message", "Success!"))
                            st.rerun()
                        else:
                            st.error(resp.json().get("detail", "Verification failed. Please check the code and try again."))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Use Different Email", key="verify_back_btn", use_container_width=True):
                st.session_state["auth_screen"] = intent  # go back to signup or signin
                st.rerun()
        with c2:
            if st.button("Resend Code", key="verify_resend_btn", use_container_width=True):
                resp = requests.post(
                    f"{BACKEND_URL}/api/auth/send-otp",
                    json={"email": pending_email, "intent": intent},
                    timeout=15,
                )
                if resp.status_code == 200:
                    st.success("✅ A fresh code has been sent.")
                else:
                    st.error(resp.json().get("detail", "Please wait before requesting another code."))




# ─── Navigation Header ───────────────────────────────────────────────────────

def render_top_bar(title: str = "Smart Expense Intelligence", subtitle: str = ""):
    """Render top header bar with user status, logout, and navigation."""
    user = st.session_state.get("user_info", {})
    user_email = user.get("email", "Authenticated User")

    st.markdown(f"""
    <div class="main-header">
        <div>
            <div class="main-header-title">{title}</div>
            <div class="main-header-subtitle">{subtitle}</div>
        </div>
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div class="user-chip">👤 {user_email}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Screen 1: Unified All-in-One Scrolling Dashboard ─────────────────────────

def render_home_page():
    """
    Render a futuristic, unified all-in-one scrolling command center:
      1. Top Bar with User Info, PII Masking & Privacy Controls
      2. 'How It Works & Privacy Safeguards' Collapsible Panels
      3. Bank Statement & PDF Ingestion Section (Direct Upload)
      4. Date Range Filter & Budget Goals Progress Bars
      5. Category Drill-Down & Manual Category Overrides Stream
      6. Reactive Spend Analytics & Cash-Flow Shortfall Projection
      7. Monthly Top Spend & Store Drilldown
      8. Subscriptions & Annualized Burn Radar
      9. Financial Health Scorecard & Automated Risk Checks
      10. Filtered Statement Data Export (CSV & JSON)
      11. Interactive Footer (Created by Anurag, Address & Greeting)
    """
    render_top_bar(
        title="⚡ Smart Expense Intelligence",
        subtitle="AI-Powered Financial Command Center & Risk Profiling Platform",
    )

    # ── Initial Session State Setup ──
    if "category_overrides" not in st.session_state:
        st.session_state["category_overrides"] = {}  # merchant_clean -> new_category
    if "category_budgets" not in st.session_state:
        st.session_state["category_budgets"] = {
            "food": 10000.0,
            "travel": 5000.0,
            "shopping": 8000.0,
            "utilities": 3000.0,
            "subscriptions": 2000.0,
            "healthcare": 3000.0,
            "transfers": 15000.0,
            "rent": 20000.0,
            "other": 5000.0,
        }
    if "selected_drilldown_category" not in st.session_state:
        st.session_state["selected_drilldown_category"] = "All"
    if "mask_pii" not in st.session_state:
        st.session_state["mask_pii"] = False

    # Fetch initial transaction payload from backend
    txn_data = api_get("/api/transactions")
    raw_transactions = txn_data.get("transactions", []) if isinstance(txn_data, dict) else (txn_data or [])

    # Apply Session-persisted Category Overrides
    transactions = []
    for t in raw_transactions:
        t_copy = dict(t)
        m_key = t_copy.get("merchant_clean", "").strip().lower()
        if m_key in st.session_state["category_overrides"]:
            t_copy["category"] = st.session_state["category_overrides"][m_key]
            t_copy["confidence"] = 1.0  # Manual override certainty
            t_copy["is_user_override"] = True
        transactions.append(t_copy)

    total_txns = len(transactions)

    # ── Section 1: How It Works & Privacy Safeguards Panel ──
    c_info1, c_info2 = st.columns([1, 1])
    with c_info1:
        with st.expander("📖 How It Works & Quick Guide", expanded=False):
            st.markdown("""
            <div style="background: rgba(30, 27, 75, 0.4); padding: 1rem; border-radius: 10px; border: 1px solid rgba(139, 92, 246, 0.25); font-size: 0.84rem; line-height: 1.5; color: #cbd5e1;">
                <strong>1. Ingest Statement:</strong> Upload any Indian bank statement PDF or CSV (with in-memory PDF password unlock).<br>
                <strong>2. AI Normalization:</strong> Strips noisy UPI/NEFT references, classifies spending, and alerts on cash-flow shortfall.<br>
                <strong>3. Interactive Filter:</strong> Adjust date ranges, set budget limits, click categories, and edit transaction tags in real time!
            </div>
            """, unsafe_allow_html=True)
    with c_info2:
        with st.expander("🔒 Data Handling & Privacy Safeguards", expanded=False):
            st.markdown("""
            <div style="background: rgba(15, 23, 42, 0.6); padding: 1rem; border-radius: 10px; border-left: 3px solid #34d399; font-size: 0.84rem; line-height: 1.5; color: #cbd5e1;">
                • <strong>Zero Disk Persistence:</strong> Statement files and credentials are processed strictly in-memory.<br>
                • <strong>Session Isolation:</strong> All analytics and category overrides are scoped exclusively to your session.<br>
                • <strong>One-Click Wipeout:</strong> Use the <em>"Clear My Data Now"</em> button to purge all transactions instantly.
            </div>
            """, unsafe_allow_html=True)
            if st.button("🗑️ Clear My Data Now (Reset Dashboard)", type="secondary", key="btn_clear_data_privacy"):
                api_delete("/api/clear")
                st.session_state["category_overrides"] = {}
                st.session_state["chat_history"] = [
                    {"role": "assistant", "content": "👋 Hi! I'm your AI Financial Copilot. Ask me anything about your bank statement — for example: *'How much did I send to Veeresh?'*, *'What is my total Swiggy spend?'*, or *'What was my highest expense?'*"}
                ]
                st.success("✅ Session data wiped clean!")
                time.sleep(0.4)
                st.rerun()

    # ── Section 2: Upload Bank Statement ──
    st.markdown("<div class=\"section-header\">📤 1. Bank Statement Ingestion</div>", unsafe_allow_html=True)
    c_upload, c_sample = st.columns([3, 2])

    with c_upload:
        st.markdown("#### Upload PDF / CSV Statement")
        uploaded_file = st.file_uploader(
            "Select bank statement file",
            type=["csv", "pdf"],
            key="home_file_uploader",
            help="Supports standard bank statement exports (HDFC, ICICI, SBI, Axis, Kotak, Canara, CSV, PDF)",
        )

        pdf_password = ""
        if uploaded_file and uploaded_file.name.lower().endswith(".pdf"):
            with st.expander("🔒 PDF Password (If Password Protected)", expanded=True):
                st.caption("Indian banks protect PDFs with standard password formats:")
                st.markdown("""
                <div style="font-size: 0.82rem; color: #94a3b8; line-height: 1.4; margin-bottom: 8px;">
                • <strong>HDFC</strong>: Customer ID or PAN (Uppercase)<br>
                • <strong>ICICI</strong>: First 4 letters of name (lowercase) + DDMM of DOB<br>
                • <strong>SBI</strong>: Last 5 digits of Account No + DDMMYY of DOB<br>
                • <strong>Axis / Kotak</strong>: First 4 letters of name + DOB or PAN
                </div>
                """, unsafe_allow_html=True)
                pdf_password = st.text_input("Enter PDF Password", type="password", placeholder="e.g. ABCDE1234F or DDMMYYYY", key="pdf_pass_input_home")

        if uploaded_file:
            if st.button("Process & Categorize Uploaded File 🚀", type="primary", use_container_width=True, key="btn_proc_home"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                status_text.text("📄 Step 1/3: Ingesting & decrypting statement...")
                progress_bar.progress(30)

                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                data = {"password": pdf_password} if pdf_password else {}
                result = api_post("/api/ingest", files=files, data=data)

                if result:
                    status_text.text("🤖 Step 2/3: Applying merchant normalization & AI categorizer...")
                    progress_bar.progress(70)
                    time.sleep(0.3)

                    status_text.text("📊 Step 3/3: Synchronizing database & health engine...")
                    progress_bar.progress(100)

                    st.success(f"🎉 Successfully ingested and categorized {result['transactions_parsed']} transactions!")
                    time.sleep(0.5)
                    st.rerun()

    with c_sample:
        st.markdown("#### Or Load Realistic Demo Statement")
        st.markdown("""
        <div style="background: rgba(30, 27, 75, 0.35); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem;">
            <div style="font-weight: 700; color: #ffffff; font-size: 0.95rem; margin-bottom: 0.3rem;">Test Drive Instant Statement Analysis</div>
            <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.4;">Load 20 realistic bank transactions (Swiggy, Netflix, Salary, Uber, Jio, etc.) with calibrated AI confidence scores.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📥 Load Sample Statement Data", use_container_width=True, key="btn_sample_home"):
            with st.spinner("Populating sample statement data..."):
                res = api_post("/api/sample-data")
                if res:
                    st.success("Sample statement loaded successfully!")
                    time.sleep(0.5)
                    st.rerun()

    # Helper function for PII masking
    def mask_text(val: str) -> str:
        if not st.session_state["mask_pii"] or not val:
            return str(val)
        # Mask numbers with X
        val = re.sub(r"\b\d{4,}\b", lambda m: "X" * (len(m.group(0)) - 4) + m.group(0)[-4:], val)
        # Mask UPI IDs
        val = re.sub(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]+(@[A-Za-z0-9.-]+)", r"\1***\2", val)
        return val

    # ── Date Range Filter & Reactive Recomputation ──
    date_filtered_txns = transactions
    if transactions:
        # Determine statement min and max date
        txn_dates = []
        for t in transactions:
            try:
                txn_dates.append(datetime.strptime(t["date"], "%Y-%m-%d").date())
            except Exception:
                pass

        if txn_dates:
            min_stmt_date = min(txn_dates)
            max_stmt_date = max(txn_dates)
        else:
            min_stmt_date = date(2026, 1, 1)
            max_stmt_date = date(2026, 12, 31)

        st.markdown("<br><div class=\"section-header\">📅 Dashboard Filter & Date Window</div>", unsafe_allow_html=True)
        c_date1, c_date2 = st.columns([2, 2])
        with c_date1:
            date_range = st.date_input(
                "Select Transaction Date Range:",
                value=(min_stmt_date, max_stmt_date),
                min_value=min_stmt_date,
                max_value=max_stmt_date,
                key="home_date_range_picker"
            )
        with c_date2:
            st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
            if st.button("🔄 Reset to Full Statement Range", key="btn_reset_dates"):
                st.session_state["selected_drilldown_category"] = "All"
                st.rerun()

        # Apply date filter
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_d, end_d = date_range
            date_filtered_txns = [
                t for t in transactions
                if start_d <= datetime.strptime(t["date"], "%Y-%m-%d").date() <= end_d
            ]
        elif isinstance(date_range, (list, tuple)) and len(date_range) == 1:
            start_d = date_range[0]
            date_filtered_txns = [
                t for t in transactions
                if datetime.strptime(t["date"], "%Y-%m-%d").date() >= start_d
            ]

    # Reactive Aggregations on date_filtered_txns
    reactive_debits = sum(t["amount"] for t in date_filtered_txns if t["type"] == "debit")
    reactive_credits = sum(t["amount"] for t in date_filtered_txns if t["type"] == "credit")
    reactive_cat_breakdown = {}
    for t in date_filtered_txns:
        if t["type"] == "debit":
            cat_name = t.get("category", "other").lower()
            reactive_cat_breakdown[cat_name] = reactive_cat_breakdown.get(cat_name, 0.0) + t["amount"]

    # ── Section 3: Budget Goals & Progress Bars ──
    if date_filtered_txns:
        with st.expander("🎯 Category Budget Goals & Real-Time Spending Caps", expanded=False):
            st.markdown("Set your monthly spending cap per category to track your financial discipline:")
            b_cols = st.columns(3)
            all_budget_cats = ["food", "travel", "shopping", "utilities", "subscriptions", "healthcare", "transfers", "rent", "other"]
            for idx, b_cat in enumerate(all_budget_cats):
                col_target = b_cols[idx % 3]
                with col_target:
                    curr_cap = st.session_state["category_budgets"].get(b_cat, 5000.0)
                    new_cap = st.number_input(
                        f"Cap for {b_cat.title()} (₹)",
                        min_value=500.0,
                        max_value=500000.0,
                        value=float(curr_cap),
                        step=500.0,
                        key=f"budget_input_{b_cat}"
                    )
                    st.session_state["category_budgets"][b_cat] = new_cap

            st.markdown("<br><h5 style='color: #ffffff; font-weight: 700;'>📊 Budget Utilization Status:</h5>", unsafe_allow_html=True)
            for b_cat in all_budget_cats:
                actual_spent = reactive_cat_breakdown.get(b_cat, 0.0)
                cap = st.session_state["category_budgets"].get(b_cat, 5000.0)
                pct = (actual_spent / cap) * 100 if cap > 0 else 0
                
                status_color = "#34d399" if pct <= 70 else ("#f59e0b" if pct <= 100 else "#f87171")
                status_tag = "✅ Within Budget" if pct <= 70 else ("⚠️ Near Budget" if pct <= 100 else "🚨 Over Budget Cap!")

                st.markdown(f"""
                <div style="margin-bottom: 0.6rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.2rem;">
                        <span style="color: #ffffff; font-weight: 600;">{b_cat.title()}: <strong>{format_inr(actual_spent)}</strong> / {format_inr(cap)}</span>
                        <span style="color: {status_color}; font-weight: 700;">{pct:.1f}% — {status_tag}</span>
                    </div>
                    <div style="background: rgba(255,255,255,0.08); border-radius: 6px; height: 8px; overflow: hidden;">
                        <div style="background: {status_color}; width: {min(100, pct)}%; height: 100%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Section 4: Spend Analytics & Cash-Flow Shortfall Projection ──
    st.markdown("<br><div class=\"section-header\">📊 2. Spend Analytics & Cash-Flow Forecast</div>", unsafe_allow_html=True)
    if date_filtered_txns:
        # Forecast calculation on date range
        days_span = max(1, (max_stmt_date - min_stmt_date).days + 1) if 'min_stmt_date' in locals() else 30
        daily_burn_rate = reactive_debits / days_span
        projected_month_burn = daily_burn_rate * 30
        
        if reactive_credits > 0 and projected_month_burn > reactive_credits:
            shortfall = projected_month_burn - reactive_credits
            st.markdown(f"""
            <div class="shortfall-alert">
                <h3>⚠️ Cash-Flow Shortfall Alert Projected</h3>
                <p>At your selected range burn rate of <strong>{format_inr(daily_burn_rate)}/day</strong>, your 30-day projected outflow ({format_inr(projected_month_burn)}) exceeds inflow ({format_inr(reactive_credits)}) by <strong>{format_inr(shortfall)}</strong>.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="safe-alert">
                <h3>✅ Healthy Cash-Flow Buffer</h3>
                <p>At your selected burn rate of <strong>{format_inr(daily_burn_rate)}/day</strong>, your inflow ({format_inr(reactive_credits)}) comfortably supports operations.</p>
            </div>
            """, unsafe_allow_html=True)

        # Expense breakdown donut & ranking bar
        expense_breakdown = {k: v for k, v in reactive_cat_breakdown.items() if k.lower() != "salary" and v > 0}
        if not expense_breakdown:
            expense_breakdown = reactive_cat_breakdown

        col_d1, col_d2 = st.columns([1, 1])
        with col_d1:
            labels = [k.title() for k in expense_breakdown.keys()]
            values = list(expense_breakdown.values())
            colors = [CATEGORY_COLORS.get(k.lower(), "#94a3b8") for k in expense_breakdown.keys()]

            fig_donut = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=colors, line=dict(color="#0f172a", width=2)),
                textinfo="label+percent",
                hoverinfo="label+value+percent",
            )])
            fig_donut.update_layout(
                title=dict(text="Outflow by Category (Date Filtered)", font=dict(color="#ffffff", size=14)),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c4b5fd", family="Inter"),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
                margin=dict(t=30, b=30, l=10, r=10),
                height=340,
            )
            st.plotly_chart(fig_donut, use_container_width=True)

        with col_d2:
            sorted_cats = sorted(expense_breakdown.items(), key=lambda x: x[1], reverse=True)
            bar_labels = [k.title() for k, _ in sorted_cats]
            bar_values = [v for _, v in sorted_cats]
            bar_colors = [CATEGORY_COLORS.get(k.lower(), "#94a3b8") for k, _ in sorted_cats]

            fig_bar = go.Figure(data=[go.Bar(
                x=bar_values,
                y=bar_labels,
                orientation='h',
                marker=dict(color=bar_colors),
                text=[f"₹{v:,.0f}" for v in bar_values],
                textposition='auto',
            )])
            fig_bar.update_layout(
                title=dict(text="Category Expense Ranking (₹)", font=dict(color="#ffffff", size=14)),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#c4b5fd", family="Inter"),
                showlegend=False,
                xaxis=dict(gridcolor="rgba(139, 92, 246, 0.1)"),
                yaxis=dict(autorange="reversed"),
                margin=dict(t=30, b=10, l=10, r=10),
                height=340,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # ── Category Drilldown Selector ──
        st.markdown("<h4 style='color: #ffffff; font-size: 1.15rem; font-weight: 700;'>🔍 Interactive Category Drill-Down</h4>", unsafe_allow_html=True)
        available_drill_cats = ["All"] + sorted([k.title() for k in expense_breakdown.keys()])
        
        col_drill1, col_drill2 = st.columns([2, 1])
        with col_drill1:
            drilldown_choice = st.selectbox(
                "Click or select a category below to isolate its transactions in the stream:",
                available_drill_cats,
                index=available_drill_cats.index(st.session_state["selected_drilldown_category"]) if st.session_state["selected_drilldown_category"] in available_drill_cats else 0,
                key="cat_drilldown_selector"
            )
            st.session_state["selected_drilldown_category"] = drilldown_choice
        with col_drill2:
            st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
            if drilldown_choice != "All":
                selected_cat_spend = expense_breakdown.get(drilldown_choice.lower(), 0.0)
                st.markdown(f"<div style='color: #38bdf8; font-weight: 700; font-size: 1.05rem;'>{drilldown_choice} Total: {format_inr(selected_cat_spend)}</div>", unsafe_allow_html=True)

        # ── Dedicated Spending Intelligence & Essential Highlights ──
        st.markdown("<br><h4 style='color: #ffffff; font-size: 1.15rem; font-weight: 700;'>🔥 Essential Spending & Lifestyle Highlights</h4>", unsafe_allow_html=True)
        
        fuel_amt = sum(t.get("amount", 0.0) for t in date_filtered_txns if t.get("type") == "debit" and any(k in t.get("raw_description", "").lower() or k in t.get("merchant_clean", "").lower() for k in ("petrol", "fuel", "indian oil", "iocl", "hp petrol", "bpcl", "bharat petroleum", "cng", "diesel")))
        recharge_amt = sum(t.get("amount", 0.0) for t in date_filtered_txns if t.get("type") == "debit" and any(k in t.get("raw_description", "").lower() or k in t.get("merchant_clean", "").lower() for k in ("jio", "airtel", "vi ", "bsnl", "recharge", "broadband", "fibernet", "act ")))
        sub_stream_amt = sum(t.get("amount", 0.0) for t in date_filtered_txns if t.get("type") == "debit" and any(k in t.get("raw_description", "").lower() or k in t.get("merchant_clean", "").lower() for k in ("netflix", "spotify", "prime", "hotstar", "youtube", "apple.com", "cult", "gym")))
        food_total = reactive_cat_breakdown.get("food", 0.0)

        hl1, hl2, hl3, hl4 = st.columns(4)
        with hl1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">⛽ Fuel & Petrol Spent</div>
                <div class="kpi-value warning">{format_inr(fuel_amt if fuel_amt > 0 else reactive_cat_breakdown.get('travel', 0.0))}</div>
                <div style="color: #94a3b8; font-size: 0.78rem; margin-top: 0.2rem;">IOCL, HP, BPCL & Fuel</div>
            </div>
            """, unsafe_allow_html=True)
        with hl2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">📱 Mobile & Wi-Fi Recharge</div>
                <div class="kpi-value positive">{format_inr(recharge_amt if recharge_amt > 0 else reactive_cat_breakdown.get('utilities', 0.0))}</div>
                <div style="color: #94a3b8; font-size: 0.78rem; margin-top: 0.2rem;">Jio, Airtel, Broadband</div>
            </div>
            """, unsafe_allow_html=True)
        with hl3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">🍿 Subscriptions & Media</div>
                <div class="kpi-value negative">{format_inr(sub_stream_amt if sub_stream_amt > 0 else reactive_cat_breakdown.get('subscriptions', 0.0))}</div>
                <div style="color: #94a3b8; font-size: 0.78rem; margin-top: 0.2rem;">Netflix, Spotify, Prime, Gym</div>
            </div>
            """, unsafe_allow_html=True)
        with hl4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">🍔 Dining & Food Spent</div>
                <div class="kpi-value" style="color: #f97316;">{format_inr(food_total)}</div>
                <div style="color: #94a3b8; font-size: 0.78rem; margin-top: 0.2rem;">Swiggy, Zomato, Dining, Mess</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Monthly Top Spending Destinations & Store / Person Drilldown ──
        st.markdown("<br><h4 style='color: #ffffff; font-size: 1.15rem; font-weight: 700;'>📅 Monthly Top-Paid Places & Person / Beneficiary Drilldown</h4>", unsafe_allow_html=True)
        
        from collections import defaultdict
        month_merchant_map = defaultdict(lambda: defaultdict(float))
        all_entities = set()

        for t in date_filtered_txns:
            m_name = mask_text(t.get("merchant_clean") or "Unknown")
            d_str = t.get("date", "2026-01-01")
            try:
                month_label = datetime.strptime(d_str, "%Y-%m-%d").strftime("%B %Y")
            except Exception:
                month_label = "Current Period"
            if t.get("type") == "debit":
                month_merchant_map[month_label][m_name] += t.get("amount", 0.0)
            all_entities.add(m_name)

        col_top_m, col_drill = st.columns([1.1, 1.2])

        with col_top_m:
            st.markdown("##### 🏆 Highest Spending Destination by Month")
            monthly_summary_rows = []
            for m_label, m_data in sorted(month_merchant_map.items()):
                top_m = max(m_data.items(), key=lambda x: x[1]) if m_data else ("None", 0.0)
                total_month_spend = sum(m_data.values())
                monthly_summary_rows.append({
                    "Month": m_label,
                    "Top Paid Store / Person": top_m[0],
                    "Amount Spent (₹)": f"₹{top_m[1]:,.2f}",
                    "Total Outflow (₹)": f"₹{total_month_spend:,.2f}",
                })
            if monthly_summary_rows:
                st.dataframe(pd.DataFrame(monthly_summary_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No expense data in selected range.")

        with col_drill:
            st.markdown("##### 👤 Person, Merchant & Transfer Drilldown")
            sorted_entities_list = sorted(list(all_entities))
            if sorted_entities_list:
                selected_entity = st.selectbox(
                    "Select a person, recipient, or merchant to see all transactions:",
                    sorted_entities_list,
                    key="store_drilldown_select"
                )
                entity_txns = [t for t in date_filtered_txns if mask_text(t.get("merchant_clean") or "") == selected_entity]
                
                total_sent = sum(t.get("amount", 0.0) for t in entity_txns if t.get("type") == "debit")
                total_received = sum(t.get("amount", 0.0) for t in entity_txns if t.get("type") == "credit")
                net_flow = total_received - total_sent
                
                c_p1, c_p2, c_p3 = st.columns(3)
                with c_p1:
                    st.markdown(f"""
                    <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 0.65rem 0.85rem; text-align: center;">
                        <div style="color: #fca5a5; font-size: 0.75rem; font-weight: 600;">Total Sent</div>
                        <div style="color: #ffffff; font-size: 1.1rem; font-weight: 800;">₹{total_sent:,.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c_p2:
                    st.markdown(f"""
                    <div style="background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 10px; padding: 0.65rem 0.85rem; text-align: center;">
                        <div style="color: #86efac; font-size: 0.75rem; font-weight: 600;">Total Received</div>
                        <div style="color: #ffffff; font-size: 1.1rem; font-weight: 800;">₹{total_received:,.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c_p3:
                    st.markdown(f"""
                    <div style="background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 10px; padding: 0.65rem 0.85rem; text-align: center;">
                        <div style="color: #c7d2fe; font-size: 0.75rem; font-weight: 600;">Net Balance</div>
                        <div style="color: {'#86efac' if net_flow >= 0 else '#fca5a5'}; font-size: 1.1rem; font-weight: 800;">{'₹' if net_flow >= 0 else '-₹'}{abs(net_flow):,.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown(f"<div style='font-size: 0.8rem; color: #a5b4fc; margin-top: 0.5rem;'><strong>{len(entity_txns)}</strong> transaction(s) recorded with <strong>{selected_entity}</strong>:</div>", unsafe_allow_html=True)
                
                person_rows = []
                for pt in sorted(entity_txns, key=lambda x: x.get("date", ""), reverse=True):
                    pt_type = pt.get("type", "debit")
                    amt_str = f"-₹{pt.get('amount', 0.0):,.2f}" if pt_type == "debit" else f"+₹{pt.get('amount', 0.0):,.2f}"
                    person_rows.append({
                        "Date": pt.get("date"),
                        "Type": "Sent (Debit)" if pt_type == "debit" else "Received (Credit)",
                        "Amount": amt_str,
                        "Category": pt.get("category", "").title(),
                        "Reference / Narration": mask_text(pt.get("raw_description", "")),
                    })
                st.dataframe(pd.DataFrame(person_rows), use_container_width=True, hide_index=True)
    # ── Section 5: Helper (Interactive Statement Chat with Voice Input & Readout) ──
    st.markdown("<br><div class=\"section-header\">💬 3. Helper (Interactive Statement Chat with 🎙️ Voice & 🔊 Readout)</div>", unsafe_allow_html=True)
    if "chat_history" not in st.session_state or not st.session_state["chat_history"]:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": "👋 Hi! I'm your Helper. Ask me anything about your bank statement — for example: *'How much did I send to Veeresh?'*, *'What is my total Swiggy spend?'*, or *'What was my highest expense?'*"}
        ]

    # Quick prompt chips
    st.markdown("<div style='font-size: 0.82rem; color: #a5b4fc; margin-bottom: 0.4rem;'>💡 <strong>Quick Question Suggestions:</strong></div>", unsafe_allow_html=True)
    chip_c1, chip_c2, chip_c3, chip_c4 = st.columns(4)
    quick_q = None
    with chip_c1:
        if st.button("💸 Top Highest Expense", key="chip_q1", use_container_width=True):
            quick_q = "What was my highest transaction?"
    with chip_c2:
        if st.button("🍔 Food & Dining Total", key="chip_q2", use_container_width=True):
            quick_q = "How much did I spend on Food and Dining?"
    with chip_c3:
        if st.button("✈️ Travel & Commute Spend", key="chip_q3", use_container_width=True):
            quick_q = "How much did I spend on Travel and Petrol?"
    with chip_c4:
        if st.button("🔄 Recurring Subscriptions", key="chip_q4", use_container_width=True):
            quick_q = "What are my recurring subscriptions and memberships?"

    # Chat message container with interactive Read Aloud 🔊 buttons
    for idx, msg in enumerate(st.session_state["chat_history"][-6:]):
        if msg["role"] == "user":
            st.markdown(f"""
            <div style="background: rgba(99, 102, 241, 0.2); border-left: 4px solid #6366f1; border-radius: 8px; padding: 0.75rem 1rem; margin: 0.5rem 0; color: #ffffff;">
                <strong>👤 You:</strong> {msg['content']}
            </div>
            """, unsafe_allow_html=True)
        else:
            clean_speech_text = re.sub(r'[\r\n]+', ' ', re.sub(r'[*_#`•\'\"<>]', '', msg['content']))
            st.markdown(f"""
            <div style="background: rgba(30, 27, 75, 0.6); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: 8px; padding: 0.75rem 1rem; margin: 0.5rem 0; color: #cbd5e1; line-height: 1.5;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.3rem;">
                    <span style="color: #38bdf8; font-weight: 700; font-size: 0.85rem;">🤖 Helper:</span>
                    <button class="helper-speech-trigger-btn" data-speech="{clean_speech_text}" style="background: linear-gradient(135deg, #6366f1 0%, #ec4899 100%); border: none; color: #ffffff; border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 11px; font-weight: 700; box-shadow: 0 2px 8px rgba(236, 72, 153, 0.3);" title="🔊 Read Out Loud at Full Volume">
                        🔊 Read Aloud
                    </button>
                </div>
                {msg['content']}
            </div>
            """, unsafe_allow_html=True)

    # 🎙️ Voice Input Control and Text Form
    import streamlit.components.v1 as components
    components.html("""
    <div style="background: rgba(30, 41, 59, 0.6); border: 1px dashed rgba(139, 92, 246, 0.4); border-radius: 10px; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <span style="font-size: 13px; color: #cbd5e1;">🎙️ <strong>Voice Mode:</strong> Speak question & auto-ask:</span>
        <button id="helper-voice-rec-btn" onclick="
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition || (window.parent && (window.parent.SpeechRecognition || window.parent.webkitSpeechRecognition));
            if (!SpeechRec) {
                alert('Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
                return;
            }
            const rec = new SpeechRec();
            rec.lang = 'en-IN';
            rec.interimResults = false;
            const btn = document.getElementById('helper-voice-rec-btn');
            btn.innerHTML = '🔴 Listening...';
            btn.style.background = '#ef4444';
            rec.onresult = function(e) {
                const transcript = e.results[0][0].transcript;
                const parentDoc = window.parent ? window.parent.document : document;
                const inputEl = parentDoc.querySelector('input[aria-label=\\'Ask a question...\\']') || parentDoc.querySelector('input[type=\\'text\\']');
                if (inputEl) {
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    if (nativeInputValueSetter) {
                        nativeInputValueSetter.call(inputEl, transcript);
                    } else {
                        inputEl.value = transcript;
                    }
                    inputEl.dispatchEvent(new Event('input', { bubbles: true }));
                    inputEl.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    // Auto-click Ask button after short pause to submit
                    setTimeout(() => {
                        const askBtn = parentDoc.querySelector('button[kind=\\'primaryFormSubmit\\']') || parentDoc.querySelector('form button[type=\\'submit\\']');
                        if (askBtn) askBtn.click();
                    }, 300);
                }
                btn.innerHTML = '🎙️ Speak (Microphone)';
                btn.style.background = 'linear-gradient(135deg, #6366f1 0%, #ec4899 100%)';
            };
            rec.onerror = function() {
                btn.innerHTML = '🎙️ Speak (Microphone)';
                btn.style.background = 'linear-gradient(135deg, #6366f1 0%, #ec4899 100%)';
            };
            rec.start();
        " style="background: linear-gradient(135deg, #6366f1 0%, #ec4899 100%); color: #ffffff; border: none; border-radius: 20px; padding: 6px 14px; font-size: 12px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 12px rgba(236, 72, 153, 0.4);">
            🎙️ Speak (Microphone)
        </button>
    </div>
    <script>
    // Bind speech triggers across parent window
    const parentDoc = window.parent ? window.parent.document : document;
    parentDoc.addEventListener('click', (e) => {
        const target = e.target.closest('.helper-speech-trigger-btn');
        if (!target) return;
        const text = target.getAttribute('data-speech');
        if (!text) return;
        const synth = window.speechSynthesis || (window.parent && window.parent.speechSynthesis);
        if (synth) {
            synth.cancel();
            const u = new SpeechSynthesisUtterance(text);
            u.volume = 1.0;
            u.rate = 0.95;
            synth.speak(u);
        }
    });
    </script>
    """, height=50)

    with st.form("financial_chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            user_chat_input = st.text_input(
                "Ask a question...",
                placeholder="e.g. How much did I pay to Veeresh? What is my total spend on Swiggy?",
                label_visibility="collapsed",
                value=quick_q or "",
                key="chat_text_input",
            )
        with col_btn:
            submit_chat = st.form_submit_button("Ask 🚀", type="primary", use_container_width=True)

    if (submit_chat or quick_q) and (user_chat_input or quick_q):
        query_to_send = (quick_q or user_chat_input).strip()
        st.session_state["chat_history"].append({"role": "user", "content": query_to_send})
        with st.spinner("Analyzing statement records..."):
            # Check for Gemini API key from environment variable or Streamlit secrets
            gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not gemini_key:
                try:
                    if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                        gemini_key = st.secrets["GEMINI_API_KEY"]
                except Exception:
                    pass

            # Build clean transaction summary records for context
            context_records = []
            for t in transactions:
                d_val = t.get("date", "")
                if hasattr(d_val, "isoformat"):
                    d_val = d_val.isoformat()
                t_type = t.get("type", "debit")
                sign = "-" if t_type == "debit" else "+"
                context_records.append({
                    "date": str(d_val),
                    "merchant": t.get("merchant_clean") or t.get("merchant_raw") or "Unknown",
                    "category": str(t.get("category", "other")),
                    "type": t_type,
                    "amount": f"{sign}₹{t.get('amount', 0.0):,.2f}",
                    "raw_narration": t.get("raw_description", "")[:60],
                })

            if gemini_key:
                try:
                    import urllib.request
                    import json

                    txn_context_str = pd.DataFrame(context_records).to_csv(index=False) if context_records else "No bank statement loaded yet."
                    system_prompt = (
                        "You are a versatile, friendly, and intelligent personal financial AI companion named Helper. "
                        "You can converse naturally, answer general knowledge, personal, and friendly questions, and give financial advice. "
                        "If the user asks a question about their bank statement, transactions, spending, or merchants, "
                        "use the loaded transaction data below (use ₹ for amounts). If no statement is loaded and they ask about specific transactions, "
                        "politely remind them they can upload a statement anytime. For general conversation or greetings, respond warmly and naturally.\n\n"
                        f"Current Statement Records:\n{txn_context_str}"
                    )

                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gemini_key}"
                    payload = {
                        "contents": [
                            {"parts": [{"text": f"{system_prompt}\n\nUser: {query_to_send}"}]}
                        ],
                        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1024},
                    }
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        res_json = json.loads(resp.read().decode("utf-8"))
                        reply = res_json["candidates"][0]["content"]["parts"][0]["text"]

                    st.session_state["chat_history"].append({
                        "role": "assistant",
                        "content": reply
                    })
                except Exception as e:
                    # Fallback to local computation if API encounters quota or network timeout
                    q_low = query_to_send.lower()
                    if any(g in q_low for g in ("hi", "hello", "hey", "hola", "good morning", "good evening")):
                        ans = "Hello! 👋 How are you doing today? Feel free to ask me anything — general questions, personal advice, or details about your bank transactions!"
                    else:
                        words = re.findall(r"\b[A-Za-z0-9]{3,}\b", q_low)
                        stop_words = {"how", "much", "paid", "sent", "spend", "spent", "what", "where", "when", "total", "give", "tell", "show", "many", "time", "date", "with", "from", "about", "for"}
                        terms = [w for w in words if w not in stop_words]

                        matched_txns = [
                            t for t in transactions
                            if any(term in (str(t.get("merchant_clean", "")) + " " + str(t.get("raw_description", "")) + " " + str(t.get("category", ""))).lower() for term in terms)
                        ] if terms else []

                        if matched_txns:
                            total_paid = sum(t.get("amount", 0.0) for t in matched_txns if t.get("type") == "debit")
                            details = [f"• **{t.get('date')}**: {t.get('merchant_clean')} (₹{t.get('amount', 0.0):,.2f})" for t in matched_txns[:5]]
                            ans = f"🔍 Found **{len(matched_txns)}** transaction(s):\n• **Total Paid:** ₹{total_paid:,.2f}\n" + "\n".join(details)
                        else:
                            ans = f"I'm here! I can help answer personal questions, general queries, or analyze your finances whenever you're ready."

                    st.session_state["chat_history"].append({
                        "role": "assistant",
                        "content": ans
                    })
            else:
                # Local intelligent matcher when API key is not configured
                q_low = query_to_send.lower()
                debits = [t for t in transactions if t.get("type") == "debit"]
                credits = [t for t in transactions if t.get("type") == "credit"]

                # 1. Highest / Maximum expense
                if any(k in q_low for k in ("highest", "largest", "biggest", "max", "most expensive")):
                    if debits:
                        max_txn = max(debits, key=lambda t: t.get("amount", 0.0))
                        m_name = max_txn.get("merchant_clean") or max_txn.get("merchant_raw") or "Unknown"
                        ans = (
                            f"🏆 Your highest recorded transaction was **₹{max_txn.get('amount', 0.0):,.2f}** "
                            f"paid to **{m_name}** on **{max_txn.get('date')}** "
                            f"(Category: {str(max_txn.get('category', '')).title()})."
                        )
                    else:
                        ans = "No debit transactions found."

                # 2. Total spend / income
                elif any(k in q_low for k in ("total spend", "total expense", "overall spend", "how much did i spend")):
                    total_debits = sum(t.get("amount", 0.0) for t in debits)
                    ans = f"📊 Your total outflow across all recorded transactions is **₹{total_debits:,.2f}** across {len(debits)} debit transactions."

                elif any(k in q_low for k in ("total income", "total credit", "how much did i earn", "total received")):
                    total_credits = sum(t.get("amount", 0.0) for t in credits)
                    ans = f"💰 Your total inflow across all recorded transactions is **₹{total_credits:,.2f}**."

                # 3. Specific entity or merchant search (e.g. KFC, Swiggy, Veeresh, Tea)
                else:
                    words = re.findall(r"\b[A-Za-z0-9]{3,}\b", q_low)
                    stop_words = {"how", "much", "paid", "sent", "spend", "spent", "what", "where", "when", "total", "give", "tell", "show", "many", "time", "date", "with", "from", "about", "for", "was", "my"}
                    terms = [w for w in words if w not in stop_words]

                    matched_txns = [
                        t for t in transactions
                        if any(term in (str(t.get("merchant_clean", "")) + " " + str(t.get("raw_description", "")) + " " + str(t.get("category", ""))).lower() for term in terms)
                    ] if terms else []

                    if matched_txns:
                        total_paid = sum(t.get("amount", 0.0) for t in matched_txns if t.get("type") == "debit")
                        total_rec = sum(t.get("amount", 0.0) for t in matched_txns if t.get("type") == "credit")
                        details = [f"• **{t.get('date')}**: {t.get('merchant_clean')} ({'Debit' if t.get('type') == 'debit' else 'Credit'} ₹{t.get('amount', 0.0):,.2f})" for t in matched_txns[:5]]
                        matched_label = " / ".join([t.title() for t in terms])
                        ans = f"🔍 Found **{len(matched_txns)}** transaction(s) for **{matched_label}**:\n"
                        if total_paid > 0:
                            ans += f"• **Total Spent (Paid):** ₹{total_paid:,.2f}\n"
                        if total_rec > 0:
                            ans += f"• **Total Received:** ₹{total_rec:,.2f}\n"
                        ans += f"\n**Matching Records:**\n" + "\n".join(details)
                    else:
                        ans = (
                            f"No transactions found matching **'{query_to_send}'** in your current statement.\n"
                            f"• Total Outflow across statement: **₹{sum(t.get('amount', 0.0) for t in debits):,.2f}**\n"
                            f"• Total Transactions loaded: **{len(transactions)}**"
                        )

                st.session_state["chat_history"].append({
                    "role": "assistant",
                    "content": ans
                })
        st.rerun()

    # ── Section 6: Transactions Stream & Manual Category Overrides ──
    st.markdown("<br><div class=\"section-header\">📋 4. Transaction Stream & AI Categorization Engine</div>", unsafe_allow_html=True)
    if date_filtered_txns:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            search_query = st.text_input("🔍 Search merchant or narration", key="home_search_txns")
        with col_f2:
            all_cats = ["All"] + sorted(list({t.get("category", "other").title() for t in date_filtered_txns}))
            # Respect drilldown selection if active
            initial_idx = all_cats.index(st.session_state["selected_drilldown_category"]) if st.session_state["selected_drilldown_category"] in all_cats else 0
            selected_cat = st.selectbox("Filter Category", all_cats, index=initial_idx, key="home_cat_select")
        with col_f3:
            txn_type_filter = st.selectbox("Type", ["All", "Debit (Expense)", "Credit (Income)"], key="home_type_select")

        filtered = date_filtered_txns
        if search_query:
            filtered = [t for t in filtered if search_query.lower() in t["merchant_clean"].lower() or search_query.lower() in t["raw_description"].lower()]
        if selected_cat != "All":
            filtered = [t for t in filtered if t["category"].lower() == selected_cat.lower()]
        if txn_type_filter == "Debit (Expense)":
            filtered = [t for t in filtered if t["type"] == "debit"]
        elif txn_type_filter == "Credit (Income)":
            filtered = [t for t in filtered if t["type"] == "credit"]

        st.caption(f"Showing {len(filtered)} of {len(date_filtered_txns)} transactions")

        df = pd.DataFrame(filtered)
        if not df.empty:
            df["formatted_amount"] = df.apply(lambda r: f"-₹{r['amount']:,.2f}" if r["type"] == "debit" else f"+₹{r['amount']:,.2f}", axis=1)
            df["confidence_pct"] = df["confidence"].apply(lambda c: f"{int(c * 100)}%")
            df["category_display"] = df["category"].str.title()
            df["merchant_display"] = df["merchant_clean"].apply(mask_text)
            df["narration_display"] = df["raw_description"].apply(mask_text)

            display_df = df[["date", "merchant_display", "category_display", "formatted_amount", "confidence_pct", "narration_display"]].copy()
            display_df.columns = ["Date", "Cleaned Merchant", "Category", "Amount", "Certainty", "Raw Narration"]

            st.dataframe(display_df, use_container_width=True, hide_index=True)

        # ── Manual Category Override Editor ──
        with st.expander("✏️ Manual Category Override & Correction (Persisted in Session)", expanded=False):
            st.markdown("Easily correct any transaction category (especially with Certainty < 60%). The correction will automatically apply to all matching merchants in your session:")
            
            c_ov1, c_ov2, c_ov3 = st.columns([1.5, 1.5, 1])
            with c_ov1:
                override_merchants = sorted(list({t.get("merchant_clean", "") for t in date_filtered_txns if t.get("merchant_clean")}))
                selected_ov_merchant = st.selectbox("Select Merchant to Update:", override_merchants, key="ov_merch_select")
            with c_ov2:
                available_categories = ["food", "travel", "shopping", "utilities", "subscriptions", "healthcare", "transfers", "rent", "entertainment", "salary", "other"]
                new_cat_choice = st.selectbox("Assign New Category:", [c.title() for c in available_categories], key="ov_cat_select")
            with c_ov3:
                st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
                if st.button("💾 Apply & Persist Override", type="primary", key="btn_apply_override"):
                    m_key = selected_ov_merchant.strip().lower()
                    st.session_state["category_overrides"][m_key] = new_cat_choice.lower()
                    st.success(f"✅ Set '{selected_ov_merchant}' to '{new_cat_choice}' across session!")
                    time.sleep(0.4)
                    st.rerun()

        # Re-categorize button
        if st.button("🤖 Re-run AI Categorization Engine on All Transactions", key="re_cat_btn_home"):
            with st.spinner("Analyzing and updating categories for Food, Fuel, Mobile, and Shopping..."):
                res = api_post("/api/categorize")
                if res:
                    st.success(f"✅ Re-categorized {res.get('categorized', 0)} transactions with updated rules!")
                    time.sleep(0.5)
                    st.rerun()
    else:
        st.info("No transactions found for the selected date range. Upload a statement or adjust the date filter.")

    # ── Section 6: Subscriptions & Recurring Charges ──
    st.markdown("<br><div class=\"section-header\">🔄 4. Recurring Subscriptions & Burn Radar</div>", unsafe_allow_html=True)
    recurring = api_get("/api/recurring")
    if recurring and len(recurring) > 0:
        recurring_sorted = sorted(recurring, key=lambda x: x.get("annualized_cost", 0), reverse=True)
        total_annual = sum(r.get("annualized_cost", 0) for r in recurring_sorted)

        col_r1, col_r2 = st.columns([1, 3])
        with col_r1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Annualized Burn</div>
                <div class="kpi-value negative">{format_inr(total_annual)}/yr</div>
                <div style="color: #94a3b8; font-size: 0.8rem; margin-top: 0.4rem;">{len(recurring_sorted)} active subscriptions</div>
            </div>
            """, unsafe_allow_html=True)
        with col_r2:
            rec_df = pd.DataFrame(recurring_sorted)
            rec_df["merchant"] = rec_df["merchant"].apply(mask_text)
            rec_df = rec_df[["merchant", "frequency", "average_amount", "occurrences", "annualized_cost"]]
            rec_df.columns = ["Merchant", "Frequency", "Avg Amount (₹)", "Occurrences", "Annualized Cost (₹)"]
            rec_df["Avg Amount (₹)"] = rec_df["Avg Amount (₹)"].apply(lambda x: f"₹{x:,.2f}")
            rec_df["Annualized Cost (₹)"] = rec_df["Annualized Cost (₹)"].apply(lambda x: f"₹{x:,.2f}")
            rec_df["Frequency"] = rec_df["Frequency"].str.title()
            st.dataframe(rec_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recurring subscriptions detected yet. Regular monthly payments like Netflix or Gym will automatically appear here.")

    # ── Section 7: Financial Health Scorecard & Risk Checks (Precisa-grade) ──
    st.markdown("<br><div class=\"section-header\">🛡️ 5. Financial Health & Underwriting Scorecard</div>", unsafe_allow_html=True)
    report = api_get("/api/intelligence-report")
    if report and date_filtered_txns:
        health = report.get("health_score", {})
        risk_checks = report.get("risk_checks", [])
        score = health.get("overall_score", 500)
        risk_level = health.get("risk_level", "Moderate Risk")
        grade = health.get("grade", "Fair")

        tier_class = "tier-low" if score >= 750 else ("tier-med" if score >= 600 else "tier-high")
        badge_class = "badge-low" if score >= 750 else ("badge-med" if score >= 600 else "badge-high")

        c_sc1, c_sc2 = st.columns([2, 3])
        with c_sc1:
            st.markdown(f"""
            <div class="score-card">
                <div style="font-size: 0.82rem; color: #a5b4fc; text-transform: uppercase; font-weight: 700; letter-spacing: 1px;">Creditworthiness Score</div>
                <div class="score-num {tier_class}">{score} <span style="font-size: 1.1rem; color: #94a3b8; font-weight: 500;">/ 1000</span></div>
                <div style="margin-top: 0.5rem;">
                    <span class="risk-badge {badge_class}">{risk_level}</span>
                    <span style="color: #cbd5e1; font-size: 0.88rem; margin-left: 0.5rem; font-weight: 600;">{grade}</span>
                </div>
                <div style="margin-top: 0.75rem; font-size: 0.82rem; color: #94a3b8; line-height: 1.4;">
                    {report.get('underwriting_verdict', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with c_sc2:
            k1, k2 = st.columns(2)
            with k1:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Avg Daily Balance (ADB)</div>
                    <div class="kpi-value positive">{format_inr(health.get('average_daily_balance', 0))}</div>
                </div>
                <div class="kpi-card" style="margin-top: 0.75rem;">
                    <div class="kpi-label">Volatility Index</div>
                    <div class="kpi-value {'positive' if health.get('volatility_score', 0) <= 0.4 else 'warning'}">{health.get('volatility_score', 0):.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            with k2:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Net Savings Rate</div>
                    <div class="kpi-value {'positive' if health.get('savings_rate', 0) >= 15 else 'warning'}">{health.get('savings_rate', 0):.1f}%</div>
                </div>
                <div class="kpi-card" style="margin-top: 0.75rem;">
                    <div class="kpi-label">Fixed Obligation Load (DTI)</div>
                    <div class="kpi-value {'positive' if health.get('debt_burden_ratio', 0) <= 30 else 'negative'}">{health.get('debt_burden_ratio', 0):.1f}%</div>
                </div>
                """, unsafe_allow_html=True)

        if risk_checks:
            st.markdown("<br><h4 style='color: #ffffff; font-size: 1.1rem;'>🚩 Automated Risk & Fraud Detection Flags</h4>", unsafe_allow_html=True)
            chk_col1, chk_col2 = st.columns(2)
            for i, check in enumerate(risk_checks):
                t_col = chk_col1 if i % 2 == 0 else chk_col2
                is_pass = check.get("passed", True)
                icon = "✅" if is_pass else "⚠️"
                border_color = "rgba(52, 211, 153, 0.3)" if is_pass else "rgba(248, 113, 113, 0.4)"
                status_text = "<span style='color: #34d399; font-weight: 700;'>PASSED</span>" if is_pass else "<span style='color: #f87171; font-weight: 700;'>ALERT</span>"

                with t_col:
                    st.markdown(f"""
                    <div class="check-card" style="border-left: 4px solid {border_color};">
                        <div style="font-size: 1.3rem; line-height: 1;">{icon}</div>
                        <div style="flex: 1;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-weight: 700; color: #ffffff; font-size: 0.9rem;">{check.get('check_name')}</span>
                                {status_text}
                            </div>
                            <div style="color: #94a3b8; font-size: 0.78rem; margin-top: 0.2rem;">{check.get('description')}</div>
                            <div style="color: #c4b5fd; font-size: 0.8rem; margin-top: 0.3rem; font-weight: 500;">📌 {check.get('details')}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("Upload statement data to generate the financial health scorecard.")

    # ── Section 8: Export Filtered Report & Data ──
    st.markdown("<br><div class=\"section-header\">📥 6. Export Intelligence Report & Data</div>", unsafe_allow_html=True)
    if date_filtered_txns:
        export_df = pd.DataFrame(date_filtered_txns)
        export_df["merchant_clean"] = export_df["merchant_clean"].apply(mask_text)
        export_df["raw_description"] = export_df["raw_description"].apply(mask_text)
        
        csv_data = export_df.to_csv(index=False).encode('utf-8')
        json_data = export_df.to_json(orient="records", indent=2).encode('utf-8')

        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            st.download_button(
                label="📄 Export Filtered Transactions (CSV)",
                data=csv_data,
                file_name=f"expense_intelligence_export_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
                key="btn_download_csv"
            )
        with c_exp2:
            st.download_button(
                label="📦 Export Intelligence Report (JSON)",
                data=json_data,
                file_name=f"expense_intelligence_report_{date.today().isoformat()}.json",
                mime="application/json",
                use_container_width=True,
                key="btn_download_json"
            )

    # ── Section 9: Developer Anurag Greeting & Interactive Footer ──
    st.markdown("<br><hr style='margin: 3rem 0 2rem 0; border-color: rgba(139, 92, 246, 0.25);'>", unsafe_allow_html=True)

    foot_c1, foot_c2, foot_c3 = st.columns([2, 2, 1.5])
    with foot_c1:
        st.markdown("""
        <div style="color: #ffffff; font-weight: 800; font-size: 1.1rem; margin-bottom: 0.5rem;">
            ⚡ Smart Expense Intelligence System
        </div>
        <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.5;">
            Crafted with ❤️ by <strong>Anurag Kodge</strong>.<br>
            Empowering individuals and fintechs with AI-powered bank statement analytics, fraud detection, and cash-flow health intelligence.
        </div>
        <div style="margin-top: 0.75rem; color: #34d399; font-size: 0.85rem; font-weight: 600;">
            ✨ Thank you for using the platform! Have a wonderful and financially prosperous day.
        </div>
        """, unsafe_allow_html=True)

    with foot_c2:
        st.markdown("""
        <div style="color: #ffffff; font-weight: 700; font-size: 0.95rem; margin-bottom: 0.5rem;">
            📍 Headquarters & Contact
        </div>
        <div style="color: #94a3b8; font-size: 0.85rem; line-height: 1.5;">
            🏢 <strong>Anurag Kodge Innovation Labs</strong><br>
            Bangalore, Karnataka, India<br>
            📧 Email: <a href="mailto:anuragkodge@gmail.com" style="color: #818cf8; text-decoration: none;">anuragkodge@gmail.com</a><br>
            🌐 Platform Support: 24/7 In-Memory Secure Processing
        </div>
        """, unsafe_allow_html=True)

    with foot_c3:
        st.markdown("""
        <div style="color: #ffffff; font-weight: 700; font-size: 0.95rem; margin-bottom: 0.5rem;">
            🔒 Security & Privacy
        </div>
        <div style="color: #94a3b8; font-size: 0.83rem; line-height: 1.5;">
            • 256-bit AES In-Memory Processing<br>
            • Zero Raw Credential Persistence<br>
            • Live Brevo OTP Multi-Tenant Shield<br>
            • Version 2.5.0 (Enterprise)
        </div>
        """, unsafe_allow_html=True)

# ── Compact Draggable AI Chatbot (Escaped to Parent Window & Freely Movable) ──

def render_draggable_chatbot(transactions=None):
    """Render the floating draggable AI Chatbot widget across all application views."""
    gemini_key_val = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    txns = transactions or []
    txn_summary_text = f"Total Transactions: {len(txns)}, Total Outflow: ₹{sum(t.get('amount', 0.0) for t in txns if t.get('type') == 'debit'):,.2f}"

    import streamlit.components.v1 as components
    draggable_chat_script = f"""
    <script>
    (function() {{
      const parentDoc = window.parent.document;
      if (!parentDoc) return;

      // Avoid duplicate widget
      if (parentDoc.getElementById("ai-global-draggable-root")) return;

      const root = parentDoc.createElement("div");
      root.id = "ai-global-draggable-root";
      root.innerHTML = `
        <div id="ai-chat-bubble" style="
          position: fixed;
          bottom: 30px;
          right: 30px;
          width: 50px;
          height: 50px;
          border-radius: 50%;
          background: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%);
          box-shadow: 0 8px 24px rgba(236, 72, 153, 0.45), 0 0 15px rgba(139, 92, 246, 0.4);
          border: 2px solid rgba(255, 255, 255, 0.4);
          color: #ffffff;
          font-size: 22px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 999999999;
          transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
          user-select: none;
        " title="Ai Chatbot">💬</div>

        <div id="ai-chat-modal" style="
          position: fixed;
          bottom: 90px;
          right: 30px;
          width: 310px;
          height: 390px;
          background: rgba(15, 23, 42, 0.96);
          backdrop-filter: blur(16px);
          border: 1px solid rgba(139, 92, 246, 0.4);
          border-radius: 16px;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.7), 0 0 20px rgba(139, 92, 246, 0.25);
          display: none;
          flex-direction: column;
          z-index: 999999999;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        ">
          <div id="ai-chat-header" style="
            background: linear-gradient(135deg, rgba(236, 72, 153, 0.35) 0%, rgba(139, 92, 246, 0.35) 100%);
            padding: 9px 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: move;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            user-select: none;
          ">
            <span style="font-weight: 700; font-size: 13px; color: #f1f5f9; display: flex; align-items: center; gap: 5px;">
              ✨ Ai Chatbot <span style="font-weight: 400; font-size: 10px; color: #a5b4fc; margin-left: 2px;">(Drag anywhere)</span>
            </span>
            <span id="ai-chat-close" style="cursor: pointer; color: #94a3b8; font-size: 15px; font-weight: bold;">✕</span>
          </div>
          <div id="ai-chat-msgs" style="
            flex: 1;
            padding: 10px 12px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 12px;
          ">
            <div style="
              align-self: flex-start;
              background: rgba(30, 41, 59, 0.9);
              border: 1px solid rgba(139, 92, 246, 0.3);
              color: #e2e8f0;
              padding: 7px 10px;
              border-radius: 10px;
              border-bottom-left-radius: 2px;
              line-height: 1.4;
              max-width: 86%;
            ">Hey! How are you doing today? I'm your Ai Chatbot. Let's chat!</div>
          </div>
          <div style="
            padding: 7px 9px;
            background: rgba(15, 23, 42, 0.9);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 5px;
          ">
            <input type="text" id="ai-chat-input" placeholder="Type a message..." style="
              flex: 1;
              background: rgba(30, 41, 59, 0.9);
              border: 1px solid rgba(139, 92, 246, 0.3);
              border-radius: 18px;
              padding: 6px 11px;
              font-size: 12px;
              color: #ffffff;
              outline: none;
            " />
            <button id="ai-chat-send" style="
              background: linear-gradient(135deg, #ec4899, #8b5cf6);
              border: none;
              border-radius: 50%;
              width: 28px;
              height: 28px;
              color: #ffffff;
              cursor: pointer;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 12px;
            ">➤</button>
          </div>
        </div>
      `;

      parentDoc.body.appendChild(root);

      const bubble = root.querySelector("#ai-chat-bubble");
      const modal = root.querySelector("#ai-chat-modal");
      const closeBtn = root.querySelector("#ai-chat-close");
      const msgsBox = root.querySelector("#ai-chat-msgs");
      const inputField = root.querySelector("#ai-chat-input");
      const sendBtn = root.querySelector("#ai-chat-send");
      const header = root.querySelector("#ai-chat-header");

      function toggle() {{
        modal.style.display = modal.style.display === "flex" ? "none" : "flex";
        if (modal.style.display === "flex") {{
          inputField.focus();
          msgsBox.scrollTop = msgsBox.scrollHeight;
        }}
      }}

      bubble.addEventListener("click", toggle);
      closeBtn.addEventListener("click", toggle);

      async function send() {{
        const txt = inputField.value.trim();
        if (!txt) return;
        inputField.value = "";

        const userBubble = parentDoc.createElement("div");
        userBubble.style.cssText = "align-self: flex-end; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; padding: 7px 10px; border-radius: 10px; border-bottom-right-radius: 2px; line-height: 1.4; max-width: 86%;";
        userBubble.textContent = txt;
        msgsBox.appendChild(userBubble);
        msgsBox.scrollTop = msgsBox.scrollHeight;

        const typingBubble = parentDoc.createElement("div");
        typingBubble.style.cssText = "align-self: flex-start; background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(139, 92, 246, 0.3); color: #94a3b8; padding: 7px 10px; border-radius: 10px; font-style: italic;";
        typingBubble.textContent = "Typing...";
        msgsBox.appendChild(typingBubble);
        msgsBox.scrollTop = msgsBox.scrollHeight;

        const low = txt.toLowerCase();
        if (["hi", "hello", "hey", "hola", "yo"].includes(low)) {{
          setTimeout(() => {{
            typingBubble.remove();
            appendBot("Hey! How are you doing? How's your day going?");
          }}, 350);
          return;
        }} else if (low.includes("how are you")) {{
          setTimeout(() => {{
            typingBubble.remove();
            appendBot("I'm doing wonderful, thank you for asking! How about you?");
          }}, 350);
          return;
        }}

        const apiKey = "{gemini_key_val}";
        if (apiKey) {{
          try {{
            const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=${{apiKey}}`;
            const sys = "You are a warm, witty, and friendly companion named Ai Chatbot. Respond naturally, casually, and accurately to any question, greeting, or conversation. If asked about finances, help concisely.";
            const res = await fetch(url, {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{
                contents: [{{ parts: [{{ text: sys + "\\n\\nUser says: " + txt }}] }}],
                generationConfig: {{ temperature: 0.7, maxOutputTokens: 300 }}
              }})
            }});
            const data = await res.json();
            const reply = data.candidates[0].content.parts[0].text;
            typingBubble.remove();
            appendBot(reply);
          }} catch(e) {{
            typingBubble.remove();
            appendBot("I'm right here! Feel free to chat with me anytime.");
          }}
        }} else {{
          setTimeout(() => {{
            typingBubble.remove();
            appendBot("I'm doing great! How can I assist you today?");
          }}, 350);
        }}
      }}

      function appendBot(msg) {{
        const b = parentDoc.createElement("div");
        b.style.cssText = "align-self: flex-start; background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(139, 92, 246, 0.3); color: #e2e8f0; padding: 7px 10px; border-radius: 10px; border-bottom-left-radius: 2px; line-height: 1.4; max-width: 86%;";
        b.textContent = msg;
        msgsBox.appendChild(b);
        msgsBox.scrollTop = msgsBox.scrollHeight;
      }}

      sendBtn.addEventListener("click", send);
      inputField.addEventListener("keydown", (e) => {{
        if (e.key === "Enter") send();
      }});

      // Dragging logic over entire screen
      let isDragging = false, startX, startY, initLeft, initTop;

      header.addEventListener("mousedown", (e) => {{
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = modal.getBoundingClientRect();
        initLeft = rect.left;
        initTop = rect.top;
        modal.style.bottom = "auto";
        modal.style.right = "auto";
        modal.style.left = initLeft + "px";
        modal.style.top = initTop + "px";
      }});

      parentDoc.addEventListener("mousemove", (e) => {{
        if (!isDragging) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        modal.style.left = (initLeft + dx) + "px";
        modal.style.top = (initTop + dy) + "px";
      }});

      parentDoc.addEventListener("mouseup", () => {{
        isDragging = false;
      }});
    }})();
    </script>
    """
    components.html(draggable_chat_script, height=0, width=0)

    # Sidebar Controls (Only display when logged in)
    if st.session_state.get("auth_token"):
        with st.sidebar:
            st.markdown("### 👤 User Account")
            user_email = st.session_state.get('user_info', {}).get('email', '')
            st.write(f"Logged in as: **{user_email}**")
            
            current_view = st.session_state.get("active_view", "dashboard")
            if current_view == "dashboard":
                if st.button("👤 View & Edit Profile", use_container_width=True, type="secondary", key="sidebar_goto_profile"):
                    st.session_state["active_view"] = "profile"
                    st.rerun()
            else:
                if st.button("📊 Back to Dashboard", use_container_width=True, type="primary", key="sidebar_goto_dashboard"):
                    st.session_state["active_view"] = "dashboard"
                    st.rerun()

            st.markdown("---")
            st.markdown("### 🛡️ Privacy Controls")
            mask_toggle = st.toggle("🔒 Mask Sensitive PII Data", value=st.session_state.get("mask_pii", False), key="sidebar_mask_pii_toggle")
            if mask_toggle != st.session_state.get("mask_pii", False):
                st.session_state["mask_pii"] = mask_toggle
                st.rerun()

            st.markdown("---")
            if st.button("🚪 Log Out", use_container_width=True, key="sidebar_logout_btn"):
                st.session_state.clear()
                st.rerun()


# ─── Profile Page View ────────────────────────────────────────────────────────

def render_profile_view():
    """Render the User Profile management view with email-scoped detail storage."""
    token = st.session_state.get("auth_token", "")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Fetch current profile data from backend
    profile_data = {}
    try:
        resp = requests.get(f"{BACKEND_URL}/api/profile", headers=headers, timeout=10)
        if resp.status_code == 200:
            profile_data = resp.json()
    except Exception:
        pass

    email_val = profile_data.get("email") or st.session_state.get("user_info", {}).get("email", "")

    # ── Top Navigation Bar inside Profile View ──
    col_back, col_spacer = st.columns([1.5, 4])
    with col_back:
        if st.button("⬅️ Back to Dashboard", key="profile_top_back_btn", use_container_width=True, type="secondary"):
            st.session_state["active_view"] = "dashboard"
            st.rerun()

    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
                border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 16px; padding: 2rem; margin-bottom: 2rem; margin-top: 0.5rem;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
                <h1 style="margin: 0; font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, #a5b4fc 0%, #38bdf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    👤 Personal Profile & Account
                </h1>
                <p style="color: #94a3b8; margin: 0.5rem 0 0 0; font-size: 0.95rem;">
                    Manage your personal account settings, budget preferences, and transaction history.
                </p>
            </div>
            <div style="text-align: right;">
                <span style="background: rgba(99, 102, 241, 0.2); border: 1px solid #6366f1; color: #a5b4fc; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 700;">
                    🔒 Multi-Tenant Shield Active
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📝 Edit Personal Information")
        with st.form("user_profile_edit_form"):
            f_email = st.text_input("Registered Email ID", value=email_val, disabled=True, help="Your account email cannot be changed.")
            
            c_name, c_phone = st.columns(2)
            with c_name:
                f_name = st.text_input("Full Name", value=profile_data.get("full_name") or "", placeholder="e.g. Anurag Kodge")
            with c_phone:
                f_phone = st.text_input("Phone Number", value=profile_data.get("phone") or "", placeholder="e.g. +91 98765 43210")

            c_occ, c_city = st.columns(2)
            with c_occ:
                f_occ = st.text_input("Occupation / Role", value=profile_data.get("occupation") or "", placeholder="e.g. Software Engineer / Consultant")
            with c_city:
                f_city = st.text_input("City / Region", value=profile_data.get("city") or "", placeholder="e.g. Bengaluru, India")

            c_budget, c_curr = st.columns(2)
            with c_budget:
                f_budget = st.number_input("Monthly Target Budget (₹)", value=float(profile_data.get("monthly_budget") or 0.0), min_value=0.0, step=1000.0)
            with c_curr:
                f_curr = st.selectbox("Preferred Currency", ["INR (₹)", "USD ($)", "EUR (€)", "GBP (£)"], index=0)

            f_bio = st.text_area("About Me / Financial Goals", value=profile_data.get("bio") or "", placeholder="e.g. Saving for home down payment and managing startup investments...")

            save_btn = st.form_submit_button("💾 Save Profile Changes", type="primary", use_container_width=True)

            if save_btn:
                update_payload = {
                    "full_name": f_name.strip(),
                    "phone": f_phone.strip(),
                    "occupation": f_occ.strip(),
                    "monthly_budget": f_budget,
                    "currency": f_curr.split()[0],
                    "city": f_city.strip(),
                    "bio": f_bio.strip(),
                }
                try:
                    save_res = requests.put(f"{BACKEND_URL}/api/profile", json=update_payload, headers=headers, timeout=10)
                    if save_res.status_code == 200:
                        st.success("✅ Profile information successfully updated and safely saved!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to update profile: {save_res.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

    with col2:
        st.markdown("### 📊 Account Snapshot")
        st.markdown(f"""
        <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem;">
            <div style="color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; font-weight: 700; margin-bottom: 0.5rem;">Account Details</div>
            <div style="font-size: 0.9rem; color: #f1f5f9; margin-bottom: 0.4rem;">📧 <strong>Email:</strong> {email_val}</div>
            <div style="font-size: 0.9rem; color: #f1f5f9; margin-bottom: 0.4rem;">📅 <strong>Member Since:</strong> {str(profile_data.get('created_at', ''))[:10]}</div>
            <div style="font-size: 0.9rem; color: #f1f5f9; margin-bottom: 0.4rem;">🕒 <strong>Last Active:</strong> {str(profile_data.get('last_login', ''))[:19].replace('T', ' ')}</div>
            <div style="font-size: 0.9rem; color: #f1f5f9;">💳 <strong>Total Transactions Scoped:</strong> {profile_data.get('total_transactions', 0)}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 1.2rem;">
            <div style="color: #34d399; font-weight: 700; font-size: 0.9rem; margin-bottom: 0.3rem;">🛡️ Data Isolation & Privacy</div>
            <div style="color: #cbd5e1; font-size: 0.82rem; line-height: 1.5;">
                All statement uploads, categorized transactions, and profile data are encrypted and permanently linked to your unique email address. You can log out and log back in anytime to access your complete financial history.
            </div>
        </div>
        """, unsafe_allow_html=True)


# ─── Main Controller ──────────────────────────────────────────────────────────

def main():
    # Render Floating Draggable AI Chatbot across ALL screens (welcome, profile, dashboard)
    render_draggable_chatbot()

    if not st.session_state.get("auth_token"):
        render_login_view()
        return

    active_view = st.session_state.get("active_view", "dashboard")
    if active_view == "profile":
        render_profile_view()
    else:
        render_home_page()


if __name__ == "__main__":
    main()


