/* MyNextCert PBQ engine v1 (our own code, not a third-party library).
   Loaded by the practice-exam code only when a question bank holds one of the new PBQ types, so every other page and
   exam never downloads it. The service worker saves it the first time it is used, like the qbank files.

   Four types (all data is plain strings and numbers, nothing is run from data):
     logsel   pick the bad lines in a log, then a diagnosis
     rules    build a firewall rule set: add only what is needed, in the right order
     term     a small terminal that only understands a few commands; scored by what the commands DID
     diagram  place devices in the right spots of a network diagram

   Every type works by tap, by keyboard and (where it makes sense) by drag. Scoring is per part, each part has a "why".
   A part may carry its own "d" (domain) and "obj" (objective); if it has none it uses the question's. */
(function () {
  "use strict";
  if (window.PBQX && window.PBQX.v === 1) return;

  var KINDS = ["logsel", "rules", "term", "diagram"];
  var MAX_CMDS = 30, MAX_CMD_LEN = 120;

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function str(x, max) { return typeof x === "string" && x.trim().length > 0 && x.length <= max; }
  function int(x, lo, hi) { return typeof x === "number" && x === Math.floor(x) && x >= lo && x <= hi; }
  function shuf(n) { var a = [], i, j, t; for (i = 0; i < n; i++) a.push(i); for (i = n - 1; i > 0; i--) { j = Math.floor(Math.random() * (i + 1)); t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
  function isPerm(a, n) { if (!Array.isArray(a) || a.length !== n) return false; var s = {}, i; for (i = 0; i < n; i++) { if (!int(a[i], 0, n - 1) || s[a[i]]) return false; s[a[i]] = 1; } return true; }
  function short(t) { t = String(t); return t.length > 72 ? t.slice(0, 70) + "…" : t; }

  /* ---------- validation of the question data (also used by the page when it loads a bank) ---------- */
  function partOk(q, x, ds) {   /* optional per-part domain / objective */
    if (x.d !== undefined && !(typeof x.d === "string" && ds && ds[x.d])) return false;
    if (x.obj !== undefined) {
      var dom = x.d || q.d;
      if (!(typeof x.obj === "string" && /^\d+\.\d+$/.test(x.obj) && x.obj.split(".")[0] + ".0" === dom)) return false;
    }
    return true;
  }
  function allParts(q, list, ds) { return Array.isArray(list) && list.every(function (x) { return x && typeof x === "object" && str(x.why, 700) && partOk(q, x, ds); }); }
  function tplOk(t) { return typeof t === "string" && t.length > 0 && t.length <= MAX_CMD_LEN && (t.match(/\{ip\}/g) || []).length <= 1 && !/[{}]/.test(t.replace("{ip}", "")); }

  function facts1(x) { return typeof x === "string" ? str(x, 60) : Array.isArray(x) && x.length >= 1 && x.length <= 6 && x.every(function (f) { return str(f, 60); }); }
  function valid(q, ds) {
    try {
      if (!q || q.t !== "pbq" || KINDS.indexOf(q.kind) < 0 || !str(q.title, 200) || !str(q.scenario, 900)) return false;
      if (q.ticket !== undefined && !str(q.ticket, 700)) return false;
      var k = q.kind, i;
      if (k === "logsel") {
        if (!Array.isArray(q.lines) || q.lines.length < 3 || q.lines.length > 30) return false;
        if (!q.lines.every(function (l) { return str(l.text, 320) && (l.bad === 0 || l.bad === 1); }) || !allParts(q, q.lines, ds)) return false;
        if (!q.lines.some(function (l) { return l.bad; }) || !q.lines.some(function (l) { return !l.bad; })) return false;
        if (q.ask !== undefined) {
          var a = q.ask;
          if (!a || !str(a.label, 200) || !Array.isArray(a.opts) || a.opts.length < 2 || a.opts.length > 6 || !a.opts.every(function (o) { return str(o, 160); }) || !int(a.a, 0, a.opts.length - 1) || !allParts(q, [a], ds)) return false;
        }
        return true;
      }
      if (k === "rules") {
        if (!Array.isArray(q.rules) || q.rules.length < 3 || q.rules.length > 14) return false;
        var ids = {};
        if (!q.rules.every(function (r) { var good = r && /^[a-z0-9]{1,6}$/.test(r.id) && !ids[r.id] && str(r.text, 200) && (r.need === 0 || r.need === 1); if (good) ids[r.id] = r; return good; }) || !allParts(q, q.rules, ds)) return false;
        if (q.rules.filter(function (r) { return r.need; }).length < 2 || q.rules.every(function (r) { return r.need; })) return false;
        if (q.before !== undefined) {
          if (!Array.isArray(q.before) || !allParts(q, q.before, ds)) return false;
          if (!q.before.every(function (b) { return ids[b.a] && ids[b.b] && ids[b.a].need && ids[b.b].need && b.a !== b.b; })) return false;
        }
        if (q.last !== undefined && !(q.last && ids[q.last.id] && ids[q.last.id].need && allParts(q, [q.last], ds))) return false;
        return true;
      }
      if (k === "term") {
        if (!Array.isArray(q.cmds) || q.cmds.length < 2 || q.cmds.length > 40) return false;
        if (!q.cmds.every(function (c) { return c && Array.isArray(c.run) && c.run.length >= 1 && c.run.length <= 16 && c.run.every(tplOk) && typeof c.out === "string" && c.out.length <= 1500 && fxList(c).every(function (f) { return str(f, 60); }) && (c.alt === undefined || (c.alt && str(c.alt.if, 60) && typeof c.alt.out === "string" && c.alt.out.length <= 1500)); })) return false;
        if (q.host !== undefined && !/^[a-z0-9-]{1,20}$/.test(q.host)) return false;
        if (q.suggest !== undefined && !(Array.isArray(q.suggest) && q.suggest.length <= 8 && q.suggest.every(function (s) { return str(s, MAX_CMD_LEN); }))) return false;
        if (!Array.isArray(q.checks) || q.checks.length < 2 || q.checks.length > 8) return false;
        return q.checks.every(function (c) {
          if (!c || !str(c.t, 200) || !str(c.why, 700) || !partOk(q, c, ds)) return false;
          var n = (c.has !== undefined ? 1 : 0) + (c.lacks !== undefined ? 1 : 0) + (c.after !== undefined ? 1 : 0);
          if (n !== 1) return false;
          if (c.after !== undefined) return facts1(c.after) && facts1(c.of);
          return facts1(c.has !== undefined ? c.has : c.lacks);
        });
      }
      if (k === "diagram") {
        if (!Array.isArray(q.slots) || q.slots.length < 2 || q.slots.length > 8 || !Array.isArray(q.devs) || q.devs.length <= q.slots.length || q.devs.length > 12) return false;
        if (q.top !== undefined && !str(q.top, 40)) return false;
        if (!q.slots.every(function (s) { return s && str(s.label, 60) && str(s.zone, 40) && (s.hint === undefined || str(s.hint, 80)); })) return false;
        var seen = {}, used = {};
        if (!q.devs.every(function (d) {
          var good = d && /^[a-z0-9]{1,6}$/.test(d.id) && !seen[d.id] && str(d.name, 40) && int(d.slot, -1, q.slots.length - 1) && str(d.why, 700) && partOk(q, d, ds);
          if (good) { seen[d.id] = 1; if (d.slot >= 0) { if (used[d.slot]) return false; used[d.slot] = 1; } }
          return good;
        })) return false;
        return Object.keys(used).length === q.slots.length && q.devs.some(function (d) { return d.slot < 0; });
      }
      return false;
    } catch (e) { return false; }
  }

  /* ---------- what a run item stores ---------- */
  function newItem(q) {
    if (q.kind === "logsel") return { ro: [], pick: { m: q.lines.map(function () { return 0; }), s: -1, t: 0 } };
    if (q.kind === "rules") return { ro: shuf(q.rules.length), pick: { set: [] } };
    if (q.kind === "term") return { ro: [], pick: { h: [] } };
    return { ro: shuf(q.devs.length), pick: { pl: q.slots.map(function () { return ""; }) } };
  }
  function ok(q, it) {   /* is a saved item well-formed for this question? (resume checks this; bad data is dropped) */
    try {
      var p = it.pick, k = q.kind, i;
      if (!p || typeof p !== "object" || !Array.isArray(it.ro)) return false;
      if (k === "logsel") return it.ro.length === 0 && Array.isArray(p.m) && p.m.length === q.lines.length && p.m.every(function (v) { return v === 0 || v === 1; }) && int(p.s, -1, q.ask ? q.ask.opts.length - 1 : -1) && (p.t === 0 || p.t === 1);
      if (k === "rules") {
        var ids = q.rules.map(function (r) { return r.id; });
        return isPerm(it.ro, q.rules.length) && Array.isArray(p.set) && p.set.length <= ids.length && p.set.every(function (id, n) { return ids.indexOf(id) >= 0 && p.set.indexOf(id) === n; });
      }
      if (k === "term") return it.ro.length === 0 && Array.isArray(p.h) && p.h.length <= MAX_CMDS && p.h.every(function (s) { return typeof s === "string" && s.length <= MAX_CMD_LEN; });
      if (k === "diagram") {
        var dv = q.devs.map(function (d) { return d.id; });
        return isPerm(it.ro, q.devs.length) && Array.isArray(p.pl) && p.pl.length === q.slots.length && p.pl.every(function (id, n) { return id === "" || (dv.indexOf(id) >= 0 && p.pl.indexOf(id) === n); });
      }
    } catch (e) { }
    return false;
  }
  function answered(q, it) {   /* 0 nothing yet, 1 started, 2 has an answer */
    var p = it.pick, k = q.kind;
    if (k === "logsel") return q.ask ? (p.s >= 0 ? 2 : p.t ? 1 : 0) : (p.t ? 2 : 0);
    if (k === "rules") return p.set.length ? 2 : 0;
    if (k === "term") return p.h.length ? 2 : 0;
    var n = p.pl.filter(function (x) { return x !== ""; }).length;
    return n === 0 ? 0 : n === p.pl.length ? 2 : 1;
  }

  /* ---------- the terminal: a few commands, scored by what they did ---------- */
  function fxList(c) { return c.fx === undefined ? [] : Array.isArray(c.fx) ? c.fx : [c.fx]; }
  function norm(s) { return String(s).toLowerCase().replace(/["']/g, "").replace(/\s+/g, " ").trim().replace(/^sudo /, ""); }
  var RE = {};
  function tplRe(t) {
    if (RE[t]) return RE[t];
    var parts = norm(t).split("{ip}").map(function (x) { return x.replace(/[.*+?^$()|[\]\\{}]/g, "\\$&"); });
    return (RE[t] = new RegExp("^" + parts.join("((?:\\d{1,3}\\.){3}\\d{1,3})") + "$"));
  }
  function ipOk(s) { return s.split(".").every(function (o) { return +o <= 255; }); }
  function match(q, input) {
    var n = norm(input), i, j, m;
    for (i = 0; i < q.cmds.length; i++) for (j = 0; j < q.cmds[i].run.length; j++) {
      m = tplRe(q.cmds[i].run[j]).exec(n);
      if (m && (!m[1] || ipOk(m[1]))) return { c: q.cmds[i], ip: m[1] || "" };
    }
    return null;
  }
  function helpText(q) { return "Commands in this lab:\n  help\n" + q.cmds.map(function (c) { return "  " + c.run[0].replace("{ip}", "<ip>"); }).join("\n"); }
  function sim(q, h) {   /* replay the history: the screen lines and the ordered facts ("what the commands did") */
    var lines = [], facts = [];
    h.forEach(function (s) {
      var m = match(q, s), out, bad = false;
      if (norm(s) === "help") out = helpText(q);
      else if (m) {
        var blocked = facts.filter(function (f) { return f.indexOf("block:") === 0; }).map(function (f) { return f.slice(6); });
        out = (m.c.alt && facts.indexOf(m.c.alt.if) >= 0 ? m.c.alt.out : m.c.out).replace("{blocked}", blocked.map(function (ip) { return "Anywhere     DENY    " + ip; }).join("\n"));
        fxList(m.c).forEach(function (f) { facts.push(f.replace("{ip}", m.ip)); });
      } else { out = "Not available in this lab. Type help to see the commands."; bad = true; }
      lines.push({ cmd: s, out: out, bad: bad });
    });
    return { lines: lines, facts: facts };
  }
  function list(x) { return Array.isArray(x) ? x : [x]; }
  function anyIn(facts, x) { return list(x).some(function (f) { return facts.indexOf(f) >= 0; }); }
  function checkTerm(c, facts, h) {   /* a fact may be one string or a list (any of them counts) */
    if (c.has !== undefined) return anyIn(facts, c.has);
    if (c.lacks !== undefined) return h.length > 0 && !anyIn(facts, c.lacks);   /* doing nothing never earns a "didn't do X" part */
    var last = -1; list(c.of).forEach(function (f) { last = Math.max(last, facts.lastIndexOf(f)); });
    return last >= 0 && anyIn(facts.slice(last + 1), c.after);
  }

  /* ---------- scoring: a list of parts, each right or wrong, each with its why ---------- */
  function parts(q, it) {
    var p = it.pick, out = [], k = q.kind, blank = answered(q, it) === 0;
    /* a question you never touched earns nothing (otherwise "leave the decoys out" would score for doing nothing) */
    function add(x, o) { o.d = x.d || q.d; o.obj = x.obj || q.obj; o.why = x.why; if (blank) { o.ok = false; o.you = "not answered"; } out.push(o); }
    if (k === "logsel") {
      q.lines.forEach(function (l, i) {
        var m = !!p.m[i];
        add(l, { ok: m === !!l.bad, t: "Line " + (i + 1) + ": " + short(l.text), ans: l.bad ? "bad line" : "normal", you: m ? "marked as bad" : "left alone" });
      });
      if (q.ask) add(q.ask, { ok: p.s === q.ask.a, t: q.ask.label, ans: q.ask.opts[q.ask.a], you: p.s >= 0 ? q.ask.opts[p.s] : "not answered" });
    } else if (k === "rules") {
      var set = p.set;
      q.rules.forEach(function (r) {
        var at = set.indexOf(r.id);
        add(r, { ok: !!r.need === (at >= 0), t: (r.need ? "Needed: " : "Not needed: ") + r.text, ans: r.need ? "add it" : "leave it out", you: at >= 0 ? "added at " + (at + 1) : "left out" });
      });
      (q.before || []).forEach(function (b) {
        var i = set.indexOf(b.a), j = set.indexOf(b.b);
        add(b, { ok: i >= 0 && j >= 0 && i < j, t: "Order: “" + short(rule(q, b.a).text) + "” above “" + short(rule(q, b.b).text) + "”", ans: "first one higher", you: i < 0 || j < 0 ? "not both added" : i < j ? "right order" : "wrong order" });
      });
      if (q.last) add(q.last, { ok: set.length > 0 && set[set.length - 1] === q.last.id, t: "Last rule: " + short(rule(q, q.last.id).text), ans: "at the very bottom", you: set.indexOf(q.last.id) < 0 ? "not added" : set[set.length - 1] === q.last.id ? "at the bottom" : "not at the bottom" });
    } else if (k === "term") {
      var s = sim(q, p.h);
      q.checks.forEach(function (c) {
        var good = checkTerm(c, s.facts, p.h);
        add(c, { ok: good, t: c.t, ans: "done", you: good ? "done" : p.h.length ? "not done" : "no commands run" });
      });
    } else {
      var by = {}; q.devs.forEach(function (d) { by[d.id] = d; });
      q.slots.forEach(function (sl, i) {
        var want = q.devs.filter(function (d) { return d.slot === i; })[0], got = p.pl[i] ? by[p.pl[i]] : null;
        add(want, { ok: !!got && got.id === want.id, t: sl.label + " (" + sl.zone + ")", ans: want.name, you: got ? got.name : "empty" });
      });
      q.devs.forEach(function (d) {
        if (d.slot >= 0) return;
        var used = p.pl.indexOf(d.id) >= 0;
        add(d, { ok: !used, t: "Not needed: " + d.name, ans: "leave it out", you: used ? "placed it" : "left out" });
      });
    }
    return out;
  }
  function rule(q, id) { return q.rules.filter(function (r) { return r.id === id; })[0]; }
  function score(q, it) { var ps = parts(q, it), n = 0; ps.forEach(function (x) { if (x.ok) n++; }); return ps.length ? n / ps.length : 0; }

  /* the answer review shown after the whole exam is submitted (never during the exam) */
  function review(q, it) {
    var h = "<ul class=\"mx-pbr\">" + parts(q, it).map(function (x) {
      return "<li class=\"" + (x.ok ? "ok" : "no") + "\"><b>" + esc(x.t) + "</b><span>Answer: " + esc(x.ans) + (x.ok ? "" : " &middot; <em>You: " + esc(x.you) + "</em>") + "</span><span>" + esc(x.why) + "</span></li>";
    }).join("");
    if (q.kind === "term") h += "<li><b>Your commands</b>" + (it.pick.h.length ? "<pre>" + esc(it.pick.h.map(function (s) { return "$ " + s; }).join("\n")) + "</pre>" : "<span>none</span>") + "</li>";
    return h + "</ul>";
  }

  /* ---------- screens ---------- */
  var CSS = ".px{display:grid;gap:14px}.px h3.px-h{margin:0 0 8px;font:600 11px var(--f-ui);letter-spacing:.12em;text-transform:uppercase;color:var(--v-muted)}" +
    ".px-ticket{padding:12px 14px;border-left:3px solid var(--v-accent);background:color-mix(in srgb,var(--v-accent) 8%,transparent);border-radius:0 8px 8px 0}.px-ticket p{margin:0;font:400 13.5px/1.55 var(--f-ui)}.px-ticket .lab{margin-bottom:4px}" +
    ".px-hint{margin:0;font:400 12.5px/1.5 var(--f-ui);color:var(--v-muted)}.px-hint kbd{font:500 11px var(--f-mono);border:1px solid var(--v-line);border-radius:4px;padding:1px 5px}" +
    ".px-logs{list-style:none;margin:0;padding:0;border:1px solid var(--v-line);border-radius:10px;overflow:hidden}.px-logs li+li{border-top:1px solid var(--v-line)}" +
    ".px-ln{display:grid;grid-template-columns:44px minmax(0,1fr);width:100%;min-height:48px;text-align:left;background:none;border:0;padding:0;color:inherit;font:inherit}" +
    ".px-ln .ck{display:grid;place-items:center;border-right:1px solid var(--v-line);font:700 16px var(--f-mono);color:transparent}.px-ln .tx{padding:9px 12px;font:400 12px/1.55 var(--f-mono);overflow-wrap:anywhere}.px-ln .tx em{font-style:normal;color:var(--v-muted)}" +
    ".px-ln[aria-checked=true]{background:color-mix(in srgb,var(--v-accent) 14%,transparent)}.px-ln[aria-checked=true] .ck{color:var(--v-accent)}" +
    ".px-pick{display:grid;gap:6px}.px-pick select{min-height:44px;width:100%;border:1px solid var(--v-line);border-radius:8px;background:transparent;color:inherit;padding:0 10px;font:inherit}.px-pick select option{color:#111}" +
    ".px-cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}.px-lst{list-style:none;margin:0;padding:8px;display:grid;gap:8px;min-height:60px;align-content:start;border:1px dashed var(--v-line);border-radius:10px}" +
    ".px-rc{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 10px;align-items:center;border:1px solid var(--v-line);border-radius:10px;padding:8px 10px;background:color-mix(in srgb,var(--v-fg) 4%,transparent)}.px-rc code{grid-column:2;font:500 12px/1.4 var(--f-mono);overflow-wrap:anywhere}" +
    ".px-rc .n{grid-column:1;grid-row:1;font:700 12px var(--f-mono);color:var(--v-accent)}.px-rc .ctl{grid-column:1/-1;display:flex;gap:6px;flex-wrap:wrap}.px-rc.drag{opacity:.6;outline:2px dashed var(--v-accent)}" +
    ".px-sm{min-height:44px;min-width:44px;padding:0 12px;border:1px solid var(--v-line);border-radius:8px;background:none;color:inherit;font:600 12px var(--f-ui);cursor:pointer}.px-sm:disabled{opacity:.4;cursor:default}.px-grip{cursor:grab;touch-action:none}" +
    ".px-empty{margin:0;padding:6px;color:var(--v-muted);font:400 12px var(--f-ui)}" +
    ".px-term{border:1px solid var(--v-line);border-radius:10px;background:#0a0d11;color:#d6dbe2;overflow:hidden}.px-scr{height:240px;overflow:auto;padding:12px;font:400 12px/1.55 var(--f-mono);white-space:pre-wrap;overflow-wrap:anywhere}.px-scr .c{color:#9ad1ff}.px-scr .e{color:#ff9d8f}" +
    ".px-term form{display:flex;border-top:1px solid #1d2530}.px-term form:focus-within{box-shadow:inset 0 0 0 2px var(--v-accent)}.px-ps{display:grid;place-items:center;padding-left:12px;font:500 12px var(--f-mono);color:#7be0a2;white-space:nowrap}" +
    ".px-term input{flex:1;min-width:0;min-height:44px;background:none;border:0;outline:none;padding:0 8px;font:400 13px var(--f-mono);color:#fff}.px-term form button{min-height:44px;padding:0 16px;border:0;border-left:1px solid #1d2530;background:none;color:#d6dbe2;font:600 12px var(--f-ui);cursor:pointer}" +
    ".px-chips{display:flex;flex-wrap:wrap;gap:6px}.px-chip{min-height:44px;padding:0 12px;border:1px solid var(--v-line);border-radius:8px;background:none;color:inherit;font:500 11.5px var(--f-mono);text-align:left;overflow-wrap:anywhere;cursor:pointer}" +
    ".px-dg{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.px-zone{border:1px dashed var(--v-line);border-radius:12px;padding:8px;display:grid;gap:8px;align-content:start}.px-zone .lab{text-align:center}" +
    ".px-top{display:grid;place-items:center;min-height:64px;border:1px solid var(--v-line);border-radius:10px;font:600 12px var(--f-ui);background:color-mix(in srgb,var(--v-fg) 5%,transparent)}" +
    ".px-slot{min-height:64px;width:100%;border:1px solid var(--v-line);border-radius:10px;background:color-mix(in srgb,var(--v-fg) 4%,transparent);color:var(--v-muted);padding:6px;display:grid;place-items:center;text-align:center;font:500 11.5px/1.35 var(--f-ui);cursor:pointer}" +
    ".px-slot.full{color:var(--v-fg);border-style:solid;font-weight:600}.px-slot.hot{border-color:var(--v-accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--v-accent) 35%,transparent)}" +
    ".px-tray{display:flex;flex-wrap:wrap;gap:8px;border:1px dashed var(--v-line);border-radius:10px;padding:8px;min-height:60px}" +
    ".px-dev{min-height:44px;padding:0 14px;border:1px solid var(--v-line);border-radius:999px;background:color-mix(in srgb,var(--v-fg) 4%,transparent);color:inherit;font:600 12.5px var(--f-ui);touch-action:none;cursor:pointer}" +
    ".px-dev[aria-pressed=true]{border-color:var(--v-accent);background:color-mix(in srgb,var(--v-accent) 16%,transparent)}.px-dev.ghost{position:fixed;z-index:200;pointer-events:none;opacity:.9;box-shadow:0 8px 24px rgba(0,0,0,.35)}" +
    ".px :focus-visible{outline:2px solid var(--v-accent);outline-offset:2px}" +
    "@media (max-width:640px){.px-cols{grid-template-columns:1fr}.px-dg{grid-template-columns:1fr}}" +
    "@media (prefers-reduced-motion:no-preference){.px-slot,.px-rc,.px-dev,.px-ln{transition:background .2s,border-color .2s,box-shadow .2s}}";
  function addCss() {
    if (document.getElementById("pbqx-css")) return;
    var s = document.createElement("style"); s.id = "pbqx-css"; s.textContent = CSS; document.head.appendChild(s);
  }

  function ticketHtml(q) { return q.ticket ? "<div class=\"px-ticket\"><p class=\"lab\">Ticket</p><p>" + esc(q.ticket) + "</p></div>" : ""; }
  function kb(t) { return "<kbd>" + t + "</kbd>"; }

  function renderLogsel(q, it, host, env) {
    var p = it.pick;
    host.innerHTML = ticketHtml(q) + "<p class=\"px-hint\">Tap a line, or press " + kb("Tab") + " then " + kb("Space") + ", to mark it as part of the attack. " + kb("↑") + " " + kb("↓") + " move between lines.</p>" +
      "<ul class=\"px-logs\" role=\"group\" aria-label=\"Log lines\">" + q.lines.map(function (l, i) {
        return "<li><button type=\"button\" class=\"px-ln\" role=\"checkbox\" aria-checked=\"" + !!p.m[i] + "\" data-i=\"" + i + "\"><span class=\"ck\" aria-hidden=\"true\">✓</span><span class=\"tx\"><em>" + (i < 9 ? "0" : "") + (i + 1) + "</em> " + esc(l.text) + "</span></button></li>";
      }).join("") + "</ul>" +
      (q.ask ? "<div class=\"px-pick\"><label class=\"lab\" for=\"px-ask\">" + esc(q.ask.label) + "</label><select id=\"px-ask\"><option value=\"-1\">Choose one…</option>" + q.ask.opts.map(function (o, i) { return "<option value=\"" + i + "\"" + (p.s === i ? " selected" : "") + ">" + esc(o) + "</option>"; }).join("") + "</select></div>" : "");
    host.addEventListener("click", function (e) {
      var b = e.target.closest(".px-ln"); if (!b) return;
      var i = +b.dataset.i; p.m[i] = p.m[i] ? 0 : 1; p.t = 1; b.setAttribute("aria-checked", String(!!p.m[i]));
      env.say("Line " + (i + 1) + (p.m[i] ? " marked." : " unmarked.")); env.save();
    });
    host.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      var bs = [].slice.call(host.querySelectorAll(".px-ln")), k = bs.indexOf(document.activeElement);
      if (k < 0) return; e.preventDefault(); (bs[k + (e.key === "ArrowDown" ? 1 : -1)] || bs[k]).focus();
    });
    host.addEventListener("change", function (e) { if (e.target.id === "px-ask") { p.s = +e.target.value; p.t = 1; env.save(); } });
  }

  function renderRules(q, it, host, env) {
    var p = it.pick;
    host.innerHTML = ticketHtml(q) + "<p class=\"px-hint\">Add only the rules you need, then put them in order. The rule set runs top to bottom and the first match wins. Use the buttons, or drag the ⠿ handle.</p>" +
      "<div class=\"px-cols\"><div><h3 class=\"px-h\">Available rules</h3><ul class=\"px-lst\" id=\"px-av\"></ul></div><div><h3 class=\"px-h\">Your rule set (first → last)</h3><ul class=\"px-lst\" id=\"px-set\"></ul></div></div>";
    var av = host.querySelector("#px-av"), setEl = host.querySelector("#px-set");
    function draw(focus) {
      av.innerHTML = ""; setEl.innerHTML = "";
      var any = false;
      it.ro.forEach(function (ri) {
        var r = q.rules[ri]; if (p.set.indexOf(r.id) >= 0) return; any = true;
        av.insertAdjacentHTML("beforeend", "<li class=\"px-rc\"><code>" + esc(r.text) + "</code><div class=\"ctl\"><button type=\"button\" class=\"px-sm\" data-add=\"" + r.id + "\" aria-label=\"Add rule: " + esc(r.text) + "\">Add →</button></div></li>");
      });
      if (!any) av.innerHTML = "<li class=\"px-empty\">All rules added.</li>";
      p.set.forEach(function (id, i) {
        var r = rule(q, id);
        setEl.insertAdjacentHTML("beforeend", "<li class=\"px-rc\" data-id=\"" + id + "\"><span class=\"n\">" + (i + 1) + "</span><code>" + esc(r.text) + "</code><div class=\"ctl\"><button type=\"button\" class=\"px-sm px-grip\" data-grip=\"" + id + "\" aria-label=\"Drag handle, rule " + (i + 1) + "\">⠿</button><button type=\"button\" class=\"px-sm\" data-up=\"" + id + "\" aria-label=\"Move rule " + (i + 1) + " up\"" + (i ? "" : " disabled") + ">Up</button><button type=\"button\" class=\"px-sm\" data-dn=\"" + id + "\" aria-label=\"Move rule " + (i + 1) + " down\"" + (i < p.set.length - 1 ? "" : " disabled") + ">Down</button><button type=\"button\" class=\"px-sm\" data-rm=\"" + id + "\" aria-label=\"Remove rule " + (i + 1) + "\">Remove</button></div></li>");
      });
      if (!p.set.length) setEl.innerHTML = "<li class=\"px-empty\">Empty. Add rules from the left.</li>";
      if (focus) { var f = host.querySelector("[data-" + focus[0] + "=\"" + focus[1] + "\"]"); if (!f || f.disabled) f = host.querySelector("#px-set button:not(:disabled)") || host.querySelector("#px-av button"); if (f) f.focus(); }
    }
    function move(id, d) { var i = p.set.indexOf(id), j = i + d; if (j < 0 || j >= p.set.length) return; p.set.splice(i, 1); p.set.splice(j, 0, id); }
    host.addEventListener("click", function (e) {
      var b = e.target.closest("button"), d = b && b.dataset; if (!d) return;
      if (d.add) { p.set.push(d.add); draw(["rm", d.add]); env.say("Added at position " + p.set.length + "."); }
      else if (d.rm) { p.set.splice(p.set.indexOf(d.rm), 1); draw(["add", d.rm]); env.say("Removed."); }
      else if (d.up) { move(d.up, -1); draw(["up", d.up]); env.say("Moved up to position " + (p.set.indexOf(d.up) + 1) + "."); }
      else if (d.dn) { move(d.dn, 1); draw(["dn", d.dn]); env.say("Moved down to position " + (p.set.indexOf(d.dn) + 1) + "."); }
      else return;
      env.save();
    });
    /* drag the handle to reorder (mouse, touch, pen). The Up / Down buttons do the same job. */
    host.addEventListener("pointerdown", function (e) {
      var g = e.target.closest("[data-grip]"); if (!g) return;
      e.preventDefault();
      var li = g.closest(".px-rc"), id = g.dataset.grip; li.classList.add("drag");
      try { g.setPointerCapture(e.pointerId); } catch (x) { }
      function mid(el) { var r = el.getBoundingClientRect(); return r.top + r.height / 2; }
      function mv(ev) {   /* swap the NEIGHBOURS around the dragged card, so the card itself never leaves the page (a touch drag would be lost) */
        var guard = 20, pv, nx;
        while (guard-- > 0) {
          pv = li.previousElementSibling; nx = li.nextElementSibling;
          if (pv && ev.clientY < mid(pv)) setEl.insertBefore(pv, li.nextSibling);
          else if (nx && ev.clientY > mid(nx)) setEl.insertBefore(nx, li);
          else break;
        }
      }
      function up() {
        document.removeEventListener("pointermove", mv); document.removeEventListener("pointerup", up); document.removeEventListener("pointercancel", up);
        p.set = [].slice.call(setEl.querySelectorAll(".px-rc")).map(function (x) { return x.dataset.id; });
        draw(["grip", id]); env.say("Moved to position " + (p.set.indexOf(id) + 1) + "."); env.save();
      }
      /* listen on the document: moving the card in the list would drop a pointer capture on the handle */
      document.addEventListener("pointermove", mv); document.addEventListener("pointerup", up); document.addEventListener("pointercancel", up);
    });
    draw();
  }

  function renderTerm(q, it, host, env) {
    var p = it.pick, hi = -1, user = q.host || "host";
    host.innerHTML = ticketHtml(q) + "<p class=\"px-hint\">Only a few commands work in this lab. Type one and press " + kb("Enter") + ", or tap a suggestion. " + kb("↑") + " recalls the last command. Type " + kb("help") + " to see them all. Up to " + MAX_CMDS + " commands.</p>" +
      "<div class=\"px-term\"><div class=\"px-scr\" role=\"log\" aria-live=\"polite\" tabindex=\"0\" aria-label=\"Terminal output\"></div><form autocomplete=\"off\"><span class=\"px-ps\">" + esc(user) + "$</span><input type=\"text\" aria-label=\"Command\" maxlength=\"" + MAX_CMD_LEN + "\" spellcheck=\"false\" autocapitalize=\"none\" autocomplete=\"off\"><button type=\"submit\">Run</button></form></div>" +
      (q.suggest && q.suggest.length ? "<div class=\"px-chips\" role=\"group\" aria-label=\"Command suggestions\">" + q.suggest.map(function (s) { return "<button type=\"button\" class=\"px-chip\" data-c=\"" + esc(s) + "\">" + esc(s) + "</button>"; }).join("") + "</div>" : "");
    var scr = host.querySelector(".px-scr"), inp = host.querySelector("input");
    function line(t, cls) { var d = document.createElement("div"); if (cls) d.className = cls; d.textContent = t; scr.appendChild(d); scr.scrollTop = scr.scrollHeight; }
    if (q.intro) line(q.intro); else line(user + " · type help");
    sim(q, p.h).lines.forEach(function (l) { line(user + "$ " + l.cmd, "c"); line(l.out, l.bad ? "e" : ""); });
    host.querySelector("form").addEventListener("submit", function (e) {
      e.preventDefault();
      var s = inp.value.replace(/\s+/g, " ").trim(); if (!s) return;
      if (p.h.length >= MAX_CMDS) { line("Command limit reached (" + MAX_CMDS + "). Move on when you are ready.", "e"); inp.value = ""; return; }
      p.h.push(s); var l = sim(q, p.h).lines.pop();
      line(user + "$ " + s, "c"); line(l.out, l.bad ? "e" : ""); inp.value = ""; hi = -1; env.save();
    });
    inp.addEventListener("keydown", function (e) {
      if (e.key === "ArrowUp" && p.h.length) { e.preventDefault(); hi = hi < 0 ? p.h.length - 1 : Math.max(0, hi - 1); inp.value = p.h[hi]; }
      else if (e.key === "ArrowDown" && hi >= 0) { e.preventDefault(); hi++; if (hi >= p.h.length) { hi = -1; inp.value = ""; } else inp.value = p.h[hi]; }
    });
    host.addEventListener("click", function (e) { var c = e.target.closest(".px-chip"); if (c) { inp.value = c.dataset.c; inp.focus(); } });
  }

  function renderDiagram(q, it, host, env) {
    var p = it.pick, sel = "", zones = [], dragged = false;
    q.slots.forEach(function (s) { if (zones.indexOf(s.zone) < 0) zones.push(s.zone); });
    host.innerHTML = ticketHtml(q) + "<p class=\"px-hint\">Tap a device, then tap an empty spot. Or drag it there. With a keyboard: " + kb("Enter") + " on a device, " + kb("Tab") + " to a spot, " + kb("Enter") + " again. Tap a placed device to take it back. Some devices are not needed.</p>" +
      "<div class=\"px-dg\">" + (q.top ? "<div class=\"px-top\">" + esc(q.top) + "</div>" : "") + zones.map(function (z) {
        return "<div class=\"px-zone\"><p class=\"lab\">" + esc(z) + "</p>" + q.slots.map(function (s, i) { return s.zone === z ? "<button type=\"button\" class=\"px-slot\" data-s=\"" + i + "\"></button>" : ""; }).join("") + "</div>";
      }).join("") + "</div><div><h3 class=\"px-h\">Device tray</h3><div class=\"px-tray\" role=\"group\" aria-label=\"Devices\"></div></div>";
    var tray = host.querySelector(".px-tray");
    function dev(id) { return q.devs.filter(function (d) { return d.id === id; })[0]; }
    function draw() {
      tray.innerHTML = "";
      it.ro.forEach(function (di) {
        var d = q.devs[di]; if (p.pl.indexOf(d.id) >= 0) return;
        tray.insertAdjacentHTML("beforeend", "<button type=\"button\" class=\"px-dev\" data-d=\"" + d.id + "\" aria-pressed=\"" + (sel === d.id) + "\">" + esc(d.name) + "</button>");
      });
      if (!tray.children.length) tray.innerHTML = "<p class=\"px-empty\">All devices placed. Tap one in the diagram to take it back.</p>";
      [].slice.call(host.querySelectorAll(".px-slot")).forEach(function (b) {
        var i = +b.dataset.s, s = q.slots[i], id = p.pl[i], d = id ? dev(id) : null;
        b.classList.toggle("full", !!d); b.classList.toggle("hot", !!sel && !d);
        b.innerHTML = d ? esc(d.name) + "<span style=\"font-weight:400;color:var(--v-muted)\">tap to remove</span>" : esc(s.label) + (s.hint ? "<span>" + esc(s.hint) + "</span>" : "");
        b.setAttribute("aria-label", s.label + ", " + s.zone + ": " + (d ? d.name + " placed. Activate to take it back." : sel ? "empty. Activate to place " + dev(sel).name + "." : "empty. Pick a device first."));
      });
    }
    function put(i, id) { p.pl[i] = id; sel = ""; draw(); env.save(); }
    host.addEventListener("click", function (e) {
      var d = e.target.closest(".px-dev");
      if (d && !d.classList.contains("ghost")) {
        if (dragged) return;
        sel = sel === d.dataset.d ? "" : d.dataset.d; draw();
        var again = host.querySelector(".px-dev[data-d=\"" + d.dataset.d + "\"]"); if (again) again.focus();
        env.say(sel ? dev(sel).name + " selected. Now choose a spot." : "Selection cleared."); return;
      }
      var s = e.target.closest(".px-slot"); if (!s) return;
      var i = +s.dataset.s;
      if (p.pl[i]) { var n = dev(p.pl[i]).name; put(i, ""); env.say(n + " returned to the tray."); }
      else if (sel) { var m = dev(sel).name; put(i, sel); env.say(m + " placed."); }
      else env.say("Pick a device from the tray first.");
    });
    /* drag a device from the tray onto a spot (mouse, touch, pen); tap and keyboard above do the same job */
    host.addEventListener("pointerdown", function (e) {
      var b = e.target.closest(".px-dev"); if (!b) return;
      var sx = e.clientX, sy = e.clientY, g = null, id = b.dataset.d;
      function slotAt(ev) { var el = document.elementFromPoint(ev.clientX, ev.clientY); return el && el.closest ? el.closest(".px-slot") : null; }
      function mv(ev) {
        if (!g && Math.hypot(ev.clientX - sx, ev.clientY - sy) > 8) { g = b.cloneNode(true); g.classList.add("ghost"); document.body.appendChild(g); b.style.opacity = ".4"; }
        if (g) { g.style.left = ev.clientX - 30 + "px"; g.style.top = ev.clientY - 22 + "px"; var s = slotAt(ev); [].slice.call(host.querySelectorAll(".px-slot")).forEach(function (x) { x.classList.toggle("hot", x === s && !p.pl[+x.dataset.s]); }); }
      }
      function up(ev) {
        document.removeEventListener("pointermove", mv); document.removeEventListener("pointerup", up); document.removeEventListener("pointercancel", up);
        if (!g) return;
        var s = slotAt(ev); g.remove(); b.style.opacity = ""; dragged = true; setTimeout(function () { dragged = false; }, 60);
        if (s && !p.pl[+s.dataset.s]) { p.pl[+s.dataset.s] = id; sel = ""; env.say(dev(id).name + " placed."); env.save(); }
        draw();
      }
      document.addEventListener("pointermove", mv); document.addEventListener("pointerup", up); document.addEventListener("pointercancel", up);
    });
    draw();
  }

  function render(q, it, host, env) {
    addCss();
    host.className = "px";
    ({ logsel: renderLogsel, rules: renderRules, term: renderTerm, diagram: renderDiagram })[q.kind](q, it, host, env);
  }

  window.PBQX = { v: 1, kinds: KINDS, valid: valid, newItem: newItem, ok: ok, answered: answered, parts: parts, score: score, review: review, render: render };
})();
