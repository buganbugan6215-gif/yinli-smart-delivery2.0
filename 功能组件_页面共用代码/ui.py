from __future__ import annotations

import html
from typing import Any

import streamlit as st

from 功能组件_页面共用代码.order_state import staff_password


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { --ink:#1d2a3a; --ink-soft:#415166; --paper:#f5f7fb; --surface:#ffffff; --surface-blue:#eef4ff; --line:#dfe7f1; --muted:#718096; --brand:#1750df; --brand-dark:#103c9e; --accent:#ff8133; --accent-soft:#fff0e6; --success:#18794e; --success-soft:#e7f6ee; }
        .stApp { background:var(--paper); color:var(--ink); font-family:'Microsoft YaHei UI','Microsoft YaHei','Segoe UI',sans-serif; }
        [data-testid='stHeader'] { background:rgba(245,247,251,.94); }
        [data-testid='stSidebar'] { background:#eef3f9; border-right:1px solid var(--line); }
        [data-testid='stSidebar'] * { color:var(--ink); }
        [data-testid='stSidebarNav'] { display:none!important; }
        html { scroll-behavior:smooth; }
        ::selection { background:rgba(255,129,51,.24); color:var(--ink); }
        * { scrollbar-width:thin; scrollbar-color:#aebbd0 transparent; }
        .block-container { max-width:1360px; padding-top:1.35rem; padding-bottom:3.5rem; }
        h1,h2,h3,h4 { color:var(--ink); letter-spacing:-.025em; }
        h1 { font-size:2.65rem!important; line-height:1.12!important; font-weight:800!important; }
        h2 { font-size:1.9rem!important; line-height:1.2!important; }
        h3 { font-size:1.2rem!important; margin-top:1.6rem!important; }
        p, li, label, .stCaption { color:var(--ink-soft); line-height:1.65; }
        .brand-mark { width:42px; height:42px; display:grid; place-items:center; background:var(--brand); color:#fff!important; font-weight:800; letter-spacing:.05em; border-radius:12px; margin-bottom:8px; box-shadow:0 6px 16px rgba(23,80,223,.18); }
        .brand-name { font-weight:800; font-size:1.15rem; }
        .nav-section-label { margin:.2rem 0 .55rem; color:var(--muted); font-size:.72rem; font-weight:800; letter-spacing:.08em; }
        .page-kicker, .hero-kicker { color:var(--brand); font-size:.72rem; font-weight:800; letter-spacing:.12em; margin-bottom:.45rem; }
        .page-subtitle { color:var(--muted); font-size:1rem; margin-top:-.4rem; margin-bottom:1.45rem; }
        .hero-panel { background:linear-gradient(135deg,#123d9e 0%,#1750df 65%,#2868e9 100%); color:#fff; border-radius:16px; padding:2rem 2.2rem; display:grid; grid-template-columns:1.5fr .8fr; gap:2rem; align-items:end; margin:1.1rem 0 1.4rem; box-shadow:0 14px 30px rgba(16,60,158,.16); }
        .hero-panel h2 { color:#fff; margin:.2rem 0 .7rem; }
        .hero-panel p { color:#e2ebff; max-width:62ch; margin:0; line-height:1.7; }
        .hero-kicker { color:#ffd2b5; }
        .hero-index { border-left:1px solid rgba(255,255,255,.25); padding-left:1.5rem; display:grid; gap:.35rem; }
        .hero-index span, .hero-index small { color:#c9d9ff; font-size:.76rem; letter-spacing:.06em; }
        .hero-index strong { color:#fff; font-size:1.3rem; letter-spacing:.04em; }
        .metric-card { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:1rem 1.1rem; min-height:116px; box-shadow:0 4px 12px rgba(35,64,105,.04); }
        .metric-value { font-size:1.85rem; font-weight:800; color:var(--brand-dark); line-height:1.15; }
        .metric-label { font-size:.95rem; font-weight:700; margin-top:.55rem; }
        .metric-note { color:var(--muted); font-size:.78rem; margin-top:.2rem; }
        .route-board, .note-panel, .table-panel { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:1rem 1.15rem; box-shadow:0 4px 12px rgba(35,64,105,.04); }
        .route-row { display:grid; grid-template-columns:18px 1fr auto; gap:.8rem; align-items:center; padding:.85rem 0; border-bottom:1px solid var(--line); }
        .route-row:last-child { border-bottom:0; }
        .route-row b { display:block; }
        .route-row small { color:var(--muted); display:block; margin-top:.2rem; }
        .route-row strong { color:var(--brand); letter-spacing:.04em; }
        .route-dot { width:11px; height:11px; border-radius:50%; display:block; }
        .route-dot.noodle { background:var(--brand); } .route-dot.ginger { background:var(--accent); } .route-dot.reuse { background:#748297; }
        .note-panel { border-color:#f2cfb7; background:#fffaf6; }
        .note-panel p { margin:.2rem 0 .8rem; line-height:1.65; }
        .note-panel p:last-child { margin-bottom:.2rem; }
        .muted { color:var(--muted)!important; font-size:.9rem; }
        .section-label { color:var(--brand); font-weight:800; font-size:.88rem; margin:1.55rem 0 .55rem; }
        .section-intro { max-width:68ch; color:var(--ink-soft); margin:-.15rem 0 1rem; }
        [data-testid='stPageLink-NavLink'] { min-height:2.65rem; display:flex; align-items:center; padding:.75rem 1rem; border:1px solid var(--line)!important; border-radius:12px; background:var(--surface)!important; color:var(--brand-dark)!important; box-shadow:0 4px 12px rgba(35,64,105,.04); }
        [data-testid='stPageLink-NavLink']:hover { border-color:var(--brand)!important; background:var(--surface-blue)!important; color:var(--brand-dark)!important; transform:translateY(-2px); box-shadow:0 8px 18px rgba(23,80,223,.12); }
        [data-testid='stPageLink-NavLink']:focus-visible { outline:3px solid rgba(255,129,51,.38); outline-offset:2px; }
        .status-good { color:var(--success); background:var(--success-soft); padding:.24rem .6rem; border-radius:999px; font-size:.82rem; font-weight:700; }
        .status-warn { color:#b45309; background:var(--accent-soft); padding:.24rem .6rem; border-radius:999px; font-size:.82rem; font-weight:700; }
        .source-note { color:var(--muted); font-size:.78rem; border-top:1px solid var(--line); padding-top:.8rem; margin-top:2rem; }
        .stButton>button, .stDownloadButton>button, [data-testid='stPageLink-NavLink'] { transition:transform .18s cubic-bezier(.16,1,.3,1), box-shadow .18s ease, border-color .18s ease, background-color .18s ease, color .18s ease; }
        .stButton>button { border-radius:9px; border:1px solid var(--brand); color:var(--brand); background:var(--surface); font-weight:700; min-height:2.65rem; }
        .stButton>button:hover { border-color:var(--accent); color:var(--accent); background:#fffaf7; transform:translateY(-1px); box-shadow:0 6px 14px rgba(255,129,51,.12); }
        .stButton>button:active, .stDownloadButton>button:active, [data-testid='stPageLink-NavLink']:active { transform:translateY(1px) scale(.98); box-shadow:none; }
        .stButton>button[kind='primary'] { background:var(--accent); border-color:var(--accent); color:#fff; box-shadow:0 5px 14px rgba(255,129,51,.2); }
        .stButton>button[kind='primary']:hover { background:#e96f24; border-color:#e96f24; color:#fff; }
        .stDownloadButton>button { border-radius:9px; background:var(--brand); color:#fff; font-weight:700; border:1px solid var(--brand); }
        .stDownloadButton>button:hover { background:var(--brand-dark); border-color:var(--brand-dark); transform:translateY(-1px); box-shadow:0 6px 14px rgba(23,80,223,.16); }
        button:focus-visible, a:focus-visible { outline:3px solid rgba(255,129,51,.42)!important; outline-offset:3px!important; }
        [data-testid='stMetric'] { background:var(--surface); border:1px solid var(--line); padding:.85rem 1rem; border-radius:12px; box-shadow:0 4px 12px rgba(35,64,105,.04); }
        [data-testid='stMetricLabel'] { color:var(--muted); }
        [data-testid='stMetricValue'] { color:var(--brand-dark); }
        [data-testid='stDataFrame'] { border:1px solid var(--line); border-radius:10px; overflow:hidden; background:var(--surface); }
        [data-baseweb='select'] > div, [data-testid='stFileUploader'] section { border-color:var(--line); border-radius:10px; background:var(--surface-blue); transition:border-color .18s ease, box-shadow .18s ease, background-color .18s ease; }
        [data-baseweb='select'] > div:hover { border-color:var(--brand); box-shadow:0 4px 12px rgba(23,80,223,.08); }
        [data-baseweb='select'] > div:focus-within { border-color:var(--brand); box-shadow:0 0 0 3px rgba(23,80,223,.14); }
        input:focus, textarea:focus { border-color:var(--brand)!important; box-shadow:0 0 0 2px rgba(23,80,223,.14)!important; }
        .home-nav { display:flex; align-items:center; justify-content:space-between; padding:.25rem 0 1rem; border-bottom:1px solid rgba(29,42,58,.09); }
        .home-brand { display:flex; align-items:center; gap:.75rem; color:var(--ink); }
        .home-brand span { width:34px; height:34px; display:grid; place-items:center; border-radius:10px; background:var(--brand); color:#fff; font-size:.78rem; font-weight:900; box-shadow:0 8px 22px rgba(23,80,223,.18); }
        .home-brand strong { font-size:1rem; letter-spacing:-.01em; }
        .home-nav-copy { color:var(--muted); font-size:.84rem; }
        .st-key-home_hero { position:relative; overflow:hidden; margin-top:1.25rem; padding:clamp(1.4rem,4vw,4.1rem); border:1px solid rgba(23,80,223,.1); border-radius:28px; background:linear-gradient(145deg,#fff 0%,#f5f8ff 54%,#eaf1ff 100%); box-shadow:0 22px 70px rgba(24,59,120,.1); isolation:isolate; }
        .st-key-home_hero::before { content:""; position:absolute; z-index:-1; width:460px; height:460px; right:-180px; top:-210px; border-radius:50%; background:radial-gradient(circle,rgba(23,80,223,.18),rgba(23,80,223,0) 68%); animation:home-ambient 8s ease-in-out infinite alternate; }
        .home-hero-copy h1 { max-width:11ch; margin:0 0 1.15rem; font-size:clamp(2.75rem,5.3vw,5.7rem)!important; line-height:.99!important; letter-spacing:-.065em; color:#102c6d; }
        .home-hero-copy p { max-width:28rem; margin:0 0 1.35rem; font-size:clamp(1rem,1.4vw,1.2rem); color:#52627a; }
        .st-key-home_hero [data-testid='stImage'] { overflow:hidden; border-radius:20px; border:1px solid rgba(23,80,223,.13); background:#fff; box-shadow:0 22px 48px rgba(23,56,119,.18); animation:home-visual .95s .14s cubic-bezier(.16,1,.3,1) both; }
        .st-key-home_hero [data-testid='stImage'] img { transition:transform .8s cubic-bezier(.16,1,.3,1), filter .8s ease; }
        .st-key-home_hero [data-testid='stImage']:hover img { transform:scale(1.025); filter:saturate(1.06); }
        .st-key-home_hero [data-testid='stImage'] p { padding:.35rem .5rem .5rem; color:var(--muted); }
        .st-key-home_hero .home-hero-copy { animation:home-copy .8s cubic-bezier(.16,1,.3,1) both; }
        .st-key-home_hero .stButton>button { min-height:3rem; }
        .customer-journey { display:grid; gap:.75rem; padding:1.1rem; border:1px solid var(--line); border-radius:16px; background:#fff; box-shadow:0 20px 42px rgba(31,57,100,.10); }
        .customer-journey>div { display:grid; grid-template-columns:34px 1fr; gap:.18rem .8rem; align-items:center; padding:1rem; border-bottom:1px solid var(--line); }
        .customer-journey>div:last-child { border-bottom:0; }
        .customer-journey span { grid-row:span 2; width:32px; height:32px; display:grid; place-items:center; border-radius:50%; background:var(--surface-blue); color:var(--brand); font-size:.72rem; font-weight:800; }
        .customer-journey b { color:var(--ink); }
        .customer-journey small { color:var(--muted); }
        .home-proof { display:grid; grid-template-columns:repeat(4,1fr); margin:1rem 0 6rem; padding:1.2rem 1.4rem; border-bottom:1px solid var(--line); }
        .home-proof>div { padding:.35rem 1.2rem; border-right:1px solid var(--line); }
        .home-proof>div:last-child { border-right:0; }
        .home-proof strong { display:block; color:#133c95; font-size:clamp(1.55rem,2.4vw,2.35rem); line-height:1.05; letter-spacing:-.04em; }
        .home-proof span { display:block; margin-top:.45rem; color:var(--muted); font-size:.82rem; }
        .home-section { max-width:790px; margin:0 0 1.65rem; padding-top:1.4rem; }
        .home-section h2 { margin:0 0 .65rem; color:#102c6d; font-size:clamp(2rem,3.8vw,3.75rem)!important; line-height:1.05!important; letter-spacing:-.055em; }
        .home-section p { max-width:43rem; margin:0; font-size:1.05rem; color:var(--muted); }
        .home-bento { display:grid; grid-template-columns:1.22fr .78fr; grid-template-rows:auto auto; gap:1rem; margin:0 0 6rem; }
        .home-feature { position:relative; overflow:hidden; min-height:245px; padding:2rem; border-radius:20px; border:1px solid var(--line); background:#fff; transition:transform .38s cubic-bezier(.16,1,.3,1), box-shadow .38s ease, border-color .38s ease; }
        .home-feature:hover { transform:translateY(-6px); border-color:rgba(23,80,223,.24); box-shadow:0 22px 42px rgba(31,57,100,.11); }
        .home-feature-large { grid-row:span 2; min-height:510px; background:linear-gradient(150deg,#edf3ff,#dfeaff); }
        .home-feature-blue { background:#164bbf; border-color:#164bbf; }
        .home-feature-dark { background:#162237; border-color:#162237; }
        .home-feature h3 { max-width:13ch; margin:3.5rem 0 .8rem!important; font-size:clamp(1.5rem,2.4vw,2.5rem)!important; line-height:1.08!important; color:#123579; }
        .home-feature p { max-width:31rem; margin:0; color:#637089; }
        .home-feature-blue h3,.home-feature-dark h3 { color:#fff; }
        .home-feature-blue p,.home-feature-dark p { color:#dce7ff; }
        .feature-number { color:var(--accent); font-size:.8rem; font-weight:800; }
        .feature-line { position:absolute; left:2rem; right:2rem; bottom:2.2rem; height:2px; background:linear-gradient(90deg,var(--brand),var(--accent),transparent); transform-origin:left; animation:line-grow 1.2s .35s cubic-bezier(.16,1,.3,1) both; }
        .feature-line::after { content:""; position:absolute; left:58%; top:-5px; width:12px; height:12px; border-radius:50%; background:var(--accent); box-shadow:0 0 0 7px rgba(255,129,51,.16); }
        .st-key-home_flow { margin-bottom:5.5rem; padding:2.2rem; border-radius:22px; background:#102f76; }
        .st-key-home_flow .home-section { padding-top:0; }
        .st-key-home_flow .home-section h2 { color:#fff; }
        .st-key-home_flow .home-section p { color:#c9d7f6; }
        .home-flow { display:grid; grid-template-columns:repeat(3,1fr); gap:.8rem; }
        .home-flow-item { min-height:160px; padding:1.35rem; border-top:1px solid rgba(255,255,255,.28); }
        .home-flow-item b { display:block; color:#fff; font-size:1.55rem; margin-bottom:2.2rem; }
        .home-flow-item span { color:#c9d7f6; font-size:.92rem; }
        [class*='st-key-entry_'] { min-height:180px; margin-bottom:4.5rem; padding:1.15rem; border:1px solid var(--line); border-radius:16px; background:#fff; transition:transform .3s cubic-bezier(.16,1,.3,1),box-shadow .3s ease,border-color .3s ease; }
        [class*='st-key-entry_']:hover { transform:translateY(-5px); border-color:rgba(23,80,223,.3); box-shadow:0 16px 34px rgba(31,57,100,.1); }
        [class*='st-key-entry_'] [data-testid='stPageLink-NavLink'] { padding:.65rem 0; border:0!important; box-shadow:none; background:transparent!important; font-size:1.08rem; }
        [class*='st-key-entry_'] [data-testid='stPageLink-NavLink']:hover { transform:none; box-shadow:none; }
        .entry-icon { width:42px; height:42px; display:grid; place-items:center; border-radius:12px; background:var(--surface-blue); color:var(--brand); font-weight:900; }
        .home-final { margin-top:1.5rem; padding:clamp(1.6rem,4vw,3.8rem); border-radius:24px 24px 0 0; background:linear-gradient(140deg,#102f76,#1854c9); }
        .home-final h2 { max-width:18ch; margin:0 0 .8rem; color:#fff; font-size:clamp(2rem,4vw,4rem)!important; line-height:1.04!important; letter-spacing:-.055em; }
        .home-final p { margin:0; color:#d7e3ff; }
        .st-key-final_upload button { border-radius:0 0 16px 16px; min-height:3.4rem; }
        .service-hero { position:relative; overflow:hidden; display:grid; grid-template-columns:1.25fr .75fr; align-items:center; gap:2rem; min-height:310px; margin:1rem 0 2rem; padding:2.4rem; border-radius:20px; background:linear-gradient(145deg,#102f76,#1750df); color:#fff; box-shadow:0 22px 54px rgba(16,47,118,.2); }
        .service-hero::after { content:""; position:absolute; inset:auto -80px -160px auto; width:360px; height:360px; border-radius:50%; border:1px solid rgba(255,255,255,.18); box-shadow:0 0 0 48px rgba(255,255,255,.04),0 0 0 96px rgba(255,255,255,.025); animation:network-breathe 5s ease-in-out infinite; }
        .service-hero h2 { max-width:12ch; margin:0 0 .8rem; color:#fff; font-size:clamp(2.25rem,4vw,4.3rem)!important; line-height:1.02!important; }
        .service-hero p { max-width:38rem; margin:0; color:#dce7ff; font-size:1.05rem; }
        .service-orbit { position:relative; z-index:1; min-height:150px; display:grid; place-items:center; text-align:center; border:1px solid rgba(255,255,255,.22); border-radius:16px; background:rgba(255,255,255,.08); backdrop-filter:blur(14px); }
        .service-orbit span { position:absolute; width:14px; height:14px; border-radius:50%; background:var(--accent); box-shadow:0 0 0 9px rgba(255,129,51,.16); animation:orbit-order 4.5s linear infinite; }
        .service-orbit b { max-width:12ch; color:#fff; font-size:1.08rem; }
        .service-assurance { display:grid; grid-template-columns:repeat(3,1fr); margin:3rem 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
        .service-assurance div { padding:1.3rem; border-right:1px solid var(--line); }
        .service-assurance div:last-child { border-right:0; }
        .service-assurance b,.service-assurance span { display:block; }
        .service-assurance b { color:var(--brand-dark); }
        .service-assurance span { margin-top:.35rem; color:var(--muted); font-size:.84rem; }
        .fee-preview { display:grid; grid-template-columns:1fr auto; gap:.25rem 1rem; margin:1rem 0; padding:1.25rem 1.35rem; border:1px solid #f0d2be; border-radius:14px; background:#fff8f3; }
        .fee-preview span { color:#7a5a45; font-size:.86rem; }
        .fee-preview strong { grid-row:span 2; align-self:center; color:#b45309; font-size:1.75rem; font-variant-numeric:tabular-nums; }
        .fee-preview small { max-width:62ch; color:#7a6a60; line-height:1.55; }
        .map-order-head { display:grid; grid-template-columns:repeat(3,1fr); margin:1rem 0 1.25rem; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
        .map-order-head>div { padding:1rem 1.2rem; border-right:1px solid var(--line); }
        .map-order-head>div:last-child { border-right:0; }
        .map-order-head span,.map-order-head b { display:block; }
        .map-order-head span { color:var(--muted); font-size:.78rem; }
        .map-order-head b { margin-top:.35rem; color:var(--brand-dark); font-size:1rem; }
        .tracking-head { display:flex; align-items:flex-end; justify-content:space-between; gap:2rem; margin:1rem 0 2rem; padding:2rem; border-radius:18px; background:#102f76; }
        .tracking-head span,.tracking-head small { color:#b9caef; font-size:.78rem; }
        .tracking-head h2 { margin:.3rem 0; color:#fff; font-size:clamp(2rem,3vw,3.2rem)!important; }
        .tracking-head p { margin:0; color:#d8e4ff; }
        .tracking-state { min-width:180px; display:grid; gap:.35rem; justify-items:end; }
        .tracking-state i { width:12px; height:12px; border-radius:50%; background:var(--accent); box-shadow:0 0 0 0 rgba(255,129,51,.45); animation:status-pulse 2s ease-out infinite; }
        .tracking-state b { color:#fff; font-size:1.08rem; }
        .delivery-track { --track:0%; position:relative; display:grid; grid-template-columns:repeat(6,1fr); margin:1rem 0 3.5rem; padding-top:1rem; }
        .delivery-track::before,.delivery-track-fill { content:""; position:absolute; top:1.82rem; left:10%; right:10%; height:2px; background:#d7e0ed; }
        .delivery-track-fill { right:auto; width:calc(var(--track) * .8); background:linear-gradient(90deg,var(--brand),var(--accent)); transform-origin:left; animation:track-flow .9s cubic-bezier(.16,1,.3,1) both; }
        .delivery-node { position:relative; z-index:1; display:grid; justify-items:center; gap:.6rem; text-align:center; color:var(--muted); }
        .delivery-node span { width:28px; height:28px; display:grid; place-items:center; border-radius:50%; background:#e5ebf3; color:#6f7d90; font-size:.72rem; font-weight:800; transition:transform .3s ease,background .3s ease,color .3s ease; }
        .delivery-node.done span { background:var(--brand); color:#fff; transform:scale(1.08); }
        .delivery-node.done:last-child span { background:var(--accent); }
        .delivery-node b { font-size:.8rem; }
        .detail-sheet { background:#fff; border-top:1px solid var(--line); }
        .detail-sheet div { display:grid; grid-template-columns:120px 1fr; gap:1rem; padding:1rem .2rem; border-bottom:1px solid var(--line); }
        .detail-sheet span { color:var(--muted); font-size:.82rem; }
        .detail-sheet b { color:var(--ink); font-size:.92rem; }
        .demo-banner { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-top:2.5rem; padding:1.1rem 1.3rem; border:1px solid #f2cfb7; border-radius:14px; background:#fff8f3; }
        .demo-banner b { color:#b45309; }
        .demo-banner span { color:#7a5a45; font-size:.86rem; }
        .empty-stage { min-height:300px; display:grid; place-content:center; text-align:center; padding:2rem; border:1px dashed #bdc9db; border-radius:16px; background:linear-gradient(145deg,#fff,#f0f5ff); }
        .empty-stage h2,.empty-stage h3 { color:var(--brand-dark); }
        .ops-ribbon { position:relative; overflow:hidden; display:flex; align-items:center; gap:1rem; margin:1rem 0 1.5rem; padding:1.3rem 1.5rem; border-radius:16px; color:#fff; background:#102f76; }
        .ops-ribbon span { color:#aebfe5; font-size:.82rem; }
        .ops-ribbon b { font-size:1.1rem; }
        .pulse-route { position:absolute; right:0; width:35%; height:100%; background:linear-gradient(90deg,transparent,rgba(255,255,255,.08)); }
        .pulse-route::before { content:""; position:absolute; left:0; right:0; top:50%; height:1px; background:rgba(255,255,255,.25); }
        .pulse-route i { position:absolute; top:calc(50% - 5px); width:10px; height:10px; border-radius:50%; background:var(--accent); box-shadow:0 0 18px rgba(255,129,51,.75); animation:route-run 3s ease-in-out infinite; }
        .ops-order { min-height:220px; padding:1.5rem; border-radius:16px; background:linear-gradient(145deg,#edf3ff,#fff); }
        .ops-order span { color:var(--accent); font-size:.78rem; font-weight:800; }
        .ops-order h3 { margin:.8rem 0 .4rem!important; color:var(--brand-dark); font-size:1.55rem!important; }
        .ops-order b { display:block; margin-top:2.3rem; color:var(--brand); }
        .integration-rail { display:grid; grid-template-columns:repeat(4,1fr); margin-bottom:2rem; border-top:1px solid var(--line); }
        .integration-rail>div { min-height:170px; padding:1.25rem; border-right:1px solid var(--line); }
        .integration-rail>div:last-child { border-right:0; }
        .integration-rail span,.integration-rail b,.integration-rail small { display:block; }
        .integration-rail span { color:var(--muted); font-size:.78rem; }
        .integration-rail b { margin:1.8rem 0 .4rem; color:#b45309; }
        .integration-rail .ready b { color:var(--success); }
        .integration-rail small { color:var(--muted); line-height:1.5; }
        .receipt-head { margin:1rem 0 2rem; padding:2rem; border-radius:18px; background:linear-gradient(145deg,#fff,#edf3ff); }
        .receipt-head span { color:var(--brand); font-size:.82rem; font-weight:800; }
        .receipt-head h2 { margin:.55rem 0!important; color:var(--brand-dark); font-size:2.4rem!important; }
        .motion-focus { animation:focus-arrive .78s cubic-bezier(.16,1,.3,1) both; }
        .motion-reveal { animation:reveal-up .55s cubic-bezier(.16,1,.3,1) both; }
        @keyframes reveal-up { from { opacity:.01; transform:translateY(16px); filter:blur(2px); } to { opacity:1; transform:none; filter:none; } }
        @keyframes reveal-on-scroll { from { opacity:.01; transform:translateY(20px); filter:blur(2px); } to { opacity:1; transform:none; filter:none; } }
        @keyframes home-copy { from { opacity:0; transform:translateY(28px); filter:blur(8px); } to { opacity:1; transform:none; filter:none; } }
        @keyframes home-visual { from { opacity:0; transform:translateX(34px) scale(.96); clip-path:inset(0 0 0 100% round 20px); } to { opacity:1; transform:none; clip-path:inset(0 0 0 0 round 20px); } }
        @keyframes home-ambient { to { transform:translate(-38px,42px) scale(1.08); } }
        @keyframes line-grow { from { transform:scaleX(0); opacity:0; } to { transform:scaleX(1); opacity:1; } }
        @keyframes focus-arrive { from { opacity:.1; transform:translateY(22px) scale(.985); filter:blur(7px); clip-path:inset(0 0 16% 0 round 16px); } to { opacity:1; transform:none; filter:none; clip-path:inset(0 0 0 0 round 16px); } }
        @keyframes network-breathe { 50% { transform:scale(1.08); opacity:.76; } }
        @keyframes orbit-order { from { transform:rotate(0deg) translateX(62px) rotate(0deg); } to { transform:rotate(360deg) translateX(62px) rotate(-360deg); } }
        @keyframes status-pulse { 70% { box-shadow:0 0 0 12px rgba(255,129,51,0); } 100% { box-shadow:0 0 0 0 rgba(255,129,51,0); } }
        @keyframes track-flow { from { transform:scaleX(0); filter:blur(3px); } to { transform:scaleX(1); filter:none; } }
        @keyframes route-run { 0% { left:4%; opacity:0; } 20% { opacity:1; } 80% { opacity:1; } 100% { left:92%; opacity:0; } }
        .metric-card, .route-board, .note-panel, [data-testid='stMetric'], [data-testid='stPlotlyChart'], [data-testid='stDataFrame'] { animation:reveal-up .62s cubic-bezier(.16,1,.3,1) both; }
        @supports (animation-timeline: view()) { .metric-card, .route-board, .note-panel, .home-reveal, [data-testid='stMetric'], [data-testid='stPlotlyChart'], [data-testid='stDataFrame'] { animation-name:reveal-on-scroll; animation-duration:1ms; animation-fill-mode:both; animation-timeline:view(); animation-range:entry 5% cover 28%; animation-delay:0ms; } }
        @media (max-width: 800px) { h1 { font-size:2rem!important; } .hero-panel { grid-template-columns:1fr; padding:1.3rem; } .hero-index { border-left:0; border-top:1px solid rgba(255,255,255,.25); padding:1rem 0 0; } .block-container { padding-left:1rem; padding-right:1rem; } .home-nav-copy { display:none; } .st-key-home_hero { padding:1.2rem; border-radius:20px; } .home-hero-copy h1 { max-width:12ch; font-size:2.75rem!important; } .home-proof { grid-template-columns:repeat(2,1fr); margin-bottom:4rem; padding:.8rem 0; } .home-proof>div { padding:.8rem; } .home-proof>div:nth-child(2) { border-right:0; } .home-proof>div:nth-child(-n+2) { border-bottom:1px solid var(--line); } .home-bento { grid-template-columns:1fr; margin-bottom:4rem; } .home-feature-large { grid-row:auto; min-height:330px; } .home-flow { grid-template-columns:1fr; } .home-flow-item { min-height:auto; } .home-flow-item b { margin-bottom:.5rem; } .st-key-home_flow { padding:1.25rem; } [class*='st-key-entry_'] { min-height:0; margin-bottom:.5rem; } .home-final { border-radius:18px 18px 0 0; } .service-hero { grid-template-columns:1fr; padding:1.4rem; } .service-orbit { min-height:120px; } .service-assurance { grid-template-columns:1fr; } .service-assurance div { border-right:0; border-bottom:1px solid var(--line); } .fee-preview { grid-template-columns:1fr; } .fee-preview strong { grid-row:auto; } .map-order-head { grid-template-columns:1fr; } .map-order-head>div { border-right:0; border-bottom:1px solid var(--line); } .map-order-head>div:last-child { border-bottom:0; } .tracking-head { align-items:flex-start; flex-direction:column; } .tracking-state { justify-items:start; } .delivery-track { overflow-x:auto; grid-template-columns:repeat(6,110px); padding-bottom:.8rem; } .delivery-track::before,.delivery-track-fill { left:55px; right:55px; } .delivery-track-fill { right:auto; width:calc(var(--track) * 5.5); } .detail-sheet div { grid-template-columns:1fr; gap:.25rem; } .demo-banner { align-items:flex-start; flex-direction:column; } .integration-rail { grid-template-columns:repeat(2,1fr); } .integration-rail>div:nth-child(2) { border-right:0; } .pulse-route { display:none; } }
        @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation:none!important; transition:none!important; scroll-behavior:auto!important; transform:none!important; filter:none!important; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("<div class='brand-mark'>YL</div>", unsafe_allow_html=True)
        st.markdown("<div class='brand-name'>银犁智慧配送</div>", unsafe_allow_html=True)
        st.caption("下单、追踪、地图与签收")
        st.divider()
        st.markdown("<div class='nav-section-label'>客户服务</div>", unsafe_allow_html=True)
        st.page_link("app.py", label="⌂  网站首页")
        st.page_link("pages/客户下单.py", label="▤  客户下单")
        st.page_link("pages/订单追踪.py", label="◎  订单追踪")
        st.page_link("pages/配送网络地图.py", label="◇  我的配送地图")
        st.page_link("pages/电子签收.py", label="✦  确认签收")
        st.divider()
        st.markdown("<div class='nav-section-label'>工作人员</div>", unsafe_allow_html=True)
        if not st.session_state.get("staff_authenticated", False):
            password = st.text_input("工作人员密码", type="password", key="staff_password")
            if password:
                configured_password = staff_password()
                if not configured_password:
                    st.error("未配置工作人员密码。请通过 YL_STAFF_PASSWORD 环境变量配置。")
                elif password == configured_password:
                    st.session_state["staff_authenticated"] = True
                    st.rerun()
                else:
                    st.error("密码不正确")
            return
        st.caption("已获得工作人员权限")
        st.page_link("pages/企业工作台.py", label="▣  订单与参数")
        st.page_link("pages/方案驾驶舱.py", label="▥  配送总览")
        st.page_link("pages/订单与需求.py", label="▦  订单情况")
        st.page_link("pages/运营配送地图.py", label="◇  配送网络地图")
        st.page_link("pages/车辆路径优化.py", label="▱  车辆路径优化")
        st.page_link("pages/成本与绩效.py", label="◒  成本与绩效")
        st.page_link("pages/方案对比.py", label="⇄  方案对比")


def require_staff_access() -> None:
    if not st.session_state.get("staff_authenticated", False):
        st.warning("该页面仅供工作人员使用。请在左侧输入工作人员密码后继续。")
        st.stop()


def page_title(title: str, subtitle: str = "") -> None:
    st.title(title)
    if subtitle:
        st.markdown(f"<div class='page-subtitle'>{html.escape(subtitle)}</div>", unsafe_allow_html=True)


def section_label(text: str) -> None:
    st.markdown(f"<div class='section-label'>{html.escape(text)}</div>", unsafe_allow_html=True)


def source_note(manifest: dict[str, Any]) -> None:
    sources = manifest.get("sources", []) if manifest else []
    updated = manifest.get("generated_at", "") if manifest else ""
    suffix = f"；整理时间：{updated}" if updated else ""
    st.markdown(f"<div class='source-note'>数据说明：页面仅展示当前结果文件和已整理的路线数据{suffix}。</div>", unsafe_allow_html=True)


def fmt_money(value: Any) -> str:
    return "暂无" if value is None or value == "" else f"¥ {float(value):,.2f}"


def fmt_num(value: Any, digits: int = 1) -> str:
    return "暂无" if value is None or value == "" else f"{float(value):,.{digits}f}"


def plotly_config() -> dict[str, Any]:
    return {"displayModeBar": False, "responsive": True}
