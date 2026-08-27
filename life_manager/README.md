# Life Manager v1.7.2

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
4. `/health` muss Version `1.7.2` liefern.
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

## v1.7.2 repository cleanup

- Example configuration no longer contains a personal LAN IP.
- Repository ships with a basic GitHub Actions validation workflow.
- Repository metadata is included at the repository root.


## v1.7.2 Quest Manager repair

- Quest creation payload uses Home Assistant's `to_json` filter.
- New inline Quest Editor replaces prompt dialogs.
- Categories, type, XP mode, KBR and schedules are editable in a proper form.
- API now exposes `GET /quests`.
- Create/update endpoints return the saved quest.
- API writes create/update events to the add-on log.


## v1.7.2 Frontend refresh fix

- Schreibaktionen warten bevorzugt auf den direkten Home-Assistant-Script-Service.
- Fallback auf `script.turn_on` bleibt erhalten.
- Nach Schreibaktionen wird der REST-Sensor mehrfach aktualisiert.
- Der Quest Manager zeigt unten `Frontend v1.7.2`, damit Cache-Probleme sofort erkennbar sind.


## v1.7.2 Achievements, Boss Fights & Streaks

- Achievements werden automatisch aus bestehenden Daten berechnet und freigeschaltet.
- Neue Achievement Card: `custom:life-manager-achievements-card`
- KBR-5-Quests werden als Boss Fights ausgewertet.
- Neue Boss Card: `custom:life-manager-boss-card`
- Bei `Kein Bock` auf einer KBR-5-Quest gibt es 15 statt 10 Willpower XP.
- Streaks zählen jetzt erledigte geplante Termine statt bloß aufeinanderfolgende Kalendertage.
- Heute offene geplante Aufgaben brechen die Streak nicht sofort.


## v1.7.2 Reward System

- Reward Manager: Rewards direkt in Home Assistant anlegen, bearbeiten und deaktivieren.
- Coin History Card mit den letzten 20 Coin-Bewegungen.
- Sparziele mit Fortschrittsanzeige.
- Neue Tabellenstruktur für Savings Goals.
- Reward Shop zeigt weiterhin nur aktive Rewards als kaufbar an.


## v1.7.2 Automation & Polish

- Datenbankmigrationen laufen automatisch vor dem API-Start.
- `schema_migrations` protokolliert bereits angewendete Migrationen.
- Bei einer fehlgeschlagenen Migration startet die API bewusst nicht.
- `/health` liefert zusätzlich `schema_version`.
- Neue Quick-Actions-Card für manuelles Aktualisieren und Tagesabschluss.
- Manuelles Ausführen von SQL-Migrationen ist ab dieser Version nicht mehr nötig.


## v1.7.2 Planner

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

The planner is intentionally rule-based in v1.7.2 so every recommendation remains
explainable. An optional AI layer can be added later without replacing the
deterministic core.


## v1.7.2 Planner Today Fix

- Planner candidates now come directly from `fetch_today()`.
- Every open quest visible in the Today card is therefore eligible for planning.
- Planner card shows:
  - number of open Today quests
  - number of Planner candidates
- Planner scoring still uses KBR, XP, duration, overdue state, training and Boss Fight status.


## v1.7.2 Stable Home Assistant data transport

Home Assistant previously had to list every `/dashboard` section separately in
`json_attributes`. That meant new features such as `planner` or `weekly_review`
required a manual package change.

From v1.7.2 onward `/dashboard` also exposes the complete response under:

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

`examples/life_manager_sensor_v1.7.2.yaml`

After that, adding new dashboard sections no longer requires modifying
`json_attributes`.


## v1.7.2 Planner 2.0

- Quests now have `priority`: low / normal / high / critical.
- Quests can have an optional `due_date`.
- Planner scoring gives priority and due dates more weight than trivial duration.
- Planner endpoint supports optional `max_minutes`, e.g. `/planner?max_minutes=20`.
- Quest Manager exposes priority and due date.
- Recommendation reasons now explicitly mention priority, due/overdue state and time fit.


## v1.7.2 Frontend Auto-Update

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


## v1.7.2 Stable frontend loader

The previous auto-update approach could not solve a browser that had already
cached an old `/local/life-manager.js`: the version-check code itself lived
inside the cached file.

v1.7.2 uses a permanent loader instead.

### One-time Lovelace change

Remove the old Life Manager JavaScript resource and add:

`/local/life-manager-loader.js`

The loader fetches `life-manager-manifest.json` with `cache: no-store` and then
loads the version-specific bundle, for example:

`/local/life-manager-1.7.2.js?v=1.7.2`

Future add-on updates write a new versioned bundle and update the manifest.
The Lovelace resource URL no longer has to change.

For compatibility, `/local/life-manager.js` is still overwritten at every
add-on start, but it should no longer be registered as the Lovelace resource.


## v1.7.2 Day & Week Planning

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


## v1.7.2 Scheduling & Occurrences

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


## v1.7.2 Scheduling UI + Analytics

### Today actions

Open quests now expose:
- ✓ complete
- 🔥 complete with overcome bonus
- → move to tomorrow
- 📅 move to a chosen date
- ⏭ skip today's occurrence

Moved occurrences show their original date in the Today card.

### Analytics

`GET /analytics`

New 30-day analytics include:
- total completions
- trainings
- Boss Fights
- moved occurrences
- skipped occurrences
- category completion counts
- KBR completion data
- daily XP history
- simple rule-based insights

### New card

```yaml
type: custom:life-manager-analytics-card
entity: sensor.life_manager
title: Insights
```


## v1.7.2 Generated Home Assistant Bridge

Life Manager now writes a small generated package at add-on startup:

`/config/packages/life_manager_generated.yaml`

This package contains Home Assistant write-actions required by newer frontend
features, beginning with:

`script.life_quest_occurrence`

The user's existing `life_manager.yaml` is not overwritten.

### Important

Home Assistant loads package YAML during Core configuration loading. After the
first update to v1.7.2, perform one Home Assistant Core restart if the generated
script is not visible immediately. Future changes to the generated bridge file
can be shipped by the add-on without manually merging YAML.

The generated bridge uses the existing `life_manager_api_key` secret.


## v1.7.2 Home Assistant package path detection

The generated Home Assistant bridge now detects the package directory at
add-on startup.

Detection order:

1. `/config/_packages` when that directory already exists
2. `/config/packages` when that directory already exists
3. `/config/packages` as the fallback for new installations

This prevents Life Manager from creating and using the wrong package directory
on Home Assistant installations configured with `_packages`.

The detected path is written to the add-on log during startup.


## v1.7.2 Home Assistant bridge fix

The generated bridge now uses valid Home Assistant script field definitions and
a configurable API base URL.

New add-on option:

`ha_bridge_base_url`

Default:

`http://homeassistant.local:8000`

If your Home Assistant host does not resolve `homeassistant.local`, set this to
the same reachable URL you already use for the Life Manager REST sensor, for
example:

`http://192.168.0.74:8000`

At add-on startup the generated bridge is rendered with this URL and written to
the detected package directory.

The add-on log prints both:
- generated package path
- bridge API URL

After the first update, restart Home Assistant Core once so the generated
script is loaded.


## v1.7.2 Home Assistant bridge restored

The direct browser-to-API action experiment from v1.5.x has been rolled back.

Today-card write actions again use Home Assistant scripts/rest_commands.

The add-on generates a minimal bridge package containing:

- `script.life_manager_bridge_test`
- `script.life_quest_occurrence`
- `rest_command.life_manager_bridge_occurrence`

New add-on option:

`ha_packages_dir`

Default: `auto`

For this installation it can explicitly be set to:

`_packages`

or:

`/config/_packages`

This removes ambiguity from package-directory detection.

The generated file is:

`life_manager_generated.yaml`

After installing/updating this version, restart Home Assistant Core once. Then
`script.life_manager_bridge_test` should be visible first; if it is, the
generated package is definitely being loaded.


## v1.7.2 Home Assistant bridge fields hotfix

The generated Home Assistant package keeps the working bridge-test script and
adds fully defined fields for `script.life_quest_occurrence`.

Generated scripts:

- `script.life_manager_bridge_test`
- `script.life_manager_rest_test`
- `script.life_quest_occurrence`

`script.life_manager_rest_test` calls the Life Manager `/health` endpoint and
can be used to verify that Home Assistant can reach the add-on API through the
configured bridge URL.

After updating, restart Home Assistant Core once so the generated package is
loaded again.


## v1.7.2 Occurrence diagnostic split

The generated bridge now separates the occurrence entity-name test from the
actual templated implementation.

Expected scripts after a Home Assistant Core restart:

- `script.life_manager_bridge_test`
- `script.life_manager_rest_test`
- `script.life_quest_occurrence` — deliberately minimal diagnostic script
- `script.life_quest_occurrence_exec` — actual REST implementation

Interpretation:

- If both occurrence scripts appear, the previous complex field/selector
  definition was the cause.
- If only `life_quest_occurrence_exec` appears, the entity ID
  `life_quest_occurrence` is colliding with another registry/config entry.
- If only the diagnostic occurrence script appears, the execution definition
  is invalid and can be simplified further.


## v1.7.2 Occurrence entity rename

Diagnostics in v1.5.5 proved that Home Assistant accepts the occurrence script
definition, but the entity ID `script.life_quest_occurrence` collides with an
existing entity-registry/config entry on the installation.

The generated script has therefore been renamed to:

`script.life_manager_quest_occurrence`

The Today card uses the new collision-free entity ID automatically.

The temporary diagnostic `life_quest_occurrence_exec` script has been removed.


## v1.7.2 Occurrence payload fix

Fixes HTTP client errors when skipping or moving quests.

- `skip`, `tomorrow` and `restore` now send JSON `null` for optional fields.
- `move` sends a target date only when required.
- Backend defensively accepts `null`, `None`, empty strings or ISO dates for
  the occurrence target before validating the action.


## v1.7.2 Complete Dashboard Card

New all-in-one Lovelace card:

```yaml
type: custom:life-manager-dashboard-card
entity: sensor.life_manager
title: Life Manager
```

It contains four internal sections:

- Today: progress, Planner recommendation, quests, day plan and training
- Progress: week metrics, achievements, streaks and analytics
- Coins: wallet, savings goals, Reward Shop and Coin History
- Overview: player status, weekly goals and system summary

Quest actions and Reward purchases remain usable directly inside the dashboard.

All existing individual Life Manager cards remain available.


## v1.7.2 Reward System 2.0

- Wishlist flag for rewards
- Savings-goal coin reservations
- Free vs. reserved wallet balance
- Reward-linked savings goals remain supported and are shown in the dashboard
- Reward affordability now respects coins reserved for other goals
- Missing coins are displayed directly in the Reward Shop
- Purchase history remains available and is expanded to 20 entries

The migration is automatic and preserves existing rewards, purchases and goals.


## v1.7.2 Dashboard Management

The all-in-one dashboard now contains a fifth internal tab:

`Verwaltung`

It includes:
- Quest overview
- create quest
- edit quest
- activate/deactivate quest
- Reward overview
- create reward
- edit reward
- activate/deactivate reward

The standalone Quest Manager and Reward Manager cards remain available.


## v1.7.2 Dashboard Management hotfix

Fixes the `Konfigurationsfehler` shown when opening the all-in-one dashboard's
`Verwaltung` tab.

The management renderer and CRUD helper methods were accidentally attached to
the standalone Today card in v1.6.1. They now correctly belong to
`LifeManagerDashboardCard`.

Release validation now also includes a JavaScript syntax check using Node.

## v1.7.2 Quest Manager UX

Quest creation/editing in the all-in-one dashboard now uses an embedded form with category names, type, priority, KBR, duration, due date, XP settings, description, weekdays and active state. Prompt dialogs are no longer used for quests.


## v1.7.2 Quest Editor focus hotfix

Fixes the Quest Editor losing focus during Home Assistant state updates.

While an input inside the Quest Editor is active, incoming `hass` updates no
longer rebuild the form DOM. Draft values are synchronized into local card
state on input/change so later renders preserve the user's input.

## v1.7.2 Category Management

Categories can now be created, edited, sorted and activated/deactivated directly in the dashboard management tab. The GitHub Actions workflow has also been rebuilt cleanly.


## v1.7.2 Category API hotfix

Fixes category editing/creation from the dashboard.

The Home Assistant bridge for categories existed in v1.6.5, but the matching
FastAPI category endpoints were not actually inserted into `main.py`.

v1.7.2 adds:
- GET /categories
- POST /categories
- PUT /categories/{category_id}
- POST /categories/{category_id}/toggle

The Overview tab also no longer contains a stale hard-coded frontend version.
It displays `window.LIFE_MANAGER_FRONTEND_VERSION` dynamically.


## v1.7.2 Embedded SQLite

Life Manager now stores its runtime data in the add-on itself:

`/data/life_manager.db`

MariaDB is no longer required after migration.

### One-time import

For this transition release `migrate_from_mariadb` defaults to `true`.
If the import marker `/data/.mariadb_import_done` does not exist, the add-on
tries to connect to the previously configured MariaDB database and copies the
known Life Manager tables to SQLite.

The importer verifies important row counts plus total coin balance and XP sum.
Only a successful import writes the marker. If MariaDB is unavailable on a
fresh installation, the import is skipped and Life Manager starts with an
empty SQLite database.

After you have confirmed the imported data, MariaDB can be removed from the
Life Manager setup.

## v1.7.2 MariaDB import hotfix

Fixes Decimal values from MariaDB during one-time SQLite migration. Failed imports remain retryable because the completion marker is only written after successful checks. The default weekly goal is not seeded while a MariaDB import is pending.

## v1.7.2 SQLite date/time compatibility

SQLite returns the Life Manager schema's TEXT date/time columns as strings.
The API now normalizes database date/time values centrally before JSON
serialization, date arithmetic, streak calculations and occurrence handling.
This fixes `/dashboard` after a successful MariaDB -> SQLite import.
