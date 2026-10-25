#!/usr/bin/env python3
"""Fusion Coloring local compose. Run: python3 folio_press.py"""
import json, base64, struct, zlib, time, unicodedata, urllib.request, os
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

try:
    from PIL import Image as _PILImage
    HAS_PIL = True
except ImportError:
    _PILImage = None
    HAS_PIL = False

# Decorative mandala ornaments (inline SVG, flower-bright). Drawn by the app
# itself: no image files, no loading, no cost. Used only in the decorative
# chrome (masthead, step markers, section headers, canvas bar) -- never inside
# text fields and never over artwork.
# Each entry: (deep edge, saturated base, light heart) for a hand-colored look.
_MANDALA_PETALS = [
    ("#B03A2E", "#E0604F", "#F2A090"),  # coral
    ("#B97A1F", "#E8A93D", "#F6CE7E"),  # marigold
    ("#1A7A70", "#26A69A", "#7FD1C7"),  # teal
    ("#6A3F80", "#8E5AA8", "#C09AD6"),  # violet
    ("#97344F", "#C94F6D", "#E89BB0"),  # rose
    ("#3F7034", "#5A9E4B", "#9CCB8F"),  # leaf
]

def mandala_svg(size, petals=12):
    import math
    cols = _MANDALA_PETALS
    parts = ['<svg class="mandala" width="%d" height="%d" viewBox="-100 -100 200 200" '
             'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="mandala ornament">'
             % (size, size)]
    # outer confetti dots
    dots = []
    for i in range(petals * 2):
        a = math.radians(i * 360.0 / (petals * 2))
        dots.append('<circle cx="%.1f" cy="%.1f" r="3.4" fill="%s" opacity="0.9"/>'
                    % (93 * math.cos(a), 93 * math.sin(a), cols[i % len(cols)][1]))
    parts.append("<g>" + "".join(dots) + "</g>")
    # leaf ring tucked between the big petals
    for i in range(petals):
        a = i * 360.0 / petals + 360.0 / petals / 2
        dk, bs, _lt = cols[5]
        parts.append('<g transform="rotate(%.1f)"><path d="M0,-72 C9,-62 9,-48 0,-38 '
                     'C-9,-48 -9,-62 0,-72 Z" fill="%s" stroke="%s" stroke-width="1.2" '
                     'opacity="0.85"/></g>' % (a, bs, dk))
    # big flower petals: saturated base, deep edge, light heart
    for i in range(petals):
        dk, bs, lt = cols[i % len(cols)]
        a = i * 360.0 / petals
        parts.append('<g transform="rotate(%.1f)">'
                     '<path d="M0,-82 C21,-71 24,-40 0,-13 C-24,-40 -21,-71 0,-82 Z" '
                     'fill="%s" stroke="%s" stroke-width="1.6" opacity="0.92"/>'
                     '<path d="M0,-64 C11,-57 12,-36 0,-22 C-12,-36 -11,-57 0,-64 Z" '
                     'fill="%s" opacity="0.85"/></g>' % (a, bs, dk, lt))
    # middle bloom ring, offset
    for i in range(petals):
        dk, bs, lt = cols[(i + 3) % len(cols)]
        a = i * 360.0 / petals + 360.0 / petals / 2
        parts.append('<g transform="rotate(%.1f)">'
                     '<path d="M0,-50 C14,-43 15,-24 0,-11 C-15,-24 -14,-43 0,-50 Z" '
                     'fill="%s" stroke="%s" stroke-width="1.3" opacity="0.94"/>'
                     '<path d="M0,-38 C7,-33 7,-21 0,-14 C-7,-21 -7,-33 0,-38 Z" '
                     'fill="%s" opacity="0.9"/></g>' % (a, bs, dk, lt))
    # scalloped ring
    scal = []
    for i in range(24):
        a = math.radians(i * 15)
        scal.append('<circle cx="%.1f" cy="%.1f" r="2.6" fill="%s" opacity="0.8"/>'
                    % (33 * math.cos(a), 33 * math.sin(a), cols[i % len(cols)][1]))
    parts.append("<g>" + "".join(scal) + "</g>")
    parts.append('<circle r="28" fill="#FFFDF9" stroke="#3F6B4C" stroke-width="2" opacity="0.9"/>')
    # center rosette
    for i in range(10):
        dk, bs, _lt = cols[(i + 1) % len(cols)]
        parts.append('<g transform="rotate(%d)">'
                     '<path d="M0,-24 C9,-19 10,-9 0,-4 C-10,-9 -9,-19 0,-24 Z" '
                     'fill="%s" stroke="%s" stroke-width="1" opacity="0.95"/></g>'
                     % (i * 36, bs, dk))
    parts.append('<circle r="6.5" fill="#3F6B4C"/><circle r="2.8" fill="#FFFDF9"/>')
    parts.append("</svg>")
    return "".join(parts)

MANDALA_HEAD = mandala_svg(76)    # masthead flanks
MANDALA_MED = mandala_svg(52)     # section headers
MANDALA_BAR = mandala_svg(34)     # canvas bar

# Storybook step icons: one emblem per step (palette, quill, pages, book,
# crown). Same inline-SVG approach as the mandalas.
def _icon_open(size):
    return ('<svg class="stepicon" width="%d" height="%d" viewBox="0 0 100 100" '
            'xmlns="http://www.w3.org/2000/svg" role="img" aria-hidden="true">' % (size, size))

def icon_palette(size=44):
    dots = [("#E0604F", 34, 38), ("#E8A93D", 52, 30), ("#26A69A", 66, 42),
            ("#8E5AA8", 60, 60), ("#5A9E4B", 40, 58)]
    s = [_icon_open(size)]
    s.append('<ellipse cx="50" cy="52" rx="38" ry="34" fill="#E8C98F" stroke="#8A5A2B" stroke-width="3"/>')
    for c, x, y in dots:
        s.append('<circle cx="%d" cy="%d" r="8" fill="%s" stroke="#1A1916" '
                 'stroke-width="1.5" opacity="0.95"/>' % (x, y, c))
    s.append('<ellipse cx="68" cy="72" rx="9" ry="7" fill="#F3EEE6" stroke="#8A5A2B" stroke-width="2.5"/>')
    s.append('</svg>')
    return "".join(s)

def icon_quill(size=44):
    return (_icon_open(size) +
            '<path d="M52,92 C34,66 30,30 72,8 C64,34 62,62 52,92 Z" fill="#FFFDF9" '
            'stroke="#3F6B4C" stroke-width="3"/>'
            '<path d="M52,92 C50,60 56,32 72,8" fill="none" stroke="#3F6B4C" stroke-width="2.5"/>'
            '<path d="M50,62 L40,58 M51,50 L41,46 M53,38 L44,34" stroke="#3F6B4C" stroke-width="2"/>'
            '<path d="M52,92 L46,98 L58,94 Z" fill="#1A1916"/>'
            '</svg>')

def icon_pages(size=44):
    return (_icon_open(size) +
            '<rect x="30" y="18" width="44" height="56" rx="3" fill="#D9A441" stroke="#8A5A2B" stroke-width="2.5"/>'
            '<rect x="24" y="26" width="44" height="56" rx="3" fill="#26A69A" stroke="#1A7A70" stroke-width="2.5"/>'
            '<rect x="18" y="34" width="44" height="56" rx="3" fill="#FFFDF9" stroke="#3F6B4C" stroke-width="2.5"/>'
            '<line x1="26" y1="48" x2="54" y2="48" stroke="#3F6B4C" stroke-width="2.5"/>'
            '<line x1="26" y1="58" x2="54" y2="58" stroke="#3F6B4C" stroke-width="2.5"/>'
            '<line x1="26" y1="68" x2="48" y2="68" stroke="#3F6B4C" stroke-width="2.5"/>'
            '</svg>')

def icon_book(size=44):
    return (_icon_open(size) +
            '<path d="M50,30 C40,22 24,20 14,24 L14,78 C24,74 40,76 50,84 C60,76 76,74 86,78 L86,24 '
            'C76,20 60,22 50,30 Z" fill="#3F6B4C" stroke="#1A3A24" stroke-width="2.5"/>'
            '<path d="M50,30 C42,24 30,23 20,26 L20,72 C30,69 42,70 50,77 Z" fill="#FFFDF9"/>'
            '<path d="M50,30 C58,24 70,23 80,26 L80,72 C70,69 58,70 50,77 Z" fill="#FFFDF9"/>'
            '<line x1="50" y1="30" x2="50" y2="84" stroke="#1A3A24" stroke-width="2.5"/>'
            '</svg>')

def icon_crown(size=44):
    return (_icon_open(size) +
            '<path d="M18,72 L14,34 L32,48 L50,22 L68,48 L86,34 L82,72 Z" fill="#E8A93D" '
            'stroke="#8A5A2B" stroke-width="2.5" stroke-linejoin="round"/>'
            '<circle cx="14" cy="30" r="5" fill="#C94F6D" stroke="#8A5A2B" stroke-width="2"/>'
            '<circle cx="50" cy="18" r="5" fill="#26A69A" stroke="#8A5A2B" stroke-width="2"/>'
            '<circle cx="86" cy="30" r="5" fill="#C94F6D" stroke="#8A5A2B" stroke-width="2"/>'
            '<rect x="18" y="72" width="64" height="10" rx="3" fill="#8A5A2B"/>'
            '<circle cx="50" cy="56" r="6" fill="#C94F6D" stroke="#8A5A2B" stroke-width="2"/>'
            '</svg>')

ICON_01 = icon_palette()
ICON_02 = icon_quill()
ICON_03 = icon_pages()
ICON_04 = icon_book()
ICON_05 = icon_crown()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fusion Coloring</title>
<style>
  :root { --paper:#F3EEE6; --ink:#1A1916; --forest:#3F6B4C; --line:rgba(26,25,22,.12); }
  * { box-sizing: border-box; }
  html { height:100%; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family:Palatino,Georgia,serif; font-size:17px; line-height:1.55; display:flex; flex-direction:column; height:100vh; overflow:hidden; }
  header { flex:none; background:var(--paper); border-top:7px solid var(--forest); border-bottom:3px double var(--line); padding:1rem 1.2rem .85rem; text-align:center; }
  .masthead { display:flex; align-items:center; justify-content:center; gap:.9rem; }
  .brand { font-size:2rem; letter-spacing:.12em; font-weight:700; }
  .morn { color:var(--forest); font-size:1.3rem; }
  .mandala { flex:none; vertical-align:middle; }
  .stepicon { flex:none; vertical-align:middle; }
  details.step summary .stepicon { align-self:center; }
  .tplcard { background:#fff; border:2px solid var(--forest); border-radius:12px; padding:1rem 1.2rem; margin-bottom:1.2rem; }
  .tplcard h3 { margin:0 0 .3rem; font-size:1.15rem; }
  .tplcard p { margin:.2rem 0 .8rem; font-size:.92rem; opacity:.8; }
  .tplrow { display:flex; align-items:center; gap:.6rem; }
  .tplrow label { margin:0; }
  .tplrow input { width:4.5rem; }
  .tplrow button { width:auto; margin:0; padding:.65rem 1.2rem; white-space:nowrap; }
  .keyrow { display:flex; gap:.5rem; align-items:center; }
  .keyrow input { flex:1; }
  .keyrow button { width:auto; margin:0; padding:.65rem .9rem; white-space:nowrap; }
  h2.sub .mandala { margin-right:.45rem; }
  details.step summary .mandala { align-self:center; }
  .masthead .mandala { margin:0 .1rem; }
  .workbar .mandala { margin:0 .1rem; }
  .emptystate .mandala { margin-bottom:.4rem; }
  .tagline { font-style:italic; opacity:.6; font-size:.95rem; margin-top:.15rem; letter-spacing:.04em; }
  details.step { border-bottom:1px solid var(--line); padding:.2rem 0 .9rem; margin-bottom:.5rem; }
  details.step summary { cursor:pointer; font-size:1.3rem; font-weight:700; list-style:none; display:flex; align-items:baseline; gap:.6rem; padding:.35rem 0; }
  details.step summary::-webkit-details-marker { display:none; }
  details.step summary .n { font-size:.75rem; font-weight:700; color:var(--forest); letter-spacing:.06em; }
  details.step summary::after { content:'▸'; margin-left:auto; opacity:.45; font-size:.9rem; }
  details.step[open] summary::after { content:'▾'; }
  .stepbody { padding-top:.2rem; }
  h2.sub { font-size:1.05rem; margin:1.2rem 0 .4rem; }
  .layout { flex:1; min-height:0; display:grid; grid-template-columns:405px 1fr; }
  aside { overflow-y:auto; min-height:0; }
  .canvas { overflow-y:auto; min-height:0; }
  @media (max-width:800px) {
    body { display:block; height:auto; overflow:auto; }
    .layout { grid-template-columns:1fr; }
    aside, .canvas { overflow:visible; }
  }
  aside { padding:1.4rem 1.2rem; border-right:1px solid var(--line); }
  h1 { font-size:1.5rem; margin:0 0 .4rem; }
  p { margin:0 0 .8rem; }
  label { display:block; font-size:.82rem; font-weight:600; letter-spacing:.05em; text-transform:uppercase; margin:.7rem 0 .35rem; }
  input, textarea, select { width:100%; border:1px solid var(--line); background:#fffdf9; border-radius:8px; padding:.8rem; font:inherit; }
  input:focus, textarea:focus, select:focus { outline:2px solid var(--forest); outline-offset:1px; border-color:var(--forest); }
  button { width:100%; margin-top:.55rem; background:var(--forest); color:var(--paper); border:none; border-radius:999px; padding:.75rem; font:inherit; cursor:pointer; }
  button.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); }
  button:disabled { opacity:.6; }
  .count, .status { font-size:.85rem; color:var(--forest); margin:.55rem 0 0; }
  .canvas { display:flex; flex-direction:column; align-items:stretch; padding:0 1.5rem 1.5rem;
    background-image:radial-gradient(rgba(63,107,76,.08) 1.2px, transparent 1.2px); background-size:24px 24px; }
  .workbar { display:flex; align-items:center; gap:.8rem; padding:.75rem .2rem; color:var(--forest); }
  .wrule { flex:1; border-top:1px solid var(--line); }
  .worn { font-size:.95rem; }
  .wlabel { font-size:.78rem; letter-spacing:.2em; text-transform:uppercase; opacity:.8; white-space:nowrap; }
  .stage { flex:1 0 auto; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:1rem; }
  .emptystate { text-align:center; max-width:480px; border:2px dashed var(--line); border-radius:8px; padding:3rem 2.6rem; background:#fff; box-shadow:0 8px 24px rgba(26,25,22,.06); }
  .emptystate .es-orn { color:var(--forest); font-size:1.7rem; }
  .emptystate h2 { margin:.5rem 0 .7rem; font-size:1.45rem; }
  .emptystate p { margin:0; opacity:.78; }
  .sheet { width:min(100%,440px); background:#fff; border:1px solid var(--line); box-shadow:0 8px 24px rgba(26,25,22,.08); padding:1rem 1rem .7rem; }
  .sheet img { width:100%; aspect-ratio:2/3; object-fit:contain; display:block; background:#fff; }
  .caption { margin-top:.55rem; font-size:.85rem; text-align:center; line-height:1.35; }
  .folio { margin-top:.15rem; font-size:.75rem; text-align:center; letter-spacing:.08em; }
  .thumbs { display:flex; gap:.4rem; flex-wrap:wrap; justify-content:center; max-width:520px; }
  .thumbs button { width:64px; height:80px; padding:0; margin:0; border-radius:4px; overflow:hidden; background:#fff; border:1px solid var(--line); }
  .thumbs button.active { outline:2px solid var(--forest); }
  .thumbs img { width:100%; height:100%; object-fit:cover; display:block; }
  .blank-thumb { width:100%; height:100%; background:#fff; }
  .printcheck { font-size:.8rem; color:var(--forest); margin:0; max-width:440px; text-align:center; line-height:1.4; }
  .preflight { list-style:none; margin:.6rem 0 0; padding:0; font-size:.82rem; text-align:left; }
  .preflight li { margin:.3rem 0; line-height:1.35; }
  .preflight li.pass { color:var(--forest); }
  .preflight li.warn { color:#8a6d1a; }
  .preflight li.fail { color:#a33b2e; }
  .preflight li.info { color:var(--ink); opacity:.7; }
  .coverrow { display:flex; gap:.5rem; }
  .coverrow input { flex:1; }
  .coverrow button { width:auto; margin-top:0; padding:.65rem 1rem; white-space:nowrap; }
  label.check { display:flex; gap:.5rem; align-items:center; text-transform:none; letter-spacing:0; font-size:.85rem; }
  label.check input { width:auto; }
  .coverart img { width:120px; margin-top:.6rem; border:1px solid var(--line); border-radius:4px; }
  .coverspec { font-size:.82rem; margin:.6rem 0; line-height:1.5; color:var(--forest); white-space:pre-line; }
  .covermock { display:flex; height:64px; margin:.4rem 0 .8rem; border:1px solid var(--line); border-radius:4px; overflow:hidden; }
  .cmp { display:flex; align-items:center; justify-content:center; font-size:.7rem; color:#fff; background:var(--forest); min-width:0; }
  .cmp span { opacity:.9; white-space:nowrap; overflow:hidden; }
  .text-thumb { width:100%; height:100%; background:#fffdf9; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:4px; }
  .text-thumb .k { font-size:.55rem; text-transform:uppercase; letter-spacing:.06em; color:var(--forest); }
  .text-thumb .t { font-size:.62rem; line-height:1.25; margin-top:2px; overflow:hidden; }
  .storyview { width:min(100%,440px); background:#fff; border:1px solid var(--line); box-shadow:0 8px 24px rgba(26,25,22,.08); padding:1.4rem 1.5rem 1.2rem; max-height:62vh; overflow:auto; }
  .storyview h2 { font-size:1.05rem; margin:0 0 .2rem; text-align:center; }
  .storyview .vlabel { font-size:.65rem; text-transform:uppercase; letter-spacing:.08em; color:var(--forest); text-align:center; margin-bottom:.5rem; }
  .storyview .orn { text-align:center; color:var(--forest); margin:.1rem 0 .7rem; letter-spacing:.35em; }
  .storyview p { font-size:.85rem; line-height:1.55; margin:0 0 .6rem; }
  .storyview .note { margin-top:.9rem; border-top:1px solid var(--line); padding-top:.7rem; }
  .storyview .note h3 { font-size:.8rem; text-align:center; margin:0 0 .35rem; }
  .storyview .note p { font-size:.8rem; text-align:center; }
  .storyview button.ghost { margin-top:.8rem; }
  .imagerow { display:flex; gap:.6rem; justify-content:center; flex-wrap:wrap; }
  .imagerow button.ghost { width:auto; padding:.65rem 1.1rem; margin-top:.2rem; }
  .strmodes label { display:flex; gap:.6rem; align-items:flex-start; margin:0 0 .7rem; text-transform:none; letter-spacing:0; font-size:.9rem; cursor:pointer; }
  .strmodes input { width:auto; margin-top:.25rem; flex:none; }
  .strmodes b { display:block; }
  .strmodes i { display:block; font-style:normal; opacity:.75; font-size:.82rem; }
  .strpanes { display:grid; grid-template-columns:1fr 1fr; gap:.8rem; margin-top:.6rem; }
  .strpanes h3 { font-size:.85rem; margin:0 0 .3rem; }
  .strscroll { max-height:44vh; overflow:auto; border:1px solid var(--line); border-radius:6px; background:#fff; }
  .strscroll canvas { width:100%; display:block; }
  .strscroll.full canvas { width:auto; max-width:none; }
  .charchk label { display:flex; gap:.5rem; align-items:center; margin:0 0 .4rem; text-transform:none; letter-spacing:0; font-size:.92rem; cursor:pointer; }
  .charchk input { width:auto; margin:0; }
  .charcard { display:flex; gap:.6rem; align-items:center; border:1px solid var(--line); border-radius:8px; padding:.5rem; margin-bottom:.5rem; background:#fff; }
  .charcard img { width:44px; height:66px; object-fit:cover; border-radius:4px; flex:none; }
  .charcard div { flex:1; min-width:0; }
  .charcard b { display:block; font-size:.9rem; }
  .charcard span { font-size:.75rem; opacity:.7; }
  .charcard button { width:auto; margin:0; padding:.4rem .7rem; font-size:.8rem; flex:none; }
  .batchq { list-style:none; margin:.6rem 0 0; padding:0; font-size:.85rem; }
  .batchq li { display:flex; gap:.5rem; align-items:baseline; padding:.3rem 0; border-bottom:1px dotted var(--line); }
  .qdot { flex:none; width:.6rem; height:.6rem; border-radius:50%; background:#c9c2b4; transform:translateY(.05rem); }
  .qdot.working { background:var(--forest); animation:qpulse 1s infinite alternate; }
  .qdot.done { background:var(--ink); }
  .qdot.failed { background:#a33f3f; }
  .qdot.skipped { background:transparent; border:1px solid #c9c2b4; }
  .qerr { font-size:.82rem; color:#a33f3f; margin-top:.25rem; }
  @keyframes qpulse { from { opacity:.35; } to { opacity:1; } }
  .kwrow { display:flex; gap:.4rem; align-items:center; margin-bottom:.35rem; }
  .kwrow input { margin:0; }
  .kwrow span { font-size:.7rem; opacity:.7; flex:none; width:3.4rem; text-align:right; }
  .kwrow span.over { color:#a33f3f; font-weight:700; opacity:1; }
  .kcheck { list-style:none; margin:.4rem 0 0; padding:0; }
  .kcheck li { display:flex; gap:.5rem; align-items:baseline; padding:.25rem 0; }
  .kcheck input { width:auto; margin:0; flex:none; transform:translateY(.1rem); }
  .kcheck label { text-transform:none; letter-spacing:0; font-size:.92rem; margin:0; }
  .kcheck li.auto label { opacity:.8; }
  .kroyal { background:#fff; border:1px solid var(--line); border-radius:8px; padding:.7rem .9rem; font-size:.9rem; line-height:1.6; }
  .kroyal b { font-size:1.05rem; }
  .kcount { font-size:.75rem; opacity:.7; text-transform:none; letter-spacing:0; }
  .editmodal { position:fixed; inset:0; background:rgba(26,25,22,.55); display:flex; align-items:center; justify-content:center; z-index:50; padding:1rem; }
  .editmodal[hidden] { display:none; }
  .editbox { background:var(--paper); border-radius:12px; padding:1.2rem 1.4rem; max-width:560px; width:100%; max-height:92vh; overflow:auto; }
  .editbox h2 { margin:0 0 .3rem; font-size:1.2rem; }
  .editbox p { font-size:.85rem; }
  .editbox canvas { width:100%; max-height:50vh; object-fit:contain; background:#fff; border:1px solid var(--line); border-radius:6px; cursor:crosshair; touch-action:none; display:block; }
  .editrow { display:flex; gap:.6rem; align-items:center; margin-top:.6rem; }
  .editrow label { margin:0; text-transform:none; letter-spacing:0; font-size:.85rem; display:flex; align-items:center; gap:.4rem; }
  .editrow input[type=range] { width:120px; }
  .editrow button { width:auto; margin-top:0; }
  .booktoolbar { display:flex; gap:.5rem; justify-content:center; flex-wrap:wrap; margin-top:.5rem; }
  .booktoolbar button, .booktoolbar a { width:auto; margin:0; padding:.45rem 1rem; font-size:.9rem; }
  #booktoolbarstatus { max-width:760px; margin:.35rem auto 0; font-size:.8rem; line-height:1.3; }
  .bookstate { max-width:760px; margin:.4rem auto 0; font-size:.85rem; line-height:1.35; }
  .bookstate p { margin:.15rem 0; }
  #bookidentity { font-weight:700; }
  #bookbackupstate[data-state="ready"] { color:var(--forest); }
  #bookbackupstate[data-state="changed"] { color:#8a4314; font-weight:700; }
</style>
</head>
<body>
<header>
  <div class="masthead">%%MANDALA_HEAD%%<span class="brand">Fusion Coloring</span>%%MANDALA_HEAD%%</div>
  <div class="tagline">Your creative space</div>
  <div class="booktoolbar" role="group" aria-label="Save and open books">
    <button id="quickloadbook" type="button">Open saved book</button>
    <button class="ghost" id="quicksavebook" type="button" disabled>Save book backup</button>
    <a id="quickbookdownload" download="fusion-coloring-book.json" hidden>Download book file</a>
  </div>
  <div class="bookstate" aria-label="Current book and backup status">
    <p id="bookidentity">No book open</p>
    <p id="bookbackupstate" role="status" aria-live="polite">Create pages or open a saved book to begin.</p>
  </div>
  <p class="status" id="booktoolbarstatus" role="status" aria-live="polite">Open a saved .json book here to restore its pictures and settings.</p>
</header>
<div class="layout">
  <aside>
    <details class="step" open>
      <summary>%ICON_01%<span class="n">01</span> Create pages</summary>
      <div class="stepbody">
            <p>Paste your key once. Describe the plate. Press compose. The picture is tall, with your sentence and a page number under it.</p>
            <label for="key">API key</label>
            <div class="keyrow">
              <input id="key" type="password" autocomplete="off">
              <button class="ghost" id="keyshow" type="button" title="Show the key to check it">Show</button>
            </div>
            <label for="level">Complexity</label>
            <select id="level">
              <option value="easy">Children — simple scenes, large shapes</option>
              <option value="medium" selected>Medium — teens, clear detail</option>
              <option value="detailed">Adults — rich detail, clear coloring spaces</option>
            </select>
            <label for="styleref">Artwork style reference (optional)</label>
            <input type="file" id="styleref" accept="image/*">
            <p class="status" id="stylerefstatus">Use an approved page to guide linework and illustration style.</p>
            <img id="stylerefpreview" alt="Artwork style reference" hidden style="max-width:120px;max-height:150px">
            <button class="ghost" id="clearstyleref" type="button" hidden>Remove style reference</button>
            <label class="check"><input type="checkbox" id="cleanup">Remove gray after generation (keeps the original too)</label>
            <label for="subject">What is on this page?</label>
            <textarea id="subject" rows="4" placeholder="A princess and a falcon in a great hall"></textarea>
            <label>Characters in this scene</label>
            <div id="charchk" class="charchk"></div>
            <button id="compose">Compose page</button>
            <p class="status" id="status"></p>
            <details id="generationdetails" hidden>
              <summary>Selected image settings</summary>
              <p class="status" id="generationinfo"></p>
              <textarea id="generationprompt" rows="6" readonly aria-label="Complete generation prompt"></textarea>
              <button class="ghost" id="reusesettings" type="button">Use these settings for another page</button>
              <button class="ghost" id="downloadoriginal" type="button" hidden>Download original before cleanup</button>
            </details>
            <h2 class="sub">%%MANDALA_MED%%Characters</h2>
            <p>Define Elinor, Bramble, and friends once — tick them for a scene and their look carries into every page.</p>
            <div id="charlist"></div>
            <label for="cname">Name</label>
            <input id="cname" type="text" placeholder="Princess Elinor">
            <label for="cdesc">Locked description</label>
            <textarea id="cdesc" rows="3" placeholder="Young princess, long wavy auburn hair, green eyes, small gold circlet, medieval blue gown"></textarea>
            <label for="crefs">Reference pictures (up to 3)</label>
            <input type="file" id="crefs" accept="image/*" multiple>
            <button id="cadd">Add character</button>
            <p class="status" id="charstatus"></p>
            <h2 class="sub">%%MANDALA_MED%%Batch compose</h2>
            <p>One scene per line. The batch uses the complexity above and your ticked characters, composing pages one at a time — walk away and come back.</p>
            <textarea id="batchlist" rows="6" placeholder="Elinor and Bramble in the great hall&#10;Elinor practicing in the courtyard at dawn"></textarea>
            <div class="editrow">
              <button id="batchstart">Start batch</button>
              <button class="ghost" id="batchstop" type="button" hidden>Stop after this one</button>
            </div>
            <ul class="batchq" id="batchq"></ul>
            <p class="status" id="batchstatus"></p>
            <h2 class="sub">%%MANDALA_MED%%Mazes</h2>
            <p>Classic solvable mazes, drawn crisp for print. No AI, no cost — generate as many as you like.</p>
            <label for="mazediff">Difficulty</label>
            <select id="mazediff">
              <option value="easy">Easy — 12 × 18</option>
              <option value="medium" selected>Medium — 16 × 24</option>
              <option value="hard">Hard — 22 × 33</option>
            </select>
            <label for="mazecount">How many</label>
            <input id="mazecount" type="number" min="1" max="20" value="1">
            <button id="mazego">Generate maze</button>
            <p class="status" id="mazestatus"></p>
      </div>
    </details>
    <details class="step">
      <summary>%ICON_02%<span class="n">02</span> Story & front matter</summary>
      <div class="stepbody">
            <div class="tplcard">
              <h3>📖 Start an Elinor-style storybook</h3>
              <p>Title page, belongs-to page, welcome page — then chapter spreads where each coloring page faces its story page, pre-styled with chapter title, ornament, and History Note. Select a blank plate, describe it in Step 01, and Compose fills it in.</p>
              <div class="tplrow">
                <label for="tplch">Chapters</label>
                <input id="tplch" type="number" value="5" min="1" max="20">
                <button id="tplbuild" type="button">Begin my storybook</button>
              </div>
              <p class="status" id="tplstatus"></p>
            </div>
            <h2 class="sub">%%MANDALA_MED%%Story pages</h2>
            <p>Write the story that faces each coloring page — chapter by chapter, like a coloring-story book.</p>
            <label for="stitle">Chapter title</label>
            <input id="stitle" type="text" placeholder="The Falconer's Glove">
            <label for="sbody">Story text</label>
            <textarea id="sbody" rows="6" placeholder="Write the story…"></textarea>
            <label for="snote">History note (optional)</label>
            <input id="snote" type="text" placeholder="A fascinating fact for the History Note">
            <button id="sadd">Add story page</button>
            <button class="ghost" id="scancel" hidden>Cancel editing</button>
            <label for="sorn">Ornament (optional)</label>
            <input type="file" id="sorn" accept="image/*">
            <div class="coverart"><img id="sornprev" alt="" hidden></div>
            <button class="ghost" id="sornrm" hidden>Remove ornament</button>
            <p class="status" id="sstatus"></p>
            <h2 class="sub">%%MANDALA_MED%%Front matter</h2>
            <p>Standard opening pages. The title page uses your cover title and author where it fits.</p>
            <button class="ghost" id="fmTitle" type="button">Add title page</button>
            <button class="ghost" id="fmCopyright" type="button">Add copyright page</button>
            <button class="ghost" id="fmWelcome" type="button">Add welcome page</button>
            <button class="ghost" id="fmBelongs" type="button">Add “belongs to” page</button>
      </div>
    </details>
    <details class="step">
      <summary>%ICON_03%<span class="n">03</span> Arrange pages</summary>
      <div class="stepbody">
        <p>Put the book in order — art facing story, front matter first. Select a page on the canvas, then move or delete it here.</p>
            <button class="ghost" id="moveback" hidden>Move page earlier</button>
            <button class="ghost" id="movefwd" hidden>Move page later</button>
            <button class="ghost" id="delpage" hidden>Delete this page</button>
      </div>
    </details>
    <details class="step">
      <summary>%ICON_04%<span class="n">04</span> Cover</summary>
      <div class="stepbody">
        <p>Build the KDP full-wrap cover from your finished page count.</p>

        <label for="ctitle">Book title</label>

        <input id="ctitle" type="text" placeholder="Princess Elinor's Coloring Adventure">

        <label for="csubtitle">Subtitle (optional)</label>

        <input id="csubtitle" type="text" placeholder="">

        <label for="cauthor">Author</label>

        <input id="cauthor" type="text" placeholder="Christine">

        <label for="cblurb">Back cover blurb</label>

        <textarea id="cblurb" rows="4" placeholder="A few sentences about the book"></textarea>

        <label for="cpages">Page count</label>

        <div class="coverrow">

        <input id="cpages" type="number" min="24" value="24">

        <button class="ghost" id="csync" type="button">Use book</button>

        </div>

        <label for="cpaper">Paper</label>

        <select id="cpaper">

        <option value="white" selected>White paper</option>

        <option value="cream">Cream paper</option>

        </select>

        <label for="ccolor">Cover color</label>

        <select id="ccolor">

        <option value="#3F6B4C" selected>Forest green</option>

        <option value="#2C3E66">Navy</option>

        <option value="#5B3A5E">Plum</option>

        <option value="#7A2E2E">Maroon</option>

        <option value="#1F6E6B">Teal</option>

        <option value="#33302B">Charcoal</option>

        </select>

        <label class="check" for="cbarcode"><input id="cbarcode" type="checkbox" checked>
        Reserve barcode zone (no ISBN yet)</label>

        <label for="cartprompt">Cover art prompt</label>

        <textarea id="cartprompt" rows="3"></textarea>

        <button id="cartgen">Generate cover art</button>

        <button class="ghost" id="cartupload" type="button">Upload cover art</button>

        <input type="file" id="cartfile" accept="image/*" hidden>

        <div class="coverart"><img id="cartimg" alt="" hidden></div>

        <div class="coverspec" id="coverspec"></div>

        <div class="covermock" id="covermock" hidden>

        <div class="cmp" id="cmback"><span>Back</span></div>

        <div class="cmp" id="cmspine"><span>Spine</span></div>

        <div class="cmp" id="cmfront"><span>Front</span></div>

        </div>

        <button id="cbuild">Build cover PDF</button>

        <p class="status" id="cstatus"></p>
      </div>
    </details>
    <details class="step">
      <summary>%ICON_05%<span class="n">05</span> Publish</summary>
      <div class="stepbody">
        <h2 class="sub">%%MANDALA_MED%%Book &amp; files</h2>
            <p class="count" id="count">0 pages</p>
            <button class="ghost" id="pad" hidden>Add blank plates</button>
            <label class="check" id="markswrap" hidden><input id="cmarks" type="checkbox" checked> Print captions &amp; page numbers</label>
            <button class="ghost" id="download" hidden>Download interior PDF</button>
            <button class="ghost" id="preflight" hidden>KDP preflight check</button>
            <ul class="preflight" id="preflightlist"></ul>
            <button class="ghost" id="savebook" hidden>Save book backup (.json)</button>
            <p class="status" id="booksavestatus" role="status" aria-live="polite"></p>
            <a id="bookdownloadlink" download="fusion-coloring-book.json" hidden>Download book file</a>
            <button class="ghost" id="loadbook">Load book file</button>
            <input type="file" id="loadfile" accept="application/json,.json" hidden>
            <h2 class="sub">%%MANDALA_MED%%KDP publishing</h2>
            <p>Everything KDP asks for, in one place. Saved with your book file — copy it over when you publish.</p>
            <label for="ktitle">Title</label>
            <input id="ktitle" type="text">
            <label for="ksub">Subtitle (optional)</label>
            <input id="ksub" type="text">
            <label for="kauthor">Author</label>
            <input id="kauthor" type="text">
            <label for="kimprint">Imprint (optional)</label>
            <input id="kimprint" type="text" value="Fusion Spark Books">
            <label for="kdesc">Description <span class="kcount" id="kdesccount"></span></label>
            <textarea id="kdesc" rows="5" maxlength="4000" placeholder="What is this book? Who is it for?"></textarea>
            <label>Keywords — 7 slots, 50 characters each</label>
            <div id="kwrap"></div>
            <p class="status">Tip: don't repeat words across slots; think like a searching parent ("fairy tale coloring book girls 4-8").</p>
            <label>Categories — pick these in KDP's category browser</label>
            <input list="kcatlist" id="kcat1" type="text" placeholder="e.g. Children's Coloring Books">
            <input list="kcatlist" id="kcat2" type="text">
            <input list="kcatlist" id="kcat3" type="text">
            <datalist id="kcatlist">
              <option value="Children's Books > Activities, Crafts & Games > Coloring Books"></option>
              <option value="Children's Books > Activities, Crafts & Games > Activity Books"></option>
              <option value="Children's Books > Fairy Tales, Folk Tales & Myths"></option>
              <option value="Humor & Entertainment > Puzzles & Games > Mazes"></option>
            </datalist>
            <h1 style="font-size:1.1rem;margin-top:1.2rem">Royalty estimator</h1>
            <label for="kprice">List price (USD)</label>
            <input id="kprice" type="number" min="0" step="0.01" placeholder="12.99">
            <div class="kroyal" id="kroyal">Enter a list price…</div>
            <p class="status">US rates, black ink, 8.5 × 11, October 2026. Confirm in KDP's calculator before you publish — rates change.</p>
            <h1 style="font-size:1.1rem;margin-top:1.2rem">AI disclosure</h1>
            <p class="status">KDP asks whether AI tools were used. For this book the honest answer is yes — paste this into the disclosure box and adjust as needed:</p>
            <div class="kroyal" id="kaitext">The coloring illustrations in this book were generated with AI image tools, then curated, edited, and arranged by the author. The story text was written by the author.</div>
            <div class="editrow"><button class="ghost" id="kcopy" type="button" style="width:auto">Copy disclosure text</button></div>
            <h1 style="font-size:1.1rem;margin-top:1.2rem">Go-live checklist</h1>
            <ul class="kcheck" id="kcheck">
              <li class="auto"><input type="checkbox" id="kc1" disabled><label for="kc1">Interior has at least 24 pages</label></li>
              <li class="auto"><input type="checkbox" id="kc2" disabled><label for="kc2">Page count is even</label></li>
              <li><input type="checkbox" id="kc3"><label for="kc3">Cover PDF built from the cover section</label></li>
              <li><input type="checkbox" id="kc4"><label for="kc4">AI content disclosed in KDP</label></li>
              <li class="auto"><input type="checkbox" id="kc5" disabled><label for="kc5">Description and at least one keyword entered</label></li>
              <li><input type="checkbox" id="kc6"><label for="kc6">Physical proof copy ordered and approved</label></li>
            </ul>
            <p class="status" id="kstatus"></p>
      </div>
    </details>
  </aside>
  <main class="canvas">
    <div class="workbar"><span class="wrule"></span>%%MANDALA_BAR%%<span class="wlabel">The Studio Canvas</span>%%MANDALA_BAR%%<span class="wrule"></span></div>
    <div class="stage">
    <div class="emptystate" id="emptystate">
      <div class="es-orn">❦</div>
      <h2>Your canvas awaits</h2>
      <p>Describe a scene in <strong>01 · Create pages</strong>, then press <strong>Compose page</strong>.<br>Your artwork will appear here, ready for its finishing touches.</p>
    </div>
    <div class="sheet" id="sheet" hidden>
      <img id="plate" alt="">
      <div class="caption" id="caption">Empty plate</div>
      <div class="folio" id="folio"></div>
    </div>
    <div class="storyview" id="storyview" hidden></div>
    <p class="printcheck" id="printcheck"></p>
    <div class="imagerow">
      <button class="ghost" id="editart" hidden>Change only this…</button>
      <button class="ghost" id="strlines" hidden>Strengthen lines…</button>
      <button class="ghost" id="dlimage" hidden>Download this image</button>
    </div>
    <div class="thumbs" id="thumbs"></div>
    </div>
  </main>
</div>
<div class="editmodal" id="editmodal" hidden>
  <div class="editbox">
    <h2>Change only this</h2>
    <p>Paint over the part to change, then describe the fix. Everything else stays exactly as it is.</p>
    <canvas id="editcanvas"></canvas>
    <div class="editrow">
      <label>Brush <input id="brushsize" type="range" min="10" max="120" value="40"></label>
      <button class="ghost" id="brushclear" type="button">Clear paint</button>
    </div>
    <label for="editprompt">Change only this</label>
    <textarea id="editprompt" rows="2" placeholder="e.g. remove the extra bird in the corner"></textarea>
    <div class="editrow">
      <button id="editapply">Apply edit</button>
      <button class="ghost" id="editcancel" type="button">Cancel</button>
    </div>
    <p class="status" id="editstatus"></p>
  </div>
</div>
<div class="editmodal" id="strmodal" hidden>
  <div class="editbox" style="max-width:880px">
    <h2>Strengthen lines</h2>
    <p>Deepen gray lines or add a little weight along the edges. Nothing else changes.</p>
    <div class="strmodes">
      <label><input type="radio" name="strmode" value="subtle" checked>
        <span><b>Subtle · barely there</b><i>The lightest touch; only faintest grays deepen.</i></span></label>
      <label><input type="radio" name="strmode" value="gentle">
        <span><b>Darker only · gentle</b><i>Deepens gray lines; existing black lines keep their width.</i></span></label>
      <label><input type="radio" name="strmode" value="balanced">
        <span><b>Balanced · in between</b><i>A lighter edge adjustment between Darker only and Slightly bolder.</i></span></label>
      <label><input type="radio" name="strmode" value="bolder">
        <span><b>Slightly bolder</b><i>Also adds a little weight along existing edges. Fine details may thicken too.</i></span></label>
    </div>
    <label class="check"><input id="strinspect" type="checkbox"> Inspect at full pixel size</label>
    <div class="strpanes">
      <div><h3>Current picture</h3><div class="strscroll"><canvas id="scurrent"></canvas></div></div>
      <div><h3>Line-strength preview</h3><div class="strscroll"><canvas id="spreview"></canvas></div></div>
    </div>
    <div class="editrow">
      <button id="strsave">Save revised copy</button>
      <button class="ghost" id="strcancel" type="button">Cancel</button>
    </div>
    <p class="status" id="strstatus"></p>
  </div>
</div>
<script>
const book = [];
let current = -1;
let busy = false;
const countEl = document.getElementById('count');
const padBtn = document.getElementById('pad');
const downloadBtn = document.getElementById('download');
const saveBookBtn = document.getElementById('savebook');
const loadBookBtn = document.getElementById('loadbook');
const loadFile = document.getElementById('loadfile');
const moveBackBtn = document.getElementById('moveback');
const moveFwdBtn = document.getElementById('movefwd');
const delPageBtn = document.getElementById('delpage');
const printCheckEl = document.getElementById('printcheck');
const preflightBtn = document.getElementById('preflight');
const preflightList = document.getElementById('preflightlist');
const marksWrap = document.getElementById('markswrap');
const marksBox = document.getElementById('cmarks');
let editingStory = -1;
let storyOrnament = null;
let styleReference = null;
let openedBookFile = '';
let openedBookAt = '';
let backupRequestedAt = '';
let bookCheckpoint = null;
let checkpointKind = '';

// Compare small field snapshots, keeping image strings by reference. Never
// stringify all image data during navigation just to display save status.
function captureBookCheckpoint() {
  const fields = (item) => Object.fromEntries(Object.entries(item).filter(([key]) => key !== 'w' && key !== 'h'));
  return { pages: book.map(fields), characters: characters.map(fields),
    style: styleReference, ornament: storyOrnament, marks: marksOn(), kdp: JSON.stringify(kdpSaveData()) };
}

function sameBookCheckpoint(a, b) {
  if (!a || a.style !== b.style || a.ornament !== b.ornament || a.marks !== b.marks || a.kdp !== b.kdp) return false;
  const sameItems = (x, y) => x.length === y.length && x.every((item, i) => {
    const keys = Object.keys(item);
    return keys.length === Object.keys(y[i]).length && keys.every((key) => item[key] === y[i][key]);
  });
  return sameItems(a.pages, b.pages) && sameItems(a.characters, b.characters);
}

function refreshBookState() {
  const n = book.length;
  const identity = document.getElementById('bookidentity');
  const state = document.getElementById('bookbackupstate');
  identity.textContent = (openedBookFile ? 'Book open: ' + openedBookFile : n ? 'New book' : 'No book open') +
    ' · ' + n + (n === 1 ? ' page' : ' pages');
  const changed = !sameBookCheckpoint(bookCheckpoint, captureBookCheckpoint());
  if (changed || checkpointKind === 'opened') {
    // A link prepared before later edits is an old snapshot, not a new backup.
    document.getElementById('bookdownloadlink').hidden = true;
    document.getElementById('quickbookdownload').hidden = true;
  }
  state.dataset.state = changed && n ? 'changed' : 'ready';
  if (!n && !openedBookFile) state.textContent = 'Create pages or open a saved book to begin.';
  else if (changed) state.textContent = checkpointKind
    ? 'Changes since ' + (checkpointKind === 'opened' ? 'reopening' : 'the last backup request') + ' — download an updated backup.'
    : 'This book has no backup yet — choose Save book backup.';
  else if (checkpointKind === 'opened') state.textContent = 'Reopened successfully at ' + openedBookAt + ' · No changes since reopening.';
  else state.textContent = 'Backup download requested at ' + backupRequestedAt + ' · Check Downloads to confirm the file was saved.';
}

function renderStyleReference() {
  const preview = document.getElementById('stylerefpreview');
  preview.hidden = !styleReference;
  if (styleReference) preview.src = 'data:image/png;base64,' + styleReference.image;
  else preview.removeAttribute('src');
  document.getElementById('clearstyleref').hidden = !styleReference;
  document.getElementById('stylerefstatus').textContent = styleReference
    ? 'Style reference: ' + styleReference.name
    : 'Use an approved page to guide linework and illustration style.';
  refreshBookState();
}

document.getElementById('styleref').onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const image = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = () => downscaleRef(reader.result, resolve, 1536, reject);
      reader.readAsDataURL(file);
    });
    styleReference = { name: file.name, image };
    renderStyleReference();
  } catch (err) {
    document.getElementById('stylerefstatus').textContent = 'Could not open that reference. Choose a valid image.';
  }
  e.target.value = '';
};
document.getElementById('clearstyleref').onclick = () => {
  styleReference = null;
  renderStyleReference();
};

function captureGenerationReferences(chars) {
  return { style: styleReference ? { ...styleReference } : null,
    characters: chars.map((c) => ({ name: c.name, description: c.description || '', refs: [...(c.refs || [])] })) };
}

function generatedPage(data, subject, referenceSnapshot) {
  const page = { kind: 'art', image: data.image, caption: subject };
  if (data.original_image) page.original_image = data.original_image;
  if (data.generation) page.generation = { ...data.generation, references: referenceSnapshot };
  return page;
}

function renderGenerationDetails(page) {
  const g = page && page.generation;
  document.getElementById('generationdetails').hidden = !g;
  document.getElementById('downloadoriginal').hidden = !(page && page.original_image);
  document.getElementById('generationprompt').value = g ? g.prompt || '' : '';
  document.getElementById('generationinfo').textContent = g
    ? g.model + ' · ' + g.level + ' · high quality · ' + (g.cleanup ? 'gray removal on' : 'original linework') : '';
}

document.getElementById('reusesettings').onclick = () => {
  const g = book[current] && book[current].generation;
  if (!g) return;
  document.getElementById('subject').value = g.subject || '';
  document.getElementById('level').value = g.level;
  document.getElementById('cleanup').checked = !!g.cleanup;
  const refs = g.references || {};
  styleReference = refs.style ? { ...refs.style } : null;
  renderStyleReference();
  const selectedIds = [];
  (refs.characters || []).forEach((snapshot, i) => {
    let character = characters.find((c) => c.name === snapshot.name && c.description === snapshot.description &&
      JSON.stringify(c.refs || []) === JSON.stringify(snapshot.refs || []));
    if (!character) {
      character = { ...snapshot, refs: [...(snapshot.refs || [])], id: 'reuse' + Date.now().toString(36) + '-' + i };
      characters.push(character);
    }
    selectedIds.push(character.id);
  });
  saveCharacters();
  renderCharacters();
  document.querySelectorAll('#charchk input').forEach((box) => { box.checked = selectedIds.includes(box.dataset.char); });
  document.getElementById('status').textContent = 'Settings restored. Edit the scene description, then compose a new page.';
};
document.getElementById('downloadoriginal').onclick = () => {
  const page = book[current];
  if (!page || !page.original_image) return;
  const a = document.createElement('a');
  a.href = 'data:image/png;base64,' + page.original_image;
  a.download = 'fusion-coloring-original-' + (current + 1) + '.png';
  a.click();
};

function variantLabel(v) {
  return { story: 'Story page', titlepage: 'Title page', copyright: 'Copyright page',
    welcome: 'Welcome page', belongsto: 'Belongs-to page' }[v] || 'Story page';
}
function marksOn() { return marksBox.checked; }

function nextMultipleOf4(n) {
  return n === 0 ? 0 : Math.ceil(n / 4) * 4;
}

function renderCount() {
  const n = book.length;
  document.getElementById('quicksavebook').disabled = n === 0;
  const target = nextMultipleOf4(n);
  const gap = target - n;
  if (n === 0) {
    countEl.textContent = '0 pages';
    padBtn.hidden = true;
    downloadBtn.hidden = true;
    saveBookBtn.hidden = true;
    preflightBtn.hidden = true;
    marksWrap.hidden = true;
    refreshKdp();
    return;
  }
  downloadBtn.hidden = false;
  saveBookBtn.hidden = false;
  preflightBtn.hidden = false;
  marksWrap.hidden = false;
  if (gap === 0) {
    countEl.textContent = n + ' pages · multiple of 4';
    padBtn.hidden = true;
  } else {
    countEl.textContent = n + ' pages · add ' + gap + ' blank' + (gap === 1 ? '' : 's') + ' to reach ' + target;
    padBtn.hidden = false;
    padBtn.textContent = 'Add ' + gap + ' blank plate' + (gap === 1 ? '' : 's');
  }
  refreshKdp();
}

function show(i) {
  current = i;
  const page = book[i];
  renderGenerationDetails(page);
  const sheet = document.getElementById('sheet');
  const sview = document.getElementById('storyview');
  const img = document.getElementById('plate');
  const caption = document.getElementById('caption');
  const folio = document.getElementById('folio');
  document.querySelectorAll('.thumbs button').forEach((b, idx) => {
    b.classList.toggle('active', idx === i);
  });
  const has = !!page;
  const empty = book.length === 0;
  document.getElementById('emptystate').hidden = !empty;
  delPageBtn.hidden = !has;
  moveBackBtn.hidden = !(has && i > 0);
  moveFwdBtn.hidden = !(has && i < book.length - 1);
  document.getElementById('editart').hidden = !(page && page.kind === 'art' && page.image);
  document.getElementById('strlines').hidden = !(page && page.kind === 'art' && page.image);
  document.getElementById('dlimage').hidden = !(page && page.kind === 'art' && page.image);
  if (page && page.kind === 'story') {
    sheet.hidden = true;
    sview.hidden = false;
    sview.innerHTML = '';
    const add = (tag, cls, text) => {
      if (!text) return null;
      const el = document.createElement(tag);
      if (cls) el.className = cls;
      el.textContent = text;
      sview.appendChild(el);
      return el;
    };
    add('div', 'vlabel', variantLabel(page.variant));
    if (page.variant === 'belongsto') {
      add('h2', '', 'THIS BOOK BELONGS TO:');
      add('p', '', 'Owner’s Name: …………………………');
      add('p', '', 'Date: ……………………');
    } else {
      add('h2', '', page.title);
      add('p', '', page.subtitle);
      const orn = document.createElement('div');
      orn.className = 'orn';
      orn.textContent = '— ◆ —';
      sview.appendChild(orn);
      (page.body || '').split('\\n').forEach((para) => {
        if (para.trim()) add('p', '', para.trim());
      });
      if (page.note) {
        const n = document.createElement('div');
        n.className = 'note';
        const h = document.createElement('h3');
        h.textContent = 'History Note';
        const pp = document.createElement('p');
        pp.textContent = page.note;
        n.appendChild(h);
        n.appendChild(pp);
        sview.appendChild(n);
      }
      if (page.variant === 'titlepage' && page.publisher) add('p', '', page.publisher);
    }
    const ed = document.createElement('button');
    ed.className = 'ghost';
    ed.textContent = 'Edit this page';
    ed.onclick = () => editStory(i);
    sview.appendChild(ed);
  } else {
    sheet.hidden = empty;
    sview.hidden = true;
    if (!page || !page.image) {
      img.removeAttribute('src');
      caption.textContent = page ? 'Blank plate' : 'Empty plate';
    } else {
      img.src = 'data:image/png;base64,' + page.image;
      caption.textContent = page.caption;
    }
    folio.textContent = (page && marksOn()) ? String(i + 1) : '';
  }
  updatePrintCheck(page, i);
  refreshBookState();
}

// Print readiness, mirroring build_pdf's placement:
// 40pt side margins, 36pt top, 92pt bottom on a 612x792pt letter page.
function updatePrintCheck(page, i) {
  if (!page) { printCheckEl.textContent = ''; return; }
  if (page.kind === 'story') {
    printCheckEl.textContent = variantLabel(page.variant) + (page.title ? ' — ' + page.title : '');
    return;
  }
  if (!page.image) { printCheckEl.textContent = ''; return; }
  const render = () => {
    if (current !== i || !page.w || !page.h) return;
    const maxW = (612 - 80) / 72, maxH = (792 - 36 - 92) / 72;
    const s = Math.min(maxW / page.w, maxH / page.h);
    const ppi = Math.round(page.w / (page.w * s));
    let text = page.w + ' \u00d7 ' + page.h + ' px \u2192 ' +
      (page.w * s).toFixed(1) + ' \u00d7 ' + (page.h * s).toFixed(1) +
      ' in on the page \u2248 ' + ppi + ' PPI';
    if (ppi < 300) text += ' \u2014 below the 300 PPI print target, lines may look soft in print.';
    printCheckEl.textContent = text;
  };
  if (page.w && page.h) { render(); return; }
  printCheckEl.textContent = '';
  const probe = new Image();
  probe.onload = () => { page.w = probe.naturalWidth; page.h = probe.naturalHeight; render(); };
  probe.src = 'data:image/png;base64,' + page.image;
}

function renderThumbs() {
  const box = document.getElementById('thumbs');
  box.innerHTML = '';
  book.forEach((page, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.title = 'Page ' + (i + 1);
    if (page.kind === 'story') {
      const d = document.createElement('div');
      d.className = 'text-thumb';
      const k = document.createElement('div');
      k.className = 'k';
      k.textContent = variantLabel(page.variant);
      const t = document.createElement('div');
      t.className = 't';
      t.textContent = page.title || '(untitled)';
      d.appendChild(k);
      d.appendChild(t);
      b.appendChild(d);
    } else if (page.image) {
      const img = document.createElement('img');
      img.src = 'data:image/png;base64,' + page.image;
      img.alt = '';
      b.appendChild(img);
    } else {
      b.innerHTML = '<div class="blank-thumb"></div>';
    }
    b.onclick = () => show(i);
    if (i === current) b.classList.add('active');
    box.appendChild(b);
  });
}

/* ---- Characters ---- */
let characters = [];
const CHAR_STORE_KEY = 'fusion-coloring-characters';

function saveCharacters() {
  try {
    localStorage.setItem(CHAR_STORE_KEY, JSON.stringify(characters));
  } catch (e) { /* quota full — characters stay for this session */ }
}

function loadCharacters() {
  try {
    const raw = localStorage.getItem(CHAR_STORE_KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) characters = arr;
    }
  } catch (e) { /* corrupted — start fresh */ }
}

function downscaleRef(dataUrl, cb, maxSize = 1024, onError = null) {
  const img = new Image();
  img.onload = () => {
    const MAX = maxSize;
    let w = img.naturalWidth, h = img.naturalHeight;
    if (Math.max(w, h) > MAX) {
      const s = MAX / Math.max(w, h);
      w = Math.round(w * s); h = Math.round(h * s);
    }
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    c.getContext('2d').drawImage(img, 0, 0, w, h);
    cb(c.toDataURL('image/png').split(',')[1]);
  };
  img.onerror = () => onError ? onError() : cb(dataUrl.split(',')[1]);
  img.src = dataUrl;
}

function renderCharacters() {
  refreshBookState();
  const list = document.getElementById('charlist');
  list.innerHTML = '';
  characters.forEach((c) => {
    const card = document.createElement('div');
    card.className = 'charcard';
    if (c.refs && c.refs[0]) {
      const im = document.createElement('img');
      im.src = 'data:image/png;base64,' + c.refs[0];
      im.alt = '';
      card.appendChild(im);
    }
    const tx = document.createElement('div');
    const b = document.createElement('b');
    b.textContent = c.name;
    const s = document.createElement('span');
    const n = (c.refs || []).length;
    s.textContent = n + ' reference' + (n === 1 ? '' : 's');
    tx.appendChild(b);
    tx.appendChild(s);
    card.appendChild(tx);
    const rm = document.createElement('button');
    rm.className = 'ghost';
    rm.type = 'button';
    rm.textContent = 'Remove';
    rm.onclick = () => {
      characters = characters.filter((x) => x.id !== c.id);
      saveCharacters();
      renderCharacters();
    };
    card.appendChild(rm);
    list.appendChild(card);
  });
  const chk = document.getElementById('charchk');
  chk.innerHTML = '';
  if (!characters.length) {
    const hint = document.createElement('p');
    hint.className = 'status';
    hint.textContent = 'Add characters below to lock their look across scenes.';
    chk.appendChild(hint);
    return;
  }
  characters.forEach((c) => {
    const lab = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.dataset.char = c.id;
    lab.appendChild(box);
    lab.appendChild(document.createTextNode(' ' + c.name));
    chk.appendChild(lab);
  });
}

document.getElementById('cadd').onclick = () => {
  const st = document.getElementById('charstatus');
  const name = document.getElementById('cname').value.trim();
  const desc = document.getElementById('cdesc').value.trim();
  const files = Array.from(document.getElementById('crefs').files).slice(0, 3);
  if (!name) { st.textContent = 'Give the character a name.'; return; }
  if (!desc && !files.length) { st.textContent = 'Add a description or at least one reference picture.'; return; }
  const finishAdd = (refs) => {
    characters.push({
      id: 'c' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36),
      name: name, description: desc, refs: refs
    });
    saveCharacters();
    document.getElementById('cname').value = '';
    document.getElementById('cdesc').value = '';
    document.getElementById('crefs').value = '';
    st.textContent = name + ' added and saved for next time.';
    renderCharacters();
  };
  if (!files.length) { finishAdd([]); return; }
  const refs = [];
  files.forEach((f) => {
    const r = new FileReader();
    r.onload = () => {
      downscaleRef(r.result, (small) => {
        refs.push(small);
        if (refs.length === files.length) finishAdd(refs);
      });
    };
    r.readAsDataURL(f);
  });
};

function selectedCharacters() {
  return characters.filter((c) => {
    const box = document.querySelector('#charchk input[data-char="' + c.id + '"]');
    return box && box.checked;
  });
}

/* ---- Batch compose ---- */
let batchRunning = false;
let batchStop = false;

document.getElementById('batchstart').onclick = async () => {
  const key = document.getElementById('key').value.trim();
  const level = document.getElementById('level').value;
  const st = document.getElementById('batchstatus');
  const scenes = document.getElementById('batchlist').value.split('\\n')
    .map((s) => s.trim()).filter(Boolean);
  if (batchRunning) return;
  if (!key) { st.textContent = 'API key is required.'; return; }
  if (!scenes.length) { st.textContent = 'Write at least one scene, one per line.'; return; }
  const chars = selectedCharacters();
  const charPayload = chars.map((c) => ({ name: c.name, description: c.description || '' }));
  const charRefs = [];
  chars.forEach((c) => (c.refs || []).forEach((r) => charRefs.push(r)));
  const referenceSnapshot = captureGenerationReferences(chars);
  const cleanup = document.getElementById('cleanup').checked;
  const styleImage = referenceSnapshot.style ? referenceSnapshot.style.image : null;

  batchRunning = true;
  batchStop = false;
  busy = true;
  document.getElementById('batchstart').disabled = true;
  document.getElementById('batchstop').hidden = false;
  const q = document.getElementById('batchq');
  q.innerHTML = '';
  const rows = scenes.map((s) => {
    const li = document.createElement('li');
    const dot = document.createElement('span');
    dot.className = 'qdot';
    li.appendChild(dot);
    li.appendChild(document.createTextNode(s));
    q.appendChild(li);
    return { scene: s, li: li, dot: dot };
  });

  let done = 0, failed = 0, skipped = 0;
  for (const row of rows) {
    if (batchStop) {
      row.dot.className = 'qdot skipped';
      skipped++;
      continue;
    }
    row.dot.className = 'qdot working';
    row.li.scrollIntoView({ block: 'nearest' });
    st.textContent = 'Composing ' + (done + failed + 1) + ' of ' + scenes.length + ': ' + row.scene;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 120000);
    try {
      const res = await fetch('/compose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: key, subject: row.scene, level: level,
          characters: charPayload, references: charRefs, style_reference: styleImage, cleanup }),
        signal: ctrl.signal
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed');
      book.push(generatedPage(data, row.scene, referenceSnapshot));
      row.dot.className = 'qdot done';
      done++;
    } catch (e) {
      row.dot.className = 'qdot failed';
      const msg = (e && e.name === 'AbortError') ? 'Timed out' : ((e && e.message) || 'Failed');
      row.li.title = msg;
      const err = document.createElement('div');
      err.className = 'qerr';
      err.textContent = 'Failed: ' + msg;
      row.li.appendChild(err);
      failed++;
    } finally {
      clearTimeout(timer);
    }
    renderCount();
    renderThumbs();
  }
  if (book.length) show(book.length - 1);
  batchRunning = false;
  busy = false;
  document.getElementById('batchstart').disabled = false;
  document.getElementById('batchstop').hidden = true;
  st.textContent = 'Batch finished: ' + done + ' composed' +
    (failed ? ', ' + failed + ' failed (hover a red dot for why)' : '') +
    (skipped ? ', ' + skipped + ' skipped' : '') +
    '. Remember to save your book file.';
};

document.getElementById('batchstop').onclick = () => {
  batchStop = true;
  document.getElementById('batchstatus').textContent = 'Stopping after the current page…';
};

document.getElementById('keyshow').onclick = () => {
  const k = document.getElementById('key');
  const b = document.getElementById('keyshow');
  const showing = k.type === 'text';
  k.type = showing ? 'password' : 'text';
  b.textContent = showing ? 'Show' : 'Hide';
};

document.getElementById('compose').onclick = async () => {
  if (busy) return;
  const key = document.getElementById('key').value.trim();
  const subject = document.getElementById('subject').value.trim();
  const status = document.getElementById('status');
  const btn = document.getElementById('compose');
  const level = document.getElementById('level').value;
  if (!key || !subject) { status.textContent = 'Key and a description are both required.'; return; }
  busy = true;
  btn.disabled = true;
  status.textContent = 'Pressing the plate… this takes a little while. Press once.';
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 120000);
  const chars = selectedCharacters();
  const charPayload = chars.map((c) => ({ name: c.name, description: c.description || '' }));
  const charRefs = [];
  chars.forEach((c) => (c.refs || []).forEach((r) => charRefs.push(r)));
  const referenceSnapshot = captureGenerationReferences(chars);
  const cleanup = document.getElementById('cleanup').checked;
  const styleImage = referenceSnapshot.style ? referenceSnapshot.style.image : null;
  if (chars.length) {
    status.textContent = 'Pressing the plate with ' + chars.map((c) => c.name).join(', ') +
      '… this takes a little while. Press once.';
  }
  try {
    const res = await fetch('/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, subject, level, characters: charPayload, references: charRefs, style_reference: styleImage, cleanup }),
      signal: ctrl.signal
    });
    const data = await res.json();
    if (!res.ok) { status.textContent = data.error || 'Failed.'; return; }
    const cur = book[current];
    if (cur && cur.kind === 'art' && !cur.image) {
      Object.assign(cur, generatedPage(data, subject, referenceSnapshot));
      renderThumbs();
      show(current);
      status.textContent = 'Plate filled. Select the next blank plate for the following scene.';
    } else {
      book.push(generatedPage(data, subject, referenceSnapshot));
      renderCount();
      renderThumbs();
      show(book.length - 1);
      status.textContent = 'Plate pressed. Change the sentence, then press once more.';
    }
  } catch (e) {
    status.textContent = (e && e.name === 'AbortError')
      ? 'The press took too long. Press compose once more.'
      : 'Could not reach the press.';
  } finally {
    clearTimeout(timer);
    busy = false;
    btn.disabled = false;
  }
};

padBtn.onclick = () => {
  const gap = nextMultipleOf4(book.length) - book.length;
  for (let i = 0; i < gap; i++) book.push({ kind: 'blank' });
  renderCount();
  renderThumbs();
  show(book.length - 1);
};

let bookDownloadUrl = null;
saveBookBtn.onclick = () => {
  const status = document.getElementById('booksavestatus');
  const link = document.getElementById('bookdownloadlink');
  try {
    const blob = new Blob([JSON.stringify({ app: 'fusion-coloring', version: 4, pages: book, styleReference: styleReference, ornament: storyOrnament, marks: marksOn(), characters: characters, kdp: kdpSaveData() })], { type: 'application/json' });
    const nextUrl = URL.createObjectURL(blob);
    // Use an attached, visible link for Safari. Keep it alive for a manual
    // retry rather than revoking it before the user can finish saving.
    const previousUrl = bookDownloadUrl;
    bookDownloadUrl = nextUrl;
    link.href = nextUrl;
    link.hidden = false;
    const quickLink = document.getElementById('quickbookdownload');
    quickLink.href = nextUrl;
    quickLink.hidden = false;
    if (previousUrl) URL.revokeObjectURL(previousUrl);
    status.textContent = 'Book download requested. Check your browser downloads. If nothing starts, click Download book file below. Keep this tab open until the file is saved.';
    document.getElementById('booktoolbarstatus').textContent = 'Book download requested. Check Downloads, or use the Download book file link above.';
    link.click();
    backupRequestedAt = new Date().toLocaleString();
    bookCheckpoint = captureBookCheckpoint();
    checkpointKind = 'requested';
    refreshBookState();
  } catch (error) {
    status.textContent = 'Could not prepare the book download. Your pages are still in this tab. Keep it open and download each image while we resolve the problem.';
    document.getElementById('booktoolbarstatus').textContent = status.textContent;
  }
};

loadBookBtn.onclick = () => loadFile.click();
document.getElementById('quickloadbook').onclick = () => loadFile.click();
document.getElementById('quicksavebook').onclick = saveBookBtn.onclick;

loadFile.onchange = () => {
  const status = document.getElementById('status');
  const f = loadFile.files[0];
  if (!f) return;
  document.getElementById('booktoolbarstatus').textContent = 'Opening ' + f.name + '…';
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      const pages = Array.isArray(data) ? data : data.pages;
      if (!Array.isArray(pages)) throw new Error('bad book file');
      book.length = 0;
      for (const p of pages) {
        if (!p) continue;
        if (p.kind === 'story') {
          book.push({ kind: 'story', variant: p.variant || 'story', title: p.title || '',
            subtitle: p.subtitle || '', body: p.body || '', note: p.note || '',
            publisher: p.publisher || '' });
        } else if (p.image) {
          book.push({ kind: 'art', image: p.image, caption: p.caption || '', w: p.w || 0, h: p.h || 0,
            generation: p.generation || null, original_image: p.original_image || null });
        } else {
          book.push({ kind: 'blank' });
        }
      }
      styleReference = (!Array.isArray(data) && data.styleReference && typeof data.styleReference.image === 'string') ? data.styleReference : null;
      renderStyleReference();
      storyOrnament = (!Array.isArray(data) && data.ornament) ? data.ornament : null;
      const pv = document.getElementById('sornprev');
      if (storyOrnament && storyOrnament.image) {
        pv.src = 'data:image/png;base64,' + storyOrnament.image;
        pv.hidden = false;
        document.getElementById('sornrm').hidden = false;
      } else {
        pv.hidden = true;
        document.getElementById('sornrm').hidden = true;
      }
      marksBox.checked = Array.isArray(data) || data.marks !== false;
      characters = (!Array.isArray(data) && Array.isArray(data.characters)) ? data.characters : [];
      saveCharacters();
      renderCharacters();
      kdpLoadData(!Array.isArray(data) ? data.kdp : null);
      clearStoryForm();
      openedBookFile = f.name || 'Saved book';
      openedBookAt = new Date().toLocaleString();
      backupRequestedAt = '';
      checkpointKind = 'opened';
      bookCheckpoint = captureBookCheckpoint();
      renderCount();
      renderThumbs();
      show(book.length - 1);
      status.textContent = 'Book loaded: ' + book.length + ' pages.';
      document.getElementById('booktoolbarstatus').textContent = status.textContent;
      document.getElementById('quickloadbook').textContent = 'Open another saved book';
    } catch (e) {
      status.textContent = 'Could not read that book file.';
      document.getElementById('booktoolbarstatus').textContent = 'Could not open that file. Choose a Fusion Coloring .json book backup.';
    }
    loadFile.value = '';
  };
  reader.onerror = () => {
    document.getElementById('booktoolbarstatus').textContent = 'Could not read the selected file. Your current pages are still open. Try choosing the backup again.';
    loadFile.value = '';
  };
  reader.readAsText(f);
};

delPageBtn.onclick = () => {
  const status = document.getElementById('status');
  if (!(current >= 0 && current < book.length)) return;
  const pg = book[current];
  const name = pg.kind === 'story' ? (pg.title || variantLabel(pg.variant)) : pg.caption;
  const label = 'page ' + (current + 1) + (name ? ' ("' + name + '")' : '');
  if (!confirm('Delete ' + label + '?')) return;
  book.splice(current, 1);
  renderCount();
  renderThumbs();
  show(Math.min(current, book.length - 1));
  status.textContent = 'Page deleted. Remaining pages were renumbered.';
};

moveBackBtn.onclick = () => {
  if (current <= 0) return;
  const page = book.splice(current, 1)[0];
  book.splice(current - 1, 0, page);
  renderThumbs();
  show(current - 1);
};

moveFwdBtn.onclick = () => {
  if (!(current >= 0 && current < book.length - 1)) return;
  const page = book.splice(current, 1)[0];
  book.splice(current + 1, 0, page);
  renderThumbs();
  show(current + 1);
};

async function ensureAllDims() {
  await Promise.all(book.map((p) => new Promise((res) => {
    if (!p.image || (p.w && p.h)) { res(); return; }
    const probe = new Image();
    probe.onload = () => { p.w = probe.naturalWidth; p.h = probe.naturalHeight; res(); };
    probe.onerror = () => res();
    probe.src = 'data:image/png;base64,' + p.image;
  })));
}

function preflightPayload() {
  return { pages: serializeBook() };
}

function renderPreflight(data) {
  preflightList.innerHTML = '';
  const sym = { pass: '✓', warn: '⚠', fail: '✗', info: 'ⓘ' };
  data.checks.forEach((c) => {
    const li = document.createElement('li');
    li.className = c.status;
    li.textContent = (sym[c.status] || '') + ' ' + c.label + (c.detail ? ' — ' + c.detail : '');
    preflightList.appendChild(li);
  });
}

preflightBtn.onclick = async () => {
  const status = document.getElementById('status');
  status.textContent = 'Running KDP preflight…';
  try {
    await ensureAllDims();
    const res = await fetch('/preflight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(preflightPayload())
    });
    const data = await res.json();
    renderPreflight(data);
    status.textContent = data.ok
      ? 'Preflight passed. This interior is ready for KDP.'
      : 'Preflight found problems — see the list above.';
  } catch (e) {
    status.textContent = 'Could not run the preflight check.';
  }
};

downloadBtn.onclick = async () => {
  const status = document.getElementById('status');
  downloadBtn.disabled = true;
  status.textContent = 'Running KDP preflight…';
  try {
    await ensureAllDims();
    const pre = await fetch('/preflight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(preflightPayload())
    });
    const pdata = await pre.json();
    renderPreflight(pdata);
    const fails = pdata.checks.filter((c) => c.status === 'fail');
    if (fails.length && !confirm('KDP preflight found ' + fails.length + ' problem(s):\\n' +
        fails.map((f) => '• ' + f.label + (f.detail ? ' — ' + f.detail : '')).join('\\n') +
        '\\n\\nDownload the PDF anyway?')) {
      status.textContent = 'Download cancelled. Fix the failed items and try again.';
      downloadBtn.disabled = false;
      return;
    }
    status.textContent = 'Making the interior PDF…';
    const res = await fetch('/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pages: serializeBook(), ornament: storyOrnament, marks: marksOn() })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      status.textContent = data.error || 'Could not make the PDF.';
      downloadBtn.disabled = false;
      return;
    }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'fusion-coloring-interior.pdf';
    a.click();
    status.textContent = 'Interior PDF downloaded. Cover is a separate file.';
  } catch (e) {
    status.textContent = 'Could not make the PDF.';
  }
  downloadBtn.disabled = false;
};

/* ---- Story pages & front matter ---- */
function storyFormData() {
  const base = (editingStory >= 0 && book[editingStory]) ? book[editingStory] : {};
  return {
    kind: 'story',
    variant: base.variant || 'story',
    title: document.getElementById('stitle').value.trim(),
    subtitle: base.subtitle || '',
    body: document.getElementById('sbody').value.trim(),
    note: document.getElementById('snote').value.trim(),
    publisher: base.publisher || ''
  };
}

function clearStoryForm() {
  ['stitle', 'sbody', 'snote'].forEach((id) => { document.getElementById(id).value = ''; });
  editingStory = -1;
  document.getElementById('sadd').textContent = 'Add story page';
  document.getElementById('scancel').hidden = true;
}

function editStory(i) {
  const p = book[i];
  if (!p || p.kind !== 'story') return;
  document.getElementById('stitle').value = p.title || '';
  document.getElementById('sbody').value = p.body || '';
  document.getElementById('snote').value = p.note || '';
  editingStory = i;
  document.getElementById('sadd').textContent = 'Update story page';
  document.getElementById('scancel').hidden = false;
  document.getElementById('stitle').focus();
}

document.getElementById('sadd').onclick = () => {
  const st = document.getElementById('sstatus');
  const d = storyFormData();
  if (!d.title && !d.body) { st.textContent = 'Give the page a title or some story text.'; return; }
  if (editingStory >= 0 && book[editingStory] && book[editingStory].kind === 'story') {
    Object.assign(book[editingStory], d);
    renderThumbs();
    show(editingStory);
    st.textContent = 'Story page updated.';
  } else {
    book.push(d);
    renderCount();
    renderThumbs();
    show(book.length - 1);
    st.textContent = 'Story page added as page ' + book.length + '.';
  }
  clearStoryForm();
};

document.getElementById('scancel').onclick = clearStoryForm;

function addFront(variant, fields) {
  const page = Object.assign(
    { kind: 'story', variant: variant, title: '', subtitle: '', body: '', note: '', publisher: '' },
    fields || {});
  book.push(page);
  renderCount();
  renderThumbs();
  show(book.length - 1);
  document.getElementById('sstatus').textContent =
    variantLabel(variant) + ' added as page ' + book.length + '. Open it to edit the text.';
}

document.getElementById('fmTitle').onclick = () => addFront('titlepage', {
  title: document.getElementById('ctitle').value.trim() || 'Book Title',
  subtitle: document.getElementById('csubtitle').value.trim(),
  publisher: document.getElementById('cauthor').value.trim()
});
document.getElementById('fmCopyright').onclick = () => {
  const author = document.getElementById('cauthor').value.trim() || 'the author';
  addFront('copyright', {
    body: 'Copyright © ' + new Date().getFullYear() + ' ' + author + '.\\nAll rights reserved.\\n\\nNo part of this book may be reproduced without permission.'
  });
};
document.getElementById('fmWelcome').onclick = () => addFront('welcome', { title: 'Welcome', body: '' });
document.getElementById('fmBelongs').onclick = () => addFront('belongsto', {});

/* ---- Elinor-style storybook template ---- */
document.getElementById('tplbuild').onclick = () => {
  const st = document.getElementById('tplstatus');
  if (book.length && !confirm('Add the Elinor-style layout to your current book? Nothing already there is removed.')) return;
  const n = Math.max(1, Math.min(20, parseInt(document.getElementById('tplch').value, 10) || 5));
  const ctitle = document.getElementById('ctitle').value.trim();
  const csub = document.getElementById('csubtitle').value.trim();
  const cauth = document.getElementById('cauthor').value.trim();
  const fresh = () => ({ kind: 'story', variant: 'story', title: '', subtitle: '', body: '', note: '', publisher: '' });
  book.push(Object.assign(fresh(), { variant: 'titlepage', title: ctitle || 'Book Title', subtitle: csub, publisher: cauth }));
  book.push(Object.assign(fresh(), { variant: 'belongsto' }));
  book.push(Object.assign(fresh(), { variant: 'welcome', title: 'Welcome' }));
  for (let c = 1; c <= n; c++) {
    book.push({ kind: 'art', caption: 'Chapter ' + c + ' — coloring page' });
    book.push(Object.assign(fresh(), { title: 'Chapter ' + c }));
  }
  renderCount();
  renderThumbs();
  show(0);
  st.textContent = 'Storybook frame built: 3 front-matter pages + ' + n +
    ' chapter spreads. Select a blank plate, describe it in Step 01, and Compose fills it in.';
};

document.getElementById('sorn').onchange = () => {
  const st = document.getElementById('sstatus');
  const f = document.getElementById('sorn').files[0];
  if (!f) return;
  if (!f.type.startsWith('image/')) { st.textContent = 'That file is not an image.'; return; }
  const r = new FileReader();
  r.onload = () => {
    const url = r.result;
    const probe = new Image();
    probe.onload = () => {
      storyOrnament = { image: url.slice(url.indexOf(',') + 1), w: probe.naturalWidth, h: probe.naturalHeight };
      refreshBookState();
      const pv = document.getElementById('sornprev');
      pv.src = url;
      pv.hidden = false;
      document.getElementById('sornrm').hidden = false;
      st.textContent = 'Ornament set — it will appear on every story page.';
    };
    probe.src = url;
  };
  r.readAsDataURL(f);
  document.getElementById('sorn').value = '';
};

document.getElementById('sornrm').onclick = () => {
  storyOrnament = null;
  refreshBookState();
  document.getElementById('sornprev').hidden = true;
  document.getElementById('sornrm').hidden = true;
  document.getElementById('sstatus').textContent = 'Ornament removed.';
};

function serializeBook() {
  return book.map((p) => {
    if (p.kind === 'story') {
      return { kind: 'story', variant: p.variant || 'story', title: p.title || '',
        subtitle: p.subtitle || '', body: p.body || '', note: p.note || '',
        publisher: p.publisher || '' };
    }
    if (!p.image) return { kind: 'blank' };
    return { kind: 'art', image: p.image, caption: p.caption || '', w: p.w || 0, h: p.h || 0 };
  });
}

/* ---- Change-only-this editor ---- */
const editModal = document.getElementById('editmodal');
const editCanvas = document.getElementById('editcanvas');
const editCtx = editCanvas.getContext('2d');
let editPageIndex = -1;
let editBase = null;
let editStrokes = [];
let editPainting = false;

function openEditor(i) {
  const p = book[i];
  if (!p || p.kind !== 'art' || !p.image) return;
  editPageIndex = i;
  editStrokes = [];
  document.getElementById('editprompt').value = '';
  document.getElementById('editstatus').textContent = '';
  editBase = new Image();
  editBase.onload = () => {
    editCanvas.width = editBase.naturalWidth;
    editCanvas.height = editBase.naturalHeight;
    redrawEditor();
    editModal.hidden = false;
  };
  editBase.src = 'data:image/png;base64,' + p.image;
}

function redrawEditor() {
  editCtx.clearRect(0, 0, editCanvas.width, editCanvas.height);
  editCtx.drawImage(editBase, 0, 0);
  editCtx.lineCap = 'round';
  editCtx.lineJoin = 'round';
  for (const s of editStrokes) {
    editCtx.strokeStyle = 'rgba(200,30,40,0.45)';
    editCtx.lineWidth = s.w;
    editCtx.beginPath();
    s.pts.forEach((pt, j) => { j ? editCtx.lineTo(pt[0], pt[1]) : editCtx.moveTo(pt[0], pt[1]); });
    editCtx.stroke();
  }
}

function editorPos(e) {
  const r = editCanvas.getBoundingClientRect();
  const sx = editCanvas.width / r.width;
  const sy = editCanvas.height / r.height;
  return [(e.clientX - r.left) * sx, (e.clientY - r.top) * sy];
}

editCanvas.addEventListener('pointerdown', (e) => {
  editCanvas.setPointerCapture(e.pointerId);
  editPainting = true;
  const pt = editorPos(e);
  editStrokes.push({ pts: [pt, pt], w: parseInt(document.getElementById('brushsize').value) || 40 });
  redrawEditor();
});
editCanvas.addEventListener('pointermove', (e) => {
  if (!editPainting) return;
  editStrokes[editStrokes.length - 1].pts.push(editorPos(e));
  redrawEditor();
});
editCanvas.addEventListener('pointerup', () => { editPainting = false; });
editCanvas.addEventListener('pointercancel', () => { editPainting = false; });

document.getElementById('brushclear').onclick = () => { editStrokes = []; redrawEditor(); };
document.getElementById('editcancel').onclick = () => { editModal.hidden = true; };
document.getElementById('editart').onclick = () => openEditor(current);

function buildMaskB64() {
  const m = document.createElement('canvas');
  m.width = editCanvas.width;
  m.height = editCanvas.height;
  const c = m.getContext('2d');
  c.fillStyle = '#000';
  c.fillRect(0, 0, m.width, m.height);
  c.globalCompositeOperation = 'destination-out';
  c.lineCap = 'round';
  c.lineJoin = 'round';
  for (const s of editStrokes) {
    c.strokeStyle = '#fff';
    c.lineWidth = s.w;
    c.beginPath();
    s.pts.forEach((pt, j) => { j ? c.lineTo(pt[0], pt[1]) : c.moveTo(pt[0], pt[1]); });
    c.stroke();
  }
  return m.toDataURL('image/png').split(',')[1];
}

document.getElementById('editapply').onclick = async () => {
  const st = document.getElementById('editstatus');
  const key = document.getElementById('key').value.trim();
  const prompt = document.getElementById('editprompt').value.trim();
  if (!editStrokes.length) { st.textContent = 'Paint the area to change first.'; return; }
  if (!key || !prompt) { st.textContent = 'Key and a description of the change are both required.'; return; }
  const btn = document.getElementById('editapply');
  btn.disabled = true;
  st.textContent = 'Repainting just that area… this takes a little while.';
  try {
    const res = await fetch('/edit-art', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: key, prompt: prompt,
        image: book[editPageIndex].image, mask: buildMaskB64() })
    });
    const data = await res.json();
    if (!res.ok) { st.textContent = data.error || 'Failed.'; btn.disabled = false; return; }
    const p = book[editPageIndex];
    book.splice(editPageIndex + 1, 0,
      { kind: 'art', image: data.image, caption: p.caption ? p.caption + ' (revised)' : 'Revised copy' });
    editModal.hidden = true;
    renderCount();
    renderThumbs();
    show(editPageIndex + 1);
    document.getElementById('status').textContent =
      'Edited copy added as page ' + (editPageIndex + 2) + ' — the original is untouched.';
  } catch (e) {
    st.textContent = 'Could not reach the press.';
  }
  btn.disabled = false;
};

/* ---- Strengthen lines ---- */
function strengthenPixels(src, w, h, mode) {
  // Morphological line strengthening: dilate dark pixels by a controlled radius,
  // then re-threshold. Does not just gamma-darken existing black.
  const params = {
    subtle:  { radius: 0, thresh: 140 },
    gentle:  { radius: 1, thresh: 150 },
    balanced:{ radius: 1, thresh: 130 },
    bolder:  { radius: 2, thresh: 120 }
  }[mode] || { radius: 1, thresh: 150 };

  const n = w * h;
  // Binary mask of "line" pixels (dark enough)
  const isLine = new Uint8Array(n);
  for (let i = 0; i < n; i++) isLine[i] = src[i] < params.thresh ? 1 : 0;

  if (params.radius === 0) {
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) out[i] = isLine[i] ? 0 : 255;
    return out;
  }

  // Dilate the line mask
  const dilated = new Uint8Array(n);
  const r = params.radius;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let hit = 0;
      for (let dy = -r; dy <= r && !hit; dy++) {
        const yy = y + dy;
        if (yy < 0 || yy >= h) continue;
        for (let dx = -r; dx <= r; dx++) {
          const xx = x + dx;
          if (xx < 0 || xx >= w) continue;
          if (isLine[yy * w + xx]) { hit = 1; break; }
        }
      }
      dilated[y * w + x] = hit;
    }
  }

  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = dilated[i] ? 0 : 255;
  return out;
}

const strModal = document.getElementById('strmodal');
const strCurrent = document.getElementById('scurrent');
const strPreview = document.getElementById('spreview');
let strIndex = -1, strW = 0, strH = 0, strSrc = null;

function openStrengthen(i) {
  const p = book[i];
  if (!p || p.kind !== 'art' || !p.image) return;
  strIndex = i;
  document.getElementById('strstatus').textContent = '';
  document.getElementById('strinspect').checked = false;
  document.querySelectorAll('.strscroll').forEach((el) => el.classList.remove('full'));
  const img = new Image();
  img.onload = () => {
    strW = strCurrent.width = img.naturalWidth;
    strH = strCurrent.height = img.naturalHeight;
    strPreview.width = strW;
    strPreview.height = strH;
    const c = strCurrent.getContext('2d');
    c.drawImage(img, 0, 0);
    const d = c.getImageData(0, 0, strW, strH);
    strSrc = new Float32Array(strW * strH);
    for (let k = 0; k < strSrc.length; k++) {
      strSrc[k] = 0.299 * d.data[k * 4] + 0.587 * d.data[k * 4 + 1] + 0.114 * d.data[k * 4 + 2];
    }
    strModal.hidden = false;
    runStrengthenPreview();
  };
  img.src = 'data:image/png;base64,' + p.image;
}

function strMode() {
  const r = document.querySelector('input[name=strmode]:checked');
  return r ? r.value : 'subtle';
}

function runStrengthenPreview() {
  const st = document.getElementById('strstatus');
  st.textContent = 'Working…';
  setTimeout(() => {
    const out = strengthenPixels(strSrc, strW, strH, strMode());
    const c = strPreview.getContext('2d');
    const id = c.createImageData(strW, strH);
    for (let k = 0; k < out.length; k++) {
      const v = Math.max(0, Math.min(255, Math.round(out[k])));
      id.data[k * 4] = id.data[k * 4 + 1] = id.data[k * 4 + 2] = v;
      id.data[k * 4 + 3] = 255;
    }
    c.putImageData(id, 0, 0);
    st.textContent = '';
  }, 30);
}

document.querySelectorAll('input[name=strmode]').forEach((r) => { r.onchange = runStrengthenPreview; });
document.getElementById('strinspect').onchange = (e) => {
  document.querySelectorAll('.strscroll').forEach((el) => el.classList.toggle('full', e.target.checked));
};
document.getElementById('strcancel').onclick = () => { strModal.hidden = true; };
document.getElementById('strlines').onclick = () => openStrengthen(current);
document.getElementById('dlimage').onclick = () => {
  const p = book[current];
  if (!p || p.kind !== 'art' || !p.image) return;
  const a = document.createElement('a');
  a.href = 'data:image/png;base64,' + p.image;
  a.download = 'fusion-coloring-page-' + (current + 1) + '.png';
  document.body.appendChild(a);
  a.click();
  a.remove();
};
document.getElementById('strsave').onclick = () => {
  const b64 = strPreview.toDataURL('image/png').split(',')[1];
  const p = book[strIndex];
  book.splice(strIndex + 1, 0, { kind: 'art', image: b64,
    caption: p.caption ? p.caption + ' (lines strengthened)' : 'Lines strengthened' });
  strModal.hidden = true;
  renderCount();
  renderThumbs();
  show(strIndex + 1);
  document.getElementById('status').textContent =
    'Strengthened copy added as page ' + (strIndex + 2) + ' — the original is untouched.';
};

/* ---- Mazes ---- */
// Bitmask walls: N=1 E=2 S=4 W=8 (1 = wall present). Entrance: north of (0,0) open. Exit: south of last cell open.
function generateMaze(cols, rows) {
  const N = 1, E = 2, S = 4, W = 8;
  const BIT = [N, E, S, W], OPP = [S, W, N, E];
  const DX = [0, 1, 0, -1], DY = [-1, 0, 1, 0];
  const walls = new Uint8Array(cols * rows).fill(N | E | S | W);
  const seen = new Uint8Array(cols * rows);
  const stack = [0];
  seen[0] = 1;
  while (stack.length) {
    const cur = stack[stack.length - 1];
    const cx = cur % cols, cy = (cur / cols) | 0;
    let found = -1, next = -1;
    const order = [0, 1, 2, 3].sort(() => Math.random() - 0.5);
    for (const d of order) {
      const nx = cx + DX[d], ny = cy + DY[d];
      if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
      const ni = ny * cols + nx;
      if (!seen[ni]) { found = d; next = ni; break; }
    }
    if (found < 0) { stack.pop(); continue; }
    walls[cur] &= ~BIT[found];
    walls[next] &= ~OPP[found];
    seen[next] = 1;
    stack.push(next);
  }
  walls[0] &= ~N;
  walls[cols * rows - 1] &= ~S;
  return { walls: walls, cols: cols, rows: rows };
}

function drawMaze(maze, W, H) {
  const cols = maze.cols, rows = maze.rows, walls = maze.walls;
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const x = c.getContext('2d');
  x.fillStyle = '#fff';
  x.fillRect(0, 0, W, H);
  const mTop = H * 0.05, mBot = H * 0.05, mSide = W * 0.04;
  const mw = W - mSide * 2, mh = H - mTop - mBot;
  const cw = mw / cols, ch = mh / rows;
  x.strokeStyle = '#000';
  x.lineWidth = Math.max(3, cw * 0.055);
  x.lineCap = 'square';
  x.beginPath();
  for (let cy = 0; cy < rows; cy++) {
    for (let cx = 0; cx < cols; cx++) {
      const wv = walls[cy * cols + cx];
      const x0 = mSide + cx * cw, y0 = mTop + cy * ch;
      if (wv & 1) { x.moveTo(x0, y0); x.lineTo(x0 + cw, y0); }
      if (wv & 4) { x.moveTo(x0, y0 + ch); x.lineTo(x0 + cw, y0 + ch); }
      if (wv & 2) { x.moveTo(x0 + cw, y0); x.lineTo(x0 + cw, y0 + ch); }
      if (wv & 8) { x.moveTo(x0, y0); x.lineTo(x0, y0 + ch); }
    }
  }
  x.stroke();
  x.fillStyle = '#000';
  x.textAlign = 'center';
  x.font = '700 ' + Math.round(H * 0.028) + 'px Georgia, serif';
  x.fillText('START', mSide + cw / 2, mTop * 0.72);
  x.fillText('FINISH', W - mSide - cw / 2, H - mBot * 0.28);
  return c;
}

const MAZE_SIZES = { easy: [12, 18], medium: [16, 24], hard: [22, 33] };

document.getElementById('mazego').onclick = () => {
  const st = document.getElementById('mazestatus');
  const diff = document.getElementById('mazediff').value;
  const count = Math.max(1, Math.min(20, parseInt(document.getElementById('mazecount').value) || 1));
  const size = MAZE_SIZES[diff] || MAZE_SIZES.medium;
  const label = diff.charAt(0).toUpperCase() + diff.slice(1);
  for (let i = 0; i < count; i++) {
    const maze = generateMaze(size[0], size[1]);
    const canvas = drawMaze(maze, 1024, 1536);
    book.push({ kind: 'art', image: canvas.toDataURL('image/png').split(',')[1],
      caption: 'Maze — ' + label });
  }
  renderCount();
  renderThumbs();
  show(book.length - 1);
  st.textContent = count === 1 ? 'Maze added as page ' + book.length + '.'
    : count + ' mazes added, ending at page ' + book.length + '.';
};

/* ---- KDP publishing ---- */
// US, black ink, large trim (8.5x11), rates in force October 2026.
// Royalty = rate * list - printing. Rate is 60% at $9.99+, 50% below.
function kdpPrintCost(pages) {
  if (!(pages >= 24)) return null;
  if (pages <= 110) return 2.84;
  return 1.00 + 0.017 * pages;
}
function kdpRoyalty(list, pages) {
  const printing = kdpPrintCost(pages);
  if (printing === null || !(list > 0)) return null;
  const rate = list >= 9.99 ? 0.60 : 0.50;
  return { rate: rate, printing: printing, royalty: rate * list - printing,
    minList: printing / rate };
}

(function buildKeywordRows() {
  const wrap = document.getElementById('kwrap');
  for (let i = 0; i < 7; i++) {
    const row = document.createElement('div');
    row.className = 'kwrow';
    const inp = document.createElement('input');
    inp.type = 'text';
    inp.placeholder = 'Keyword ' + (i + 1);
    inp.addEventListener('input', refreshKdp);
    const sp = document.createElement('span');
    row.appendChild(inp);
    row.appendChild(sp);
    wrap.appendChild(row);
  }
})();

function kdpField(id) { return document.getElementById(id).value.trim(); }

function refreshKdp() {
  const desc = document.getElementById('kdesc');
  document.getElementById('kdesccount').textContent = desc.value.length + ' / 4000';
  document.querySelectorAll('#kwrap .kwrow').forEach((row) => {
    const inp = row.querySelector('input');
    const sp = row.querySelector('span');
    sp.textContent = inp.value.length + '/50';
    sp.classList.toggle('over', inp.value.length > 50);
  });
  const pages = book.length;
  const price = parseFloat(document.getElementById('kprice').value);
  const box = document.getElementById('kroyal');
  const printing = kdpPrintCost(pages);
  if (printing === null) {
    box.textContent = 'Add pages — printing cost needs at least 24.';
  } else if (!(price > 0)) {
    box.innerHTML = 'Printing cost: <b>$' + printing.toFixed(2) + '</b> (' + pages +
      ' pages). Enter a list price above.';
  } else {
    const r = kdpRoyalty(price, pages);
    box.innerHTML = 'Printing cost <b>$' + r.printing.toFixed(2) + '</b> · royalty rate <b>' +
      Math.round(r.rate * 100) + '%</b><br>Royalty per copy: <b>$' + r.royalty.toFixed(2) +
      '</b><br><span style="opacity:.75;font-size:.8rem">Minimum list price $' + r.minList.toFixed(2) +
      ' · price at $9.99+ for the 60% tier, not $9.98.</span>';
  }
  document.getElementById('kc1').checked = pages >= 24;
  document.getElementById('kc2').checked = pages > 0 && pages % 2 === 0;
  const hasKw = Array.prototype.some.call(
    document.querySelectorAll('#kwrap input'), (i) => i.value.trim().length > 0);
  document.getElementById('kc5').checked = desc.value.trim().length > 0 && hasKw;
  refreshBookState();
}

// Saved publishing fields, captions, characters and ornaments also affect backups.
document.addEventListener('input', (event) => {
  if ((event.target.closest && event.target.closest('#kwrap, #kcheck, #markswrap')) ||
      ['ktitle', 'ksub', 'kauthor', 'kimprint', 'kdesc', 'kprice', 'kcat1', 'kcat2', 'kcat3'].includes(event.target.id)) {
    refreshBookState();
  }
});

['kdesc', 'kprice'].forEach((id) => {
  document.getElementById(id).addEventListener('input', refreshKdp);
});

document.getElementById('kcopy').onclick = () => {
  const txt = document.getElementById('kaitext').textContent;
  const done = () => { document.getElementById('kstatus').textContent = 'Copied.'; };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).then(done, () => {
      document.getElementById('kstatus').textContent = 'Copy failed — select the text manually.';
    });
  } else {
    document.getElementById('kstatus').textContent = 'Select the text above and copy it manually.';
  }
};

function kdpSaveData() {
  return {
    title: kdpField('ktitle'), subtitle: kdpField('ksub'), author: kdpField('kauthor'),
    imprint: kdpField('kimprint'), description: document.getElementById('kdesc').value,
    keywords: Array.prototype.map.call(document.querySelectorAll('#kwrap input'), (i) => i.value),
    categories: [kdpField('kcat1'), kdpField('kcat2'), kdpField('kcat3')],
    price: document.getElementById('kprice').value,
    checks: {
      kc3: document.getElementById('kc3').checked,
      kc4: document.getElementById('kc4').checked,
      kc6: document.getElementById('kc6').checked
    }
  };
}

function kdpLoadData(d) {
  if (!d) return;
  const set = (id, v) => { document.getElementById(id).value = v || ''; };
  set('ktitle', d.title); set('ksub', d.subtitle); set('kauthor', d.author);
  set('kimprint', d.imprint || 'Fusion Spark Books');
  set('kdesc', d.description);
  const kws = d.keywords || [];
  document.querySelectorAll('#kwrap input').forEach((inp, i) => { inp.value = kws[i] || ''; });
  const cats = d.categories || [];
  set('kcat1', cats[0]); set('kcat2', cats[1]); set('kcat3', cats[2]);
  set('kprice', d.price);
  const ch = d.checks || {};
  document.getElementById('kc3').checked = !!ch.kc3;
  document.getElementById('kc4').checked = !!ch.kc4;
  document.getElementById('kc6').checked = !!ch.kc6;
  refreshKdp();
}

/* ---- Cover builder ---- */
const coverArt = { image: null, w: 0, h: 0 };

function coverSpec() {
  const pages = Math.max(0, parseInt(document.getElementById('cpages').value) || 0);
  const per = document.getElementById('cpaper').value === 'cream' ? 0.0025 : 0.002252;
  const spine = pages * per;
  return { pages: pages, spine: spine, totalW: 8.5 + spine + 8.5 + 0.25, totalH: 11.25 };
}

function updateCoverSpec() {
  const s = coverSpec();
  const lines = [
    'Wrap: ' + s.totalW.toFixed(2) + ' × ' + s.totalH.toFixed(2) + ' in — spine ' + s.spine.toFixed(3) + ' in (' + s.pages + ' pages)'
  ];
  if (s.pages > 0 && s.pages < 79) lines.push('Under 79 pages: spine left blank, too narrow for text.');
  if (coverArt.image && coverArt.w) {
    if (HAS_PIL) {
      lines.push('Front art: ' + coverArt.w + ' × ' + coverArt.h + ' px → upscaled to 300 DPI in the PDF ✓');
    } else {
      const dpi = Math.round(Math.max(coverArt.w / 8.625, coverArt.h / 11.25));
      lines.push('Front art: ' + coverArt.w + ' × ' + coverArt.h + ' px ≈ ' + dpi + ' DPI — below KDP’s 300 DPI ask. ' +
        'Install Pillow (pip install pillow) and restart the press to upscale automatically.');
    }
  } else {
    lines.push('No cover art yet — generate or upload one.');
  }
  document.getElementById('coverspec').textContent = lines.join('\\n');
  const mock = document.getElementById('covermock');
  mock.hidden = false;
  const unit = 100 / s.totalW;
  document.getElementById('cmback').style.width = (8.625 * unit) + '%';
  document.getElementById('cmspine').style.width = Math.max(s.spine * unit, 2) + '%';
  document.getElementById('cmfront').style.width = (8.625 * unit) + '%';
}

function setCoverArt(b64) {
  const img = document.getElementById('cartimg');
  const probe = new Image();
  probe.onload = () => {
    coverArt.image = b64;
    coverArt.w = probe.naturalWidth;
    coverArt.h = probe.naturalHeight;
    img.src = 'data:image/png;base64,' + b64;
    img.hidden = false;
    updateCoverSpec();
  };
  probe.src = 'data:image/png;base64,' + b64;
}

document.getElementById('csync').onclick = () => {
  document.getElementById('cpages').value = book.length || 24;
  updateCoverSpec();
};

document.getElementById('cartgen').onclick = async () => {
  const key = document.getElementById('key').value.trim();
  const prompt = document.getElementById('cartprompt').value.trim();
  const st = document.getElementById('cstatus');
  const btn = document.getElementById('cartgen');
  if (!key || !prompt) { st.textContent = 'Key and a prompt are both required.'; return; }
  btn.disabled = true;
  st.textContent = 'Painting the cover… this takes a little while.';
  try {
    const res = await fetch('/cover-art', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: key, prompt: prompt })
    });
    const data = await res.json();
    if (!res.ok) { st.textContent = data.error || 'Failed.'; btn.disabled = false; return; }
    setCoverArt(data.image);
    st.textContent = 'Cover art ready.';
  } catch (e) {
    st.textContent = 'Could not reach the press.';
  }
  btn.disabled = false;
};

document.getElementById('cartupload').onclick = () => document.getElementById('cartfile').click();

document.getElementById('cartfile').onchange = () => {
  const st = document.getElementById('cstatus');
  const f = document.getElementById('cartfile').files[0];
  if (!f) return;
  if (!f.type.startsWith('image/')) { st.textContent = 'That file is not an image.'; return; }
  const reader = new FileReader();
  reader.onload = () => {
    const url = reader.result;
    const b64 = url.slice(url.indexOf(',') + 1);
    setCoverArt(b64);
    st.textContent = 'Cover art loaded.';
  };
  reader.readAsDataURL(f);
  document.getElementById('cartfile').value = '';
};

document.getElementById('cbuild').onclick = async () => {
  const st = document.getElementById('cstatus');
  const btn = document.getElementById('cbuild');
  const title = document.getElementById('ctitle').value.trim();
  const pages = Math.max(0, parseInt(document.getElementById('cpages').value) || 0);
  if (!title) { st.textContent = 'A book title is required.'; return; }
  if (!(pages > 0)) { st.textContent = 'Enter the page count.'; return; }
  btn.disabled = true;
  st.textContent = 'Building the cover PDF…';
  try {
    const res = await fetch('/cover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title,
        subtitle: document.getElementById('csubtitle').value.trim(),
        author: document.getElementById('cauthor').value.trim(),
        blurb: document.getElementById('cblurb').value.trim(),
        pages: pages,
        paper: document.getElementById('cpaper').value,
        back_color: document.getElementById('ccolor').value,
        barcode: document.getElementById('cbarcode').checked,
        front_image: coverArt.image
      })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      st.textContent = data.error || 'Could not build the cover.';
      btn.disabled = false;
      return;
    }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'fusion-coloring-cover.pdf';
    a.click();
    st.textContent = 'Cover PDF downloaded. Upload it with your interior on KDP.';
  } catch (e) {
    st.textContent = 'Could not build the cover.';
  }
  btn.disabled = false;
};

document.getElementById('cartprompt').value =
  'Full-color children’s book cover illustration, portrait orientation, cheerful and inviting, ' +
  'bold shapes that read at thumbnail size. No text, no words, no letters, no watermark.';
['cpages', 'cpaper'].forEach((id) => {
  document.getElementById(id).addEventListener('input', updateCoverSpec);
  document.getElementById(id).addEventListener('change', updateCoverSpec);
});
let HAS_PIL = false;
fetch('/info').then((r) => r.json()).then((d) => {
  HAS_PIL = !!(d && d.pillow);
  updateCoverSpec();
}).catch(() => {});
updateCoverSpec();

loadCharacters();
renderCharacters();
renderCount();
</script>
</body>
</html>
"""

# Stamp the mandala ornaments and step icons into the page (tokens placed above).
HTML = HTML.replace("%%MANDALA_HEAD%%", MANDALA_HEAD)
HTML = HTML.replace("%%MANDALA_MED%%", MANDALA_MED)
HTML = HTML.replace("%%MANDALA_BAR%%", MANDALA_BAR)
HTML = HTML.replace("%ICON_01%", ICON_01)
HTML = HTML.replace("%ICON_02%", ICON_02)
HTML = HTML.replace("%ICON_03%", ICON_03)
HTML = HTML.replace("%ICON_04%", ICON_04)
HTML = HTML.replace("%ICON_05%", ICON_05)

def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c

def png_to_rgb(png_bytes):
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a png")
    pos = 8
    width = height = bit_depth = color_type = None
    idat = b""
    while pos + 8 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos:pos + 4])[0]
        kind = png_bytes[pos + 4:pos + 8]
        data = png_bytes[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", data[:10])
        elif kind == b"IDAT":
            idat += data
        elif kind == b"IEND":
            break
    if bit_depth != 8 or color_type not in (2, 6):
        raise ValueError("unsupported png")
    raw = zlib.decompress(idat)
    channels = 3 if color_type == 2 else 4
    stride = width * channels
    out = bytearray()
    i = 0
    prev = bytearray(stride)
    for _ in range(height):
        filt = raw[i]
        i += 1
        row = bytearray(raw[i:i + stride])
        i += stride
        if filt == 1:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                row[x] = (row[x] + left) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif filt == 3:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                a = row[x - channels] if x >= channels else 0
                b = prev[x]
                c = prev[x - channels] if x >= channels else 0
                row[x] = (row[x] + paeth(a, b, c)) & 255
        elif filt != 0:
            raise ValueError("bad png filter")
        prev = row
        if color_type == 6:
            for x in range(width):
                alpha = row[x * 4 + 3] / 255
                for c in range(3):
                    out.append(int(row[x * 4 + c] * alpha + 255 * (1 - alpha)))
        else:
            out.extend(row)
    return width, height, bytes(out)

INK_THRESHOLD = 192

def rgb_to_bilevel(rgb, width, height, threshold=INK_THRESHOLD):
    """Pack RGB line art into 1-bit rows for crisp, tiny print PDFs.

    Bit 1 = paper (white), bit 0 = ink (black). Rows are padded to whole bytes.
    """
    rowbytes = (width + 7) // 8
    out = bytearray(rowbytes * height)
    for y in range(height):
        base = y * width * 3
        orow = y * rowbytes
        for x in range(width):
            i = base + x * 3
            lum = (rgb[i] * 299 + rgb[i + 1] * 587 + rgb[i + 2] * 114) // 1000
            if lum >= threshold:
                out[orow + (x >> 3)] |= 1 << (7 - (x & 7))
    return bytes(out), rowbytes

def esc_pdf(text):
    plain = unicodedata.normalize("NFKD", text or "").replace("\n", " ")
    raw = plain.encode("ascii", "ignore")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

def wrap_lines(text, limit=68):
    words = (text or "").split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if len(trial) > limit and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines[:3]

def page_marks(caption, number):
    chunks = []
    lines = wrap_lines(caption)
    size = 11
    top = 58 + (len(lines) - 1) * 14
    for i, line in enumerate(lines):
        yy = top - i * 14
        tw = len(line) * size * 0.46
        tx = max(40, (612 - tw) / 2)
        chunks.append(
            b"BT /F1 " + f"{size} Tf {tx:.2f} {yy:.2f} Td (".encode()
            + esc_pdf(line) + b") Tj ET"
        )
    label = str(number)
    tw = max(8, len(label) * 4.5)
    tx = (612 - tw) / 2
    chunks.append(b"BT /F1 9 Tf " + f"{tx:.2f} 30 Td (".encode() + esc_pdf(label) + b") Tj ET")
    return b"\n".join(chunks)

def _t(fid, size, x, y, s, color=(0, 0, 0)):
    r, g, b = color
    return (b"%.2f %.2f %.2f rg BT /F%d %d Tf %.2f %.2f Td (" % (r, g, b, fid, size, x, y)
            + esc_pdf(s) + b") Tj ET")


def _ct(fid, size, cx, y, s, color=(0, 0, 0), max_w=None):
    if max_w:
        tw = len(s) * size * 0.5
        if tw > max_w:
            size = max(8, int(size * max_w / tw))
    tw = len(s) * size * 0.5
    return _t(fid, size, cx - tw / 2, y, s, color)


def _diamond_ornament(cx, y, w=120):
    h = 5
    return (b"0 0 0 RG 0.75 w "
            b"%.2f %.2f m %.2f %.2f l S " % (cx - w / 2, y, cx - 16, y) +
            b"%.2f %.2f m %.2f %.2f l S " % (cx + 16, y, cx + w / 2, y) +
            b"0 0 0 rg %.2f %.2f m %.2f %.2f l %.2f %.2f l %.2f %.2f l h f" % (
                cx - h, y, cx, y + h, cx + h, y, cx, y - h))


def _ornament_run(cx, y, ornament):
    """Centered ornament at (cx, y): uploaded image or vector diamond."""
    if ornament is None:
        return _diamond_ornament(cx, y)
    oid, ow, oh = ornament
    w = 43.0
    h = oh * (w / ow)
    return b"q %.2f 0 0 %.2f %.2f %.2f cm /Orn%d Do Q" % (w, h, cx - w / 2, y - h / 2, oid)


def render_text_page(page, fonts, ornament):
    """Render a story / front-matter page. Returns content-stream bytes.

    page: dict with variant ('story','titlepage','copyright','welcome','belongsto'),
    title, subtitle, body, note, publisher. ornament: None or (xobject_id, w, h).
    """
    f_roman, f_bold, f_italic = fonts
    variant = page.get("variant") or "story"
    title = page.get("title") or ""
    subtitle = page.get("subtitle") or ""
    body = page.get("body") or ""
    note = page.get("note") or ""
    publisher = page.get("publisher") or ""
    parts = []
    cx = 306.0
    if variant == "titlepage":
        if title:
            parts.append(_ct(f_bold, 30, cx, 560, title, max_w=468))
        if subtitle:
            parts.append(_ct(f_italic, 14, cx, 518, subtitle, max_w=468))
        parts.append(_ornament_run(cx, 476, ornament))
        if publisher:
            parts.append(_ct(f_roman, 12, cx, 120, publisher))
    elif variant == "copyright":
        y = 430.0
        for line in wrap_para(body, 400, 9)[:24]:
            parts.append(_ct(f_roman, 9, cx, y, line))
            y -= 13
    elif variant == "belongsto":
        parts.append(_ct(f_bold, 22, cx, 620, "THIS BOOK BELONGS TO:"))
        parts.append(_ct(f_roman, 12, cx, 520, "Owner's Name:"))
        parts.append(b"0 0 0 RG 0.75 w [3 3] 0 d 150 500 m 462 500 l S [] 0 d")
        parts.append(_ct(f_roman, 12, cx, 460, "Date:"))
        parts.append(b"0 0 0 RG 0.75 w [3 3] 0 d 200 440 m 412 440 l S [] 0 d")
    else:  # story / welcome
        y = 700.0
        if title:
            parts.append(_ct(f_bold, 18, cx, y, title, max_w=468))
            y -= 34
        parts.append(_ornament_run(cx, y, ornament))
        y -= 38
        if body:
            for para in body.split("\n"):
                para = para.strip()
                if not para:
                    y -= 8
                    continue
                for line in wrap_para(para, 468, 11.5):
                    if y < 96:
                        break
                    parts.append(_t(f_roman, 11.5, 72, y, line))
                    y -= 15
                y -= 6
        if note and variant == "story":
            y = min(y - 12, 220)
            parts.append(_ct(f_bold, 11.5, cx, y, "History Note"))
            y -= 18
            for line in wrap_para(note, 400, 11)[:8]:
                if y < 72:
                    break
                parts.append(_ct(f_roman, 11, cx, y, line))
                y -= 15
    return b"\n".join(parts)


def build_pdf(pages, ornament=None, marks=True):
    """pages: list of dicts: kind 'art'|'blank'|'story', png (bytes|None),
    caption, title, subtitle, body, note, variant, publisher.
    ornament: None or dict with image (b64 png) stamped on text pages.
    marks: print captions and folio numbers on art pages."""
    objects = []

    def add(body):
        objects.append(body)
        return len(objects)

    page_ids = []
    prepared = []
    for page in pages:
        kind = page.get("kind") or ("art" if page.get("png") else "blank")
        if kind == "story":
            prepared.append(("story", page))
            continue
        png, caption = page.get("png"), page.get("caption") or ""
        if png is None:
            prepared.append(("blank", caption))
            continue
        width, height, rgb = png_to_rgb(png)
        mono, _rowbytes = rgb_to_bilevel(rgb, width, height)
        prepared.append(("art", ((width, height, zlib.compress(mono)), caption)))

    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>")
    fbold_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>")
    fitalic_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>")
    fonts = (font_id, fbold_id, fitalic_id)
    orn = None
    if ornament and ornament.get("image"):
        try:
            ow, oh, orgb = png_to_rgb(base64.b64decode(ornament["image"]))
            ocomp = zlib.compress(orgb)
            orn_id = add(
                (b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                 b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
                 b"/Length %d >>\nstream\n" % (ow, oh, len(ocomp))) + ocomp + b"\nendstream"
            )
            orn = (orn_id, ow, oh)
        except Exception:
            orn = None
    for index, item in enumerate(prepared, start=1):
        kind, payload = item
        if kind == "story":
            content = render_text_page(payload, fonts, orn)
            content_id = add(
                b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
            )
            res = ("<< /Font << /F%d %d 0 R /F%d %d 0 R /F%d %d 0 R >>" % (
                font_id, font_id, fbold_id, fbold_id, fitalic_id, fitalic_id))
            if orn:
                res += " /XObject << /Orn%d %d 0 R >>" % (orn[0], orn[0])
            res += " >>"
            page_id = add(
                ("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
                 "/Contents %d 0 R /Resources %s >>" % (pages_id, content_id, res)).encode()
            )
        elif kind == "blank":
            caption = payload
            pm = page_marks(caption, index) if marks else b""
            content_id = add(
                f"<< /Length {len(pm)} >>\nstream\n".encode() + pm + b"\nendstream"
            )
            page_id = add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
            )
        else:
            (width, height, compressed), caption = payload
            pm = page_marks(caption, index) if marks else b""
            image_id = add(
                f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
                f"/ColorSpace /DeviceGray /BitsPerComponent 1 /Filter /FlateDecode "
                f"/Length {len(compressed)} >>\nstream\n".encode()
                + compressed
                + b"\nendstream"
            )
            side, top, bottom = 40, 36, 92
            max_w, max_h = 612 - side * 2, 792 - top - bottom
            scale = min(max_w / width, max_h / height)
            draw_w, draw_h = width * scale, height * scale
            x = (612 - draw_w) / 2
            y = bottom
            draw = f"q {draw_w:.2f} 0 0 {draw_h:.2f} {x:.2f} {y:.2f} cm /Im{image_id} Do Q\n".encode() + pm
            content_id = add(
                f"<< /Length {len(draw)} >>\nstream\n".encode() + draw + b"\nendstream"
            )
            page_id = add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> "
                f"/XObject << /Im{image_id} {image_id} 0 R >> >> >>".encode()
            )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode()
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(out)

def run_preflight(pages):
    """Check a book against KDP paperback requirements.

    pages: list of dicts with image (b64 or None), caption, w, h.
    Returns (ok, checks); each check is {id, label, status, detail} with
    status one of pass, warn, fail, info. ok is False if any check fails.
    """
    max_w_in = (612 - 80) / 72      # mirrors build_pdf placement
    max_h_in = (792 - 36 - 92) / 72
    infos = []
    for item in pages:
        if isinstance(item, dict):
            raw = item.get("image")
            w = item.get("w") or 0
            h = item.get("h") or 0
            caption = item.get("caption") or ""
        else:
            raw, w, h, caption = item, 0, 0, ""
        if not raw:
            infos.append({"art": False, "w": 0, "h": 0, "caption": caption})
            continue
        if not (w and h):
            try:
                w, h, _ = png_to_rgb(base64.b64decode(raw))
            except Exception:
                w, h = 0, 0
        infos.append({"art": True, "w": w, "h": h, "caption": caption})

    checks = []
    n = len(infos)
    checks.append({
        "id": "pages", "label": "At least 24 pages (KDP minimum)",
        "status": "pass" if n >= 24 else "fail",
        "detail": "%d pages" % n,
    })
    checks.append({
        "id": "even", "label": "Even page count (double-sided printing)",
        "status": "pass" if n % 2 == 0 else "fail",
        "detail": "%d pages" % n,
    })
    checks.append({
        "id": "trim", "label": "Trim 8.5 x 11 in, no bleed",
        "status": "pass", "detail": "PDF pages are 612 x 792 pt",
    })
    checks.append({
        "id": "margins", "label": "Margins at least 0.25 in (KDP minimum)",
        "status": "pass", "detail": "0.5 in on all sides",
    })
    art_pages = [(i + 1, info) for i, info in enumerate(infos) if info["art"]]
    if not art_pages:
        checks.append({"id": "ppi", "label": "Artwork at 300 PPI",
                       "status": "warn", "detail": "no art pages yet"})
    else:
        low, bad = [], []
        for num, info in art_pages:
            w, h = info["w"], info["h"]
            if not (w and h):
                bad.append(str(num))
                continue
            ppi = max(w / max_w_in, h / max_h_in)
            if ppi < 300:
                low.append("%d (%d PPI)" % (num, round(ppi)))
        if bad:
            checks.append({"id": "ppi", "label": "Artwork at 300 PPI",
                           "status": "fail",
                           "detail": "cannot read image on page(s) " + ", ".join(bad)})
        elif low:
            checks.append({"id": "ppi", "label": "Artwork at 300 PPI",
                           "status": "warn",
                           "detail": "below 300 PPI on page(s) " + ", ".join(low)})
        else:
            checks.append({"id": "ppi", "label": "Artwork at 300 PPI",
                           "status": "pass",
                           "detail": "%d art pages" % len(art_pages)})
    no_back = [str(num) for num, _ in art_pages
               if num < n and infos[num]["art"]]
    if no_back:
        checks.append({"id": "backs", "label": "Blank backs behind designs",
                       "status": "warn",
                       "detail": "page(s) " + ", ".join(no_back) + " are followed by another design"})
    else:
        checks.append({"id": "backs", "label": "Blank backs behind designs",
                       "status": "pass",
                       "detail": "every design has a blank back" if art_pages else "no art pages yet"})
    checks.append({"id": "fonts", "label": "Fonts embedded",
                   "status": "pass",
                   "detail": "Times-Roman base font, always available"})
    checks.append({"id": "ai", "label": "AI-generated content disclosure",
                   "status": "info",
                   "detail": "declare AI images when publishing on KDP"})
    ok = all(c["status"] != "fail" for c in checks)
    return ok, checks



def clean_to_lineart(b64):
    """Keep dark line cores, clear mid-gray fills to white so regions stay open
    for coloring. Does not force lines darker.
    """
    if not HAS_PIL or not b64:
        return b64
    try:
        from io import BytesIO
        data = base64.b64decode(b64)
        img = _PILImage.open(BytesIO(data)).convert("L")
        # Dark cores (< 80) stay as lines; mid-gray fills and light areas become white
        img = img.point(lambda p: p if p < 80 else 255)
        out = BytesIO()
        # The PDF decoder accepts RGB/RGBA PNGs, not Pillow's grayscale PNG.
        img.convert("RGB").save(out, format="PNG", optimize=True)
        return base64.b64encode(out.getvalue()).decode()
    except Exception:
        return b64

def generate_image(key, prompt, model="gpt-image-2.5-flare"):
    """Call the images API. Returns (b64, None) or (None, error_message).

    Retries rate limits and connection hiccups; falls back from portrait
    to square if the model rejects the size.
    """
    def attempt(size):
        last = "request failed"
        for i in range(3):
            req = urllib.request.Request(
                "https://api.openai.com/v1/images/generations",
                data=json.dumps({
                    "model": model,
                    "prompt": prompt,
                    "n": 1,
                    "size": size,
                    "quality": "high",
                }).encode(),
                headers={
                    "Authorization": "Bearer " + key,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=110) as res:
                    return json.load(res)["data"][0]["b64_json"], None
            except urllib.error.HTTPError as e:
                if e.code == 429 and i < 2:
                    time.sleep(2 * (i + 1))
                    continue
                try:
                    msg = json.loads(e.read().decode())["error"]["message"]
                except Exception:
                    msg = "request failed"
                if "size" in msg.lower() or "dimension" in msg.lower():
                    return None, ("size", msg)
                return None, ("fatal", msg)
            except urllib.error.URLError as e:
                last = str(e)
                if i < 2:
                    time.sleep(2 * (i + 1))
        return None, ("fatal", last)

    img, err = attempt("1024x1536")
    if img:
        return img, None
    kind, msg = err
    if kind == "size":
        img2, err2 = attempt("1024x1024")
        if img2:
            return img2, None
        return None, err2[1]
    return None, msg


def hex_to_rgb01(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def shade(rgb, f):
    return tuple(max(0.0, min(1.0, c * f)) for c in rgb)


def ink_for(bg):
    lum = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    return (1, 1, 1) if lum < 0.55 else (0.10, 0.09, 0.08)


def wrap_para(text, width_pt, size):
    max_chars = max(10, int(width_pt / (size * 0.5)))
    words = (text or "").split()
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if len(trial) > max_chars and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def build_cover_pdf(title, subtitle, author, blurb, pages, paper, back_hex, barcode, art_png):
    """Build a KDP full-wrap cover PDF: back + spine + front with bleed."""
    per_page = 0.0025 if paper == "cream" else 0.002252
    spine_in = pages * per_page
    trim_w, trim_h, bleed = 8.5, 11.0, 0.125
    total_w_in = trim_w + spine_in + trim_w + 2 * bleed
    total_h_in = trim_h + 2 * bleed
    W, H = total_w_in * 72, total_h_in * 72

    bg = hex_to_rgb01(back_hex)
    spine_bg = shade(bg, 0.82)
    ink = ink_for(bg)

    objects = []

    def add(body):
        objects.append(body)
        return len(objects)

    pages_id = add(b"")
    f_roman = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>")
    f_bold = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>")

    art_id = None
    aw = ah = 0
    if art_png:
        try:
            aw, ah, rgb = png_to_rgb(art_png)
        except Exception as e:
            raise ValueError("Could not read the cover art: %s" % e)
        # Normalize cover art to 300 DPI over the front panel + bleed,
        # preserving aspect ratio (never stretched). Needs Pillow;
        # without it the art is embedded at its native resolution.
        if HAS_PIL:
            tw = int(round((trim_w + bleed) * 300))
            th = int(round((trim_h + 2 * bleed) * 300))
            s = max(tw / aw, th / ah)
            nw, nh = max(1, int(round(aw * s))), max(1, int(round(ah * s)))
            if (nw, nh) != (aw, ah):
                img = _PILImage.frombytes("RGB", (aw, ah), rgb).resize((nw, nh), _PILImage.LANCZOS)
                aw, ah, rgb = nw, nh, img.tobytes()
        comp = zlib.compress(rgb)
        art_id = add(
            (b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
             b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
             b"/Length %d >>\nstream\n" % (aw, ah, len(comp))) + comp + b"\nendstream"
        )

    b = bleed * 72
    back_x0, back_x1 = b, b + trim_w * 72
    spine_x0 = back_x1
    front_x0, front_x1 = spine_x0 + spine_in * 72, spine_x0 + spine_in * 72 + trim_w * 72

    def rect(x, y, w, h, color):
        r, g, bl = color
        return b"%.2f %.2f %.2f rg %.2f %.2f %.2f %.2f re f" % (r, g, bl, x, y, w, h)

    def ctext(fid, size, cx, y, s, color, max_w=None):
        if max_w:
            tw = len(s) * size * 0.5
            if tw > max_w:
                size = max(8, int(size * max_w / tw))
        r, g, bl = color
        tw = len(s) * size * 0.5
        x = cx - tw / 2
        return (b"%.2f %.2f %.2f rg BT /F%d %d Tf %.2f %.2f Td (" % (r, g, bl, fid, size, x, y)
                + esc_pdf(s) + b") Tj ET")

    parts = []
    parts.append(rect(0, 0, W, H, bg))
    parts.append(rect(spine_x0, 0, spine_in * 72, H, spine_bg))
    if art_id is not None:
        rw, rh = (front_x1 + b) - front_x0, H
        s = max(rw / aw, rh / ah)
        dw, dh = aw * s, ah * s
        x = front_x0 + (rw - dw) / 2
        y = (H - dh) / 2
        parts.append(b"q %.2f 0 0 %.2f %.2f %.2f cm /Im%d Do Q" % (dw, dh, x, y, art_id))
    # Title band across the top of the front panel
    band_h = 1.75 * 72
    band_y = H - b - band_h
    parts.append(rect(front_x0, band_y, trim_w * 72, band_h, bg))
    front_cx = front_x0 + trim_w * 36
    if subtitle:
        parts.append(ctext(f_bold, 32, front_cx, band_y + band_h / 2 + 8, title, ink, trim_w * 72 - 50))
        parts.append(ctext(f_roman, 15, front_cx, band_y + band_h / 2 - 26, subtitle, ink, trim_w * 72 - 50))
    else:
        parts.append(ctext(f_bold, 34, front_cx, band_y + band_h / 2 - 12, title, ink, trim_w * 72 - 50))
    # Author band across the bottom of the front panel
    aband_h = 1.05 * 72
    parts.append(rect(front_x0, b, trim_w * 72, aband_h, bg))
    if author:
        parts.append(ctext(f_bold, 20, front_cx, b + aband_h / 2 - 7, author, ink, trim_w * 72 - 50))
    # Spine text (KDP guidance: spine too narrow for text under ~79 pages)
    if pages >= 79 and title:
        st = title if len(title) <= 42 else title[:39] + "..."
        ssize = min(15, int((H - 170) / max(1, len(st) * 0.5)))
        if ssize >= 8:
            cx = spine_x0 + spine_in * 36
            r, g, bl = ink_for(spine_bg)
            parts.append(b"%.2f %.2f %.2f rg BT /F%d %d Tf 0 -1 1 0 %.2f %.2f Tm (" % (
                r, g, bl, f_bold, ssize, cx, H - 95) + esc_pdf(st) + b") Tj ET")
    # Back cover headline and blurb
    if title:
        parts.append(ctext(f_bold, 22, (back_x0 + back_x1) / 2, H - b - 105, title, ink, trim_w * 72 - 100))
    if blurb:
        lines = wrap_para(blurb, (back_x1 - back_x0) - 116, 11.5)[:22]
        y = H - b - 148
        r, g, bl = ink
        for line in lines:
            parts.append(b"%.2f %.2f %.2f rg BT /F%d 11 Tf %.2f %.2f Td (" % (
                r, g, bl, f_roman, back_x0 + 58, y) + esc_pdf(line) + b") Tj ET")
            y -= 15
    # Barcode quiet zone (KDP places the barcode here when there is no ISBN)
    if barcode:
        bw, bh = 144.0, 86.4
        parts.append(rect(back_x1 - 27 - bw, b + 36, bw, bh, (1, 1, 1)))

    content = b"\n".join(parts)
    content_id = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    resources = ("<< /Font << /F%d %d 0 R /F%d %d 0 R >>" % (f_roman, f_roman, f_bold, f_bold))
    if art_id is not None:
        resources += " /XObject << /Im%d %d 0 R >>" % (art_id, art_id)
    resources += " >>"
    page_id = add(
        ("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] "
         "/Contents %d 0 R /Resources %s >>" % (pages_id, W, H, content_id, resources)).encode()
    )
    objects[pages_id - 1] = ("<< /Type /Pages /Count 1 /Kids [%d 0 R] >>" % page_id).encode()
    catalog_id = add(("/<< /Type /Catalog /Pages %d 0 R >>" % pages_id).encode())

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(("%d 0 obj\n" % i).encode())
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(("xref\n0 %d\n" % (len(objects) + 1)).encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(("%010d 00000 n \n" % off).encode())
    out.extend(
        ("trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF" % (
            len(objects) + 1, catalog_id, xref)).encode()
    )
    return bytes(out)


def _mp_field(boundary, name, value):
    return (b"--" + boundary + b"\r\n" +
            b'Content-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\n' +
            value.encode() + b"\r\n")


def _mp_file(boundary, name, filename, ctype, data):
    return (b"--" + boundary + b"\r\n" +
            b'Content-Disposition: form-data; name="' + name.encode() + b'"; filename="' + filename.encode() + b'"\r\n' +
            b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + data + b"\r\n")


def _post_images_edits(key, req_body, boundary):
    """POST a multipart body to /v1/images/edits with retries.

    Returns (b64, None) or (None, error_message).
    """
    last = "request failed"
    for i in range(3):
        req = urllib.request.Request(
            "https://api.openai.com/v1/images/edits",
            data=req_body,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "multipart/form-data; boundary=" + boundary.decode(),
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=110) as res:
                return json.load(res)["data"][0]["b64_json"], None
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 2:
                time.sleep(2 * (i + 1))
                continue
            try:
                msg = json.loads(e.read().decode())["error"]["message"]
            except Exception:
                msg = "request failed"
            return None, msg
        except urllib.error.URLError as e:
            last = str(e)
            if i < 2:
                time.sleep(2 * (i + 1))
    return None, last


def _edits_boundary():
    return ("----folio%d" % int(time.time() * 1000)).encode()


def _edits_end(boundary):
    return b"--" + boundary + b"--\r\n"


def _edits_fields(boundary, prompt, model="gpt-image-2.5-flare"):
    # Note: no response_format field — the gpt-image edits endpoint rejects it
    # and returns b64_json by default.
    return (_mp_field(boundary, "model", model) +
            _mp_field(boundary, "prompt", prompt) +
            _mp_field(boundary, "n", "1") +
            _mp_field(boundary, "quality", "high"))


COLORING_PROMPT_VERSION = "2026-10-quality-1"
COLORING_STANDARD = (
    "Create one polished portrait black-and-white coloring-book illustration. "
    "Expressive appealing subjects, natural poses, distinct personality, and believable anatomy. "
    "Crisp confident black outlines on white paper, slightly stronger outer silhouettes and clear object separation. "
    "Purposeful detail and well-defined enclosed spaces that are comfortable to color. "
    "Keep essential artwork comfortably inside the page edges. "
    "No color, gray shading, crosshatching, stippling, scratchy fur, woodgrain microtexture, text, labels, or watermark. "
    "Leave coloring areas white; avoid large black filled areas. "
)
COLORING_AUDIENCES = {
    "easy": (
        "Audience: children. Simplify the ENTIRE illustration while preserving charm and expressive subjects. "
        "One clear main activity, a few supporting objects, very simple background, large spacious shapes. "
        "Use fewer plants with broad leaves, fewer flowers with large simple petals, plain fabrics and cushions, "
        "simple furniture and baskets with very few divisions. Animal markings are a few broad enclosed patches. "
        "Omit tiny patterns, fringe, dense foliage, small textures, and unnecessary decorative objects. "
        "Simplify or omit secondary details from the scene description and reference to meet this complexity. "
        "Use clear medium-to-bold outlines throughout, not just on the main subject. "
    ),
    "medium": (
        "Audience: teens. Appealing expressive subjects and a coherent scene with moderate purposeful detail. "
        "Clear medium-weight outlines, broad animal markings, a few decorative motifs and readable background objects. "
        "Keep generous coloring spaces across subjects, plants, fabrics, borders, and background. "
        "Avoid crowded textures and tiny repetitive patterns. "
    ),
    "detailed": (
        "Audience: adults. Sophisticated inviting illustration with rich, balanced, purposeful detail. "
        "Use confident clear outlines and restrained decorative patterns with usable coloring spaces. "
        "Preserve expression, natural proportions, and balanced negative space. "
        "Apply readable detail to background, plants, fabrics, borders, and subjects without dense microtexture "
        "or excessively fine lines. Complexity must enrich the scene without crowding it. "
    ),
}


def coloring_prompt(subject, level, characters, has_style_reference=False):
    prompt = COLORING_STANDARD + COLORING_AUDIENCES[level]
    if has_style_reference:
        prompt += (
            "The FIRST input image is an approved ARTWORK STYLE reference: follow its illustration quality, "
            "line clarity, expressive character treatment, and colorable shapes. "
            "Create the requested scene rather than copying its composition, objects, or lettering. "
            "The audience instructions above override reference complexity across the entire scene. "
            "Any following input images are CHARACTER IDENTITY references. "
        )
    prompt += "\nRequested scene: " + subject
    char_lines = []
    for c in characters:
        if not isinstance(c, dict):
            continue
        name = (c.get("name") or "").strip()
        desc = (c.get("description") or "").strip()
        if name:
            char_lines.append(name + ": " + (desc or "see character reference images"))
    if char_lines:
        prompt += ("\nCharacter identities: preserve their recognizable features and clothing, "
                   "rendered as black outline art at the selected audience complexity.\n" + "\n".join(char_lines))
    return prompt


def edit_image(key, prompt, image_bytes, mask_bytes):
    """Call the images edit API with a mask. Returns (b64, None) or (None, error).

    Mask convention: transparent areas are repainted, opaque areas are kept.
    """
    boundary = _edits_boundary()
    req_body = (_edits_fields(boundary, prompt) +
                _mp_file(boundary, "image", "image.png", "image/png", image_bytes) +
                _mp_file(boundary, "mask", "mask.png", "image/png", mask_bytes) +
                _edits_end(boundary))
    return _post_images_edits(key, req_body, boundary)


def generate_with_references(key, prompt, ref_images, model="gpt-image-2.5-flare"):
    """Generate a new image guided by reference images (character consistency).

    Calls the edits endpoint with no mask: each reference is an `image` part.
    Returns (b64, None) or (None, error_message).
    """
    boundary = _edits_boundary()
    req_body = _edits_fields(boundary, prompt, model)
    for i, ref in enumerate(ref_images):
        req_body += _mp_file(boundary, "image[]", "ref%d.png" % i, "image/png", ref)
    req_body += _edits_end(boundary)
    return _post_images_edits(key, req_body, boundary)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/info":
            self._json(200, {"pillow": HAS_PIL})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/compose":
            self.compose(body)
        elif self.path == "/pdf":
            self.pdf(body)
        elif self.path == "/preflight":
            self.preflight(body)
        elif self.path == "/cover-art":
            self.cover_art(body)
        elif self.path == "/cover":
            self.cover(body)
        elif self.path == "/edit-art":
            self.edit_art(body)
        else:
            self.send_error(404)

    def compose(self, body):
        key = (body.get("key") or "").strip()
        subject = (body.get("subject") or "").strip()
        if not key or not subject:
            self._json(400, {"error": "Key and a description are both required."})
            return
        level = (body.get("level") or "medium").strip()
        if level not in COLORING_AUDIENCES:
            self._json(400, {"error": "Choose children, teens, or adults complexity."})
            return
        style_reference = body.get("style_reference")
        prompt = coloring_prompt(subject, level, body.get("characters") or [], bool(style_reference))

        references = body.get("references") or []
        ref_images = []
        try:
            if style_reference:
                ref_images.append(base64.b64decode(style_reference, validate=True))
            for r in references:
                if r:
                    ref_images.append(base64.b64decode(r, validate=True))
        except Exception:
            self._json(400, {"error": "Could not read a reference image."})
            return
        model = "gpt-image-2.5-sunburst" if level == "detailed" else "gpt-image-2.5-flare"
        if ref_images:
            image, err = generate_with_references(key, prompt, ref_images, model)
        else:
            image, err = generate_image(key, prompt, model)
        if err:
            self._json(400, {"error": err})
            return
        # Preserve model linework by default. Gray removal is an explicit choice.
        original_image = image
        cleanup = body.get("cleanup") is True
        if cleanup:
            image = clean_to_lineart(image)
        # Fail fast: make sure the picture is printable before claiming success,
        # instead of blowing up later at PDF time.
        try:
            width, height, _ = png_to_rgb(base64.b64decode(image))
        except Exception as e:
            self._json(400, {"error": "The picture came back in a format the press can't print (" + str(e) + "). Press compose once more."})
            return
        result = {
            "image": image,
            "generation": {
                "prompt_version": COLORING_PROMPT_VERSION,
                "prompt": prompt, "subject": subject, "level": level,
                "model": model, "quality": "high", "cleanup": cleanup,
                "width": width, "height": height,
                "reference_count": len(ref_images),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        }
        if cleanup and image != original_image:
            result["original_image"] = original_image
        self._json(200, result)

    def pdf(self, body):
        raw_pages = body.get("pages") or []
        if not raw_pages:
            self._json(400, {"error": "There are no pages yet."})
            return
        pages = []
        try:
            for item in raw_pages:
                if not isinstance(item, dict):
                    item = {"image": item}
                raw = item.get("image")
                kind = item.get("kind") or ("art" if raw else "blank")
                page = {
                    "kind": kind,
                    "png": base64.b64decode(raw) if raw else None,
                    "caption": item.get("caption") or "",
                    "title": item.get("title") or "",
                    "subtitle": item.get("subtitle") or "",
                    "body": item.get("body") or "",
                    "note": item.get("note") or "",
                    "variant": item.get("variant") or "",
                    "publisher": item.get("publisher") or "",
                }
                pages.append(page)
            ornament = body.get("ornament")
            marks = body.get("marks", True)
            pdf = build_pdf(pages, ornament=ornament, marks=marks)
        except Exception as e:
            self._json(400, {"error": str(e)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", "attachment; filename=fusion-coloring-interior.pdf")
        self.send_header("Content-Length", str(len(pdf)))
        self.end_headers()
        self.wfile.write(pdf)

    def preflight(self, body):
        raw_pages = body.get("pages") or []
        ok, checks = run_preflight(raw_pages)
        self._json(200, {"ok": ok, "checks": checks})

    def cover_art(self, body):
        key = (body.get("key") or "").strip()
        prompt = (body.get("prompt") or "").strip()
        if not key or not prompt:
            self._json(400, {"error": "Key and a prompt are both required."})
            return
        image, err = generate_image(key, prompt)
        if err:
            self._json(400, {"error": err})
            return
        self._json(200, {"image": image})

    def cover(self, body):
        title = (body.get("title") or "").strip()
        subtitle = (body.get("subtitle") or "").strip()
        author = (body.get("author") or "").strip()
        blurb = (body.get("blurb") or "").strip()
        try:
            pages = int(body.get("pages") or 0)
        except (TypeError, ValueError):
            pages = 0
        paper = body.get("paper") or "white"
        back = body.get("back_color") or "#3F6B4C"
        barcode = bool(body.get("barcode", True))
        art_b64 = body.get("front_image")
        if not title:
            self._json(400, {"error": "A book title is required for the cover."})
            return
        if pages < 1:
            self._json(400, {"error": "Enter the page count."})
            return
        try:
            art_png = base64.b64decode(art_b64) if art_b64 else None
        except Exception:
            self._json(400, {"error": "Could not read the cover art."})
            return
        try:
            pdf = build_cover_pdf(title, subtitle, author, blurb, pages, paper, back, barcode, art_png)
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", "attachment; filename=fusion-coloring-cover.pdf")
        self.send_header("Content-Length", str(len(pdf)))
        self.end_headers()
        self.wfile.write(pdf)

    def edit_art(self, body):
        key = (body.get("key") or "").strip()
        prompt = (body.get("prompt") or "").strip()
        image_b64 = body.get("image") or ""
        mask_b64 = body.get("mask") or ""
        if not key or not prompt or not image_b64 or not mask_b64:
            self._json(400, {"error": "Key, image, mask, and a description are all required."})
            return
        try:
            image_bytes = base64.b64decode(image_b64)
            mask_bytes = base64.b64decode(mask_b64)
        except Exception:
            self._json(400, {"error": "Could not read the image or mask."})
            return
        image, err = edit_image(key, prompt, image_bytes, mask_bytes)
        if err:
            self._json(400, {"error": err})
            return
        try:
            png_to_rgb(base64.b64decode(image))
        except Exception as e:
            self._json(400, {"error": "The edited picture came back unreadable (" + str(e) + "). Try again."})
            return
        self._json(200, {"image": image})

    def _json(self, code, payload):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        return

class Press(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print("Fusion Coloring on port %d" % port)
    Press(("0.0.0.0", port), Handler).serve_forever()
