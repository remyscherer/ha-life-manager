window.LIFE_MANAGER_FRONTEND_VERSION="1.4.0";
console.info("Life Manager Frontend v1.4.0 loaded");
const LM={
  dataRoot:e=>{
    const attrs=e?.attributes||{};
    return attrs.data||attrs;
  },
  entity:c=>c.entity||"sensor.life_manager",
  esc:v=>String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;"),
  missing:e=>`<ha-card><div style="padding:16px">Sensor ${LM.esc(e)} fehlt.</div></ha-card>`,
  async refresh(h,e){
    for(const delay of [250,750,1500]){
      await new Promise(r=>setTimeout(r,delay));
      await h.callService("homeassistant","update_entity",{entity_id:e});
    }
  },
  async callScript(h,scriptEntity,variables={}){
    const parts=String(scriptEntity||"").split(".");
    if(parts.length===2 && parts[0]==="script"){
      try{
        await h.callService("script",parts[1],variables);
        return;
      }catch(err){
        console.warn("Direct script call failed; falling back to script.turn_on",err);
      }
    }
    await h.callService("script","turn_on",{entity_id:scriptEntity,variables});
    await new Promise(r=>setTimeout(r,1000));
  },
  styles:()=>`:host{display:block}ha-card{overflow:hidden}.stat{background:var(--secondary-background-color);border-radius:12px;padding:10px}.stat b{display:block;font-size:18px}.stat small{opacity:.65}.bar{height:9px;background:var(--divider-color);border-radius:999px;overflow:hidden}.fill{height:100%;background:var(--primary-color)}button{border:0;border-radius:9px;padding:8px 10px;font-weight:700;cursor:pointer;background:var(--primary-color);color:white}button.secondary{background:var(--secondary-background-color);color:var(--primary-text-color)}button:disabled{opacity:.45}`
};


class LifeManagerCard extends HTMLElement{
  constructor(){
    super();
    this.attachShadow({mode:"open"});
    this._busy=new Set();
  }

  setConfig(c){
    this._config={
      entity:LM.entity(c),
      script:c.script||"script.life_quest_complete",
      occurrence_script:c.occurrence_script||"script.life_quest_occurrence",
      title:c.title||"Life Manager"
    };
    this.render();
  }

  set hass(h){this._hass=h;this.render();}

  async complete(id,overcome){
    if(this._busy.has(id))return;
    this._busy.add(id);this.render();
    try{
      await LM.callScript(this._hass,this._config.script,{
        quest_id:Number(id),
        overcome:Boolean(overcome)
      });
      await LM.refresh(this._hass,this._config.entity);
    }catch(e){
      alert(e?.message||"Quest konnte nicht abgeschlossen werden.");
    }finally{
      this._busy.delete(id);this.render();
    }
  }

  async occurrence(id,action,targetDate=null){
    if(this._busy.has(id))return;
    this._busy.add(id);this.render();
    try{
      await LM.callScript(this._hass,this._config.occurrence_script,{
        quest_id:Number(id),
        action,
        target_date:targetDate,
        note:null
      });
      await LM.refresh(this._hass,this._config.entity);
    }catch(e){
      alert(e?.message||"Quest konnte nicht verschoben werden.");
    }finally{
      this._busy.delete(id);this.render();
    }
  }

  async moveDate(id){
    const target=prompt("Auf welches Datum verschieben? (YYYY-MM-DD)");
    if(!target)return;
    await this.occurrence(id,"move",target);
  }

  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){
      this.shadowRoot.innerHTML=LM.missing(this._config.entity);
      return;
    }

    const d=LM.dataRoot(e).today||{};
    const qs=Array.isArray(d.quests)?d.quests:[];
    const groups={};
    for(const q of qs)(groups[q.category||"Sonstiges"]??=[]).push(q);

    const html=Object.entries(groups).map(([cat,items])=>`
      <h3>${LM.esc(cat)}</h3>
      ${items.map(q=>`
        <div class="q ${q.completed?"done":""}">
          <div class="q-main">
            <b>${LM.esc(q.name)}</b>
            <small>
              +${Number(q.xp||0)} XP
              ${q.moved_from?` · ↪ verschoben von ${LM.esc(q.moved_from)}`:""}
            </small>
          </div>
          ${q.completed
            ? `<span class="check">✓</span>`
            : `<div class="actions">
                <button data-complete="${q.id}" title="Erledigt">✓</button>
                <button class="secondary" data-overcome="${q.id}" title="Kein Bock überwunden">🔥</button>
                <button class="secondary" data-tomorrow="${q.id}" title="Auf morgen verschieben">→</button>
                <button class="secondary" data-date="${q.id}" title="Auf Datum verschieben">📅</button>
                <button class="secondary" data-skip="${q.id}" title="Heute auslassen">⏭</button>
              </div>`
          }
        </div>
      `).join("")}
    `).join("");

    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .head{display:flex;justify-content:space-between;align-items:end}
        .pct{font-size:28px;font-weight:800}
        .bar{margin:12px 0 16px}
        .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
        .q{display:flex;justify-content:space-between;align-items:center;gap:12px;border-top:1px solid var(--divider-color);padding:10px 0}
        .q-main{min-width:0}
        .q small{display:block;opacity:.65;margin-top:3px}
        .done{opacity:.55}
        .actions{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}
        .actions button{min-width:38px}
        .check{font-size:18px}
        @media(max-width:600px){
          .stats{grid-template-columns:repeat(2,1fr)}
          .q{align-items:flex-start;flex-direction:column}
          .actions{width:100%;justify-content:flex-start}
          .actions button{min-width:44px;min-height:40px}
        }
      </style>
      <ha-card>
        <div class="head">
          <div><small>HEUTE</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div>
          <div class="pct">${Number(d.progress_percent||0)}%</div>
        </div>
        <div class="bar"><div class="fill" style="width:${Math.min(100,Number(d.progress_percent||0))}%"></div></div>
        <div class="stats">
          <div class="stat"><b>${Number(d.xp_today||0)}/${Number(d.possible_xp||0)}</b><small>XP</small></div>
          <div class="stat"><b>${Number(d.completed_count||0)}/${Number(d.quest_count||0)}</b><small>Quests</small></div>
          <div class="stat"><b>${Number(d.willpower_xp_today||0)}</b><small>Willpower</small></div>
          <div class="stat"><b>${Number(d.projected_coins||0)} 🪙</b><small>Heute</small></div>
        </div>
        ${html}
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll("[data-complete]").forEach(b=>b.onclick=()=>this.complete(Number(b.dataset.complete),false));
    this.shadowRoot.querySelectorAll("[data-overcome]").forEach(b=>b.onclick=()=>this.complete(Number(b.dataset.overcome),true));
    this.shadowRoot.querySelectorAll("[data-tomorrow]").forEach(b=>b.onclick=()=>this.occurrence(Number(b.dataset.tomorrow),"tomorrow"));
    this.shadowRoot.querySelectorAll("[data-date]").forEach(b=>b.onclick=()=>this.moveDate(Number(b.dataset.date)));
    this.shadowRoot.querySelectorAll("[data-skip]").forEach(b=>b.onclick=()=>this.occurrence(Number(b.dataset.skip),"skip"));
  }
}

class LifeManagerPlayerCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Player"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=LM.dataRoot(e).player||{};this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:20px}.top{display:flex;justify-content:space-between;align-items:center}.level{font-size:34px;font-weight:800}.bar{margin:14px 0}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}</style><ha-card><div class="top"><div><small>🎮 ${LM.esc(this._config.title)}</small><div class="level">Level ${Number(d.level||1)}</div></div><b>${Number(d.xp_into_level||0)}/100 XP</b></div><div class="bar"><div class="fill" style="width:${Math.min(100,Number(d.level_progress_percent||0))}%"></div></div><div class="stats"><div class="stat"><b>${Number(d.total_xp||0)}</b><small>Gesamt-XP</small></div><div class="stat"><b>${Number(d.coin_balance||0)} 🪙</b><small>Coins</small></div><div class="stat"><b>${Number(d.willpower_xp||0)} 🔥</b><small>Willpower</small></div></div></ha-card>`;}
}

class LifeManagerTrainingCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Trainingswoche"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=LM.dataRoot(e).training||{},it=Array.isArray(d.trainings)?d.trainings:[],n=["","Mo","Di","Mi","Do","Fr","Sa","So"];this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.head{display:flex;justify-content:space-between;align-items:center}.score{font-size:22px;font-weight:800}.row{display:grid;grid-template-columns:42px 28px 1fr;gap:8px;padding:10px 0;border-top:1px solid var(--divider-color)}.done{opacity:.6}</style><ha-card><div class="head"><div><small>🏋️ FITNESS</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div><div class="score">${Number(d.completed_count||0)}/${Number(d.planned_count||0)}</div></div>${it.map(x=>`<div class="row ${x.completed?"done":""}"><b>${n[x.weekday]||""}</b><span>${x.completed?"✅":"○"}</span><span>${LM.esc(x.name)}</span></div>`).join("")}</ha-card>`;}
}

class LifeManagerStreakCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Streaks"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=LM.dataRoot(e).streaks||{},it=Array.isArray(d.streaks)?d.streaks:[];this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.row{display:grid;grid-template-columns:1fr auto auto;gap:12px;padding:9px 0;border-top:1px solid var(--divider-color)}.fire{font-weight:800}.best{opacity:.6;font-size:12px}</style><ha-card><small>🔥 CONSISTENCY</small><h2 style="margin:2px 0 12px">${LM.esc(this._config.title)}</h2>${it.length?it.map(x=>`<div class="row"><span>${LM.esc(x.name)}</span><span class="fire">${Number(x.current_streak||0)} 🔥</span><span class="best">Best ${Number(x.best_streak||0)}</span></div>`).join(""):"<div>Noch keine Streaks.</div>"}</ha-card>`;}
}

class LifeManagerWeekCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Diese Woche"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=LM.dataRoot(e).week||{},days=Array.isArray(d.days)?d.days:[],names=["Mo","Di","Mi","Do","Fr","Sa","So"],max=Math.max(1,...days.map(x=>Number(x.xp||0)));this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.summary{display:flex;gap:16px;margin-bottom:18px}.summary b{font-size:20px}.summary small{display:block;opacity:.65}.chart{height:150px;display:grid;grid-template-columns:repeat(7,1fr);gap:8px;align-items:end}.col{display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end}.bd{width:70%;min-height:2px;background:var(--primary-color);border-radius:6px 6px 2px 2px}.label{font-size:11px;margin-top:6px}.val{font-size:10px;opacity:.65}</style><ha-card><small>📊 WEEKLY</small><h2 style="margin:2px 0 12px">${LM.esc(this._config.title)}</h2><div class="summary"><span><b>${Number(d.xp_total||0)}</b><small>XP</small></span><span><b>${Number(d.completed_total||0)}</b><small>Quests</small></span><span><b>${Number(d.willpower_xp_total||0)}</b><small>Willpower</small></span></div><div class="chart">${days.map((x,i)=>`<div class="col"><div class="val">${Number(x.xp||0)}</div><div class="bd" style="height:${Math.max(2,(Number(x.xp||0)/max)*110)}px"></div><div class="label">${names[i]||""}</div></div>`).join("")}</div></ha-card>`;}
}

class LifeManagerRewardCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._busy=null;}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Reward Shop",script:c.script||"script.life_reward_purchase"};this.render();}
  set hass(h){this._hass=h;this.render();}
  async buy(id){this._busy=id;this.render();try{await LM.callScript(this._hass,this._config.script,{reward_id:Number(id),quantity:1});await LM.refresh(this._hass,this._config.entity);}catch(e){alert(e?.message||"Reward konnte nicht gekauft werden.");}finally{this._busy=null;this.render();}}
  render(){if(!this._config)return;const e=this._hass?.states?.[this._config.entity];if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}const d=LM.dataRoot(e).rewards||{},rs=Array.isArray(d.rewards)?d.rewards:[];this.shadowRoot.innerHTML=`<style>${LM.styles()}ha-card{padding:18px}.head{display:flex;justify-content:space-between;align-items:center}.balance{font-size:26px;font-weight:800}.reward{display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;border-top:1px solid var(--divider-color);padding:12px 0}.reward small{display:block;opacity:.65}.cost{font-weight:800}.locked{opacity:.45}</style><ha-card><div class="head"><div><small>🪙 REWARDS</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div><div class="balance">${Number(d.coin_balance||0)} 🪙</div></div>${rs.map(x=>`<div class="reward ${x.can_afford?"":"locked"}"><div><b>${LM.esc(x.name)}</b><small>${LM.esc(x.description||"")}</small></div><div class="cost">${Number(x.cost||0)} 🪙</div><button data-buy="${x.id}" ${(!x.can_afford||this._busy===x.id)?"disabled":""}>${this._busy===x.id?"…":"Kaufen"}</button></div>`).join("")||"<div>Keine Rewards angelegt.</div>"}</ha-card>`;this.shadowRoot.querySelectorAll("button[data-buy]").forEach(b=>b.onclick=()=>this.buy(Number(b.dataset.buy)));}
}


class LifeManagerQuestManagerCard extends HTMLElement{
  constructor(){
    super();
    this.attachShadow({mode:"open"});
    this._editId=null;
    this._message="";
    this._filter="";
  }

  setConfig(c){
    this._config={
      entity:LM.entity(c),
      title:c.title||"Quest Manager",
      create_script:c.create_script||"script.life_quest_create",
      update_script:c.update_script||"script.life_quest_update",
      toggle_script:c.toggle_script||"script.life_quest_toggle"
    };
    this.render();
  }

  set hass(h){this._hass=h;this.render();}

  getData(){
    return LM.dataRoot(this._hass?.states?.[this._config.entity]).quest_manager||{};
  }

  async call(script,variables){
    await LM.callScript(this._hass,script,variables);
    await LM.refresh(this._hass,this._config.entity);
  }

  scheduleValues(q){
    const schedules=q?.schedules||[];
    return {
      weekdays:schedules.filter(s=>s.weekday).map(s=>Number(s.weekday)),
      interval_days:schedules.find(s=>s.interval_days)?.interval_days||null,
      next_due:schedules.find(s=>s.next_due)?.next_due||""
    };
  }

  openEditor(id=null){
    this._editId=id;
    this._message="";
    this.render();
  }

  closeEditor(){
    this._editId=null;
    this.render();
  }

  value(id){
    return this.shadowRoot.getElementById(id)?.value ?? "";
  }

  checked(id){
    return Boolean(this.shadowRoot.getElementById(id)?.checked);
  }

  nullableNumber(id){
    const v=this.value(id);
    return v==="" ? null : Number(v);
  }

  async save(){
    const weekdays=[...this.shadowRoot.querySelectorAll("input[data-weekday]:checked")]
      .map(x=>Number(x.dataset.weekday));

    const payload={
      name:this.value("lm-name").trim(),
      category_id:Number(this.value("lm-category")),
      quest_type:this.value("lm-type"),
      description:this.value("lm-description").trim()||null,
      xp_mode:this.value("lm-xpmode"),
      fixed_xp:this.nullableNumber("lm-fixed-xp"),
      estimated_minutes:this.nullableNumber("lm-minutes"),
      kbr:this.nullableNumber("lm-kbr"),
      frequency_days:this.nullableNumber("lm-frequency"),
      project_factor:this.nullableNumber("lm-project-factor"),
      priority:this.value("lm-priority")||"normal",
      due_date:this.value("lm-due-date")||null,
      weekdays,
      interval_days:this.nullableNumber("lm-interval"),
      next_due:this.value("lm-next-due")||null,
      active:this.checked("lm-active")
    };

    if(!payload.name){
      this._message="❌ Name fehlt.";
      this.render();
      return;
    }

    try{
      if(this._editId){
        await this.call(this._config.update_script,{quest_id:Number(this._editId),...payload});
        this._message="✅ Quest gespeichert.";
      }else{
        await this.call(this._config.create_script,payload);
        this._message="✅ Quest angelegt.";
      }
      this._editId=null;
      await LM.refresh(this._hass,this._config.entity);
      this.render();
    }catch(e){
      console.error("Life Manager Quest Save Error:",e);
      this._message=`❌ ${e?.message||"Quest konnte nicht gespeichert werden."}`;
      this.render();
    }
  }

  async toggle(id){
    try{
      await this.call(this._config.toggle_script,{quest_id:Number(id)});
      this._message="✅ Status geändert.";
      this.render();
    }catch(e){
      this._message=`❌ ${e?.message||"Status konnte nicht geändert werden."}`;
      this.render();
    }
  }

  renderEditor(d){
    const cats=Array.isArray(d.categories)?d.categories:[];
    const q=this._editId ? (d.quests||[]).find(x=>Number(x.id)===Number(this._editId)) : null;
    const sched=this.scheduleValues(q);

    const weekdayBtns=[1,2,3,4,5,6,7].map((n,i)=>{
      const names=["Mo","Di","Mi","Do","Fr","Sa","So"];
      return `<label class="weekday">
        <input type="checkbox" data-weekday="${n}" ${sched.weekdays.includes(n)?"checked":""}>
        <span>${names[i]}</span>
      </label>`;
    }).join("");

    return `
      <div class="editor">
        <div class="editor-head">
          <h3>${q?"Quest bearbeiten":"Neue Quest"}</h3>
          <button class="secondary" id="lm-cancel">Schließen</button>
        </div>

        <div class="grid">
          <label class="wide">Name
            <input id="lm-name" value="${LM.esc(q?.name||"")}">
          </label>

          <label>Kategorie
            <select id="lm-category">
              ${cats.map(c=>`<option value="${c.id}" ${Number(q?.category_id)===Number(c.id)?"selected":""}>${LM.esc(c.name)}</option>`).join("")}
            </select>
          </label>

          <label>Typ
            <select id="lm-type">
              ${["routine","habit","training","project","milestone"].map(x=>`<option ${q?.quest_type===x?"selected":""}>${x}</option>`).join("")}
            </select>
          </label>

          <label class="wide">Beschreibung
            <textarea id="lm-description">${LM.esc(q?.description||"")}</textarea>
          </label>

          <label>XP-Modus
            <select id="lm-xpmode">
              <option value="formula" ${q?.xp_mode!=="fixed"?"selected":""}>Automatisch</option>
              <option value="fixed" ${q?.xp_mode==="fixed"?"selected":""}>Fix</option>
            </select>
          </label>

          <label>Feste XP
            <input id="lm-fixed-xp" type="number" min="0" value="${q?.fixed_xp??""}">
          </label>

          <label>Zeit (Min.)
            <input id="lm-minutes" type="number" min="0" value="${q?.estimated_minutes??""}">
          </label>

          <label>KBR
            <select id="lm-kbr">
              <option value="">–</option>
              ${[1,2,3,4,5].map(n=>`<option value="${n}" ${Number(q?.kbr)===n?"selected":""}>${n}</option>`).join("")}
            </select>
          </label>

          <label>Frequenz (Tage)
            <input id="lm-frequency" type="number" min="1" value="${q?.frequency_days??""}">
          </label>

          <label>Projektfaktor
            <input id="lm-project-factor" type="number" min="0" step="0.5" value="${q?.project_factor??""}">
          </label>

          <label>Priorität
            <select id="lm-priority">
              <option value="low" ${q?.priority==="low"?"selected":""}>Niedrig</option>
              <option value="normal" ${!q?.priority||q?.priority==="normal"?"selected":""}>Normal</option>
              <option value="high" ${q?.priority==="high"?"selected":""}>Hoch</option>
              <option value="critical" ${q?.priority==="critical"?"selected":""}>Kritisch</option>
            </select>
          </label>

          <label>Fällig am
            <input id="lm-due-date" type="date" value="${q?.due_date||""}">
          </label>

          <div class="wide">
            <div class="field-title">Wochentage</div>
            <div class="weekdays">${weekdayBtns}</div>
          </div>

          <label>Intervall (Tage)
            <input id="lm-interval" type="number" min="1" value="${sched.interval_days??""}">
          </label>

          <label>Nächste Fälligkeit
            <input id="lm-next-due" type="date" value="${sched.next_due||""}">
          </label>

          <label class="switch-row wide">
            <input id="lm-active" type="checkbox" ${q?.active===false?"":"checked"}>
            Aktiv
          </label>
        </div>

        <div class="editor-actions">
          <button class="secondary" id="lm-cancel2">Abbrechen</button>
          <button id="lm-save">Speichern</button>
        </div>
      </div>
    `;
  }

  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){
      this.shadowRoot.innerHTML=LM.missing(this._config.entity);
      return;
    }

    const d=(e.attributes||{}).quest_manager||{};
    let quests=Array.isArray(d.quests)?d.quests:[];

    if(this._filter){
      const f=this._filter.toLowerCase();
      quests=quests.filter(q=>
        String(q.name||"").toLowerCase().includes(f) ||
        String(q.category||"").toLowerCase().includes(f)
      );
    }

    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .head{display:flex;justify-content:space-between;align-items:center;gap:12px}
        .toolbar{display:flex;gap:8px;margin:12px 0}
        .toolbar input{flex:1}
        .message{padding:9px 11px;background:var(--secondary-background-color);border-radius:9px;margin:10px 0}
        .row{display:grid;grid-template-columns:1fr auto auto auto;gap:8px;align-items:center;border-top:1px solid var(--divider-color);padding:10px 0}
        .row small{display:block;opacity:.65}
        .inactive{opacity:.45}
        input,select,textarea{box-sizing:border-box;width:100%;padding:9px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color)}
        textarea{min-height:70px;resize:vertical}
        .editor{margin-top:14px;padding:14px;background:var(--secondary-background-color);border-radius:12px}
        .editor-head,.editor-actions{display:flex;justify-content:space-between;align-items:center;gap:8px}
        .editor-head h3{margin:0}
        .editor-actions{justify-content:flex-end;margin-top:14px}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
        .grid label{font-size:12px;font-weight:600}
        .wide{grid-column:1/-1}
        .field-title{font-size:12px;font-weight:600;margin-bottom:6px}
        .weekdays{display:flex;gap:6px;flex-wrap:wrap}
        .weekday input{display:none}
        .weekday span{display:inline-block;padding:7px 9px;border-radius:8px;background:var(--card-background-color);border:1px solid var(--divider-color)}
        .weekday input:checked+span{background:var(--primary-color);color:white}
        .switch-row{display:flex!important;align-items:center;gap:8px}
        .switch-row input{width:auto}
        @media(max-width:700px){
          .row{grid-template-columns:1fr auto}
          .grid{grid-template-columns:1fr}
          .wide{grid-column:1}
        }
      </style>

      <ha-card>
        <div class="head">
          <div><small>⚙️ ADMIN</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div>
          <button id="lm-new">+ Neue Quest</button>
        </div>

        <div class="toolbar">
          <input id="lm-search" placeholder="Quest suchen…" value="${LM.esc(this._filter)}">
        </div>

        ${this._message?`<div class="message">${LM.esc(this._message)}</div>`:""}

        ${this._editId!==null ? this.renderEditor(d) : ""}

        <div class="list">
          ${quests.map(q=>`
            <div class="row ${q.active?"":"inactive"}">
              <div>
                <b>${LM.esc(q.name)}</b>
                <small>${LM.esc(q.category)} · ${LM.esc(q.quest_type)} · ${LM.esc(q.xp_mode)}${q.kbr?` · KBR ${q.kbr}`:""}${q.priority?` · ${LM.esc(q.priority)}`:""}${q.due_date?` · fällig ${LM.esc(q.due_date)}`:""}</small>
              </div>
              <span>${q.active?"Aktiv":"Aus"}</span>
              <button class="secondary" data-edit="${q.id}">Bearbeiten</button>
              <button class="secondary" data-toggle="${q.id}">${q.active?"Deaktivieren":"Aktivieren"}</button>
            </div>
          `).join("") || "<div>Keine Quests gefunden.</div>"}
        </div>
      </ha-card>
    `;

    this.shadowRoot.getElementById("lm-new").onclick=()=>this.openEditor(0);
    const search=this.shadowRoot.getElementById("lm-search");
    search.oninput=()=>{this._filter=search.value;};

    this.shadowRoot.querySelectorAll("button[data-edit]").forEach(b=>{
      b.onclick=()=>this.openEditor(Number(b.dataset.edit));
    });
    this.shadowRoot.querySelectorAll("button[data-toggle]").forEach(b=>{
      b.onclick=()=>this.toggle(Number(b.dataset.toggle));
    });

    if(this._editId!==null){
      this.shadowRoot.getElementById("lm-save").onclick=()=>this.save();
      this.shadowRoot.getElementById("lm-cancel").onclick=()=>this.closeEditor();
      this.shadowRoot.getElementById("lm-cancel2").onclick=()=>this.closeEditor();
    }
  }
}


class LifeManagerAchievementsCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Achievements"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const d=LM.dataRoot(e).achievements||{};
    const items=Array.isArray(d.achievements)?d.achievements:[];
    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .head{display:flex;justify-content:space-between;align-items:center}
        .score{font-size:24px;font-weight:800}
        .row{display:grid;grid-template-columns:34px 1fr auto;gap:10px;align-items:center;padding:11px 0;border-top:1px solid var(--divider-color)}
        .locked{opacity:.5}
        .name{font-weight:700}
        .desc{font-size:12px;opacity:.65}
        .progress{font-size:12px;font-weight:700}
      </style>
      <ha-card>
        <div class="head">
          <div><small>🏆 PROGRESS</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div>
          <div class="score">${Number(d.unlocked_count||0)}/${Number(d.total_count||0)}</div>
        </div>
        ${items.map(x=>`
          <div class="row ${x.unlocked?"":"locked"}">
            <ha-icon icon="${LM.esc(x.icon||"mdi:trophy-outline")}"></ha-icon>
            <div>
              <div class="name">${x.unlocked?"✅ ":""}${LM.esc(x.name)}</div>
              <div class="desc">${LM.esc(x.description||"")}</div>
            </div>
            <div class="progress">${Number(x.current||0)}/${Number(x.target||0)}</div>
          </div>
        `).join("")||"<div>Noch keine Achievements vorhanden.</div>"}
      </ha-card>
    `;
  }
}

class LifeManagerBossCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Boss Fights"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const d=LM.dataRoot(e).boss_fights||{};
    const items=Array.isArray(d.active)?d.active:[];
    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .head{display:flex;justify-content:space-between;align-items:center}
        .count{font-size:22px;font-weight:800}
        .boss{display:grid;grid-template-columns:34px 1fr auto;gap:10px;align-items:center;padding:11px 0;border-top:1px solid var(--divider-color)}
        .meta{font-size:12px;opacity:.65}
        .xp{font-weight:800}
      </style>
      <ha-card>
        <div class="head">
          <div><small>⚔️ KBR 5</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div>
          <div class="count">${Number(d.completed_total||0)} besiegt</div>
        </div>
        ${items.map(x=>`
          <div class="boss">
            <ha-icon icon="mdi:sword-cross"></ha-icon>
            <div>
              <b>${LM.esc(x.name)}</b>
              <div class="meta">${LM.esc(x.category)} · KBR ${Number(x.kbr||5)}</div>
            </div>
            <div class="xp">+${Number(x.xp||0)} XP</div>
          </div>
        `).join("")||"<div>Aktuell keine aktiven Boss Fights.</div>"}
      </ha-card>
    `;
  }
}


class LifeManagerCoinHistoryCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Coin History"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const d=LM.dataRoot(e).rewards||{};
    const items=Array.isArray(d.coin_history)?d.coin_history:[];
    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .row{display:grid;grid-template-columns:auto 1fr auto;gap:10px;padding:9px 0;border-top:1px solid var(--divider-color)}
        .amount{font-weight:800}
        .pos{color:var(--success-color,#4caf50)}
        .neg{color:var(--error-color,#f44336)}
        .time{font-size:11px;opacity:.55}
      </style>
      <ha-card>
        <small>🪙 LEDGER</small>
        <h2 style="margin:2px 0 12px">${LM.esc(this._config.title)}</h2>
        ${items.map(x=>`
          <div class="row">
            <span class="amount ${Number(x.amount)>=0?"pos":"neg"}">${Number(x.amount)>=0?"+":""}${Number(x.amount)} 🪙</span>
            <span>${LM.esc(x.reason||"")}</span>
            <span class="time">${LM.esc((x.created_at||"").replace("T"," ").slice(0,16))}</span>
          </div>
        `).join("")||"<div>Noch keine Coin-Bewegungen.</div>"}
      </ha-card>
    `;
  }
}

class LifeManagerSavingsCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Sparziele",script:c.script||"script.life_savings_goal_create"};this.render();}
  set hass(h){this._hass=h;this.render();}
  async create(){
    const name=prompt("Name des Sparziels:");
    if(!name)return;
    const target=Number(prompt("Ziel in Coins:","50"));
    if(!target)return;
    try{
      await LM.callScript(this._hass,this._config.script,{name,target_coins:target,reward_id:null});
      await LM.refresh(this._hass,this._config.entity);
    }catch(e){alert(e?.message||"Sparziel konnte nicht erstellt werden.");}
  }
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const d=LM.dataRoot(e).rewards||{};
    const goals=Array.isArray(d.savings_goals)?d.savings_goals:[];
    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .head{display:flex;justify-content:space-between;align-items:center}
        .goal{padding:12px 0;border-top:1px solid var(--divider-color)}
        .goal-head{display:flex;justify-content:space-between;gap:12px}
        .bar{margin-top:8px}
        .meta{font-size:12px;opacity:.65;margin-top:4px}
      </style>
      <ha-card>
        <div class="head">
          <div><small>🎯 SAVINGS</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div>
          <button id="add-goal">+ Ziel</button>
        </div>
        ${goals.map(g=>`
          <div class="goal">
            <div class="goal-head">
              <b>${LM.esc(g.name)}</b>
              <span>${Number(g.current_coins||0)} / ${Number(g.target_coins||0)} 🪙</span>
            </div>
            <div class="bar"><div class="fill" style="width:${Math.min(100,Number(g.progress_percent||0))}%"></div></div>
            <div class="meta">${Number(g.remaining||0)} Coins fehlen noch</div>
          </div>
        `).join("")||"<div>Noch keine Sparziele.</div>"}
      </ha-card>
    `;
    this.shadowRoot.getElementById("add-goal").onclick=()=>this.create();
  }
}

class LifeManagerRewardManagerCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._editId=null;this._message="";}
  setConfig(c){
    this._config={
      entity:LM.entity(c),
      title:c.title||"Reward Manager",
      create_script:c.create_script||"script.life_reward_create",
      update_script:c.update_script||"script.life_reward_update",
      toggle_script:c.toggle_script||"script.life_reward_toggle"
    };
    this.render();
  }
  set hass(h){this._hass=h;this.render();}
  data(){return LM.dataRoot(this._hass?.states?.[this._config.entity]).rewards||{};}
  async call(script,variables){await LM.callScript(this._hass,script,variables);await LM.refresh(this._hass,this._config.entity);}
  edit(id){this._editId=id;this.render();}
  close(){this._editId=null;this.render();}
  async save(){
    const name=this.shadowRoot.getElementById("rm-name").value.trim();
    const cost=Number(this.shadowRoot.getElementById("rm-cost").value);
    const description=this.shadowRoot.getElementById("rm-description").value.trim()||null;
    const icon=this.shadowRoot.getElementById("rm-icon").value.trim()||null;
    const sort_order=Number(this.shadowRoot.getElementById("rm-sort").value||0);
    const active=this.shadowRoot.getElementById("rm-active").checked;
    try{
      if(this._editId){
        await this.call(this._config.update_script,{reward_id:this._editId,name,description,cost,icon,sort_order,active});
      }else{
        await this.call(this._config.create_script,{name,description,cost,icon,sort_order,active});
      }
      this._message="✅ Reward gespeichert.";
      this._editId=null;
      this.render();
    }catch(e){this._message=`❌ ${e?.message||"Fehler"}`;this.render();}
  }
  async toggle(id){
    try{await this.call(this._config.toggle_script,{reward_id:id});this._message="✅ Status geändert.";this.render();}
    catch(e){this._message=`❌ ${e?.message||"Fehler"}`;this.render();}
  }
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const d=this.data(),rs=Array.isArray(d.rewards)?d.rewards:[];
    const q=this._editId?rs.find(x=>Number(x.id)===Number(this._editId)):null;
    const editor=this._editId!==null?`
      <div class="editor">
        <h3>${q?"Reward bearbeiten":"Neuer Reward"}</h3>
        <div class="grid">
          <label>Name<input id="rm-name" value="${LM.esc(q?.name||"")}"></label>
          <label>Coins<input id="rm-cost" type="number" min="0" value="${q?.cost??""}"></label>
          <label class="wide">Beschreibung<textarea id="rm-description">${LM.esc(q?.description||"")}</textarea></label>
          <label>Icon<input id="rm-icon" value="${LM.esc(q?.icon||"mdi:gift")}"></label>
          <label>Sortierung<input id="rm-sort" type="number" value="${q?.sort_order??0}"></label>
          <label class="wide"><input id="rm-active" type="checkbox" ${q?.active===false?"":"checked"}> Aktiv</label>
        </div>
        <div class="actions"><button class="secondary" id="rm-cancel">Abbrechen</button><button id="rm-save">Speichern</button></div>
      </div>`:"";
    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .head{display:flex;justify-content:space-between;align-items:center}
        .row{display:grid;grid-template-columns:1fr auto auto auto;gap:8px;align-items:center;border-top:1px solid var(--divider-color);padding:10px 0}
        .inactive{opacity:.45}
        .editor{margin:12px 0;padding:12px;background:var(--secondary-background-color);border-radius:12px}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
        .wide{grid-column:1/-1}
        input,textarea{box-sizing:border-box;width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color)}
        .actions{display:flex;justify-content:flex-end;gap:8px;margin-top:10px}
      </style>
      <ha-card>
        <div class="head"><div><small>🛠️ REWARDS</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div><button id="rm-new">+ Neuer Reward</button></div>
        ${this._message?`<div>${LM.esc(this._message)}</div>`:""}
        ${editor}
        ${rs.map(r=>`<div class="row ${r.active?"":"inactive"}"><div><b>${LM.esc(r.name)}</b><small>${Number(r.cost)} 🪙</small></div><span>${r.active?"Aktiv":"Aus"}</span><button class="secondary" data-edit="${r.id}">Bearbeiten</button><button class="secondary" data-toggle="${r.id}">${r.active?"Deaktivieren":"Aktivieren"}</button></div>`).join("")}
      </ha-card>`;
    this.shadowRoot.getElementById("rm-new").onclick=()=>{this._editId=0;this.render();};
    this.shadowRoot.querySelectorAll("[data-edit]").forEach(b=>b.onclick=()=>this.edit(Number(b.dataset.edit)));
    this.shadowRoot.querySelectorAll("[data-toggle]").forEach(b=>b.onclick=()=>this.toggle(Number(b.dataset.toggle)));
    if(this._editId!==null){
      this.shadowRoot.getElementById("rm-save").onclick=()=>this.save();
      this.shadowRoot.getElementById("rm-cancel").onclick=()=>this.close();
    }
  }
}


class LifeManagerQuickActionsCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});this._busy=false;this._message="";}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Quick Actions",finalize_script:c.finalize_script||"script.life_day_finalize"};this.render();}
  set hass(h){this._hass=h;this.render();}
  async finalize(){
    if(this._busy)return;this._busy=true;this._message="";this.render();
    try{
      await LM.callScript(this._hass,this._config.finalize_script,{});
      await LM.refresh(this._hass,this._config.entity);
      this._message="✅ Tagesabschluss durchgeführt.";
    }catch(e){this._message=`❌ ${e?.message||"Tagesabschluss fehlgeschlagen."}`;}
    finally{this._busy=false;this.render();}
  }
  async refresh(){
    if(this._busy)return;this._busy=true;this.render();
    try{
      await this._hass.callService("homeassistant","update_entity",{entity_id:this._config.entity});
      this._message="✅ Daten aktualisiert.";
    }catch(e){this._message=`❌ ${e?.message||"Aktualisierung fehlgeschlagen."}`;}
    finally{this._busy=false;this.render();}
  }
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const today=LM.dataRoot(e).today||{};
    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:14px 18px}
        .head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
        .actions{display:flex;gap:8px;flex-wrap:wrap}
        .status{font-size:12px;opacity:.7;margin-top:8px}
        .summary{font-size:12px;opacity:.65}
        @media(max-width:520px){.actions{width:100%}.actions button{flex:1;min-height:44px}}
      </style>
      <ha-card>
        <div class="head">
          <div><b>${LM.esc(this._config.title)}</b><div class="summary">${Number(today.progress_percent||0)}% · ${Number(today.xp_today||0)}/${Number(today.possible_xp||0)} XP · ${Number(today.projected_coins||0)} 🪙</div></div>
          <div class="actions">
            <button class="secondary" id="lm-refresh" ${this._busy?"disabled":""}>↻ Aktualisieren</button>
            <button id="lm-finalize" ${this._busy||today.day_finalized?"disabled":""}>${today.day_finalized?"✓ Abgeschlossen":"Tagesabschluss"}</button>
          </div>
        </div>
        ${this._message?`<div class="status">${LM.esc(this._message)}</div>`:""}
      </ha-card>`;
    this.shadowRoot.getElementById("lm-refresh").onclick=()=>this.refresh();
    this.shadowRoot.getElementById("lm-finalize").onclick=()=>this.finalize();
  }
}


class LifeManagerPlannerCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Was soll ich jetzt machen?"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}

    const d=LM.dataRoot(e).planner||{};
    const rec=d.recommendation||null;
    const focus=Array.isArray(d.focus)?d.focus:[];

    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .hero{padding:14px;border-radius:14px;background:var(--secondary-background-color);margin-top:10px}
        .hero-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
        .name{font-size:20px;font-weight:800}
        .meta,.reason{font-size:12px;opacity:.68;margin-top:5px}
        .score{font-weight:800;white-space:nowrap}
        .focus{margin-top:14px}
        .row{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:9px 0;border-top:1px solid var(--divider-color)}
        .rank{font-weight:800;opacity:.65}
        .empty{opacity:.65;padding:12px 0}
      </style>
      <ha-card>
        <small>🧭 PLANNER</small>
        <h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2>
        <div style="font-size:12px;opacity:.6;margin-top:4px">${Number(d.today_open_count||0)} offene Tagesquests · ${Number(d.planner_candidate_count||0)} vom Planner berücksichtigt</div>

        ${rec?`
          <div class="hero">
            <div class="hero-head">
              <div>
                <div class="name">${rec.boss_fight?"⚔️ ":""}${LM.esc(rec.name)}</div>
                <div class="meta">${LM.esc(rec.category)} · ${Number(rec.estimated_minutes||0)} Min · KBR ${Number(rec.kbr||1)} · ${LM.esc(rec.priority||"normal")} · +${Number(rec.xp||0)} XP${rec.due_date?` · fällig ${LM.esc(rec.due_date)}`:""}</div>
                <div class="reason"><b>Warum:</b> ${LM.esc(rec.reason||"heute sinnvoll")}</div>
              </div>
              <div class="score">${Number(rec.score||0)} P</div>
            </div>
          </div>
        `:`<div class="empty">🎉 Aktuell gibt es nichts Dringendes zu empfehlen.</div>`}

        ${focus.length?`
          <div class="focus">
            <b>Tagesfokus</b>
            ${focus.map((x,i)=>`
              <div class="row">
                <span class="rank">${i+1}.</span>
                <span>${LM.esc(x.name)}<div class="meta">${LM.esc(x.reason||"")}</div></span>
                <span>+${Number(x.xp||0)} XP</span>
              </div>
            `).join("")}
          </div>
        `:""}
      </ha-card>
    `;
  }
}

class LifeManagerWeeklyReviewCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Wochenrückblick"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}

    const d=LM.dataRoot(e).weekly_review||{};
    const insights=Array.isArray(d.insights)?d.insights:[];
    const focus=Array.isArray(d.next_focus)?d.next_focus:[];

    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}
        .stat{text-align:left}
        .section{margin-top:14px}
        .line{padding:7px 0;border-top:1px solid var(--divider-color);font-size:13px}
        @media(max-width:620px){.stats{grid-template-columns:repeat(2,1fr)}}
      </style>
      <ha-card>
        <small>📝 REVIEW</small>
        <h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2>

        <div class="stats">
          <div class="stat"><b>${Number(d.xp_total||0)}</b><small>XP</small></div>
          <div class="stat"><b>${Number(d.completed_total||0)}</b><small>Quests</small></div>
          <div class="stat"><b>${Number(d.training_completed||0)}/${Number(d.training_planned||0)}</b><small>Training</small></div>
          <div class="stat"><b>${Number(d.willpower_xp_total||0)}</b><small>Willpower</small></div>
        </div>

        <div class="section">
          <b>Diese Woche</b>
          ${insights.map(x=>`<div class="line">• ${LM.esc(x)}</div>`).join("")||'<div class="line">Noch zu wenig Daten für einen Rückblick.</div>'}
        </div>

        <div class="section">
          <b>Nächster Fokus</b>
          ${focus.map(x=>`<div class="line">→ ${LM.esc(x)}</div>`).join("")}
        </div>
      </ha-card>
    `;
  }
}


class LifeManagerDayPlanCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Dein Tagesplan"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}

    const d=LM.dataRoot(e).day_plan||{};
    const plan=Array.isArray(d.plan)?d.plan:[];
    const missing=Array.isArray(d.missing_this_week)?d.missing_this_week:[];

    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .item{display:grid;grid-template-columns:34px 1fr auto;gap:10px;align-items:center;padding:11px 0;border-top:1px solid var(--divider-color)}
        .order{font-size:18px;font-weight:800;opacity:.6}
        .meta{font-size:12px;opacity:.65;margin-top:3px}
        .week{margin-top:16px}
        .goal{padding:8px 0;border-top:1px solid var(--divider-color)}
      </style>
      <ha-card>
        <small>🗓️ PLAN</small>
        <h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2>

        ${plan.length?plan.map(x=>`
          <div class="item">
            <span class="order">${Number(x.order)}</span>
            <div>
              <b>${LM.esc(x.name)}</b>
              <div class="meta">${LM.esc(x.reason||"")} · ${Number(x.estimated_minutes||0)} Min</div>
            </div>
            <span>+${Number(x.xp||0)} XP</span>
          </div>
        `).join(""):'<div style="opacity:.65;padding:12px 0">Heute ist aktuell nichts mehr einzuplanen.</div>'}

        <div class="week">
          <b>Diese Woche fehlt noch</b>
          ${missing.length?missing.map(g=>`
            <div class="goal">
              ${LM.esc(g.name)} · noch ${Number(g.remaining||0)}
            </div>
          `).join(""):'<div class="goal">✅ Alle Wochenziele erreicht.</div>'}
        </div>
      </ha-card>
    `;
  }
}

class LifeManagerWeeklyGoalsCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Wochenziele",script:c.script||"script.life_weekly_goal_create"};this.render();}
  set hass(h){this._hass=h;this.render();}
  async create(){
    const name=prompt("Name des Wochenziels:");
    if(!name)return;
    const target=Number(prompt("Wie oft pro Woche?","1"));
    if(!target)return;
    try{
      await LM.callScript(this._hass,this._config.script,{
        name,
        goal_type:"quest",
        quest_id:null,
        target_count:target,
        sort_order:0
      });
      await LM.refresh(this._hass,this._config.entity);
    }catch(e){alert(e?.message||"Wochenziel konnte nicht erstellt werden.");}
  }
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}

    const d=LM.dataRoot(e).weekly_goals||{};
    const goals=Array.isArray(d.goals)?d.goals:[];

    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .head{display:flex;justify-content:space-between;align-items:center}
        .goal{padding:11px 0;border-top:1px solid var(--divider-color)}
        .goal-head{display:flex;justify-content:space-between;gap:12px}
        .bar{margin-top:8px}
        .meta{font-size:12px;opacity:.65;margin-top:4px}
      </style>
      <ha-card>
        <div class="head">
          <div><small>🎯 WEEKLY</small><h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2></div>
          <button id="wg-add">+ Ziel</button>
        </div>
        ${goals.map(g=>`
          <div class="goal">
            <div class="goal-head">
              <b>${g.completed?"✅ ":""}${LM.esc(g.name)}</b>
              <span>${Number(g.current_count||0)}/${Number(g.target_count||0)}</span>
            </div>
            <div class="bar"><div class="fill" style="width:${Math.min(100,Number(g.progress_percent||0))}%"></div></div>
            <div class="meta">${g.completed?"Ziel erreicht":`${Number(g.remaining||0)} fehlen noch`}</div>
          </div>
        `).join("")||"<div>Noch keine Wochenziele.</div>"}
      </ha-card>
    `;
    this.shadowRoot.getElementById("wg-add").onclick=()=>this.create();
  }
}


class LifeManagerAnalyticsCard extends HTMLElement{
  constructor(){super();this.attachShadow({mode:"open"});}
  setConfig(c){this._config={entity:LM.entity(c),title:c.title||"Insights"};this.render();}
  set hass(h){this._hass=h;this.render();}
  render(){
    if(!this._config)return;
    const e=this._hass?.states?.[this._config.entity];
    if(!e){this.shadowRoot.innerHTML=LM.missing(this._config.entity);return;}
    const d=LM.dataRoot(e).analytics||{};
    const cats=Array.isArray(d.categories)?d.categories.filter(x=>x.completions>0).slice(0,5):[];
    const insights=Array.isArray(d.insights)?d.insights:[];
    const max=Math.max(1,...cats.map(x=>Number(x.completions||0)));

    this.shadowRoot.innerHTML=`
      <style>
        ${LM.styles()}
        ha-card{padding:18px}
        .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}
        .category{display:grid;grid-template-columns:120px 1fr auto;gap:8px;align-items:center;padding:7px 0}
        .mini{height:7px;background:var(--divider-color);border-radius:999px;overflow:hidden}
        .mini>span{display:block;height:100%;background:var(--primary-color)}
        .insight{padding:8px 0;border-top:1px solid var(--divider-color);font-size:13px}
        @media(max-width:600px){.stats{grid-template-columns:repeat(2,1fr)}.category{grid-template-columns:90px 1fr auto}}
      </style>
      <ha-card>
        <small>📈 30 TAGE</small>
        <h2 style="margin:2px 0">${LM.esc(this._config.title)}</h2>
        <div class="stats">
          <div class="stat"><b>${Number(d.completion_total||0)}</b><small>Quests</small></div>
          <div class="stat"><b>${Number(d.training_total||0)}</b><small>Trainings</small></div>
          <div class="stat"><b>${Number(d.moved_total||0)}</b><small>Verschoben</small></div>
          <div class="stat"><b>${Number(d.skipped_total||0)}</b><small>Ausgelassen</small></div>
        </div>
        <b>Stärkste Kategorien</b>
        ${cats.map(x=>`
          <div class="category">
            <span>${LM.esc(x.category)}</span>
            <div class="mini"><span style="width:${Math.round(Number(x.completions||0)/max*100)}%"></span></div>
            <b>${Number(x.completions||0)}</b>
          </div>
        `).join("")||'<div style="opacity:.65;padding:8px 0">Noch zu wenig Daten.</div>'}
        <div style="margin-top:12px"><b>Insights</b></div>
        ${insights.map(x=>`<div class="insight">• ${LM.esc(x)}</div>`).join("")}
      </ha-card>
    `;
  }
}

const defs=[
["life-manager-card",LifeManagerCard],
["life-manager-player-card",LifeManagerPlayerCard],
["life-manager-training-card",LifeManagerTrainingCard],
["life-manager-streak-card",LifeManagerStreakCard],
["life-manager-week-card",LifeManagerWeekCard],
["life-manager-reward-card",LifeManagerRewardCard],
["life-manager-quest-manager-card",LifeManagerQuestManagerCard],
["life-manager-achievements-card",LifeManagerAchievementsCard],
["life-manager-boss-card",LifeManagerBossCard],
["life-manager-coin-history-card",LifeManagerCoinHistoryCard],
["life-manager-savings-card",LifeManagerSavingsCard],
["life-manager-reward-manager-card",LifeManagerRewardManagerCard],
["life-manager-quick-actions-card",LifeManagerQuickActionsCard],
["life-manager-planner-card",LifeManagerPlannerCard],
["life-manager-weekly-review-card",LifeManagerWeeklyReviewCard],
["life-manager-day-plan-card",LifeManagerDayPlanCard],
["life-manager-weekly-goals-card",LifeManagerWeeklyGoalsCard],
["life-manager-analytics-card",LifeManagerAnalyticsCard]
];
for(const [n,c] of defs){if(!customElements.get(n))customElements.define(n,c);}
