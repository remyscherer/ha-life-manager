# Life Manager v0.7.4

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
4. `/health` muss Version `0.7.4` liefern.
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

## v0.7.4 repository cleanup

- Example configuration no longer contains a personal LAN IP.
- Repository ships with a basic GitHub Actions validation workflow.
- Repository metadata is included at the repository root.


## v0.7.4 Quest Manager repair

- Quest creation payload uses Home Assistant's `to_json` filter.
- New inline Quest Editor replaces prompt dialogs.
- Categories, type, XP mode, KBR and schedules are editable in a proper form.
- API now exposes `GET /quests`.
- Create/update endpoints return the saved quest.
- API writes create/update events to the add-on log.


## v0.7.4 Frontend refresh fix

- Schreibaktionen warten bevorzugt auf den direkten Home-Assistant-Script-Service.
- Fallback auf `script.turn_on` bleibt erhalten.
- Nach Schreibaktionen wird der REST-Sensor mehrfach aktualisiert.
- Der Quest Manager zeigt unten `Frontend v0.7.4`, damit Cache-Probleme sofort erkennbar sind.
