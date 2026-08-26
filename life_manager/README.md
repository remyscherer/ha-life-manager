# Life Manager v1.3.0

## Neu

### Automatischer Tagesabschluss
Home Assistant führt um 23:55 automatisch aus:

`script.life_day_finalize`

Das ruft geschützt per `rest_command` auf:

`POST /day/finalize`

Coins werden nur einmal pro Datum verbucht.

### Vollständiger Quest-Editor
Der Quest Manager kann jetzt:

- neue Quest anlegen
- Quest bearbeiten
- Kategorie ändern
- Quest-Typ ändern
- XP-Modus ändern
- feste XP ändern
- Zeit/KBR/Frequenz ändern
- Wochentage ändern
- Intervall ändern
- aktivieren/deaktivieren

Der Editor verwendet weiterhin Home-Assistant-Skripte.
Der API-Key bleibt ausschließlich in `secrets.yaml`.

## Update

1. Add-on stoppen.
2. Dateien ersetzen.
3. Add-on neu bauen.
4. `/health` muss Version `1.3.0` liefern.
5. Frontend-Ressource auf `/local/life-manager.js?v=070` ändern.
6. `examples/life_manager_package.yaml` übernehmen/abgleichen.
7. YAML-Konfiguration prüfen.
8. Home Assistant neu starten.
9. Browser/App vollständig neu laden.

## Datenbank
Keine zusätzliche Migration gegenüber v0.6.x erforderlich.

## Automatischer Tagesabschluss
Standard: 23:55.

Wenn du einen anderen Zeitpunkt möchtest, ändere in der Package-Datei:

```yaml
at: "23:55:00"
```

## Quest Editor
Card:

```yaml
type: custom:life-manager-quest-manager-card
entity: sensor.life_manager
create_script: script.life_quest_create
update_script: script.life_quest_update
toggle_script: script.life_quest_toggle
```

## v1.3.0 repository cleanup

- Example configuration no longer contains a personal LAN IP.
- Repository ships with a basic GitHub Actions validation workflow.
- Repository metadata is included at the repository root.


## v1.3.0 Quest Manager repair

- Quest creation payload uses Home Assistant's `to_json` filter.
- New inline Quest Editor replaces prompt dialogs.
- Categories, type, XP mode, KBR and schedules are editable in a proper form.
- API now exposes `GET /quests`.
- Create/update endpoints return the saved quest.
- API writes create/update events to the add-on log.


## v1.3.0 Frontend refresh fix

- Schreibaktionen warten bevorzugt auf den direkten Home-Assistant-Script-Service.
- Fallback auf `script.turn_on` bleibt erhalten.
- Nach Schreibaktionen wird der REST-Sensor mehrfach aktualisiert.
- Der Quest Manager zeigt unten `Frontend v1.3.0`, damit Cache-Probleme sofort erkennbar sind.


## v1.3.0 Achievements, Boss Fights & Streaks

- Achievements werden automatisch aus bestehenden Daten berechnet und freigeschaltet.
- Neue Achievement Card: `custom:life-manager-achievements-card`
- KBR-5-Quests werden als Boss Fights ausgewertet.
- Neue Boss Card: `custom:life-manager-boss-card`
- Bei `Kein Bock` auf einer KBR-5-Quest gibt es 15 statt 10 Willpower XP.
- Streaks zählen jetzt erledigte geplante Termine statt bloß aufeinanderfolgende Kalendertage.
- Heute offene geplante Aufgaben brechen die Streak nicht sofort.


## v1.3.0 Reward System

- Reward Manager: Rewards direkt in Home Assistant anlegen, bearbeiten und deaktivieren.
- Coin History Card mit den letzten 20 Coin-Bewegungen.
- Sparziele mit Fortschrittsanzeige.
- Neue Tabellenstruktur für Savings Goals.
- Reward Shop zeigt weiterhin nur aktive Rewards als kaufbar an.


## v1.3.0 Automation & Polish

- Datenbankmigrationen laufen automatisch vor dem API-Start.
- `schema_migrations` protokolliert bereits angewendete Migrationen.
- Bei einer fehlgeschlagenen Migration startet die API bewusst nicht.
- `/health` liefert zusätzlich `schema_version`.
- Neue Quick-Actions-Card für manuelles Aktualisieren und Tagesabschluss.
- Manuelles Ausführen von SQL-Migrationen ist ab dieser Version nicht mehr nötig.


## v1.3.0 Planner

Life Manager now contains a deterministic planning engine.

### Planner

`GET /planner`

Scores currently available quests using:

- due today / overdue
- KBR
- XP value
- estimated duration
- training priority
- Boss Fight status

The planner returns:
- one recommended next quest
- a Top-3 daily focus
- a human-readable reason for each recommendation

### Weekly Review

`GET /weekly-review`

Summarizes:
- XP
- completed quests
- training completion
- Willpower XP
- Boss Fights
- active days
- strongest streak
- concrete observations and next-focus suggestions

### New cards

```yaml
type: custom:life-manager-planner-card
entity: sensor.life_manager
title: Was soll ich jetzt machen?
```

```yaml
type: custom:life-manager-weekly-review-card
entity: sensor.life_manager
title: Wochenrückblick
```

The planner is intentionally rule-based in v1.3.0 so every recommendation remains
explainable. An optional AI layer can be added later without replacing the
deterministic core.


## v1.3.0 Planner Today Fix

- Planner candidates now come directly from `fetch_today()`.
- Every open quest visible in the Today card is therefore eligible for planning.
- Planner card shows:
  - number of open Today quests
  - number of Planner candidates
- Planner scoring still uses KBR, XP, duration, overdue state, training and Boss Fight status.


## v1.3.0 Stable Home Assistant data transport

Home Assistant previously had to list every `/dashboard` section separately in
`json_attributes`. That meant new features such as `planner` or `weekly_review`
required a manual package change.

From v1.3.0 onward `/dashboard` also exposes the complete response under:

`data`

The Home Assistant REST sensor therefore only needs:

```yaml
value_template: "{{ value_json.data.today.progress_percent }}"
json_attributes:
  - data
```

All Life Manager cards automatically read `attributes.data` and remain backwards
compatible with the old flat sensor attributes.

### Important one-time Home Assistant change

Replace the existing Life Manager `rest:` sensor block once with:

`examples/life_manager_sensor_v1.3.0.yaml`

After that, adding new dashboard sections no longer requires modifying
`json_attributes`.


## v1.3.0 Planner 2.0

- Quests now have `priority`: low / normal / high / critical.
- Quests can have an optional `due_date`.
- Planner scoring gives priority and due dates more weight than trivial duration.
- Planner endpoint supports optional `max_minutes`, e.g. `/planner?max_minutes=20`.
- Quest Manager exposes priority and due date.
- Recommendation reasons now explicitly mention priority, due/overdue state and time fit.


## v1.3.0 Frontend Auto-Update

From this version onward the Lovelace resource should be registered permanently as:

`/local/life-manager.js`

No version query string is required anymore.

At add-on startup:
- `life-manager.js` is copied to `/config/www`
- `life-manager-version.json` is written with the installed version

The frontend checks this version file without browser cache. If a newer
frontend version is detected, Home Assistant is reloaded once automatically.

### One-time change

Change the Lovelace resource from e.g.

`/local/life-manager.js?v=110`

to

`/local/life-manager.js`

After this, future Life Manager updates should no longer require manually
editing the frontend resource URL.


## v1.3.0 Stable frontend loader

The previous auto-update approach could not solve a browser that had already
cached an old `/local/life-manager.js`: the version-check code itself lived
inside the cached file.

v1.3.0 uses a permanent loader instead.

### One-time Lovelace change

Remove the old Life Manager JavaScript resource and add:

`/local/life-manager-loader.js`

The loader fetches `life-manager-manifest.json` with `cache: no-store` and then
loads the version-specific bundle, for example:

`/local/life-manager-1.3.0.js?v=1.3.0`

Future add-on updates write a new versioned bundle and update the manifest.
The Lovelace resource URL no longer has to change.

For compatibility, `/local/life-manager.js` is still overwritten at every
add-on start, but it should no longer be registered as the Lovelace resource.


## v1.3.0 Day & Week Planning

### Day Plan

`GET /day-plan`

Creates a short ordered day plan from the current Planner focus. Training is
placed first when scheduled, followed by the strongest remaining candidates.

### Weekly Goals

`GET /weekly-goals`

Weekly goals track recurring targets such as:
- 5 trainings per week
- a specific quest N times per week

A default training goal of 5/week is created on first migration.

### New cards

```yaml
type: custom:life-manager-day-plan-card
entity: sensor.life_manager
title: Dein Tagesplan
```

```yaml
type: custom:life-manager-weekly-goals-card
entity: sensor.life_manager
title: Wochenziele
script: script.life_weekly_goal_create
```

The stable frontend loader introduced in v1.1.2 remains in place. No Lovelace
resource version change is required.


## v1.3.0 Scheduling & Occurrences

A quest's base schedule is no longer modified when real life changes one occurrence.

New `quest_occurrences` records can:
- skip today's occurrence
- move today's occurrence to tomorrow
- move it to another future date
- restore the original occurrence

Moved quests appear on their target day while the recurring base schedule remains intact.

### API

`POST /quests/{quest_id}/occurrence`

Payload examples:

```json
{"action":"tomorrow"}
```

```json
{"action":"skip"}
```

```json
{"action":"move","target_date":"2026-09-03"}
```

```json
{"action":"restore"}
```

The dashboard's `today`, Planner and Day Plan use the effective occurrence-aware day.
