"""Genera panel_director.html: un único archivo autocontenido, pensado para el móvil."""

import json

TEMPLATE = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Director Deportivo · __TEAM__</title>
<style>
:root{color-scheme:light;--bg:#f4f3ef;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;--line:#e4e2dc;
--accent:#2a78d6;--accent-soft:#e3eefb;--bar:#c9c7c0;--good:#0a7d3c;--good-bg:#e2f4e8;--warn:#9a5b00;--warn-bg:#fdf0d5;
--bad:#b4231f;--bad-bg:#fbe3e2;--neutral-bg:#ecebe7}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#121211;--card:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e86;
--line:#2c2c2a;--accent:#3987e5;--accent-soft:#1d2c40;--bar:#4a4945;--good:#4cc27a;--good-bg:#173323;--warn:#e7a73a;--warn-bg:#3a2b12;
--bad:#f07c78;--bad-bg:#3c1b1a;--neutral-bg:#252523}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{padding:18px 16px 10px;max-width:1100px;margin:auto}
h1{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink2);margin:0 0 4px;font-weight:600}
.hero{display:flex;flex-wrap:wrap;gap:10px 22px;align-items:baseline}
.big{font-size:44px;font-weight:700;letter-spacing:-.02em;line-height:1}
.sub{color:var(--ink2);font-size:14px}
.meta{color:var(--ink3);font-size:12px;margin-top:6px}
nav{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line)}
nav .in{max-width:1100px;margin:auto;display:flex;overflow-x:auto;padding:0 8px}
nav button{flex:none;border:0;background:none;color:var(--ink2);font:inherit;font-weight:600;padding:12px 10px;border-bottom:2px solid transparent;cursor:pointer}
nav button.on{color:var(--ink);border-color:var(--accent)}
main{max-width:1100px;margin:auto;padding:14px 12px 60px}
section{display:none}section.on{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:12px}
.card h2{font-size:15px;margin:0 0 10px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.kpi{font-size:26px;font-weight:700}.kpi small{font-size:13px;color:var(--ink2);font-weight:500}
.memo{white-space:pre-wrap;font-size:15px}
.who{font-size:12px;color:var(--ink3);margin-top:8px}
.dec{display:flex;gap:12px;padding:12px 0;border-top:1px solid var(--line)}.dec:first-of-type{border-top:0}
.tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;padding:3px 7px;border-radius:6px;white-space:nowrap}
.t-PUJAR,.t-CLAUSULAZO,.v-PUJAR{background:var(--good-bg);color:var(--good)}
.t-BLINDAR,.n-ALTO,.t-ALINEACIÓN{background:var(--bad-bg);color:var(--bad)}
.t-VENDER,.v-VIGILAR,.n-MEDIO,.a-VIGILAR{background:var(--warn-bg);color:var(--warn)}
.a-VENDER{background:var(--bad-bg);color:var(--bad)}
.t-DATOS,.v-PASAR,.n-BAJO,.n-PROTEGIDO{background:var(--neutral-bg);color:var(--ink2)}
.dec b{display:block}.dec p{margin:2px 0 0;color:var(--ink2);font-size:14px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink3);text-align:left;font-weight:600;padding:6px 6px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr.me td{background:var(--accent-soft)}
.scroll{overflow-x:auto}
.muted{color:var(--ink3);font-size:12px}
.pos{font-size:11px;color:var(--ink3)}
.up{color:var(--good)}.down{color:var(--bad)}
.bars .row{display:grid;grid-template-columns:140px 1fr 46px;gap:8px;align-items:center;margin:4px 0;font-size:13px}
.bars .track{height:14px;position:relative}
.bars .fill{height:14px;border-radius:0 4px 4px 0;background:var(--bar)}
.bars .row.me .fill{background:var(--accent)}.bars .row.me{font-weight:700}
.bars .lbl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.spark{vertical-align:middle}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.filters button{border:1px solid var(--line);background:var(--card);color:var(--ink2);border-radius:20px;padding:5px 12px;font:inherit;font-size:13px;cursor:pointer}
.filters button.on{background:var(--ink);color:var(--card);border-color:var(--ink)}
.warn{background:var(--warn-bg);color:var(--warn);border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:12px}
.only-m{display:none}
@media (max-width:640px){.big{font-size:36px}.hide-m{display:none}.only-m{display:inline-block;margin-top:4px}div.only-m{display:block}.bars .row{grid-template-columns:100px 1fr 40px}}
</style></head><body>
<header>
 <h1>Director Deportivo · <span id="team"></span></h1>
 <div class="hero"><div class="big" id="pos"></div><div class="sub" id="heroSub"></div></div>
 <div class="meta" id="meta"></div>
</header>
<nav><div class="in" id="tabs"></div></nav>
<main id="main"></main>
<script>
const B = __DATA__;
const MEMO = __MEMO__;
const $ = (s, r=document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const f = (v, d=1) => v==null || isNaN(v) ? "–" : Number(v).toLocaleString("es-ES",{minimumFractionDigits:d,maximumFractionDigits:d});
const m = v => v==null ? "–" : f(v, v>=10?1:2)+"M";
const pct = v => v==null ? "–" : `<span class="${v>0?'up':v<0?'down':''}">${v>0?'+':''}${f(v)}%</span>`;
const role = r => ({portero:"POR",defensa:"DEF",centrocampista:"MED",delantero:"DEL"}[r]||r);
const ago = iso => { if(!iso) return "–"; const d=new Date(iso); return d.toLocaleString("es-ES",{weekday:"short",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}); };
const status = s => ({injured:"🚑 lesionado",injured2:"🚑 lesionado",doubt:"❓ duda",redcard:"🟥 sancionado",yellowcard:"apercibido"}[s]||"");
function spark(vals){ if(!vals||!vals.length) return ""; const w=60,h=18,mx=Math.max(10,...vals),mn=Math.min(0,...vals);
  const pts=vals.map((v,i)=>`${(i/(vals.length-1||1))*w},${h-((v-mn)/(mx-mn||1))*h}`).join(" ");
  return `<svg class="spark" width="${w}" height="${h}" viewBox="-1 -2 ${w+2} ${h+4}" aria-label="Últimas jornadas: ${vals.join(', ')}"><title>Últimas 5: ${vals.join(' · ')}</title><polyline fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="${pts}"/></svg>`;}
function name(p){ return `<b>${esc(p.name)}</b> <span class="pos">${role(p.role)} · ${esc(p.club||"")}</span>${p.status?` <span class="muted">${status(p.status)}</span>`:""}${p.absent_streak>=2?` <span class="muted">· ${p.absent_streak} jornadas sin jugar</span>`:""}`; }

const S = B.situacion;
$("#team").textContent = B.mi_equipo;
$("#pos").textContent = S.posicion ? `${S.posicion}º` : "–";
let sub = `de ${S.equipos} · jornada ~${S.jornada_aprox} · quedan ${S.jornadas_restantes}`;
if (S.objetivos && S.objetivos.length) { const o=S.objetivos[0]; sub += `<br>Objetivo: <b>${esc(o.equipo)}</b> a ${f(o.gap)} pts → +${f(o.pts_extra_por_jornada)} pts/jornada`; }
$("#heroSub").innerHTML = sub;
$("#meta").textContent = `Datos de ${ago(B.captura)} · ${B.historico.capturas} capturas en el histórico · Los precios caducan en horas: confirma en la app antes de pagar.`;

const tabs = [["hoy","Hoy"],["mercado","Mercado"],["clausulas","Clausulazos"],["plantilla","Mi plantilla"],["rivales","Rivales"],["liga","Liga y pujas"]];
$("#tabs").innerHTML = tabs.map(([id,t],i)=>`<button data-t="${id}" class="${i?'':'on'}">${t}</button>`).join("");
$("#main").innerHTML = tabs.map(([id],i)=>`<section id="s-${id}" class="${i?'':'on'}"></section>`).join("");
$("#tabs").addEventListener("click", e => { const t=e.target.dataset.t; if(!t) return;
  document.querySelectorAll("nav button").forEach(b=>b.classList.toggle("on", b.dataset.t===t));
  document.querySelectorAll("section").forEach(s=>s.classList.toggle("on", s.id==="s-"+t)); window.scrollTo(0,0); });

/* ---------- HOY */
(function(){
  const fin = B.finanzas;
  let h = "";
  if (B.errores_captura && B.errores_captura.length) h += `<div class="warn">Avisos de la captura: ${esc(B.errores_captura.join(" · "))}</div>`;
  h += `<div class="grid">
   <div class="card"><h2>Once proyectado</h2><div class="kpi">${f(S.mi_xi_proxima)} <small>pts/jornada · ${esc(S.formacion||"")}</small></div><div class="muted">Media esperada de tu mejor once disponible.</div></div>
   <div class="card"><h2>Distancia</h2><div class="kpi">${f(S.gap_lider)} <small>pts al líder</small></div><div class="muted">${S.perseguidor?`Por detrás: ${esc(S.perseguidor.equipo)} a ${f(S.perseguidor.gap)} pts`:""}</div></div>
   <div class="card"><h2>Caja</h2><div class="kpi">${fin.fondos_M!=null?m(fin.fondos_M):"–"}</div><div class="muted">${esc(fin.fuente)}</div></div>
  </div>`;
  h += `<div class="card"><h2>Parte del Director</h2><div class="memo">${esc(MEMO.texto)}</div><div class="who">Redactado por: ${esc(MEMO.autor)}</div></div>`;
  h += `<div class="card"><h2>Decisiones propuestas</h2>` + (B.decisiones.map(d=>`<div class="dec"><div><span class="tag t-${d.tipo}">${d.tipo}</span></div><div><b>${esc(d.titulo)}</b><p>${esc(d.detalle)}${d.expira?` · cierra ${ago(d.expira)}`:""}</p></div></div>`).join("") || "<p class='muted'>Nada urgente hoy.</p>") + `</div>`;
  if (S.objetivos && S.objetivos.length) {
    h += `<div class="card"><h2>¿A quién puedes alcanzar?</h2><div class="scroll"><table><tr><th>Equipo</th><th class="n">Distancia</th><th class="n">Necesitas/jornada</th><th class="n">Tu once vs el suyo</th><th></th></tr>` +
     S.objetivos.map(o=>`<tr><td>${o.pos}º ${esc(o.equipo)}</td><td class="n">${f(o.gap)}</td><td class="n">+${f(o.pts_extra_por_jornada)}</td><td class="n">${o.diferencia_xi>0?'+':''}${f(o.diferencia_xi)}</td><td>${o.lo_alcanzas_a_este_ritmo?'<span class="tag v-PUJAR">a tiro</span>':'<span class="tag v-VIGILAR">refuérzate</span>'}</td></tr>`).join("") +
     `</table></div><p class="muted">"Tu once vs el suyo" compara los puntos por jornada que proyectan ambos once ideales. Si es mayor que lo que necesitas por jornada, lo alcanzas manteniendo el ritmo.</p></div>`;
  }
  $("#s-hoy").innerHTML = h;
})();

/* ---------- MERCADO */
(function(){
  const box = $("#s-mercado");
  let filt = "todos";
  function render(){
    const rows = B.mercado.filter(p => filt==="todos" || p.role===filt || (filt==="PUJAR" && p.veredicto==="PUJAR"));
    box.innerHTML = `<div class="filters">${[["todos","Todos"],["PUJAR","Solo PUJAR"],["portero","POR"],["defensa","DEF"],["centrocampista","MED"],["delantero","DEL"]].map(([k,t])=>`<button data-f="${k}" class="${k===filt?'on':''}">${t}</button>`).join("")}</div>
    <div class="card"><h2>Jugadores en venta (${rows.length})</h2><div class="scroll"><table>
    <tr><th>Jugador</th><th class="hide-m"></th><th class="n">Mejora once</th><th class="n hide-m">Valor</th><th class="n">Puja objetivo</th><th class="n hide-m">Rango</th><th class="n hide-m">Media / últ.5</th><th class="hide-m">Forma</th><th class="hide-m">Cierra</th></tr>
    ${rows.map(p=>`<tr><td>${name(p)}<div class="muted">${esc(p.vendedor)}</div><span class="tag v-${p.veredicto} only-m">${p.veredicto}</span></td><td class="hide-m"><span class="tag v-${p.veredicto}">${p.veredicto}</span></td>
     <td class="n"><b>${p.mejora_xi>0?'+':''}${f(p.mejora_xi,2)}</b></td><td class="n hide-m">${m(p.value_M)}${p.trend7==null?'':`<div class="muted">${pct(p.trend7)} 7d</div>`}</td>
     <td class="n"><b>${m(p.puja.objetivo_M)}</b><div class="muted only-m">valor ${m(p.value_M)}</div></td><td class="n hide-m">${m(p.puja.minimo_M)} – ${m(p.puja.agresiva_M)}</td>
     <td class="n hide-m">${f(p.avg)} / ${f(p.avg5)}</td><td class="hide-m">${spark(p.fitness)}</td><td class="hide-m muted">${ago(p.expira)}</td></tr>`).join("")}
    </table></div><p class="muted">"Mejora once" = puntos por jornada que gana tu once ideal si lo fichas. La puja objetivo usa lo que se ha pagado en tu liga en su tramo de precio (${esc(Object.values(B.pujas_liga.tramos).map(t=>t.fuente)[0])}); la agresiva, el percentil 75.</p></div>`;
    if (B.mis_jugadores_en_venta && B.mis_jugadores_en_venta.length)
      box.innerHTML += `<div class="card"><h2>Tus jugadores en venta</h2>${B.mis_jugadores_en_venta.map(p=>`<div>${name(p)} · salida ${m(p.precio_salida_M)}</div>`).join("")}</div>`;
  }
  box.addEventListener("click", e => { if(e.target.dataset.f){ filt=e.target.dataset.f; render(); }});
  render();
})();

/* ---------- CLAUSULAZOS */
(function(){
  let h = `<div class="card"><h2>Mejores clausulazos para tu once</h2><div class="scroll"><table>
   <tr><th>Jugador</th><th class="hide-m">Dueño</th><th class="n">Cláusula</th><th class="n">Mejora once</th><th class="n hide-m">pts por M</th><th class="n hide-m">Colchón</th><th class="hide-m">Forma</th></tr>
   ${B.clausulazos.map(p=>`<tr><td>${name(p)}<div class="muted only-m">de ${esc(p.equipo_rival)}</div></td><td class="hide-m">${esc(p.equipo_rival)}${p.rival_directo?' <span class="tag v-VIGILAR">directo</span>':''}${p.dependencia_rival_pct?`<div class="muted">su estrella: ${f(p.dependencia_rival_pct)}% de sus puntos</div>`:''}</td>
   <td class="n"><b>${p.clausula_exacta?m(p.clausula_max_M):m(p.clausula_min_M)+' – '+m(p.clausula_max_M)}</b>${p.clausula_exacta?'':(p.clausula_min_M===p.clausula_max_M?'<div class="muted">probable</div>':'<div class="muted">estimada</div>')}${p.clausula_subida?'<div class="muted">blindada por su dueño</div>':''}</td>
   <td class="n"><b>+${f(p.mejora_xi,2)}</b></td><td class="n hide-m">${f(p.mejora_por_M,3)}</td><td class="n hide-m">${m(p.colchon_M)}</td><td class="hide-m">${spark(p.fitness)}</td></tr>`).join("")}
   </table></div><p class="muted">Colchón = valor de mercado − cláusula: si es positivo, pagarla no te hace perder valor de plantilla. Cuando la cláusula sale como rango es porque no se pudo leer la ficha del jugador; confírmala en la app.</p></div>`;
  if (B.bloqueados.length) h += `<div class="card"><h2>Bloqueados (fichados hace poco)</h2><table><tr><th>Jugador</th><th>Equipo</th><th class="n">Cláusula</th><th>Libre desde</th></tr>${B.bloqueados.map(b=>`<tr><td>${esc(b.jugador)}</td><td>${esc(b.equipo)}</td><td class="n">${m(b.clausula_M)}</td><td>${ago(b.libre_desde)}</td></tr>`).join("")}</table></div>`;
  $("#s-clausulas").innerHTML = h;
})();

/* ---------- PLANTILLA */
(function(){
  const P = B.posiciones;
  let h = `<div class="card"><h2>Tu once por líneas vs la liga</h2><div class="scroll"><table><tr><th>Línea</th><th class="n hide-m">Jugadores</th><th class="n">Tu media</th><th class="n">Media liga</th><th class="n">Diferencia</th></tr>
   ${Object.entries(P).map(([r,v])=>`<tr class="${r===B.posicion_debil?'me':''}"><td>${esc(r)}${r===B.posicion_debil?' · <b>punto débil</b>':''}</td><td class="n hide-m">${v.jugadores}</td><td class="n">${f(v.mi_media_xi,2)}</td><td class="n">${f(v.media_liga_xi,2)}</td><td class="n">${v.diferencia>0?'+':''}${f(v.diferencia,2)}</td></tr>`).join("")}
   </table></div></div>`;
  h += `<div class="card"><h2>Plantilla</h2><div class="scroll"><table><tr><th>Jugador</th><th class="n">Proyección</th><th class="n hide-m">Media / últ.5</th><th class="hide-m">Forma</th><th class="n">Valor</th><th class="n hide-m">7 días</th><th class="n hide-m">Titular</th></tr>
   ${B.mi_once.map(p=>`<tr class="${p.en_once?'me':''}"><td>${name(p)}${p.en_once?' <span class="muted">· once</span>':''}</td><td class="n"><b>${f(p.proj,1)}</b></td><td class="n hide-m">${f(p.avg)} / ${f(p.avg5)}</td><td class="hide-m">${spark(p.fitness)}</td><td class="n">${m(p.value_M)}</td><td class="n hide-m">${pct(p.trend7)}</td><td class="n hide-m">${p.starter_rate==null?'–':f(p.starter_rate*100,0)+'%'}</td></tr>`).join("")}
   </table></div><p class="muted">Resaltados: tu once ideal para la próxima jornada. Proyección = puntos esperados por jornada (mezcla media de temporada y últimos 5, corregida por partidos jugados).</p></div>`;
  h += `<div class="card"><h2>Blindaje: riesgo de clausulazo</h2><div class="scroll"><table><tr><th>Jugador</th><th>Riesgo</th><th class="n">Cláusula</th><th class="hide-m">A quién le interesa</th><th class="n">Lo que perderías</th></tr>
   ${B.blindaje.map(p=>`<tr><td>${name(p)}</td><td><span class="tag n-${p.nivel}">${p.nivel}</span></td><td class="n">${m(p.clausula_M)}${p.clausula_exacta?'':'<div class="muted">estimada</div>'}</td><td class="hide-m">${p.interesado?esc(p.interesado)+` <span class="muted">(+${f(p.ganancia_interesado,2)} pts)</span>`:'–'}</td><td class="n">${p.perdida_si_me_lo_quitan?'-'+f(p.perdida_si_me_lo_quitan,2)+' pts':'–'}</td></tr>`).join("")}
   </table></div><p class="muted">El riesgo combina cuánto mejoraría el once de cada rival con tu jugador, lo barata que es la cláusula y cuántas cláusulas paga ese rival.</p></div>`;
  if (B.ventas.length) h += `<div class="card"><h2>Candidatos a venta</h2>${B.ventas.map(v=>`<div class="dec"><div><span class="tag a-${v.accion}">${v.accion}</span></div><div>${name(v)} · ${m(v.valor_M)}<p>${esc(v.motivos.join("; "))}</p></div></div>`).join("")}</div>`;
  $("#s-plantilla").innerHTML = h;
})();

/* ---------- RIVALES */
(function(){
  const mx = Math.max(...B.tabla.map(t=>t.xi_proyectado||0));
  let h = `<div class="card"><h2>Fuerza del once ideal (pts/jornada proyectados)</h2><div class="bars">
   ${[...B.tabla].sort((a,b)=>b.xi_proyectado-a.xi_proyectado).map(t=>`<div class="row ${t.es_mio?'me':''}" title="${esc(t.equipo)}: ${f(t.xi_proyectado)} pts/jornada"><div class="lbl">${esc(t.equipo)}</div><div class="track"><div class="fill" style="width:${(t.xi_proyectado/mx*100).toFixed(1)}%"></div></div><div class="n">${f(t.xi_proyectado)}</div></div>`).join("")}
   </div><p class="muted">Es lo que se espera que sume cada equipo por jornada con su mejor once actual. En azul, tú.</p></div>`;
  h += `<div class="card"><h2>Inteligencia de rivales</h2><div class="scroll"><table><tr><th>Equipo</th><th class="n">Distancia</th><th>Perfil</th><th class="hide-m">Estrella</th><th class="hide-m">Débil en</th><th class="n hide-m">Cláus. hechas / sufridas</th><th class="hide-m">Lesionados en su once</th></tr>
   ${B.rivales.map(r=>`<tr><td>${r.pos}º ${esc(r.equipo)}<div class="muted">${m(r.valor_M)} · once ${f(r.xi_proyectado)}</div></td><td class="n">${r.gap_conmigo>0?'+':''}${f(r.gap_conmigo)}</td><td>${r.perfil.map(t=>`<span class="tag t-DATOS">${esc(t)}</span>`).join(" ")}</td><td class="hide-m">${esc(r.estrella)} <span class="muted">${f(r.dependencia_pct)}%</span></td><td class="hide-m">${esc(r.posicion_debil||'–')}</td><td class="n hide-m">${r.clausulazos_hechos??'–'} / ${r.clausulazos_sufridos??'–'}</td><td class="hide-m">${esc((r.lesionados_en_once||[]).join(', ')||'–')}</td></tr>`).join("")}
   </table></div></div>`;
  $("#s-rivales").innerHTML = h;
})();

/* ---------- LIGA */
(function(){
  let h = `<div class="card"><h2>Clasificación</h2><div class="scroll"><table><tr><th>#</th><th>Equipo</th><th class="n">Puntos</th><th class="n">Valor</th><th class="n hide-m">Once proy.</th></tr>
   ${B.tabla.map(t=>`<tr class="${t.es_mio?'me':''}"><td>${t.pos}</td><td>${esc(t.equipo)}</td><td class="n">${f(t.puntos)}</td><td class="n">${m(t.valor_M)}</td><td class="n hide-m">${f(t.xi_proyectado)}</td></tr>`).join("")}</table></div></div>`;
  const T = B.pujas_liga.tramos;
  h += `<div class="card"><h2>Cómo se puja en tu liga</h2><div class="scroll"><table><tr><th>Tramo</th><th class="n">Pagado sobre valor (mediana)</th><th class="n">p75</th><th class="n">Sobre el 2º postor</th><th>Base</th></tr>
   ${Object.entries(T).map(([k,t])=>`<tr><td>${k}</td><td class="n">+${f(t.sobre_valor_mediana*100)}%</td><td class="n">+${f(t.sobre_valor_p75*100)}%</td><td class="n">${t.sobre_2o_mediana==null?'–':'+'+f(t.sobre_2o_mediana*100)+'%'}</td><td class="muted">${esc(t.fuente)}</td></tr>`).join("")}</table></div></div>`;
  h += `<div class="card"><h2>Movimientos recientes</h2><div class="scroll"><table><tr><th>Fecha</th><th>Jugador</th><th>Comprador</th><th class="hide-m">Origen</th><th class="n">Precio</th></tr>
   ${B.pujas_liga.recientes.map(r=>`<tr><td class="muted">${esc(r.fecha)}</td><td>${esc(r.jugador)}</td><td>${esc(r.comprador)}</td><td class="hide-m">${esc(r.vendedor)}</td><td class="n">${m(r.precio_M)}</td></tr>`).join("")}</table></div></div>`;
  $("#s-liga").innerHTML = h;
})();
</script></body></html>"""


def build_html(briefing, memo, path):
    html = (TEMPLATE
            .replace("__TEAM__", briefing.get("mi_equipo", ""))
            .replace("__DATA__", json.dumps(briefing, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__MEMO__", json.dumps(memo, ensure_ascii=False).replace("</", "<\\/")))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path
