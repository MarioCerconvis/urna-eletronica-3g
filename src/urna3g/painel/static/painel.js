"use strict";
/* Painel ao vivo do urna3g — sem dependências externas. */

const $ = (s, r = document) => r.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const fmt = new Intl.NumberFormat("pt-BR");
const reduzMov = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function svg(tag, attrs = {}, pai) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (pai) pai.appendChild(el);
  return el;
}

const ICONES = {
  eleicao: '<path d="M4 8h12v8H4zM7 8V5h6v3M8 12h4"/>',
  blockchain: '<path d="M10 2l7 4v8l-7 4-7-4V6z"/><path d="M3 6l7 4 7-4M10 10v8"/>',
  rede: '<circle cx="5" cy="10" r="2"/><circle cx="15" cy="5" r="2"/><circle cx="15" cy="15" r="2"/><path d="M7 9l6-3M7 11l6 3"/>',
  maquina: '<rect x="3" y="4" width="14" height="9" rx="1.5"/><path d="M7 16h6M10 13v3"/>',
  sistema: '<circle cx="10" cy="10" r="3"/><path d="M10 2v3M10 15v3M2 10h3M15 10h3M4.3 4.3l2.1 2.1M13.6 13.6l2.1 2.1M4.3 15.7l2.1-2.1M13.6 6.4l2.1-2.1"/>',
};
const SITUACAO = {
  produzindo: { txt: "Produzindo", ic: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="currentColor"/><path d="M6 10l3 3 5-6" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round"/></svg>' },
  lenta: { txt: "Lenta", ic: '<svg viewBox="0 0 20 20"><path d="M10 2l9 16H1z" fill="currentColor"/><path d="M10 8v4M10 14.5v.5" stroke="#111" stroke-width="2" stroke-linecap="round"/></svg>' },
  travada: { txt: "Sem novos blocos", ic: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="currentColor"/><path d="M7.5 6.5v7M12.5 6.5v7" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>' },
  parada: { txt: "Parada · sem quórum", ic: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="currentColor"/><path d="M6.5 6.5l7 7M13.5 6.5l-7 7" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>' },
  sem_conexao: { txt: "Sem conexão", ic: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="currentColor"/><path d="M6 10h8" stroke="#fff" stroke-width="2" stroke-linecap="round"/></svg>' },
};
const FASES = ["aguardando", "votando", "encerrada", "apurando", "boletim", "ancorando", "ancorado"];
const FASE_TXT = {
  aguardando: "Aguardando abertura", votando: "Votando", encerrada: "Votação encerrada", apurando: "Apurando",
  boletim: "Boletim assinado", ancorando: "Ancorando na blockchain", ancorado: "Ancorado", erro: "Falhou",
};
const FASE_COR = { aguardando: "var(--neutro)", votando: "var(--acento)", encerrada: "var(--acento)", apurando: "var(--violeta)",
  boletim: "var(--aqua)", ancorando: "var(--aviso)", ancorado: "var(--ok)", erro: "var(--critico)" };

/* ------------------------------------------------------------------ estado */
const S = {
  est: null, eventos: [], vistos: new Set(), filtro: "todos", pausado: false, fila: [],
  sel: null, hover: null, pos: {}, nosEl: {}, ultimoBloco: 0, particulas: [], cont: {},
};

/* ------------------------------------------------------------------ tema e relógio */
(function tema() {
  let salvo = null;
  try { salvo = localStorage.getItem("urna3g-tema"); } catch (_) { /* sem storage */ }
  if (salvo) document.documentElement.dataset.theme = salvo;
  $("#btn-tema").addEventListener("click", () => {
    const atual = document.documentElement.dataset.theme
      || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    const novo = atual === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = novo;
    try { localStorage.setItem("urna3g-tema", novo); } catch (_) { /* ok */ }
  });
})();
setInterval(() => {
  $("#relogio").textContent = new Date().toLocaleTimeString("pt-BR");
  document.querySelectorAll(".ev-t").forEach((el) => { el.textContent = haQuanto(+el.dataset.ts); });
}, 1000);
function haQuanto(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 5) return "agora";
  if (s < 60) return `há ${Math.floor(s)} s`;
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  return new Date(ts * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}
function toast(msg, erro = false) {
  const t = document.createElement("div");
  t.className = "toast" + (erro ? " erro" : "");
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4500);
}

/* ------------------------------------------------------------------ conexão ao vivo */
function conectar() {
  const fonte = new EventSource("/api/stream");
  const c = $("#conexao");
  fonte.onopen = () => { c.className = "conexao ao-vivo"; $(".txt", c).textContent = "Ao vivo"; };
  fonte.onerror = () => { c.className = "conexao erro"; $(".txt", c).textContent = "Reconectando…"; };
  fonte.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.t === "estado") aplicarEstado(d);
    else if (d.t === "evento") novoEvento(d);
    else if (d.t === "historico") d.eventos.forEach(novoEvento);
    else if (d.t === "bloco") animarBloco(d);
  };
}

function aplicarEstado(e) {
  S.est = e;
  $("#nome-modo").textContent = e.nome;
  $("#ponte").textContent = e.modo === "cluster"
    ? `ponte ${e.ponte.host}${e.ponte.ativo ? "" : " (desconectada)"}` : "contêineres neste computador";
  if (!e.ponte.ativo && e.modo === "cluster") {
    const c = $("#conexao"); c.className = "conexao erro"; $(".txt", c).textContent = "Cluster inacessível";
  } else if ($("#conexao").classList.contains("erro") && e.ponte.ativo) {
    const c = $("#conexao"); c.className = "conexao ao-vivo"; $(".txt", c).textContent = "Ao vivo";
  }
  renderKpis(e);
  renderGrafo(e);
  renderCadeia(e.rede.blocos);
  renderSecoes(e);
  renderResultados(e.eleicao);
  if (S.sel) renderGaveta();
  const b = $("#btn-ensaio");
  b.classList.toggle("parar", e.ensaio_ativo);
  $("span", b).textContent = e.ensaio_ativo ? "Parar ensaio" : "Iniciar ensaio";
  b.querySelector("svg").innerHTML = e.ensaio_ativo ? '<rect x="5" y="5" width="10" height="10" rx="1.5"/>' : '<path d="M6 4l10 6-10 6z"/>';
}

/* ------------------------------------------------------------------ KPIs */
function renderKpis(e) {
  const r = e.rede;
  $("#k-altura").textContent = r.altura ? fmt.format(r.altura) : "—";
  const ult = r.blocos.length ? r.blocos[r.blocos.length - 1] : null;
  $("#k-altura-nota").textContent = ult ? `último bloco ${haQuanto(ult.ts)}` : "aguardando blocos";
  $("#k-ritmo").textContent = r.ritmo == null ? "—" : Math.round(r.ritmo);
  $("#k-ritmo-nota").textContent = `esperado ${Math.round(r.esperado)}/min · janela de 60 s`;
  desenharSpark(r.serie, r.esperado);
  $("#k-vivos").textContent = `${r.vivos}/${r.total}`;
  $("#k-vivos-unid").textContent = "no ar";
  const med = $("#k-medidor");
  if (med.children.length !== r.total + 1) {
    med.innerHTML = "";
    for (let i = 0; i < r.total; i++) med.appendChild(document.createElement("span"));
    const m = document.createElement("i"); m.className = "marca-quorum"; med.appendChild(m);
  }
  [...med.querySelectorAll("span")].forEach((s, i) => s.classList.toggle("on", i < r.vivos));
  $(".marca-quorum", med).style.left = `calc(${(r.quorum / r.total) * 100}% - 1px)`;
  const margem = r.vivos - r.quorum;
  $("#k-quorum").textContent = margem >= 0
    ? `quórum ${r.quorum} · aguenta mais ${margem} ${margem === 1 ? "queda" : "quedas"}`
    : `quórum ${r.quorum} · faltam ${-margem} para voltar`;
  const sit = SITUACAO[r.situacao] || SITUACAO.sem_conexao;
  const pill = $("#k-situacao");
  pill.dataset.s = r.situacao;
  $(".ic", pill).innerHTML = sit.ic;
  $(".txt", pill).textContent = sit.txt;
  $("#k-situacao-nota").textContent = r.situacao === "travada" && r.parada_ha ? `sem blocos há ${Math.round(r.parada_ha)} s`
    : r.situacao === "parada" ? `${r.vivos} de ${r.total} no ar; mínimo ${r.quorum}`
    : r.situacao === "lenta" ? "consenso esperando nós fora da vez" : "1 bloco a cada 2 s";
  const el = e.eleicao;
  const secoes = Object.values(el.secoes || {});
  const anc = secoes.filter((s) => s.fase === "ancorado").length;
  const total = el.total_secoes || secoes.length;
  const faseTxt = { sem_eleicao: "Sem eleição", preparando: "Preparando…", votacao: "Em andamento", encerrada: "Encerrada" }[el.fase] || el.fase;
  $("#k-eleicao").textContent = faseTxt;
  $("#k-eleicao-barra").style.width = total ? `${(anc / total) * 100}%` : "0";
  $("#k-eleicao-nota").textContent = total ? `${anc} de ${total} seções ancoradas` : "inicie um ensaio para acompanhar";
  const ced = secoes.reduce((a, s) => a + (s.cedulas || 0), 0);
  const apu = secoes.reduce((a, s) => a + (s.apuradas || s.cedulas_apuradas || 0), 0);
  $("#k-cedulas").textContent = fmt.format(ced);
  $("#k-cedulas-nota").textContent = ced ? `${fmt.format(apu)} apuradas` : "emitidas no ensaio";
}

function desenharSpark(serie, esperado) {
  const el = $("#k-spark");
  if (!serie || serie.length < 3) { el.innerHTML = ""; return; }
  const pts = [];
  for (let i = 10; i < serie.length; i += 5) {
    const [t1, h1] = serie[i], [t0, h0] = serie[i - 10];
    if (t1 - t0 > 0) pts.push([t1, ((h1 - h0) * 60) / (t1 - t0)]);
  }
  if (pts.length < 2) { el.innerHTML = ""; return; }
  const W = 200, H = 40, tmin = pts[0][0], tmax = pts[pts.length - 1][0] || 1;
  const vmax = Math.max(esperado * 1.25, ...pts.map((p) => p[1]));
  const x = (t) => ((t - tmin) / (tmax - tmin || 1)) * W;
  const y = (v) => H - (v / vmax) * (H - 4) - 2;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  el.innerHTML = `<line class="ref" x1="0" x2="${W}" y1="${y(esperado)}" y2="${y(esperado)}"/>
    <path class="area" d="${d}L${W},${H}L0,${H}Z"/><path class="linha" d="${d}"/>`;
  el.onmousemove = (ev) => {
    const r = el.getBoundingClientRect();
    const t = tmin + ((ev.clientX - r.left) / r.width) * (tmax - tmin);
    const p = pts.reduce((a, b) => (Math.abs(b[0] - t) < Math.abs(a[0] - t) ? b : a));
    $("#k-ritmo-nota").textContent = `${Math.round(p[1])}/min ${Math.abs(Math.round(p[0])) < 3 ? "agora" : `há ${Math.abs(Math.round(p[0]))} s`}`;
  };
  el.onmouseleave = () => { $("#k-ritmo-nota").textContent = `esperado ${Math.round(esperado)}/min · janela de 60 s`; };
}

/* ------------------------------------------------------------------ grafo */
const CX = 450, CY = 318;
function layout(n) {
  const R = n <= 4 ? 190 : n <= 8 ? 230 : 250;
  const pos = {};
  return (lista) => {
    lista.forEach((no, i) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / lista.length;
      pos[no.id] = { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
    });
    return pos;
  };
}
function estadoVisual(no, altura) {
  if (no.estado === "fora") return "fora";
  if (no.estado !== "no_ar") return "desconhecido";
  if (altura && no.bloco != null && altura - no.bloco > 2) return "sync";
  return "no_ar";
}
function faseDoNo(e, nid) {
  return Object.values(e.eleicao.secoes || {}).find((s) => s.no === nid);
}

function renderGrafo(e) {
  const nos = [...e.nos].sort((a, b) => a.indice - b.indice);
  if (Object.keys(S.pos).length !== nos.length) {
    S.pos = layout(nos.length)(nos);
    $("#camada-nos").innerHTML = ""; S.nosEl = {};
    desenharCentro();
  }
  // arestas (conjunto não direcionado das conexões reais)
  const pares = new Set();
  nos.forEach((n) => n.pares.forEach((p) => { if (S.pos[p]) pares.add([n.id, p].sort().join("|")); }));
  const ga = $("#camada-arestas");
  const existentes = new Map([...ga.children].map((l) => [l.dataset.k, l]));
  pares.forEach((k) => {
    if (!existentes.has(k)) {
      const [a, b] = k.split("|");
      const l = svg("line", { class: "aresta", x1: S.pos[a].x, y1: S.pos[a].y, x2: S.pos[b].x, y2: S.pos[b].y }, ga);
      l.dataset.k = k; l.dataset.a = a; l.dataset.b = b;
    }
    existentes.delete(k);
  });
  existentes.forEach((l) => l.remove());
  // nós
  nos.forEach((n) => {
    let g = S.nosEl[n.id];
    const p = S.pos[n.id];
    if (!g) g = S.nosEl[n.id] = criarNo(n, p);
    g.dataset.e = estadoVisual(n, e.rede.altura);
    $(".rot", g).textContent = n.rotulo;
    $(".rot-sub", g).textContent = `nó ${n.indice}`;
    const anel = $(".anel", g);
    if (n.mem_total) {
      const frac = Math.min(1, n.mem_usada / n.mem_total), C = 2 * Math.PI * 38;
      anel.style.display = ""; $(".anel-fundo", g).style.display = "";
      anel.setAttribute("stroke-dasharray", `${C}`);
      anel.setAttribute("stroke-dashoffset", `${C * (1 - frac)}`);
    } else { anel.style.display = "none"; $(".anel-fundo", g).style.display = "none"; }
    atualizarPill(g, faseDoNo(e, n.id), n);
    g.classList.toggle("selecionado", S.sel === n.id);
  });
  $("#centro-num").textContent = e.rede.altura ? fmt.format(e.rede.altura) : "—";
  $("#centro-val").textContent = `${e.rede.vivos}/${e.rede.validadores} validadores`;
  aplicarRealce();
}

function desenharCentro() {
  const c = $("#camada-centro"); c.innerHTML = "";
  svg("circle", { class: "centro-disco", cx: CX, cy: CY, r: 110 }, c);
  svg("rect", { class: "centro-caixa", x: CX - 78, y: CY - 52, width: 156, height: 104, rx: 18 }, c);
  const cubo = svg("g", { transform: `translate(${CX - 11},${CY - 42})` }, c);
  svg("path", { class: "centro-cubo", d: "M11 1l10 5.5v11L11 23 1 17.5v-11z M1 6.5L11 12l10-5.5 M11 12v11" }, cubo);
  svg("text", { class: "centro-num", x: CX, y: CY + 14, id: "centro-num" }, c).textContent = "—";
  svg("text", { class: "centro-rot", x: CX, y: CY + 36, id: "centro-val" }, c).textContent = "bloco atual";
}

function criarNo(n, p) {
  const g = svg("g", { class: "no", transform: `translate(${p.x},${p.y})`, tabindex: 0, role: "button",
    "aria-label": `Máquina ${n.rotulo}` }, $("#camada-nos"));
  g.dataset.id = n.id;
  svg("circle", { class: "pulso", r: 32 }, g).style.transformOrigin = "0 0";
  svg("circle", { class: "anel-fundo", r: 38 }, g);
  svg("circle", { class: "anel", r: 38, transform: "rotate(-90)" }, g);
  svg("circle", { class: "disco", r: 30 }, g);
  svg("text", { class: "rot", y: -3 }, g);
  svg("text", { class: "rot-sub", y: 14 }, g);
  const x = svg("g", { class: "x-fora", transform: "translate(20,-22)" }, g);
  svg("path", { d: "M-4,-4L4,4M4,-4L-4,4" }, x);
  const pill = svg("g", { class: "pill-fase", transform: "translate(0,56)" }, g);
  svg("rect", { rx: 9, height: 20, y: -10 }, pill);
  svg("circle", { class: "bola", r: 4 }, pill);
  svg("text", {}, pill);
  g.addEventListener("mouseenter", (ev) => { S.hover = n.id; aplicarRealce(); mostrarTooltip(n.id, ev); });
  g.addEventListener("mousemove", (ev) => mostrarTooltip(n.id, ev));
  g.addEventListener("mouseleave", () => { S.hover = null; aplicarRealce(); $("#tooltip").hidden = true; });
  g.addEventListener("click", () => abrirGaveta(n.id));
  g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrirGaveta(n.id); } });
  return g;
}

function atualizarPill(g, sec, n) {
  const pill = $(".pill-fase", g);
  let txt, cor;
  if (sec) {
    const extra = sec.fase === "votando" ? ` ${sec.cedulas || 0}` : sec.fase === "apurando" ? ` ${sec.apuradas || 0}/${sec.cedulas || 0}` : sec.fase === "ancorado" ? " ✓" : "";
    txt = `Seção ${sec.secao} · ${({ aguardando: "aguardando", votando: "votando", encerrada: "encerrada", apurando: "apurando", boletim: "boletim", ancorando: "ancorando", ancorado: "ancorada" })[sec.fase] || sec.fase}${extra}`;
    cor = FASE_COR[sec.fase];
  } else {
    txt = n.estado === "fora" ? "fora do ar" : n.propostos ? `${n.propostos} blocos propostos` : "validador";
    cor = n.estado === "fora" ? "var(--critico)" : "var(--neutro)";
  }
  const t = $("text", pill);
  t.textContent = txt;
  const w = Math.max(60, txt.length * 6.3 + 26);
  $("rect", pill).setAttribute("width", w); $("rect", pill).setAttribute("x", -w / 2);
  $(".bola", pill).setAttribute("cx", -w / 2 + 11); $(".bola", pill).setAttribute("fill", cor);
  t.setAttribute("x", -w / 2 + 20);
}

function aplicarRealce() {
  const alvo = S.hover || S.sel;
  const svgEl = $("#grafo");
  svgEl.classList.toggle("esmaecido", !!alvo);
  document.querySelectorAll(".aresta").forEach((l) => l.classList.toggle("realce", !!alvo && (l.dataset.a === alvo || l.dataset.b === alvo)));
  const vizinhos = new Set(alvo ? [alvo] : []);
  if (alvo) document.querySelectorAll(".aresta.realce").forEach((l) => { vizinhos.add(l.dataset.a); vizinhos.add(l.dataset.b); });
  Object.entries(S.nosEl).forEach(([id, g]) => g.classList.toggle("realce", vizinhos.has(id)));
  document.querySelectorAll(".secao").forEach((li) => li.classList.toggle("realce", li.dataset.no === alvo));
}

function mostrarTooltip(id, ev) {
  const n = S.est.nos.find((x) => x.id === id);
  if (!n) return;
  const tt = $("#tooltip"), wrap = $(".grafo-wrap").getBoundingClientRect();
  const sec = faseDoNo(S.est, id);
  tt.innerHTML = `<b>${esc(n.rotulo)} · nó ${n.indice}</b>
    <dl><dt>Estado</dt><dd>${({ no_ar: "no ar", fora: "fora do ar", desconhecido: "?" })[n.estado]}</dd>
    <dt>Bloco</dt><dd>${n.bloco != null ? fmt.format(n.bloco) : "—"}</dd>
    <dt>Conexões</dt><dd>${n.pares.length}</dd>
    <dt>Blocos propostos</dt><dd>${n.propostos}</dd>
    ${n.mem_total ? `<dt>Memória</dt><dd>${n.mem_usada.toFixed(1)} / ${n.mem_total.toFixed(1)} GB</dd>` : ""}
    ${n.besu_mem ? `<dt>Besu</dt><dd>${esc(n.besu_mem)}</dd>` : ""}
    ${sec ? `<dt>Seção ${esc(sec.secao)}</dt><dd>${FASE_TXT[sec.fase] || sec.fase}</dd>` : ""}</dl>`;
  tt.hidden = false;
  let x = ev.clientX - wrap.left + 16, y = ev.clientY - wrap.top + 16;
  if (x + 230 > wrap.width) x -= 250;
  if (y + 190 > wrap.height) y -= 200;
  tt.style.left = `${x}px`; tt.style.top = `${y}px`;
}

/* ------------------------------------------------------------------ animação dos blocos */
function animarBloco(b) {
  if (b.num <= S.ultimoBloco) return;
  S.ultimoBloco = b.num;
  const g = b.proponente && S.nosEl[b.proponente];
  if (!g || reduzMov) return;
  const p = $(".pulso", g);
  p.classList.remove("ativo"); void p.getBoundingClientRect(); p.classList.add("ativo");
  const o = S.pos[b.proponente];
  const destinos = (b.pares && b.pares.length ? b.pares : Object.keys(S.pos).filter((k) => k !== b.proponente));
  const t0 = performance.now();
  destinos.forEach((d) => { if (S.pos[d]) S.particulas.push({ x0: o.x, y0: o.y, x1: S.pos[d].x, y1: S.pos[d].y, t0, dur: 700, r: b.txs ? 5 : 3.2 }); });
  S.particulas.push({ x0: o.x, y0: o.y, x1: CX, y1: CY, t0, dur: 600, r: b.txs ? 6 : 4 });
  if (S.particulas.length && !S.raf) S.raf = requestAnimationFrame(quadro);
}
function quadro(agora) {
  const camada = $("#camada-particulas");
  camada.innerHTML = "";
  S.particulas = S.particulas.filter((p) => agora - p.t0 < p.dur);
  S.particulas.forEach((p) => {
    const k = (agora - p.t0) / p.dur, e = 1 - Math.pow(1 - k, 3);
    svg("circle", { class: "particula", cx: p.x0 + (p.x1 - p.x0) * e, cy: p.y0 + (p.y1 - p.y0) * e, r: p.r, opacity: 1 - k * 0.6 }, camada);
  });
  S.raf = S.particulas.length ? requestAnimationFrame(quadro) : null;
}

function renderCadeia(blocos) {
  const c = $("#cadeia");
  const ult = c.lastElementChild ? +c.lastElementChild.dataset.n : 0;
  blocos.filter((b) => b.num > ult).forEach((b) => {
    const d = document.createElement("div");
    d.className = "blk" + (b.txs ? " tx" : "");
    d.dataset.n = b.num;
    d.textContent = `#${b.num}`;
    const prop = S.est.nos.find((n) => n.id === b.proponente);
    d.title = `Bloco ${b.num} · proposto por ${prop ? prop.rotulo : "?"} · ${b.txs} transação(ões)`;
    c.appendChild(d);
  });
  while (c.children.length > 22) c.firstElementChild.remove();
}

/* ------------------------------------------------------------------ linha do tempo */
function novoEvento(ev) {
  if (S.vistos.has(ev.seq)) return;
  S.vistos.add(ev.seq);
  S.cont[ev.categoria] = (S.cont[ev.categoria] || 0) + 1;
  S.cont.todos = (S.cont.todos || 0) + 1;
  Object.keys(S.cont).forEach((k) => { const b = $(`#c-${k}`); if (b) b.textContent = S.cont[k]; });
  if (S.pausado) { S.fila.push(ev); $("#btn-pausar").textContent = `Retomar (${S.fila.length})`; return; }
  inserirEvento(ev);
}
function inserirEvento(ev) {
  const feed = $("#feed");
  const li = document.createElement("li");
  li.className = "ev"; li.dataset.c = ev.categoria; li.dataset.n = ev.nivel;
  li.hidden = S.filtro !== "todos" && S.filtro !== ev.categoria;
  const chips = (ev.nos || []).map((id) => {
    const n = S.est && S.est.nos.find((x) => x.id === id);
    return `<button class="ev-no" type="button" data-no="${esc(id)}">${esc(n ? n.rotulo : id)}</button>`;
  }).join("");
  li.innerHTML = `<span class="ev-ic"><svg viewBox="0 0 20 20" aria-hidden="true">${ICONES[ev.categoria] || ICONES.sistema}</svg></span>
    <div><div class="ev-txt">${esc(ev.texto)}</div>${chips ? `<div class="ev-nos">${chips}</div>` : ""}</div>
    <time class="ev-t" data-ts="${ev.ts}" title="${new Date(ev.ts * 1000).toLocaleString("pt-BR")}">${haQuanto(ev.ts)}</time>`;
  li.addEventListener("mouseenter", () => { if (ev.nos && ev.nos[0]) { S.hover = ev.nos[0]; aplicarRealce(); } });
  li.addEventListener("mouseleave", () => { S.hover = null; aplicarRealce(); });
  feed.prepend(li);
  while (feed.children.length > 400) feed.lastElementChild.remove();
}
$("#feed").addEventListener("click", (e) => { const b = e.target.closest(".ev-no"); if (b) abrirGaveta(b.dataset.no); });
document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
  S.filtro = c.dataset.cat;
  document.querySelectorAll(".chip").forEach((x) => x.classList.toggle("ativo", x === c));
  document.querySelectorAll(".ev").forEach((li) => { li.hidden = S.filtro !== "todos" && li.dataset.c !== S.filtro; });
}));
$("#btn-pausar").addEventListener("click", (e) => {
  S.pausado = !S.pausado;
  e.currentTarget.setAttribute("aria-pressed", S.pausado);
  if (!S.pausado) { S.fila.forEach(inserirEvento); S.fila = []; }
  e.currentTarget.textContent = S.pausado ? "Retomar (0)" : "Pausar";
});

/* ------------------------------------------------------------------ seções e resultados */
function renderSecoes(e) {
  const ul = $("#secoes");
  const secoes = Object.values(e.eleicao.secoes || {}).sort((a, b) => a.secao.localeCompare(b.secao));
  $("#selo-ensaio").hidden = !e.eleicao.ensaio;
  if (!secoes.length) { ul.innerHTML = '<li class="vazio">Nenhuma eleição em andamento. Use “Iniciar ensaio”.</li>'; return; }
  if (ul.querySelector(".vazio")) ul.innerHTML = "";
  secoes.forEach((s) => {
    let li = ul.querySelector(`[data-s="${s.secao}"]`);
    if (!li) {
      li = document.createElement("li");
      li.className = "secao"; li.dataset.s = s.secao; li.tabIndex = 0;
      li.innerHTML = `<span class="num"></span><span class="maq"></span>
        <div><div class="passos">${'<span class="passo"></span>'.repeat(4)}</div><div class="fase-txt"></div></div>
        <span class="cont"></span><span class="blc"></span>`;
      li.addEventListener("mouseenter", () => { S.hover = li.dataset.no; aplicarRealce(); });
      li.addEventListener("mouseleave", () => { S.hover = null; aplicarRealce(); });
      li.addEventListener("click", () => li.dataset.no && abrirGaveta(li.dataset.no));
      ul.appendChild(li);
    }
    li.dataset.no = s.no || "";
    const n = e.nos.find((x) => x.id === s.no);
    $(".num", li).textContent = s.secao;
    $(".maq", li).textContent = n ? n.rotulo : "—";
    const i = FASES.indexOf(s.fase);
    const passos = li.querySelectorAll(".passo");
    const estadoPasso = [
      i >= 2 ? "feito" : i === 1 ? "atual" : "",
      i >= 4 ? "feito" : i === 3 || i === 2 ? "atual" : "",
      i >= 5 ? "feito" : i === 4 ? "atual" : "",
      i >= 6 ? "feito" : i === 5 ? "atual espera" : "",
    ];
    passos.forEach((p, k) => { p.className = "passo " + estadoPasso[k]; });
    let txt = FASE_TXT[s.fase] || s.fase;
    if (s.fase === "votando") txt += ` · ${s.cedulas || 0} cédulas`;
    if (s.fase === "apurando") txt += ` · ${s.apuradas || 0} de ${s.cedulas || 0}`;
    if (s.fase === "boletim" && s.hash_boletim) txt += ` · ${s.hash_boletim.slice(0, 10)}…`;
    if (s.fase === "ancorando") txt = n && n.estado !== "no_ar" ? `Aguardando ${n.rotulo} voltar ao ar` : (S.est.rede.vivos < S.est.rede.quorum ? "Aguardando quórum da rede" : "Enviando à blockchain…");
    $(".fase-txt", li).innerHTML = `<svg class="ic" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5" fill="${FASE_COR[s.fase] || "var(--neutro)"}"/></svg>${esc(txt)}`;
    $(".cont", li).textContent = fmt.format(s.cedulas_apuradas ?? s.cedulas ?? 0);
    $(".blc", li).textContent = s.bloco ? `#${s.bloco}` : "—";
  });
}

function renderResultados(el) {
  const box = $("#resultados");
  const res = el.resultados || {};
  const ids = Object.keys(res);
  if (!ids.length) { box.innerHTML = '<p class="vazio">Os resultados aparecem conforme as seções emitem boletins.</p>'; return; }
  const secoes = Object.values(el.secoes || {});
  const com = secoes.filter((s) => ["boletim", "ancorando", "ancorado"].includes(s.fase)).length;
  $("#res-sub").textContent = `Soma de ${com} de ${el.total_secoes || secoes.length} boletins assinados${el.encerrada ? " · eleição encerrada" : ""}.`;
  box.innerHTML = ids.map((cid) => {
    const r = res[cid];
    const leg = (el.legenda || {})[cid] || {};
    const cands = Object.keys(r.votos).filter((k) => k !== "branco" && k !== "nulo").sort((a, b) => +a - +b);
    const linhas = [...cands.map((k, i) => ({ nome: leg[k] || k, v: r.votos[k], cls: `s${Math.min(i + 1, 3)}` })),
      { nome: "Branco", v: r.votos.branco || 0, cls: "sn" }, { nome: "Nulo", v: r.votos.nulo || 0, cls: "sn" }];
    const tot = linhas.reduce((a, l) => a + l.v, 0) || 1, max = Math.max(...linhas.map((l) => l.v), 1);
    return `<div class="cargo"><h3>${esc(r.nome)}</h3>${linhas.map((l) => `
      <div class="linha-res"><span class="nome" title="${esc(l.nome)}">${esc(l.nome)}</span>
        <span class="trilho"><span class="preench ${l.cls}" style="width:${(l.v / max) * 100}%"></span></span>
        <span class="val">${fmt.format(l.v)}<span class="pct">${Math.round((l.v / tot) * 100)}%</span></span></div>`).join("")}</div>`;
  }).join("");
}

/* ------------------------------------------------------------------ gaveta da máquina */
function abrirGaveta(id) {
  S.sel = id;
  $("#gaveta").hidden = false;
  renderGaveta();
  renderGrafo(S.est);
}
function fecharGaveta() { S.sel = null; $("#gaveta").hidden = true; renderGrafo(S.est); }
$("#g-fechar").addEventListener("click", fecharGaveta);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#gaveta").hidden) fecharGaveta(); });
function renderGaveta() {
  const n = S.est.nos.find((x) => x.id === S.sel);
  if (!n) return;
  const sec = faseDoNo(S.est, n.id);
  const r = S.est.rede;
  $("#g-titulo").textContent = `${n.rotulo} · nó ${n.indice}`;
  const nomes = n.pares.map((p) => { const o = S.est.nos.find((x) => x.id === p); return o ? o.rotulo : p; });
  const mem = n.mem_total ? `<div><h3>Memória da máquina</h3><div>${n.mem_usada.toFixed(1)} de ${n.mem_total.toFixed(1)} GB</div>
      <div class="mini-barra"><span style="width:${(n.mem_usada / n.mem_total) * 100}%"></span></div></div>` : "";
  $("#g-corpo").innerHTML = `
    <dl>
      <dt>Estado</dt><dd>${({ no_ar: "No ar", fora: "Fora do ar", desconhecido: "Desconhecido" })[n.estado]}</dd>
      <dt>IP</dt><dd>${esc(n.ip)}</dd>
      <dt>Bloco</dt><dd>${n.bloco != null ? fmt.format(n.bloco) : "—"}${n.bloco != null && r.altura - n.bloco > 0 ? ` (−${r.altura - n.bloco})` : ""}</dd>
      <dt>Blocos propostos</dt><dd>${n.propostos}${n.ultimo_proposto ? ` · último #${n.ultimo_proposto}` : ""}</dd>
      <dt>Carga (1 min)</dt><dd>${n.carga != null ? `${n.carga.toFixed(2)}${n.nucleos ? ` / ${n.nucleos} núcleos` : ""}` : "—"}</dd>
      <dt>Contêiner Besu</dt><dd>${esc(n.besu_estado || "—")}${n.besu_mem ? ` · ${esc(n.besu_mem)}` : ""}</dd>
      <dt>Conta do validador</dt><dd><code>${esc(n.endereco.slice(0, 10))}…${esc(n.endereco.slice(-6))}</code></dd>
    </dl>
    ${mem}
    <div><h3>Conectado a ${n.pares.length} ${n.pares.length === 1 ? "nó" : "nós"}</h3>
      <div class="pares">${nomes.map((x) => `<span class="ev-no">${esc(x)}</span>`).join("") || '<span class="vazio">nenhum</span>'}</div></div>
    ${sec ? `<div><h3>Seção ${esc(sec.secao)}</h3><dl>
      <dt>Fase</dt><dd>${FASE_TXT[sec.fase] || sec.fase}</dd>
      <dt>Cédulas</dt><dd>${fmt.format(sec.cedulas || 0)}</dd>
      ${sec.hash_boletim ? `<dt>Hash do boletim</dt><dd><code>${esc(sec.hash_boletim.slice(0, 16))}…</code></dd>` : ""}
      ${sec.bloco ? `<dt>Ancorado no bloco</dt><dd>#${sec.bloco}</dd>` : ""}</dl></div>` : ""}`;
  $("#g-derrubar").disabled = n.estado !== "no_ar";
  $("#g-religar").disabled = n.estado === "no_ar";
}

async function confirmar(titulo, texto, botao) {
  const m = $("#modal-confirmar");
  $("#c-titulo").textContent = titulo; $("#c-texto").innerHTML = texto; $("#c-ok").textContent = botao;
  m.showModal();
  return new Promise((ok) => m.addEventListener("close", () => ok(m.returnValue === "ok"), { once: true }));
}
async function acaoNo(acao) {
  const n = S.est.nos.find((x) => x.id === S.sel);
  if (!n) return;
  const r = S.est.rede;
  if (acao === "derrubar") {
    const ficam = r.vivos - 1;
    const efeito = ficam >= r.quorum
      ? `A rede continua: ficam <b>${ficam} de ${r.total}</b> e o consenso exige ${r.quorum}.`
      : `<b>A rede vai parar</b>: ficam ${ficam} de ${r.total} e o consenso exige ${r.quorum}. Nenhum boletim será ancorado até um nó voltar.`;
    if (!(await confirmar(`Desligar o nó ${n.rotulo}?`, `Para o contêiner Besu desta máquina (reversível). ${efeito}`, "Desligar"))) return;
  }
  try {
    const resp = await fetch(`/api/nos/${encodeURIComponent(n.id)}/${acao}`, { method: "POST" });
    if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
    toast(acao === "derrubar" ? `Nó ${n.rotulo} desligado` : `Nó ${n.rotulo} religado — sincronizando`);
  } catch (e) { toast(`Falhou: ${e.message}`, true); }
}
$("#g-derrubar").addEventListener("click", () => acaoNo("derrubar"));
$("#g-religar").addEventListener("click", () => acaoNo("religar"));

/* ------------------------------------------------------------------ ensaio */
$("#i-eleitores").addEventListener("input", (e) => { $("#o-eleitores").textContent = e.target.value; });
$("#i-duracao").addEventListener("input", (e) => { $("#o-duracao").textContent = `${e.target.value} s`; });
$("#btn-ensaio").addEventListener("click", async () => {
  if (S.est && S.est.ensaio_ativo) {
    if (await confirmar("Parar o ensaio?", "As seções em andamento serão interrompidas. O que já foi gravado na blockchain permanece.", "Parar")) {
      await fetch("/api/ensaio/parar", { method: "POST" });
    }
    return;
  }
  $("#modal-ensaio").showModal();
});
$("#modal-ensaio").addEventListener("close", async () => {
  if ($("#modal-ensaio").returnValue !== "iniciar") return;
  try {
    const resp = await fetch("/api/ensaio", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eleitores: +$("#i-eleitores").value, duracao: +$("#i-duracao").value }) });
    if (!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
    toast("Ensaio iniciado — acompanhe as seções");
  } catch (e) { toast(`Não foi possível iniciar: ${e.message}`, true); }
});

conectar();
