const LM={
  entity:c=>c.entity||"sensor.life_manager",
  esc:v=>String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;"),
  missing:e=>`<ha-card><div style="padding:16px">Sensor ${LM.esc(e)} fehlt.</div></ha-card>`,
  async refresh(h,e){await new Promise(r=>setTimeout(r,500));await h.callService("homeassistant","update_entity",{entity_id:e});},
  styles:()=>`:host{display:block}ha-card{overflow:hidden}.stat{background:var(--secondary-background-color);border-radius:12px;padding:10px}.stat b{display:block;font-size:18px}.stat small{opacity:.65}.bar{height:9px;background:var(--divider-color);border-radius:999px;overflow:hidden}.fill{height:100%;background:var(--primary-color)}button{border:0;border-radius:9px;padding:8px 10px;font-weight:700;cursor:pointer;background:var(--primary-color);color:white}button.secondary{background:var(--secondary-background-color);color:var(--primary-text-color)}button:disabled{opacity:.45}`
};

class LifeManagerCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._busy=new Set();}
  setConfig(c){this._config={entity:LM.entity(c),script:c.script||"script.life_quest_complete",title:c.title||"Life Manager"};this.render();}
  set hass(h){this._hass=h;this.render();}
  async complete(id,o){if(this._busy.has(id))return;this._busy.add(id);this.render();try{await this._hass.callService("script","turn_on",{entity_id:this._config.script,variables:{quest_id:Number(id),overcome:Boolean(o)}});await LM.refresh(this._hass,this._config.entity);}catch(e){alert(e?.message||"Quest konnte nicht abgeschlossen werden.");}finally{this._busy.delete(id);this.render();}}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=(e.attributes||{}).today||{},qs=Array.isArray(d.quests)?d.quests:[],g={};for(const q of qs)(g[q.category||"Sonstiges"]??=[]).push(q);const html=Object.entries(g).map(([cat,items])=>`<h3>${LM.esc(cat)}</h3>${items.map(q=>`<div class="q ${q.completed?"done":""}"><div><b>${LM.esc(q.name)}</b><small>+${Number(q.xp||0)} XP</small></div>${q.completed?`<span>✓</span>`:`<div class="actions"><button data-id="${q.id}" data-o="0">✓</button>${q.quest_type==="training"?`<button class="secondary" data-id="${q.id}" data-o="1">🔥</button>`:""}</div>`}</div>`).join("")}`).join("");this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.head{display:flex;justify-content:space-between;align-items:end}.pct{font-size:28px;font-weight:800}.bar{margin:12px 0 16px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.q{display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--divider-color);padding:10px 0}.q small{display:block;opacity:.65}.done{opacity:.55}.actions{display:flex;gap:6px}@media(max-width:600px){.stats{grid-template-columns:repeat(2,1fr)}}</style><ha-card><div class="head"><div><small>HEUTE</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div><div class="pct">${Number(d.progress_percent||0)}%</div></div><div class="bar"><div class="fill" style="width:${Math.min(100,Number(d.progress_percent||0))}%"></div></div><div class="stats"><div class="stat"><b>${Number(d.xp_today||0)}/${Number(d.possible_xp||0)}</b><small>XP</small></div><div class="stat"><b>${Number(d.completed_count||0)}/${Number(d.quest_count||0)}</b><small>Quests</small></div><div class="stat"><b>${Number(d.willpower_xp_today||0)}</b><small>Willpower</small></div><div class="stat"><b>${Number(d.projected_coins||0)} 🪙</b><small>Heute</small></div></div>${html}</ha-card>`;this.shadowRoot.querySelectorAll("button[data-id]").forEach(b=>b.onclick=()=>this.complete(Number(b.dataset.id),b.dataset.o==="1"));}
}

class LifeManagerPlayerCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Player"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=(e.attributes||{}).player||{};this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:20px}.top{display:flex;justify-content:space-between;align-items:center}.level{font-size:34px;font-weight:800}.bar{margin:14px 0}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}</style><ha-card><div class="top"><div><small>🎮 ${LM.esc(this._config.title)}</small><div class="level">Level ${Number(d.level||1)}</div></div><b>${Number(d.xp_into_level||0)}/100 XP</b></div><div class="bar"><div class="fill" style="width:${Math.min(100,Number(d.level_progress_percent||0))}%"></div></div><div class="stats"><div class="stat"><b>${Number(d.total_xp||0)}</b><small>Gesamt-XP</small></div><div class="stat"><b>${Number(d.coin_balance||0)} 🪙</b><small>Coins</small></div><div class="stat"><b>${Number(d.willpower_xp||0)} 🔥</b><small>Willpower</small></div></div></ha-card>`;}
}

class LifeManagerTrainingCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Trainingswoche"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=(e.attributes||{}).training||{},it=Array.isArray(d.trainings)?d.trainings:[],n=["","Mo","Di","Mi","Do","Fr","Sa","So"];this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.head{display:flex;justify-content:space-between;align-items:center}.score{font-size:22px;font-weight:800}.row{display:grid;grid-template-columns:42px 28px 1fr;gap:8px;padding:10px 0;border-top:1px solid var(--divider-color)}.done{opacity:.6}</style><ha-card><div class="head"><div><small>🏋️ FITNESS</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div><div class="score">${Number(d.completed_count||0)}/${Number(d.planned_count||0)}</div></div>${it.map(x=>`<div class="row ${x.completed?"done":""}"><b>${n[x.weekday]||""}</b><span>${x.completed?"✅":"○"}</span><span>${LM.esc(x.name)}</span></div>`).join("")}</ha-card>`;}
}

class LifeManagerStreakCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Streaks"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=(e.attributes||{}).streaks||{},it=Array.isArray(d.streaks)?d.streaks:[];this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.row{display:grid;grid-template-columns:1fr auto auto;gap:12px;padding:9px 0;border-top:1px solid var(--divider-color)}.fire{font-weight:800}.best{opacity:.6;font-size:12px}</style><ha-card><small>🔥 CONSISTENCY</small><h2 style="margin:2px 0 12px">${LM.esc(this._config.title)}</h2>${it.length?it.map(x=>`<div class="row"><span>${LM.esc(x.name)}</span><span class="fire">${Number(x.current_streak||0)} 🔥</span><span class="best">Best ${Number(x.best_streak||0)}</span></div>`).join(""):"<div>Noch keine Streaks.</div>"}</ha-card>`;}
}

class LifeManagerWeekCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Diese Woche"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=(e.attributes||{}).week||{},days=Array.isArray(d.days)?d.days:[],names=["Mo","Di","Mi","Do","Fr","Sa","So"],max=Math.max(1,...days.map(x=>Number(x.xp||0)));this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.summary{display:flex;gap:16px;margin-bottom:18px}.summary b{font-size:20px}.summary small{display:block;opacity:.65}.chart{height:150px;display:grid;grid-template-columns:repeat(7,1fr);gap:8px;align-items:end}.col{display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end}.bd{width:70%;min-height:2px;background:var(--primary-color);border-radius:6px 6px 2px 2px}.label{font-size:11px;margin-top:6px}.val{font-size:10px;opacity:.65}</style><ha-card><small>📊 WEEKLY</small><h2 style="margin:2px 0 12px">${LM.esc(this._config.title)}</h2><div class="summary"><span><b>${Number(d.xp_total||0)}</b><small>XP</small></span><span><b>${Number(d.completed_total||0)}</b><small>Quests</small></span><span><b>${Number(d.willpower_xp_total||0)}</b><small>Willpower</small></span></div><div class="chart">${days.map((x,i)=>`<div class="col"><div class="val">${Number(x.xp||0)}</div><div class="bd" style="height:${Math.max(2,(Number(x.xp||0)/max)*110)}px"></div><div class="label">${names[i]||""}</div></div>`).join("")}</div></ha-card>`;}
}

class LifeManagerRewardCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._busy=null;}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Reward Shop",script:c.script||"script.life_reward_purchase"};this.render();}
  set hass(h){this._hass=h;this.render();}
  async buy(id){this._busy=id;this.render();try{await this._hass.callService("script","turn_on",{entity_id:this._config.script,variables:{reward_id:Number(id),quantity:1}});await LM.refresh(this._hass,this._config.entity);}catch(e){alert(e?.message||"Reward konnte nicht gekauft werden.");}finally{this._busy=null;this.render();}}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=(e.attributes||{}).rewards||{},rs=Array.isArray(d.rewards)?d.rewards:[];this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.head{display:flex;justify-content:space-between;align-items:center}.balance{font-size:26px;font-weight:800}.reward{display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;border-top:1px solid var(--divider-color);padding:12px 0}.reward small{display:block;opacity:.65}.cost{font-weight:800}.locked{opacity:.45}</style><ha-card><div class="head"><div><small>🪙 REWARDS</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div><div class="balance">${Number(d.coin_balance||0)} 🪙</div></div>${rs.map(x=>`<div class="reward ${x.can_afford?"":"locked"}"><div><b>${LM.esc(x.name)}</b><small>${LM.esc(x.description||"")}</small></div><div class="cost">${Number(x.cost||0)} 🪙</div><button data-buy="${x.id}" ${(!x.can_afford||this._busy===x.id)?"disabled":""}>${this._busy===x.id?"…":"Kaufen"}</button></div>`).join("")||"<div>Keine Rewards angelegt.</div>"}</ha-card>`;this.shadowRoot.querySelectorAll("button[data-buy]").forEach(b=>b.onclick=()=>this.buy(Number(b.dataset.buy)));}
}

class LifeManagerQuestManagerCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Quest Manager",create_script:c.create_script||"script.life_quest_create",update_script:c.update_script||"script.life_quest_update",toggle_script:c.toggle_script||"script.life_quest_toggle"};this.render();}
  set hass(h){this._hass=h;this.render();}

  async call(script,variables){
    await this._hass.callService("script","turn_on",{entity_id:script,variables});
    await LM.refresh(this._hass,this._config.entity);
  }

  getData(){
    return (this._hass?.states?.[this._config.entity]?.attributes||{}).quest_manager||{};
  }

  async toggle(id){
    try{await this.call(this._config.toggle_script,{quest_id:Number(id)});}
    catch(e){alert(e?.message||"Quest konnte nicht geändert werden.");}
  }

  collect(existing=null){
    const d=this.getData();
    const cats=Array.isArray(d.categories)?d.categories:[];
    if(!cats.length){alert("Keine Kategorien vorhanden.");return null;}

    const name=prompt("Quest-Name:",existing?.name||"");
    if(!name)return null;

    const catText=cats.map(x=>`${x.id}: ${x.name}`).join("\n");
    const categoryId=Number(prompt(`Kategorie-ID:\n${catText}`,String(existing?.category_id||cats[0].id)));
    if(!categoryId)return null;

    const type=prompt("Typ: routine, habit, training, project, milestone",existing?.quest_type||"routine")||"routine";
    const xpMode=prompt("XP-Modus: fixed oder formula",existing?.xp_mode||"formula")||"formula";

    let fixedXp=null,minutes=null,kbr=null,frequency=null;
    if(xpMode==="fixed"){
      fixedXp=Number(prompt("Feste XP:",String(existing?.fixed_xp??10))||"10");
    }else{
      minutes=Number(prompt("Geschätzte Minuten:",String(existing?.estimated_minutes??30))||"30");
      kbr=Number(prompt("KBR 1-5:",String(existing?.kbr??3))||"3");
      frequency=Number(prompt("Frequenz in Tagen:",String(existing?.frequency_days??7))||"7");
    }

    const existingWeekdays=(existing?.schedules||[]).filter(s=>s.weekday).map(s=>s.weekday).join(",");
    const intervalExisting=(existing?.schedules||[]).find(s=>s.interval_days)?.interval_days||0;
    const weekdayInput=prompt("Wochentage 1-7 kommasepariert, leer wenn nicht benötigt:",existingWeekdays)||"";
    const intervalInput=prompt("Intervall in Tagen (z.B. 1 täglich), leer wenn nicht benötigt:",String(intervalExisting||""))||"";

    return {
      name,
      category_id:categoryId,
      quest_type:type,
      xp_mode:xpMode,
      fixed_xp:fixedXp,
      estimated_minutes:minutes,
      kbr,
      frequency_days:frequency,
      weekdays:weekdayInput,
      interval_days:intervalInput?Number(intervalInput):0,
      active:existing?.active!==false
    };
  }

  async create(){
    const data=this.collect();
    if(!data)return;
    try{await this.call(this._config.create_script,data);}
    catch(e){alert(e?.message||"Quest konnte nicht erstellt werden.");}
  }

  async edit(id){
    const d=this.getData();
    const q=(d.quests||[]).find(x=>Number(x.id)===Number(id));
    if(!q)return;
    const data=this.collect(q);
    if(!data)return;
    data.quest_id=Number(id);
    try{await this.call(this._config.update_script,data);}
    catch(e){alert(e?.message||"Quest konnte nicht gespeichert werden.");}
  }

  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const d=(e.attributes||{}).quest_manager||{},qs=Array.isArray(d.quests)?d.quests:[];
    this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.row{display:grid;grid-template-columns:1fr auto auto auto;gap:8px;align-items:center;border-top:1px solid var(--divider-color);padding:10px 0}.row small{display:block;opacity:.65}.inactive{opacity:.45}@media(max-width:700px){.row{grid-template-columns:1fr auto}.meta{grid-column:1}.status{grid-column:2}}</style><ha-card><div class="head"><div><small>⚙️ ADMIN</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div><button id="create">+ Neue Quest</button></div>${qs.map(q=>`<div class="row ${q.active?"":"inactive"}"><div class="meta"><b>${LM.esc(q.name)}</b><small>${LM.esc(q.category)} · ${LM.esc(q.quest_type)} · ${LM.esc(q.xp_mode)}</small></div><span class="status">${q.active?"Aktiv":"Aus"}</span><button class="secondary" data-edit="${q.id}">Bearbeiten</button><button class="secondary" data-toggle="${q.id}">${q.active?"Deaktivieren":"Aktivieren"}</button></div>`).join("")}</ha-card>`;
    this.shadowRoot.getElementById("create").onclick=()=>this.create();
    this.shadowRoot.querySelectorAll("button[data-edit]").forEach(b=>b.onclick=()=>this.edit(Number(b.dataset.edit)));
    this.shadowRoot.querySelectorAll("button[data-toggle]").forEach(b=>b.onclick=()=>this.toggle(Number(b.dataset.toggle)));
  }
}

const defs=[
["life-manager-card",LifeManagerCard],
["life-manager-player-card",LifeManagerPlayerCard],
["life-manager-training-card",LifeManagerTrainingCard],
["life-manager-streak-card",LifeManagerStreakCard],
["life-manager-week-card",LifeManagerWeekCard],
["life-manager-reward-card",LifeManagerRewardCard],
["life-manager-quest-manager-card",LifeManagerQuestManagerCard]
];
for(const [n,c] of defs){if(!customElements.get(n))customElements.define(n,c);}
