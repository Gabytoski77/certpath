/* MyNextCert SOC Simulator engine v1 (our own code, not a third-party library).
   Loaded by the practice-exam code only when a question bank holds a "socsim" item, so every other page and exam never
   downloads it. The service worker saves it the first time it is used, like vendor/pbq-engine.js.

   One "socsim" item = one incident scenario with four panes (tabs on phones, side by side on wide screens):
     Alert queue   alerts with severity, time, rule and status. Some appear later (after N seconds, or after another alert's
                   case report is submitted), so the attack chain unfolds. Take an alert before you work it.
     SIEM search   a tiny Splunk-style search over the scenario's made-up events. Safe subset only (see parseQuery).
     Analyst VM    a terminal (allowed commands only), a make-believe threat-intel lookup and a decode tool.
     Case report   per alert: true/false positive, severity, escalate, ATT&CK technique, host/user, IOCs, action, summary.

   Everything is plain strings and numbers. Nothing from the data or the learner is ever run: queries are parsed by hand
   (no eval, no RegExp built from input), and every string goes through esc() or textContent.
   Same interface as vendor/pbq-engine.js (valid, newItem, ok, answered, parts, score, review, render), exposed as
   window.SOCSIM. Scoring is per part; a part may carry its own "d" (domain) and "obj" (objective). */
(function () {
  "use strict";
  if (window.SOCSIM && window.SOCSIM.v === 1) return;

  var MAX_ALERTS = 12, MAX_EVENTS = 400, MAX_FIELDS = 12, MAX_CMDS = 30, MAX_QRY = 30, MAX_TI = 30, MAX_DEC = 20, MAX_Q = 200, MAX_CMD_LEN = 120, MAX_ROWS = 100;
  var SEV = ["low", "medium", "high", "critical"];
  var TECH = [   /* a pick list of MITRE ATT&CK technique IDs (public); names shortened */
    ["T1595", "Active Scanning"], ["T1190", "Exploit Public-Facing Application"], ["T1566.001", "Phishing: Spearphishing Attachment"], ["T1566.002", "Phishing: Spearphishing Link"],
    ["T1204.002", "User Execution: Malicious File"], ["T1059.001", "Command and Scripting: PowerShell"], ["T1059.003", "Command and Scripting: Windows Command Shell"],
    ["T1027", "Obfuscated Files or Information"], ["T1140", "Deobfuscate/Decode Files or Information"], ["T1105", "Ingress Tool Transfer"], ["T1218", "System Binary Proxy Execution"],
    ["T1053.005", "Scheduled Task"], ["T1547.001", "Registry Run Keys / Startup Folder"], ["T1136.001", "Create Account: Local Account"], ["T1078", "Valid Accounts"],
    ["T1110.001", "Brute Force: Password Guessing"], ["T1110.003", "Brute Force: Password Spraying"], ["T1003.001", "OS Credential Dumping: LSASS Memory"],
    ["T1087", "Account Discovery"], ["T1018", "Remote System Discovery"], ["T1046", "Network Service Discovery"], ["T1021.001", "Remote Services: RDP"], ["T1021.002", "Remote Services: SMB/Admin Shares"],
    ["T1569.002", "System Services: Service Execution"], ["T1543.003", "Create or Modify System Process: Windows Service"], ["T1505.003", "Server Software Component: Web Shell"], ["T1071.001", "Application Layer Protocol: Web"], ["T1219", "Remote Access Software"], ["T1041", "Exfiltration Over C2 Channel"],
    ["T1048", "Exfiltration Over Alternative Protocol"], ["T1567", "Exfiltration Over Web Service"], ["T1070.004", "Indicator Removal: File Deletion"], ["T1562.001", "Impair Defenses: Disable or Modify Tools"],
    ["T1486", "Data Encrypted for Impact"], ["T1490", "Inhibit System Recovery"]
  ];
  var ACT = [
    ["iso", "Isolate the host from the network"], ["pwd", "Reset the password and end the user's sessions"], ["blk", "Block the indicator at the firewall or proxy"],
    ["purge", "Delete the email from all mailboxes"], ["mon", "Keep monitoring, no action yet"], ["none", "Close it, no action needed"]
  ];
  var RANGES = { all: ["All time", 0], "15m": ["Last 15 minutes", 900], "1h": ["Last hour", 3600], "4h": ["Last 4 hours", 14400], "24h": ["Last 24 hours", 86400] };
  var IOCK = [["ip", "IP address"], ["domain", "Domain"], ["hash", "File hash"], ["file", "File name"]];
  var TABS = [["al", "Alerts"], ["si", "SIEM"], ["vm", "Analyst VM"], ["rp", "Case report"]];

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function str(x, max) { return typeof x === "string" && x.trim().length > 0 && x.length <= max; }
  function int(x, lo, hi) { return typeof x === "number" && x === Math.floor(x) && x >= lo && x <= hi; }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function short(t, n) { t = String(t); n = n || 72; return t.length > n ? t.slice(0, n - 2) + "…" : t; }
  function secs(t) { var m = /^(\d\d):(\d\d):(\d\d)$/.exec(t); return m && +m[1] < 24 && +m[2] < 60 && +m[3] < 60 ? +m[1] * 3600 + +m[2] * 60 + +m[3] : -1; }
  function p2(n) { return (n < 10 ? "0" : "") + n; }
  function hms(s) { s = ((s % 86400) + 86400) % 86400; return p2(Math.floor(s / 3600)) + ":" + p2(Math.floor(s / 60) % 60) + ":" + p2(s % 60); }
  function pair(list, id) { for (var i = 0; i < list.length; i++) if (list[i][0] === id) return list[i]; return null; }
  function ids(list) { return list.map(function (x) { return x[0]; }); }

  /* ---------- text helpers: matching, defang/refang, normalising answers ---------- */
  function refang(s) { return String(s).replace(/\[\.\]|\(\.\)|\[dot\]/gi, ".").replace(/\[:\]/g, ":").replace(/\[@\]/g, "@").replace(/hxxp/gi, "http"); }
  function defang(s) { return String(s).replace(/http/gi, function (m) { return m.charAt(0) === "H" ? "Hxxp" : "hxxp"; }).replace(/\./g, "[.]").replace(/@/g, "[@]"); }
  function nrm(s) { return refang(s).toLowerCase().replace(/["']/g, "").replace(/\s+/g, " ").trim().replace(/\.$/, ""); }
  function toks(s) { return String(s).split(/[\s,;]+/).map(nrm).filter(Boolean); }
  function glob(pat, s) {   /* case-insensitive * wildcard match, by hand (no RegExp from data) */
    pat = pat.toLowerCase(); s = s.toLowerCase();
    var pi = 0, si = 0, star = -1, mark = 0;
    while (si < s.length) {
      if (pi < pat.length && pat.charAt(pi) === "*") { star = pi++; mark = si; }
      else if (pi < pat.length && pat.charAt(pi) === s.charAt(si)) { pi++; si++; }
      else if (star >= 0) { pi = star + 1; si = ++mark; }
      else return false;
    }
    while (pi < pat.length && pat.charAt(pi) === "*") pi++;
    return pi === pat.length;
  }

  /* ---------- validation of the question data ---------- */
  function partOk(q, x, ds) {
    if (x.d !== undefined && !(typeof x.d === "string" && ds && ds[x.d])) return false;
    if (x.obj !== undefined) {
      var dom = x.d || q.d;
      if (!(typeof x.obj === "string" && /^\d+\.\d+$/.test(x.obj) && x.obj.split(".")[0] + ".0" === dom)) return false;
    }
    return true;
  }
  function pw(q, x, ds) { return x && typeof x === "object" && str(x.why, 700) && partOk(q, x, ds); }
  function facts1(x) { return typeof x === "string" ? str(x, 60) : Array.isArray(x) && x.length >= 1 && x.length <= 6 && x.every(function (f) { return str(f, 60); }); }
  function fxList(c) { return c.fx === undefined ? [] : Array.isArray(c.fx) ? c.fx : [c.fx]; }
  function valid(q, ds) {
    try {
      if (!q || q.t !== "pbq" || q.kind !== "socsim" || !str(q.title, 200) || !str(q.scenario, 900)) return false;
      if (q.ticket !== undefined && !str(q.ticket, 700)) return false;
      if (!int(q.minutes, 1, 45) || !/^\d{4}-\d\d-\d\d$/.test(q.day || "") || secs(q.now) < 0) return false;
      if (q.host !== undefined && !/^[a-z0-9-]{1,20}$/.test(q.host)) return false;
      var al = q.alerts, aid = {}, i;
      if (!Array.isArray(al) || al.length < 1 || al.length > MAX_ALERTS) return false;
      if (!al.every(function (a) {
        var ok = a && /^[a-z0-9]{1,6}$/.test(a.id) && !aid[a.id] && str(a.name, 120) && SEV.indexOf(a.sev) >= 0 && secs(a.t) >= 0 && str(a.host, 60) && str(a.desc, 600) &&
          (a.at === undefined || int(a.at, 0, 2700)) && (a.after === undefined || (typeof a.after === "string" && aid[a.after])) && a.ans && typeof a.ans === "object";
        if (ok) aid[a.id] = a;
        return ok;
      })) return false;
      if (!al.some(function (a) { return !a.at && !a.after; })) return false;   /* something to work on from the start */
      if (!al.every(function (a) { return ansOk(q, a.ans, ds); })) return false;
      if (!al.some(function (a) { return a.ans.tp; }) || !al.some(function (a) { return !a.ans.tp; })) return false;   /* both kinds, or nothing to get wrong */
      var ev = q.events;
      if (!Array.isArray(ev) || ev.length < 3 || ev.length > MAX_EVENTS) return false;
      if (!ev.every(function (e) {
        if (!e || secs(e.t) < 0 || !/^[a-z0-9_]{1,16}$/.test(e.i) || !/^[a-z0-9_:]{1,24}$/.test(e.st) || !str(e.raw, 320) || (e.fx !== undefined && !facts1(e.fx))) return false;
        var fk = Object.keys(e.f || {});
        return e.f && typeof e.f === "object" && !Array.isArray(e.f) && fk.length <= MAX_FIELDS && fk.every(function (k) { return /^[a-z_][a-z0-9_]{0,23}$/.test(k) && k !== "index" && k !== "sourcetype" && k.charAt(0) !== "_" && typeof e.f[k] === "string" && e.f[k].length <= 120; });
      })) return false;
      if (q.ti !== undefined) {
        if (!Array.isArray(q.ti) || q.ti.length > MAX_TI) return false;
        if (!q.ti.every(function (t) { return t && str(t.ind, 200) && ["malicious", "suspicious", "benign"].indexOf(t.v) >= 0 && str(t.note, 300); })) return false;
      }
      if (q.cmds !== undefined) {
        if (!Array.isArray(q.cmds) || q.cmds.length > 30) return false;
        if (!q.cmds.every(function (c) { return c && Array.isArray(c.run) && c.run.length >= 1 && c.run.length <= 8 && c.run.every(function (r) { return str(r, MAX_CMD_LEN); }) && typeof c.out === "string" && c.out.length <= 1500 && fxList(c).every(function (f) { return str(f, 60); }); })) return false;
      }
      if (q.suggest !== undefined && !(Array.isArray(q.suggest) && q.suggest.length <= 8 && q.suggest.every(function (s) { return str(s, MAX_CMD_LEN); }))) return false;
      if (q.suggestq !== undefined && !(Array.isArray(q.suggestq) && q.suggestq.length <= 6 && q.suggestq.every(function (s) { return str(s, MAX_Q) && !parseQuery(s).err; }))) return false;
      if (q.checks !== undefined) {
        if (!Array.isArray(q.checks) || q.checks.length > 8) return false;
        if (!q.checks.every(function (c) {
          if (!c || !str(c.t, 200) || !pw(q, c, ds)) return false;
          var n = (c.has !== undefined ? 1 : 0) + (c.lacks !== undefined ? 1 : 0) + (c.after !== undefined ? 1 : 0);
          if (n !== 1) return false;
          if (c.after !== undefined) return facts1(c.after) && facts1(c.of);
          return facts1(c.has !== undefined ? c.has : c.lacks);
        })) return false;
      }
      return true;
    } catch (e) { return false; }
  }
  function ansOk(q, an, ds) {
    if (an.tp !== 0 && an.tp !== 1) return false;
    if (!str(an.why, 700) || !pw(q, an, ds) || !pw(q, an.cls, ds) || !pw(q, an.esc, ds)) return false;
    if (an.esc.v !== undefined && an.esc.v !== 0 && an.esc.v !== 1) return false;
    var tp = an.tp;
    if (tp && !(an.sev && an.tech && an.host && an.act && Array.isArray(an.iocs) && an.iocs.length)) return false;
    if (an.sev && !(SEV.indexOf(an.sev.v) >= 0 && pw(q, an.sev, ds))) return false;
    if (an.tech && !(pair(TECH, an.tech.v) && pw(q, an.tech, ds))) return false;
    if (an.act && !(pair(ACT, an.act.v) && pw(q, an.act, ds))) return false;
    if (an.host && !((str(an.host.v, 120) || (Array.isArray(an.host.v) && an.host.v.length > 0 && an.host.v.length <= 4 && an.host.v.every(function (h) { return str(h, 120); }))) && pw(q, an.host, ds))) return false;
    if (an.iocs !== undefined) {
      if (!Array.isArray(an.iocs) || an.iocs.length > 8) return false;
      if (!an.iocs.every(function (c) { return c && pair(IOCK, c.k) && str(c.v, 200) && (c.need === undefined || c.need === 0 || c.need === 1) && pw(q, c, ds); })) return false;
    }
    return true;
  }

  /* ---------- the item a run stores ---------- */
  function newItem(q) { return { ro: [], pick: { el: 0, tab: "al", sel: "", own: {}, sub: {}, act: [], r: {}, up: 0, lq: "", lr: "all" } }; }
  function alertIds(q) { return q.alerts.map(function (a) { return a.id; }); }
  function rOk(r, techs) {
    return r && typeof r === "object" && ["", "tp", "fp"].indexOf(r.c) >= 0 && ["", "low", "medium", "high", "critical"].indexOf(r.s) >= 0 && ["", "y", "n"].indexOf(r.e) >= 0 &&
      (r.t === "" || techs.indexOf(r.t) >= 0) && typeof r.h === "string" && r.h.length <= 120 && ["", "iso", "pwd", "blk", "purge", "mon", "none"].indexOf(r.a) >= 0 &&
      typeof r.n === "string" && r.n.length <= 600 && (r.d === 0 || r.d === 1) && r.i && typeof r.i === "object" &&
      IOCK.every(function (k) { return typeof r.i[k[0]] === "string" && r.i[k[0]].length <= 200; });
  }
  function ok(q, it) {   /* is a saved item well-formed for this question? (resume checks this; bad data is dropped) */
    try {
      var p = it.pick, ai = alertIds(q), cnt = { c: 0, q: 0, t: 0, d: 0 };
      if (!p || typeof p !== "object" || !Array.isArray(it.ro) || it.ro.length) return false;
      if (!int(p.el, 0, q.minutes * 60) || ["al", "si", "vm", "rp"].indexOf(p.tab) < 0 || (p.sel !== "" && ai.indexOf(p.sel) < 0) || (p.up !== 0 && p.up !== 1)) return false;
      if (typeof p.lq !== "string" || p.lq.length > MAX_Q || !has(RANGES, p.lr)) return false;
      if (!p.own || !p.sub || !p.r || typeof p.own !== "object" || typeof p.sub !== "object" || typeof p.r !== "object") return false;
      if (!Object.keys(p.own).every(function (k) { return ai.indexOf(k) >= 0 && p.own[k] === 1; })) return false;
      if (!Object.keys(p.sub).every(function (k) { return ai.indexOf(k) >= 0 && int(p.sub[k], 0, q.minutes * 60); })) return false;
      if (!Object.keys(p.r).every(function (k) { return ai.indexOf(k) >= 0 && rOk(p.r[k], ids(TECH)); })) return false;
      if (!Array.isArray(p.act) || p.act.length > MAX_CMDS + MAX_QRY + MAX_TI + MAX_DEC) return false;
      return p.act.every(function (a) {
        if (!a || ["c", "q", "t", "d"].indexOf(a.k) < 0 || typeof a.s !== "string" || a.s.length > (a.k === "c" ? MAX_CMD_LEN : a.k === "d" ? 520 : MAX_Q + 8)) return false;
        return ++cnt[a.k] <= { c: MAX_CMDS, q: MAX_QRY, t: MAX_TI, d: MAX_DEC }[a.k];
      });
    } catch (e) { return false; }
  }
  function answered(q, it) {   /* 0 nothing yet, 1 started, 2 has an answer */
    var p = it.pick;
    if (Object.keys(p.sub).length) return 2;
    return Object.keys(p.own).length || p.act.length ? 1 : 0;
  }
  function seen(a, p) {   /* has this alert reached the queue yet? (the scenario clock p.el, and who it waits for) */
    if (a.after) return p.sub[a.after] !== undefined && p.el >= p.sub[a.after] + (a.at || 0);
    return p.el >= (a.at || 0);
  }
  function rr(p, id) { return p.r[id] || (p.r[id] = { c: "", s: "", e: "", t: "", h: "", i: { ip: "", domain: "", hash: "", file: "" }, a: "", n: "", d: 0 }); }

  /* ---------- the analyst VM: allowed commands, threat-intel lookup, decode tool ---------- */
  function ncmd(s) { return String(s).toLowerCase().replace(/["']/g, "").replace(/\s+/g, " ").trim().replace(/^sudo /, ""); }
  function runCmd(q, s) {
    var n = ncmd(s), i, j, cs = q.cmds || [];
    if (n === "help") return { out: "Commands in this lab:\n  help\n" + cs.map(function (c) { return "  " + c.run[0]; }).join("\n"), bad: false, fx: [] };
    for (i = 0; i < cs.length; i++) for (j = 0; j < cs[i].run.length; j++) if (ncmd(cs[i].run[j]) === n) return { out: cs[i].out, bad: false, fx: fxList(cs[i]) };
    return { out: "Not available in this lab. Type help to see the commands.", bad: true, fx: [] };
  }
  function tiFind(q, s) {
    var n = nrm(s), l = q.ti || [], i;
    for (i = 0; i < l.length; i++) if (nrm(l[i].ind) === n) return { key: n, rec: l[i] };
    return { key: n, rec: null };
  }
  function tiText(q, s) {
    var m = tiFind(q, s);
    return m.rec ? defang(m.rec.ind) + " : " + m.rec.v.toUpperCase() + "\n" + m.rec.note : "No match for " + short(defang(s), 60) + " in this lab's threat-intel feed. Verdict: unknown.";
  }
  function b64(s) {
    var t = String(s).replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
    if (!t || !/^[A-Za-z0-9+/]*={0,2}$/.test(t)) return "Not valid Base64.";
    while (t.length % 4) t += "=";
    var bin, bytes, i, u16 = false;
    try { bin = atob(t); } catch (e) { return "Not valid Base64."; }
    bytes = new Uint8Array(bin.length);
    for (i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    if (bytes.length >= 4 && bytes.length % 2 === 0) { u16 = true; for (i = 1; i < Math.min(bytes.length, 40); i += 2) if (bytes[i] !== 0) { u16 = false; break; } }   /* PowerShell -EncodedCommand is UTF-16 */
    try { bin = new TextDecoder(u16 ? "utf-16le" : "utf-8", { fatal: true }).decode(bytes); } catch (e) { return "Decoded to binary data, not readable text."; }
    return /[\u0000-\u0008\u000e-\u001f]/.test(bin) ? "Decoded to binary data, not readable text." : bin.slice(0, 2000);
  }
  function decode(kind, s) {
    s = String(s).slice(0, 500);
    if (kind === "b64") return b64(s);
    if (kind === "url") { try { return decodeURIComponent(s.replace(/\+/g, " ")).slice(0, 2000); } catch (e) { return "Not valid percent-encoding."; } }
    if (kind === "defang") return defang(s);
    return refang(s);
  }
  var DEC = [["b64", "Base64 decode"], ["url", "URL decode"], ["defang", "Defang"], ["refang", "Refang"]];

  /* the ordered facts: what the learner's commands, lookups, decodes and searches turned up */
  function facts(q, act) {
    var f = [];
    act.forEach(function (a) {
      if (a.k === "c") runCmd(q, a.s).fx.forEach(function (x) { f.push(x); });
      else if (a.k === "t") { var m = tiFind(q, a.s); if (m.rec) { f.push("ti:" + m.key); fxList(m.rec).forEach(function (x) { f.push(x); }); } }
      else if (a.k === "d") f.push("dec:" + a.s.split(":")[0]);
      else if (a.k === "q") { var r = parseQuery(a.s.split("\u0001")[0]); if (!r.err) evFacts(q, r, a.s.split("\u0001")[1] || "all").forEach(function (x) { f.push(x); }); }
    });
    return f;
  }
  function evFacts(q, parsed, range) {
    var out = [];
    runSearch(q, parsed, range).hit.forEach(function (e) { fxList(e).forEach(function (x) { if (out.indexOf(x) < 0) out.push(x); }); });
    return out;
  }
  function list(x) { return Array.isArray(x) ? x : [x]; }
  function anyIn(fs, x) { return list(x).some(function (f) { return fs.indexOf(f) >= 0; }); }
  function checkOne(c, fs, n) {
    if (c.has !== undefined) return anyIn(fs, c.has);
    if (c.lacks !== undefined) return n > 0 && !anyIn(fs, c.lacks);   /* doing nothing never earns a "didn't do X" part */
    var last = -1; list(c.of).forEach(function (f) { last = Math.max(last, fs.lastIndexOf(f)); });
    return last >= 0 && anyIn(fs.slice(last + 1), c.after);
  }

  /* ---------- the SIEM: a safe subset of Splunk search, parsed by hand ---------- */
  var FIELDRE = /^[a-z_][a-z0-9_.]{0,30}$/i;
  function lex(s) {   /* words, quoted strings, ( ) and | ; field=value stays one word */
    var out = [], i = 0, n = s.length, w, c, inq;
    while (i < n) {
      c = s.charAt(i);
      if (c === " " || c === "\t") { i++; continue; }
      if (c === "|" || c === "(" || c === ")") { out.push({ t: c }); i++; continue; }
      w = ""; inq = false;
      while (i < n) {
        c = s.charAt(i);
        if (c === '"') { inq = !inq; w += c; i++; continue; }
        if (!inq && (c === " " || c === "\t" || c === "|" || c === "(" || c === ")")) break;
        w += c; i++;
      }
      if (inq) return { err: "A quote is not closed." };
      out.push({ t: "w", v: w });
    }
    return { toks: out };
  }
  function unq(v) { return v.length >= 2 && v.charAt(0) === '"' && v.charAt(v.length - 1) === '"' ? v.slice(1, -1) : v.replace(/"/g, ""); }
  function parseQuery(s) {
    s = String(s);
    if (!s.trim()) return { err: "Type a search first." };
    if (s.length > MAX_Q) return { err: "Searches are limited to " + MAX_Q + " characters." };
    if (/[\u0000-\u001f]/.test(s)) return { err: "That search has characters this simulator does not allow." };
    var L = lex(s);
    if (L.err) return L;
    var segs = [[]], k;
    L.toks.forEach(function (t) { if (t.t === "|") segs.push([]); else segs[segs.length - 1].push(t); });
    var pos = 0, terms = 0, search = segs[0], err = "";
    function fail(m) { if (!err) err = m; return null; }
    function peekW() { var t = search[pos]; return t && t.t === "w" ? t.v.toUpperCase() : ""; }
    function atom(depth) {
      var t = search[pos];
      if (!t) return fail("The search ends too soon.");
      if (t.t === "(") {
        if (depth > 6) return fail("Too many brackets inside brackets.");
        pos++; var e = expr(depth + 1);
        if (!search[pos] || search[pos].t !== ")") return fail("A bracket is not closed.");
        pos++; return e;
      }
      if (t.t === ")") return fail("A closing bracket has nothing before it.");
      var v = t.v, eq = v.indexOf("="), neg = false, field, val;
      if (++terms > 12) return fail("Too many terms (the limit is 12).");
      if (eq > 0 && v.charAt(0) !== '"') {
        field = v.slice(0, eq); if (field.slice(-1) === "!") { neg = true; field = field.slice(0, -1); }
        val = unq(v.slice(eq + 1));
        if (!FIELDRE.test(field)) return fail("'" + short(field, 20) + "' is not a field name.");
        pos++; field = field.toLowerCase();
        return { f: field, v: val, neg: neg };
      }
      pos++;
      return { w: unq(v) };
    }
    function not(depth) { if (peekW() === "NOT") { pos++; var x = not(depth); return x && { not: x }; } return atom(depth); }
    function and(depth) {
      var a = not(depth), b;
      while (a && pos < search.length && search[pos].t !== ")" && peekW() !== "OR") {
        if (peekW() === "AND") pos++;
        b = not(depth); if (!b) return null;
        a = { and: [a, b] };
      }
      return a;
    }
    function expr(depth) {
      var a = and(depth), b;
      while (a && peekW() === "OR") { pos++; b = and(depth); if (!b) return null; a = { or: [a, b] }; }
      return a;
    }
    var tree = null;
    if (search.length) { tree = expr(0); if (!err && pos < search.length) fail("Something in the search was not understood near '" + short(search[pos].v || search[pos].t, 20) + "'."); }
    if (err) return { err: err };
    var pipes = [];
    for (k = 1; k < segs.length; k++) {
      var sg = segs[k], cmd = sg[0] && sg[0].t === "w" ? sg[0].v.toLowerCase() : "", args = sg.slice(1).map(function (t) { return t.t === "w" ? t.v : t.t; });
      if (!sg.length || sg.some(function (t) { return t.t !== "w"; })) return { err: "A | must be followed by a command and its words (no brackets)." };
      if (cmd === "stats") {
        if (!args.length || args[0].toLowerCase() !== "count") return { err: "stats only supports: stats count [by field ...]" };
        var by = [];
        if (args.length > 1) { if (args[1].toLowerCase() !== "by" || args.length < 3 || args.length > 5) return { err: "stats only supports: stats count [by field ...] (up to 3 fields)" }; by = args.slice(2).map(function (x) { return x.toLowerCase(); }); }
        if (!by.every(function (x) { return FIELDRE.test(x); })) return { err: "A field name has odd characters in it." };
        pipes.push({ c: "stats", by: by });
      } else if (cmd === "table") {
        if (!args.length || args.length > 8 || !args.every(function (x) { return FIELDRE.test(x); })) return { err: "table needs 1 to 8 field names, like: table _time host" };
        pipes.push({ c: "table", f: args.map(function (x) { return x.toLowerCase(); }) });
      } else if (cmd === "sort") {
        var f = args[0] || "", d = 1;
        if (args.length !== 1) return { err: "sort needs one field, like: sort -count" };
        if (f.charAt(0) === "-") { d = -1; f = f.slice(1); } else if (f.charAt(0) === "+") f = f.slice(1);
        if (!FIELDRE.test(f)) return { err: "sort needs a field name, like: sort -count" };
        pipes.push({ c: "sort", f: f.toLowerCase(), d: d });
      } else if (cmd === "head") {
        var nn = args.length ? +args[0] : 10;
        if (args.length > 1 || !(nn >= 1 && nn <= 100 && nn === Math.floor(nn)) || (args.length && !/^\d+$/.test(args[0]))) return { err: "head needs a number from 1 to 100, like: head 10" };
        pipes.push({ c: "head", n: nn });
      } else return { err: "'" + short(cmd, 20) + "' is not available in this simulator. You can use: stats count by, table, sort, head." };
    }
    return { tree: tree, pipes: pipes };
  }
  function prep(q) {   /* a lowercase field map and a search text for each event, built once */
    if (q._ss) return q._ss;
    return (q._ss = q.events.map(function (e, n) {
      var row = { _time: hms(secs(e.t)), index: e.i, sourcetype: e.st, _raw: e.raw }, k, hay = [e.raw];
      for (k in e.f) if (has(e.f, k)) { row[k] = e.f[k]; hay.push(e.f[k]); }
      return { e: e, row: row, t: secs(e.t), hay: hay.join(" "), n: n };
    }));
  }
  function tmatch(node, ev) {
    if (node.and) return tmatch(node.and[0], ev) && tmatch(node.and[1], ev);
    if (node.or) return tmatch(node.or[0], ev) || tmatch(node.or[1], ev);
    if (node.not) return !tmatch(node.not, ev);
    if (node.w !== undefined) return glob("*" + node.w + "*", ev.hay);
    var v = has(ev.row, node.f) ? ev.row[node.f] : null, hit = v !== null && glob(node.v, v);
    return node.neg ? !hit : hit;
  }
  function cmpv(a, b) {
    var na = /^-?\d+(\.\d+)?$/.test(a), nb = /^-?\d+(\.\d+)?$/.test(b);
    if (na && nb) return +a - +b;
    a = String(a).toLowerCase(); b = String(b).toLowerCase();
    return a < b ? -1 : a > b ? 1 : 0;
  }
  function runSearch(q, parsed, range) {
    var all = prep(q), now = secs(q.now), span = RANGES[range] ? RANGES[range][1] : 0;
    var hit = all.filter(function (ev) { return (!span || (ev.t >= now - span && ev.t <= now)) && (!parsed.tree || tmatch(parsed.tree, ev)); });
    hit.sort(function (a, b) { return b.t - a.t || b.n - a.n; });   /* newest first */
    var rows = hit.map(function (ev) { return ev.row; }), cols = ["_time", "host", "sourcetype", "_raw"], ord = false;
    parsed.pipes.forEach(function (pp) {
      if (pp.c === "stats") {
        var g = {}, keys = [];
        rows.forEach(function (r) {
          if (!pp.by.every(function (b) { return has(r, b); })) return;
          var key = pp.by.map(function (b) { return r[b]; }).join("\u0001");
          if (!has(g, key)) { g[key] = { n: 0, r: pp.by.map(function (b) { return r[b]; }) }; keys.push(key); }
          g[key].n++;
        });
        rows = keys.map(function (key) { var o = {}; pp.by.forEach(function (b, i) { o[b] = g[key].r[i]; }); o.count = String(g[key].n); return o; });
        rows.sort(function (a, b) { return b.count - a.count; });
        cols = pp.by.concat(["count"]);
      } else if (pp.c === "table") {
        cols = pp.f; rows = rows.map(function (r) { var o = {}; pp.f.forEach(function (f) { o[f] = has(r, f) ? r[f] : ""; }); return o; });
      } else if (pp.c === "sort") {
        rows = rows.slice().sort(function (a, b) { return pp.d * cmpv(has(a, pp.f) ? a[pp.f] : "", has(b, pp.f) ? b[pp.f] : ""); }); ord = true;
      } else rows = rows.slice(0, pp.n);
    });
    return { hit: hit.map(function (ev) { return ev.e; }), rows: rows, cols: cols, total: hit.length, stamps: hit.map(function (ev) { return ev.t; }) };
  }

  /* ---------- scoring: a list of parts, each right or wrong, each with its why ---------- */
  function tl(id) { var t = pair(TECH, id); return t ? t[0] + " " + t[1] : "none"; }
  function actl(id) { var t = pair(ACT, id); return t ? t[1] : "none"; }
  function parts(q, it) {
    var p = it.pick, out = [], blank = answered(q, it) === 0;
    function add(x, o) { o.d = x.d || q.d; o.obj = x.obj || q.obj; o.why = x.why; if (blank) { o.ok = false; o.you = "not answered"; } out.push(o); }
    q.alerts.forEach(function (a) {
      var an = a.ans, r = p.r[a.id] || rr({ r: {} }, a.id), nm = short(a.name, 48) + ": ", tp = an.tp, esc1 = an.esc.v !== undefined ? an.esc.v : tp;
      add(an.cls, { ok: r.c === (tp ? "tp" : "fp"), t: nm + "true or false positive", ans: tp ? "true positive" : "false positive", you: r.c === "tp" ? "true positive" : r.c === "fp" ? "false positive" : "not answered" });
      add(an.esc, { ok: r.e === (esc1 ? "y" : "n"), t: nm + "escalate?", ans: esc1 ? "escalate" : "close it, don't escalate", you: r.e === "y" ? "escalated" : r.e === "n" ? "closed" : "not answered" });
      if (an.sev) add(an.sev, { ok: r.s === an.sev.v, t: nm + "severity", ans: an.sev.v, you: r.s || "not answered" });
      if (an.tech) add(an.tech, { ok: r.t === an.tech.v, t: nm + "ATT&CK technique", ans: tl(an.tech.v), you: r.t ? tl(r.t) : "not answered" });
      if (an.host) {
        var hs = list(an.host.v).map(nrm), hv = nrm(r.h);
        add(an.host, { ok: !!hv && hs.indexOf(hv) >= 0, t: nm + "affected host or user", ans: list(an.host.v)[0], you: r.h.trim() || "not answered" });
      }
      (an.iocs || []).forEach(function (c) {
        var got = toks(r.i[c.k] || ""), want = nrm(c.v), listed = got.indexOf(want) >= 0, need = c.need !== 0;
        add(c, { ok: need ? listed : !listed, t: nm + (need ? "IOC, " : "not an IOC, ") + pair(IOCK, c.k)[1].toLowerCase(), ans: need ? defang(c.v) : "leave " + defang(c.v) + " out", you: need ? (listed ? "listed" : "not listed") : (listed ? "listed it" : "left out") });
      });
      if (an.act) add(an.act, { ok: r.a === an.act.v, t: nm + "recommended action", ans: actl(an.act.v), you: r.a ? actl(r.a) : "not answered" });
      var worked = !!r.d, missed = tp && !(r.c === "tp" && r.e === "y"), wrongEsc = !tp && r.e === "y";
      add(an, { ok: worked && !missed && !wrongEsc, t: nm + "triage outcome", ans: tp ? "true positive escalated" : "false positive closed", you: !worked ? "case report not submitted" : missed ? "missed a true positive" : wrongEsc ? "escalated a false positive" : "right call" });
    });
    var fs = facts(q, p.act), nact = p.act.length;
    (q.checks || []).forEach(function (c) { var good = checkOne(c, fs, nact); add(c, { ok: good, t: c.t, ans: "done", you: good ? "done" : nact ? "not done" : "nothing run" }); });
    return out;
  }
  function score(q, it) { var ps = parts(q, it), n = 0; ps.forEach(function (x) { if (x.ok) n++; }); return ps.length ? n / ps.length : 0; }
  function modelLine(a) {
    var an = a.ans, bits = [an.tp ? "True positive" : "False positive", (an.esc.v !== undefined ? an.esc.v : an.tp) ? "escalate" : "close, no escalation"];
    if (an.sev) bits.push("severity " + an.sev.v);
    if (an.tech) bits.push(tl(an.tech.v));
    if (an.host) bits.push("host/user " + list(an.host.v)[0]);
    (an.iocs || []).forEach(function (c) { if (c.need !== 0) bits.push(pair(IOCK, c.k)[1].toLowerCase() + " " + defang(c.v)); });
    if (an.act) bits.push(actl(an.act.v));
    return bits.join(" · ");
  }
  function review(q, it) {   /* shown after the whole exam is submitted (never during the exam) */
    var p = it.pick, h = "<ul class=\"mx-pbr\">" + parts(q, it).map(function (x) {
      return "<li class=\"" + (x.ok ? "ok" : "no") + "\"><b>" + esc(x.t) + "</b><span>Answer: " + esc(x.ans) + (x.ok ? "" : " &middot; <em>You: " + esc(x.you) + "</em>") + "</span><span>" + esc(x.why) + "</span></li>";
    }).join("");
    q.alerts.forEach(function (a) {
      var r = p.r[a.id];
      h += "<li><b>Model case report: " + esc(a.name) + "</b><span>" + esc(modelLine(a)) + "</span><span>" + esc(a.ans.why) + "</span>" + (r && r.n.trim() ? "<span><em>Your summary (not scored):</em> " + esc(r.n) + "</span>" : "") + "</li>";
    });
    if (p.act.some(function (a) { return a.k === "c"; })) h += "<li><b>Your commands</b><pre>" + esc(p.act.filter(function (a) { return a.k === "c"; }).map(function (a) { return "$ " + a.s; }).join("\n")) + "</pre></li>";
    if (p.act.some(function (a) { return a.k === "q"; })) h += "<li><b>Your searches</b><pre>" + esc(p.act.filter(function (a) { return a.k === "q"; }).map(function (a) { return a.s.split("\u0001")[0]; }).join("\n")) + "</pre></li>";
    return h + "</ul>";
  }

  /* ---------- screens ---------- */
  var CSS = ".ss{display:grid;gap:12px}.ss h3.ss-h{margin:0 0 8px;font:600 11px var(--f-ui);letter-spacing:.12em;text-transform:uppercase;color:var(--v-muted)}" +
    ".ss-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}" +
    ".ss-bar{display:flex;flex-wrap:wrap;gap:6px 14px;justify-content:space-between;align-items:center;padding:8px 12px;border:1px solid var(--v-line);border-radius:10px;font:500 12px var(--f-mono)}" +
    ".ss-cd.low{color:#ff8a7a;font-weight:700}.ss-tick{overflow:hidden;border:1px solid var(--v-line);border-radius:8px;height:26px}.ss-tick-in{display:inline-flex;white-space:nowrap;font:400 11.5px/26px var(--f-mono);color:var(--v-muted);will-change:transform}.ss-tick-in span{padding-right:48px}" +
    ".ss-tabs{display:flex;gap:6px;overflow-x:auto}.ss-tab{position:relative;flex:1 0 auto;min-height:44px;padding:0 12px;border:1px solid var(--v-line);border-radius:8px;background:none;color:inherit;font:600 12.5px var(--f-ui);cursor:pointer}" +
    ".ss-tab[aria-selected=true]{border-color:var(--v-accent);background:color-mix(in srgb,var(--v-accent) 14%,transparent)}.ss-badge{display:none;margin-left:6px;min-width:18px;padding:1px 5px;border-radius:9px;background:#e5484d;color:#fff;font:700 11px var(--f-ui)}.ss-badge.on{display:inline-block}" +
    ".ss-grid{display:grid;gap:12px}.ss-pane{display:none;border:1px solid var(--v-line);border-radius:12px;padding:12px;min-width:0}.ss-pane.on{display:block}.ss-pane>.ss-h{margin:0 0 10px}" +
    ".ss-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}.ss-al{border:1px solid var(--v-line);border-radius:10px;overflow:hidden}.ss-al.sel{border-color:var(--v-accent)}" +
    ".ss-ab{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 10px;width:100%;min-height:48px;text-align:left;background:none;border:0;padding:8px 10px;color:inherit;font:inherit;cursor:pointer}.ss-ab .nm{font:600 13px/1.4 var(--f-ui);overflow-wrap:anywhere}.ss-ab .mt{grid-column:2;font:400 11.5px var(--f-mono);color:var(--v-muted)}" +
    ".ss-sev{align-self:start;padding:2px 7px;border-radius:6px;font:700 10.5px var(--f-ui);text-transform:uppercase;letter-spacing:.06em;border:1px solid currentColor}.ss-sev.low{color:#5fb3ff}.ss-sev.medium{color:#e6b422}.ss-sev.high{color:#ff9a3c}.ss-sev.critical{color:#ff6b6b}" +
    ".ss-st{font-weight:600}.ss-ad{padding:4px 12px 12px;display:grid;gap:8px;font:400 13px/1.55 var(--f-ui)}.ss-ad p{margin:0}.ss-row{display:flex;flex-wrap:wrap;gap:8px}.ss-empty{margin:0;color:var(--v-muted);font:400 12.5px var(--f-ui)}" +
    ".ss-btn{min-height:44px;min-width:44px;padding:0 14px;border:1px solid var(--v-line);border-radius:8px;background:none;color:inherit;font:600 12.5px var(--f-ui);cursor:pointer}.ss-btn.pri{border-color:var(--v-accent);background:color-mix(in srgb,var(--v-accent) 16%,transparent)}.ss-btn:disabled{opacity:.45;cursor:default}" +
    ".ss-f{display:grid;gap:10px}.ss-f label{display:grid;gap:4px;font:600 12px var(--f-ui)}.ss-f label small{font:400 11.5px var(--f-ui);color:var(--v-muted)}.ss-f select,.ss-f input,.ss-f textarea,.ss-q input,.ss-q select,.ss-tool input,.ss-tool select{min-height:44px;width:100%;box-sizing:border-box;border:1px solid var(--v-line);border-radius:8px;background:transparent;color:inherit;padding:0 10px;font:400 13px var(--f-mono)}" +
    ".ss-f textarea{padding:8px 10px;min-height:84px;font-family:var(--f-ui)}.ss select option{color:#111}.ss-g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.ss-msg{margin:0;font:600 12.5px var(--f-ui);color:#ff8a7a}.ss-ok{color:#7be0a2}" +
    ".ss-q{display:grid;gap:8px}.ss-q .ss-g2{align-items:end}.ss-res{margin-top:10px;display:grid;gap:8px;min-width:0}.ss-cnt{margin:0;font:500 12px var(--f-mono);color:var(--v-muted)}.ss-hist{display:flex;align-items:flex-end;gap:3px;height:56px}.ss-hist i{flex:1;height:100%;background:var(--v-accent);opacity:.75;transform-origin:bottom;border-radius:2px 2px 0 0}" +
    ".ss-tw{overflow:auto;max-height:300px;border:1px solid var(--v-line);border-radius:8px}.ss-tw table{border-collapse:collapse;width:100%;font:400 11.5px/1.5 var(--f-mono)}.ss-tw th,.ss-tw td{padding:5px 8px;border-bottom:1px solid var(--v-line);text-align:left;vertical-align:top;overflow-wrap:anywhere}.ss-tw th{position:sticky;top:0;background:var(--v-bg,#0f1318);font-weight:600}.ss-tw td.raw{min-width:220px}" +
    ".ss-term{border:1px solid var(--v-line);border-radius:10px;background:#0a0d11;color:#d6dbe2;overflow:hidden}.ss-scr{height:220px;overflow:auto;padding:12px;font:400 12px/1.55 var(--f-mono);white-space:pre-wrap;overflow-wrap:anywhere}.ss-scr .c{color:#9ad1ff}.ss-scr .e{color:#ff8a7a}.ss-scr .t{color:#e6b422}" +
    ".ss-term form{display:flex;border-top:1px solid #1d2530}.ss-term form:focus-within{box-shadow:inset 0 0 0 2px var(--v-accent)}.ss-ps{display:grid;place-items:center;padding-left:12px;font:500 12px var(--f-mono);color:#7be0a2;white-space:nowrap}.ss-term input{flex:1;min-width:0;min-height:44px;background:none;border:0;outline:none;padding:0 8px;font:400 13px var(--f-mono);color:#fff}" +
    ".ss-term form button{min-height:44px;padding:0 16px;border:0;border-left:1px solid #1d2530;background:none;color:#7be0a2;font:600 12px var(--f-ui);cursor:pointer}.ss-chips{display:flex;flex-wrap:wrap;gap:6px}.ss-chip{min-height:44px;padding:0 12px;border:1px solid var(--v-line);border-radius:8px;background:none;color:inherit;font:500 11.5px var(--f-mono);text-align:left;overflow-wrap:anywhere;cursor:pointer}" +
    ".ss-tool{display:grid;gap:8px;margin-top:12px}.ss-tool form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.ss-tool form.dec{grid-template-columns:auto minmax(0,1fr) auto}" +
    ".ss :focus-visible{outline:2px solid var(--v-accent);outline-offset:2px}.ss [disabled]{cursor:default}" +
    "@media (min-width:960px){.ss-tabs{display:none}.ss-grid{grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);align-items:start}.ss-pane,.ss-pane.on{display:block}.ss-grid>[data-p=al]{grid-column:1;grid-row:1}.ss-grid>[data-p=rp]{grid-column:1;grid-row:2}.ss-grid>[data-p=si]{grid-column:2;grid-row:1}.ss-grid>[data-p=vm]{grid-column:2;grid-row:2}}" +
    "@media (max-width:420px){.ss-g2{grid-template-columns:1fr}.ss-tool form.dec{grid-template-columns:1fr}}" +
    "@media (pointer:coarse),(max-width:640px){.ss-f select,.ss-f input,.ss-f textarea,.ss-q input,.ss-q select,.ss-tool input,.ss-tool select,.ss-term input{font-size:16px}}" +
    /* motion: transform and opacity only, and only when the page is not in Lite mode and the person has not asked for less motion (the engine adds .ss-m) */
    "@keyframes ss-in{from{opacity:0;transform:translateY(-14px)}to{opacity:1;transform:none}}@keyframes ss-pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.25);opacity:.7}}@keyframes ss-run{from{transform:translateX(0)}to{transform:translateX(-50%)}}" +
    ".ss-m .ss-al.new{animation:ss-in .5s ease-out}.ss-m .ss-badge.on{animation:ss-pulse 1.4s ease-in-out infinite}.ss-m .ss-tick-in{animation:ss-run 60s linear infinite}.ss-m.ss-paused .ss-tick-in,.ss-m.ss-paused .ss-badge{animation-play-state:paused}.ss-m .ss-hist i{transition:transform .5s ease-out}" +
    "@media (prefers-reduced-motion:reduce){.ss *{animation:none!important;transition:none!important}}html.lite .ss *{animation:none!important;transition:none!important}";
  function addCss() {
    if (document.getElementById("socsim-css")) return;
    var s = document.createElement("style"); s.id = "socsim-css"; s.textContent = CSS; document.head.appendChild(s);
  }
  function el(tag, cls, text) { var d = document.createElement(tag); if (cls) d.className = cls; if (text !== undefined) d.textContent = text; return d; }
  function opts(list2, cur, blank) { return (blank ? "<option value=\"\">" + esc(blank) + "</option>" : "") + list2.map(function (o) { return "<option value=\"" + esc(o[0]) + "\"" + (o[0] === cur ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join(""); }
  function kb(t) { return "<kbd>" + t + "</kbd>"; }

  var cur = { timer: 0, vis: null };
  function stop() { if (cur.timer) clearInterval(cur.timer); cur.timer = 0; if (cur.vis) document.removeEventListener("visibilitychange", cur.vis); cur.vis = null; }

  function render(q, it, host, env) {
    addCss(); stop();
    var p = it.pick, lim = q.minutes * 60, lite = document.documentElement.classList.contains("lite"), reduced = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
    var motion = !lite && !reduced, user = q.host || "analyst", known = {}, unseen = 0, nsave = 0;
    host.className = "px ss" + (motion ? " ss-m" : "");
    function say(t) { var l = host.querySelector("#ss-live"); if (l) l.textContent = t; }
    function A(id) { return q.alerts.filter(function (a) { return a.id === id; })[0]; }
    function clockText() { return "SOC clock " + q.day + " " + hms(secs(q.now) + p.el) + " UTC"; }
    function left() { var s = Math.max(0, lim - p.el); return p2(Math.floor(s / 60)) + ":" + p2(s % 60); }

    host.innerHTML = (q.ticket ? "<div class=\"px-ticket\"><p class=\"lab\">Ticket</p><p>" + esc(q.ticket) + "</p></div>" : "") +
      "<p class=\"px-hint\">You are the Tier 1 analyst. Take an alert, look into it with the SIEM and the analyst VM, then fill in and submit its case report. Some alerts show up later. The scenario clock only runs while this question is open.</p>" +
      "<div class=\"ss-bar\"><span id=\"ss-clock\">" + esc(clockText()) + "</span><span id=\"ss-cd\" class=\"ss-cd\" role=\"timer\">Scenario time left " + left() + "</span></div>" +
      "<div class=\"ss-tabs\" role=\"tablist\" aria-label=\"SOC panes\">" + TABS.map(function (t) { return "<button type=\"button\" role=\"tab\" class=\"ss-tab\" id=\"ss-t-" + t[0] + "\" data-p=\"" + t[0] + "\" aria-controls=\"ss-p-" + t[0] + "\" aria-selected=\"false\" tabindex=\"-1\">" + t[1] + (t[0] === "al" ? "<span class=\"ss-badge\" id=\"ss-badge\"></span>" : "") + "</button>"; }).join("") + "</div>" +
      "<div class=\"ss-grid\">" + TABS.map(function (t) { return "<section class=\"ss-pane\" id=\"ss-p-" + t[0] + "\" data-p=\"" + t[0] + "\" role=\"tabpanel\" aria-labelledby=\"ss-t-" + t[0] + "\"><h3 class=\"ss-h\">" + ({ al: "Alert queue", si: "SIEM search", vm: "Analyst VM", rp: "Case report" })[t[0]] + "</h3><div class=\"ss-body\"></div></section>"; }).join("") + "</div>" +
      "<div class=\"ss-sr\" id=\"ss-live\" role=\"status\" aria-live=\"polite\"></div>";
    var body = {}; TABS.forEach(function (t) { body[t[0]] = host.querySelector("#ss-p-" + t[0] + " .ss-body"); });

    if (motion) {   /* a scrolling ticker of the scenario's events (decoration only, hidden from screen readers) */
      var tk = el("div", "ss-tick"), tin = el("div", "ss-tick-in"), txt = q.events.slice(0, 14).map(function (e) { return e.t + " " + short(e.raw, 90); });
      tk.setAttribute("aria-hidden", "true");
      [0, 1].forEach(function () { txt.forEach(function (s) { tin.appendChild(el("span", "", s)); }); });
      tk.appendChild(tin); host.insertBefore(tk, host.querySelector(".ss-tabs"));
    }

    /* ---- tabs ---- */
    function tab(id, focus) {
      p.tab = id;
      TABS.forEach(function (t) {
        var b = host.querySelector("#ss-t-" + t[0]), on = t[0] === id;
        b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1;
        host.querySelector("#ss-p-" + t[0]).classList.toggle("on", on);
      });
      if (id === "al") { unseen = 0; badge(); }
      if (focus) host.querySelector("#ss-t-" + id).focus();
    }
    function badge() { var b = host.querySelector("#ss-badge"); b.textContent = unseen ? String(unseen) : ""; b.classList.toggle("on", unseen > 0); b.setAttribute("aria-label", unseen ? unseen + " new" : ""); }
    host.querySelector(".ss-tabs").addEventListener("click", function (e) { var b = e.target.closest(".ss-tab"); if (b) { tab(b.dataset.p); env.save(); } });
    host.querySelector(".ss-tabs").addEventListener("keydown", function (e) {
      var ids2 = ids(TABS), at = ids2.indexOf(p.tab), n = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : e.key === "Home" ? -at : e.key === "End" ? ids2.length - 1 - at : 0;
      if (n) { e.preventDefault(); tab(ids2[(at + n + ids2.length) % ids2.length], true); env.save(); }
    });

    /* ---- alert queue ---- */
    function stat(a) { var r = p.r[a.id]; return r && r.d ? (r.e === "y" ? "Escalated" : "Closed") : p.own[a.id] ? "In progress" : "New"; }
    function visible() { return q.alerts.filter(function (a) { return seen(a, p); }); }
    function renderList(focusId) {
      var vs = visible(), b = body.al;
      if (!p.sel && vs.length) p.sel = vs[0].id;
      b.innerHTML = "<ul class=\"ss-list\">" + vs.map(function (a) {
        var sel = a.id === p.sel, fresh = !known[a.id];
        return "<li class=\"ss-al" + (sel ? " sel" : "") + (fresh && known._ready ? " new" : "") + "\" data-id=\"" + esc(a.id) + "\"><button type=\"button\" class=\"ss-ab\" aria-expanded=\"" + sel + "\" data-id=\"" + esc(a.id) + "\"><span class=\"ss-sev " + esc(a.sev) + "\">" + esc(a.sev) + "</span><span class=\"nm\">" + esc(a.name) + "</span><span class=\"mt\">" + esc(a.t) + " · " + esc(a.host) + " · <span class=\"ss-st\">" + stat(a) + "</span></span></button>" +
          (sel ? "<div class=\"ss-ad\"><p>" + esc(a.desc) + "</p><div class=\"ss-row\">" + (p.own[a.id] ? "<button type=\"button\" class=\"ss-btn pri\" data-go=\"rp\">Open case report</button>" : "<button type=\"button\" class=\"ss-btn pri\" data-take=\"" + esc(a.id) + "\"" + (p.up ? " disabled" : "") + ">Take this alert</button>") + "</div></div>" : "") + "</li>";
      }).join("") + "</ul>" + (vs.length < q.alerts.length ? "<p class=\"ss-empty\">Queue is quiet. More alerts may arrive.</p>" : "");
      vs.forEach(function (a) { known[a.id] = 1; }); known._ready = 1;
      if (focusId) { var f = b.querySelector(".ss-ab[data-id=\"" + focusId + "\"]"); if (f) f.focus(); }
    }
    body.al.addEventListener("click", function (e) {
      var t = e.target.closest("[data-take]"), g = e.target.closest("[data-go]"), a = e.target.closest(".ss-ab");
      if (t && !p.up) { p.own[t.dataset.take] = 1; renderList(); renderRep(); say("Alert taken: " + A(t.dataset.take).name); env.save(); var f = body.al.querySelector("[data-go]"); if (f) f.focus(); }
      else if (g) { tab("rp", true); env.save(); }
      else if (a) { p.sel = a.dataset.id; renderList(p.sel); renderRep(); env.save(); }
    });

    /* ---- case report ---- */
    function renderRep() {
      var b = body.rp, a = A(p.sel);
      if (!a) { b.innerHTML = "<p class=\"ss-empty\">Pick an alert in the queue first.</p>"; return; }
      if (!p.own[a.id]) { b.innerHTML = "<p class=\"ss-empty\">Take the alert &ldquo;" + esc(a.name) + "&rdquo; from the queue before you work on it.</p><button type=\"button\" class=\"ss-btn pri\" data-take=\"" + esc(a.id) + "\"" + (p.up ? " disabled" : "") + ">Take this alert</button>"; return; }
      var r = rr(p, a.id), dis = r.d || p.up ? " disabled" : "";
      b.innerHTML = "<form class=\"ss-f\" autocomplete=\"off\" novalidate><p class=\"px-hint\" style=\"margin:0\">Case report for <b>" + esc(a.name) + "</b> (" + esc(a.t) + ", " + esc(a.host) + ")</p>" +
        "<div class=\"ss-g2\"><label>Classification<select id=\"ss-c\"" + dis + ">" + opts([["tp", "True positive"], ["fp", "False positive"]], r.c, "Choose...") + "</select></label>" +
        "<label>Severity<select id=\"ss-s\"" + dis + ">" + opts(SEV.map(function (s) { return [s, s.charAt(0).toUpperCase() + s.slice(1)]; }), r.s, "Choose...") + "</select></label></div>" +
        "<div class=\"ss-g2\"><label>Escalate to Tier 2?<select id=\"ss-e\"" + dis + ">" + opts([["y", "Yes, escalate"], ["n", "No, close it"]], r.e, "Choose...") + "</select></label>" +
        "<label>Recommended action<select id=\"ss-a\"" + dis + ">" + opts(ACT, r.a, "Choose...") + "</select></label></div>" +
        "<label>MITRE ATT&amp;CK technique<select id=\"ss-t\"" + dis + ">" + opts(TECH.map(function (t) { return [t[0], t[0] + " " + t[1]]; }), r.t, "Choose...") + "</select></label>" +
        "<label>Affected host or user<input id=\"ss-h\" type=\"text\" maxlength=\"120\" value=\"" + esc(r.h) + "\" spellcheck=\"false\"" + dis + "></label>" +
        "<p class=\"px-hint\" style=\"margin:0\">Indicators of compromise (IOCs). Separate several with spaces or commas. Defanged is fine, like 203.0.113[.]7.</p><div class=\"ss-g2\">" +
        IOCK.map(function (k) { return "<label>" + k[1] + "<input data-i=\"" + k[0] + "\" type=\"text\" maxlength=\"200\" value=\"" + esc(r.i[k[0]]) + "\" spellcheck=\"false\"" + dis + "></label>"; }).join("") + "</div>" +
        "<label>Summary <small>(not scored; write it like a real handoff)</small><textarea id=\"ss-n\" maxlength=\"600\"" + dis + ">" + esc(r.n) + "</textarea></label>" +
        "<p class=\"ss-msg\" id=\"ss-m\" role=\"alert\"></p><div class=\"ss-row\"><button type=\"submit\" class=\"ss-btn pri\"" + dis + ">" + (r.d ? "Submitted" : "Submit case report") + "</button></div></form>";
      if (p.up && !r.d) b.querySelector("#ss-m").textContent = "Time is up for this scenario. Your answers so far are saved.";
    }
    body.rp.addEventListener("input", function (e) {
      var t = e.target, r = A(p.sel) && rr(p, p.sel); if (!r || r.d || p.up) return;
      if (t.id === "ss-c") r.c = t.value; else if (t.id === "ss-s") r.s = t.value; else if (t.id === "ss-e") r.e = t.value; else if (t.id === "ss-a") r.a = t.value;
      else if (t.id === "ss-t") r.t = t.value; else if (t.id === "ss-h") r.h = t.value.slice(0, 120); else if (t.id === "ss-n") r.n = t.value.slice(0, 600);
      else if (t.dataset.i) r.i[t.dataset.i] = t.value.slice(0, 200); else return;
      env.save();
    });
    body.rp.addEventListener("click", function (e) { var t = e.target.closest("[data-take]"); if (t && !p.up) { p.own[t.dataset.take] = 1; renderList(); renderRep(); say("Alert taken."); env.save(); } });
    body.rp.addEventListener("submit", function (e) {
      e.preventDefault();
      var a = A(p.sel), r = a && rr(p, a.id), m = body.rp.querySelector("#ss-m");
      if (!a || r.d || p.up) return;
      if (!r.c || !r.e) { m.textContent = "Choose a classification and whether to escalate before you submit."; return; }
      r.d = 1; p.sub[a.id] = p.el; renderList(); renderRep(); say("Case report submitted for " + a.name + ". " + (r.e === "y" ? "Escalated." : "Closed.")); env.save();
    });

    /* ---- SIEM ---- */
    body.si.innerHTML = "<form class=\"ss-q\" autocomplete=\"off\"><label class=\"ss-sr\" for=\"ss-qi\">Search</label><input id=\"ss-qi\" type=\"text\" maxlength=\"" + MAX_Q + "\" spellcheck=\"false\" placeholder=\"index=win EventCode=4625 | stats count by user\" value=\"" + esc(p.lq) + "\">" +
      "<div class=\"ss-g2\"><label class=\"ss-sr\" for=\"ss-qr\">Time range</label><select id=\"ss-qr\">" + opts(Object.keys(RANGES).map(function (k) { return [k, RANGES[k][0]]; }), p.lr) + "</select><button type=\"submit\" class=\"ss-btn pri\">Search</button></div></form>" +
      "<p class=\"px-hint\" style=\"margin:8px 0 0\">Supported: index= sourcetype= field=value (* wildcard), free words, AND OR NOT, brackets, then | stats count by f, | table f1 f2, | sort -f, | head N. Fields: _time, host, user and more. Up to " + MAX_QRY + " searches.</p>" +
      (q.suggestq && q.suggestq.length ? "<div class=\"ss-chips\" style=\"margin-top:8px\" role=\"group\" aria-label=\"Search suggestions\">" + q.suggestq.map(function (s) { return "<button type=\"button\" class=\"ss-chip\" data-c=\"" + esc(s) + "\">" + esc(s) + "</button>"; }).join("") + "</div>" : "") +
      "<div class=\"ss-res\" id=\"ss-res\" aria-live=\"polite\"></div>";
    var qi = body.si.querySelector("#ss-qi"), qr = body.si.querySelector("#ss-qr"), res = body.si.querySelector("#ss-res");
    function showRes(parsed, range) {
      var r = runSearch(q, parsed, range), now = secs(q.now), span = RANGES[range][1];
      res.textContent = "";
      var shown = r.rows.slice(0, MAX_ROWS), pipes = parsed.pipes.length;
      res.appendChild(el("p", "ss-cnt", r.total + (r.total === 1 ? " event" : " events") + " matched" + (pipes ? " · " + r.rows.length + " result" + (r.rows.length === 1 ? "" : "s") : "") + (r.rows.length > MAX_ROWS ? " · showing the first " + MAX_ROWS : "")));
      if (r.total) {   /* event-count histogram: 12 bars, growing in when motion is on */
        var lo = span ? now - span : Math.min.apply(null, r.stamps), hi = span ? now : Math.max.apply(null, r.stamps), n = 12, cnt = [], mx = 1, i, w = Math.max(1, hi - lo + 1);
        for (i = 0; i < n; i++) cnt.push(0);
        r.stamps.forEach(function (t) { var k = Math.min(n - 1, Math.floor((t - lo) * n / w)); if (k >= 0) cnt[k]++; });
        cnt.forEach(function (c) { if (c > mx) mx = c; });
        var hs = el("div", "ss-hist"); hs.setAttribute("role", "img"); hs.setAttribute("aria-label", "Events over time, " + n + " bars from " + hms(lo) + " to " + hms(hi) + ", busiest bar " + mx + " events");
        var bars = cnt.map(function (c) { var b = el("i"); b.style.transform = "scaleY(" + (motion ? 0 : Math.max(c / mx, c ? .06 : .02)) + ")"; hs.appendChild(b); return [b, Math.max(c / mx, c ? .06 : .02)]; });
        res.appendChild(hs);
        if (motion) requestAnimationFrame(function () { requestAnimationFrame(function () { bars.forEach(function (b) { b[0].style.transform = "scaleY(" + b[1] + ")"; }); }); });
      }
      if (r.rows.length) {
        var wrap = el("div", "ss-tw"), tb = el("table"), th = el("tr");
        wrap.tabIndex = 0; wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", "Search results");
        r.cols.forEach(function (c) { var h = el("th", "", c); h.scope = "col"; th.appendChild(h); });
        tb.appendChild(el("thead")).appendChild(th);
        var tbd = el("tbody");
        shown.forEach(function (row) { var tr = el("tr"); r.cols.forEach(function (c) { tr.appendChild(el("td", c === "_raw" ? "raw" : "", has(row, c) ? row[c] : "")); }); tbd.appendChild(tr); });
        tb.appendChild(tbd); wrap.appendChild(tb); res.appendChild(wrap);
      }
    }
    function search(logIt) {
      var s = qi.value.replace(/\s+/g, " ").trim(), parsed = parseQuery(s), range = qr.value;
      if (parsed.err) { res.textContent = ""; var m = el("p", "ss-msg", parsed.err); m.setAttribute("role", "alert"); res.appendChild(m); return; }
      if (logIt) {
        if (p.up) return;
        if (p.act.filter(function (a) { return a.k === "q"; }).length >= MAX_QRY) { res.textContent = ""; res.appendChild(el("p", "ss-msg", "Search limit reached (" + MAX_QRY + ").")); return; }
        p.act.push({ k: "q", s: s + "\u0001" + range }); p.lq = s; p.lr = range; env.save();
      }
      showRes(parsed, range);
    }
    body.si.querySelector("form").addEventListener("submit", function (e) { e.preventDefault(); search(true); });
    body.si.addEventListener("click", function (e) { var c = e.target.closest(".ss-chip"); if (c) { qi.value = c.dataset.c; qi.focus(); } });

    /* ---- analyst VM ---- */
    body.vm.innerHTML = "<p class=\"px-hint\" style=\"margin:0 0 8px\">Type a command and press " + kb("Enter") + ", or tap a suggestion. " + kb("↑") + " recalls the last command. Type " + kb("help") + " to see them all.</p>" +
      "<div class=\"ss-term\"><div class=\"ss-scr\" role=\"log\" aria-live=\"polite\" tabindex=\"0\" aria-label=\"Analyst VM output\"></div><form autocomplete=\"off\"><span class=\"ss-ps\">" + esc(user) + "$</span><input type=\"text\" id=\"ss-ci\" aria-label=\"Command\" maxlength=\"" + MAX_CMD_LEN + "\" spellcheck=\"false\" autocapitalize=\"off\"><button type=\"submit\">Run</button></form></div>" +
      (q.suggest && q.suggest.length ? "<div class=\"ss-chips\" style=\"margin-top:8px\" role=\"group\" aria-label=\"Command suggestions\">" + q.suggest.map(function (s) { return "<button type=\"button\" class=\"ss-chip\" data-c=\"" + esc(s) + "\">" + esc(s) + "</button>"; }).join("") + "</div>" : "") +
      "<div class=\"ss-tool\"><form id=\"ss-ti\" autocomplete=\"off\"><label class=\"ss-sr\" for=\"ss-tii\">Threat-intel lookup</label><input id=\"ss-tii\" type=\"text\" maxlength=\"200\" placeholder=\"Threat intel: IP, domain or file hash\" spellcheck=\"false\"><button type=\"submit\" class=\"ss-btn\">Look up</button></form>" +
      "<form id=\"ss-dc\" class=\"dec\" autocomplete=\"off\"><label class=\"ss-sr\" for=\"ss-dk\">Decode tool</label><select id=\"ss-dk\">" + opts(DEC, "b64") + "</select><label class=\"ss-sr\" for=\"ss-di\">Text to convert</label><input id=\"ss-di\" type=\"text\" maxlength=\"500\" placeholder=\"Text to convert\" spellcheck=\"false\"><button type=\"submit\" class=\"ss-btn\">Run</button></form></div>";
    var scr = body.vm.querySelector(".ss-scr"), ci = body.vm.querySelector("#ss-ci"), hi = -1;
    function line(t, cls) { var d = el("div", cls || "", t); scr.appendChild(d); scr.scrollTop = scr.scrollHeight; }
    function cnt(k) { return p.act.filter(function (a) { return a.k === k; }).length; }
    function full(k, max, name) { if (p.up) { line("Time is up for this scenario.", "e"); return true; } if (cnt(k) >= max) { line(name + " limit reached (" + max + ").", "e"); return true; } return false; }
    line(q.intro || (user + " · type help"));
    p.act.forEach(function (a) {
      if (a.k === "c") { var o = runCmd(q, a.s); line(user + "$ " + a.s, "c"); line(o.out, o.bad ? "e" : ""); }
      else if (a.k === "t") { line("ti> " + a.s, "t"); line(tiText(q, a.s)); }
      else if (a.k === "d") { var kd = a.s.split(":")[0], src = a.s.slice(kd.length + 1); line(kd + "> " + short(src, 80), "t"); line(decode(kd, src)); }
    });
    body.vm.querySelector(".ss-term form").addEventListener("submit", function (e) {
      e.preventDefault();
      var s = ci.value.replace(/\s+/g, " ").trim(); if (!s || full("c", MAX_CMDS, "Command")) { ci.value = ""; return; }
      p.act.push({ k: "c", s: s }); var o = runCmd(q, s); line(user + "$ " + s, "c"); line(o.out, o.bad ? "e" : ""); ci.value = ""; hi = -1; env.save();
    });
    ci.addEventListener("keydown", function (e) {
      var h = p.act.filter(function (a) { return a.k === "c"; }).map(function (a) { return a.s; });
      if (e.key === "ArrowUp" && h.length) { e.preventDefault(); hi = hi < 0 ? h.length - 1 : Math.max(0, hi - 1); ci.value = h[hi]; }
      else if (e.key === "ArrowDown" && hi >= 0) { e.preventDefault(); hi++; if (hi >= h.length) { hi = -1; ci.value = ""; } else ci.value = h[hi]; }
    });
    body.vm.addEventListener("click", function (e) { var c = e.target.closest(".ss-chip"); if (c) { ci.value = c.dataset.c; ci.focus(); } });
    body.vm.querySelector("#ss-ti").addEventListener("submit", function (e) {
      e.preventDefault();
      var f = body.vm.querySelector("#ss-tii"), s = f.value.replace(/\s+/g, " ").trim(); if (!s || full("t", MAX_TI, "Lookup")) return;
      p.act.push({ k: "t", s: s }); line("ti> " + s, "t"); line(tiText(q, s)); f.value = ""; env.save();
    });
    body.vm.querySelector("#ss-dc").addEventListener("submit", function (e) {
      e.preventDefault();
      var f = body.vm.querySelector("#ss-di"), kd = body.vm.querySelector("#ss-dk").value, s = f.value.trim().slice(0, 500); if (!s || !pair(DEC, kd) || full("d", MAX_DEC, "Decode")) return;
      p.act.push({ k: "d", s: kd + ":" + s }); line(kd + "> " + short(s, 80), "t"); line(decode(kd, s)); f.value = ""; env.save();
    });

    /* ---- time: scenario clock, countdown, alerts arriving ---- */
    function lock() {
      p.up = 1; host.querySelector("#ss-cd").textContent = "Scenario time is up"; say("Time is up for this scenario. Your answers so far are saved.");
      host.querySelectorAll(".ss-pane input,.ss-pane select,.ss-pane textarea,.ss-pane button[type=submit],[data-take]").forEach(function (x) { x.disabled = true; });
      renderRep(); env.save();
    }
    function step() {
      if (!host.isConnected) { stop(); return; }
      if (document.hidden || p.up) return;
      p.el++;
      host.querySelector("#ss-clock").textContent = clockText();
      var cd = host.querySelector("#ss-cd"); cd.textContent = "Scenario time left " + left(); cd.classList.toggle("low", lim - p.el <= 60);
      var fresh = visible().filter(function (a) { return !known[a.id]; });
      if (fresh.length) {
        if (p.tab !== "al") { unseen += fresh.length; badge(); }
        var sel0 = p.sel;
        renderList(document.activeElement && document.activeElement.classList.contains("ss-ab") ? document.activeElement.dataset.id : "");
        if (sel0 !== p.sel) renderRep();
        say(fresh.map(function (a) { return "New alert: " + a.name + ", severity " + a.sev; }).join(". "));
      }
      if (p.el >= lim) lock();
      else if (++nsave % 5 === 0) env.save();
    }
    if (p.up) { host.querySelectorAll("input,select,textarea").forEach(function (x) { x.disabled = true; }); }
    renderList(); renderRep(); tab(p.tab);
    if (p.up) { host.querySelectorAll(".ss-pane input,.ss-pane select,.ss-pane textarea,.ss-pane button[type=submit]").forEach(function (x) { x.disabled = true; }); host.querySelector("#ss-cd").textContent = "Scenario time is up"; }
    if (p.lq && !parseQuery(p.lq).err) { qi.value = p.lq; showRes(parseQuery(p.lq), p.lr); }
    if (!p.up) {
      cur.timer = setInterval(step, 1000);
      cur.vis = function () { host.classList.toggle("ss-paused", document.hidden); };
      document.addEventListener("visibilitychange", cur.vis);
    }
  }

  window.SOCSIM = { v: 1, kinds: ["socsim"], valid: valid, newItem: newItem, ok: ok, answered: answered, parts: parts, score: score, review: review, render: render, parseQuery: parseQuery, tech: TECH };
})();
