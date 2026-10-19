# Eigenes Spiel in Python **und** R eintragen

`first_to_three.json` ist eine vollständige, **fiktive** Demo für die
sprachneutrale, beschränkte Regel-DSL. Beispielregeln:

- Zwei Spielende `p0`, `p1`, Turn-Index 0 oder 1;
- `score(player)` ist nur für die Person am Zug legal;
- jede gültige Aktion erhöht ihren Score und dreht den Turn;
- wer 3 Punkte erreicht, gewinnt; danach keine Aktion mehr.

Die Datei ist ein **Beispiel**, kein zusätzliches Sportprofil und noch keine
funktionierende Library. Nach Implementierung der APIs soll dies möglich sein:

## Python

```python
import ruleatlas
ruleatlas.register_rules("examples/rulepacks/first_to_three.json")
s = ruleatlas.new_state("user.first_to_three", players=[{"id":"p0"},{"id":"p1"}],
                        ruleset_version="1.0.0")
print(ruleatlas.legal_actions(s))
s2 = ruleatlas.apply_action(s, {"type":"score", "params":{"player":0}})
print(ruleatlas.outcome(s2))
```

## R

```r
library(ruleatlas)
register_rules("examples/rulepacks/first_to_three.json")
s <- new_state("user.first_to_three",
               players = list(list(id="p0"), list(id="p1")),
               ruleset_version = "1.0.0")
print(legal_actions(s))
s2 <- apply_action(s, list(type="score", params=list(player=0L)))
print(outcome(s2))
```

Beide Beispiele verwenden **identische** Spieler-IDs und 0-basierte
öffentliche Indizes. Ergebnisse müssen JSON-kanonisch identisch sein.
Konkrete Ein- und Ausgabe-Schemata: `contracts/*.json` und
`docs/02_SEMANTIK_UND_ZUSTANDSMODELL.md`.

## Eigene Varianten und Erweiterungen

1. Regelpack mit eigenem Namen im Namespace `user.<slug>` erstellen,
   Version und Quelle/Hausregelbasis angeben.
2. Die `state.fields` auf nötige Felder begrenzen (Punkte, Zug, Phasen,
   Team-/Kartendaten).
3. Aktionen mit definierten Parameterschemas, Guard-AST und atomaren
   Effekten modellieren; Outcomes mit eindeutigem Gewinner/-ranking.
4. Mit `validate_rules(path)` in beiden Sprachen prüfen; dann `register_rules`.
5. Erlaubte und verbotene Abläufe als Golden-Tests angeben; Änderungen an
   Regeln brauchen neue `ruleset_version`, bestehende States werden nicht
   still migriert.

**Sicherheit:** keine Python-/R-Ausdrücke als Strings, kein dynamisches
`eval`, keine Shell, keine URL als externe Regelquelle oder heimliche
Installation. Die DSL hat bewusst begrenzte Operatoren und Limits.
Schachähnliche Komplexität erfordert ggf. kleinen explizit geprüften Adapter
in beiden Sprachen – kein unsicheres Nutzercode-Plugin.
