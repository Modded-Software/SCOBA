# SPEC-LOADING-SCREEN: Loading Screen Text and Wait

**Date:** 2026-11-26
**Requirements:** [REQ-LOADING-SCREEN](../requirements/REQ-LOADING-SCREEN.md)

## 1. Requirement state

States: `[build]` = the validator checks it on every build; `[tested]` =
an in-game test passed in a named run; `[operator]` = only a person can
judge it.

| ID | State | Backed by |
| --- | --- | --- |
| R-LOAD-1 | [build] | `loading_screen.check_text`: name and author in all 13 locales. `test_loading_screen` `test_every_locale_is_set`, `test_missing_field_fails` |
| R-LOAD-2 | [build] [operator] | enGB equals enUS (`test_locales_must_agree`). Every other locale differs from enUS (`test_untranslated_locale_fails`) and keeps the enUS keys, labels, numbers and lines (`tip_tokens`, `test_dropped_key_in_a_translation_fails`). The quality of the translations: operator (O-LOAD-4) |
| R-LOAD-3 | [build] | `STALE` words in every field of every locale (`test_old_texts_fail`); in the built `DocumentHeader`: `test_built_map_with_the_old_header_fails` |
| R-LOAD-4 | [build] | `check_bindings` on the enUS tip: `test_rebound_key_fails`, `test_unbound_key_fails`, `test_renamed_button_fails`, `test_dropped_phrase_fails` |
| R-LOAD-5 | [tested] | `loadwait/20261126-203204`: bank absent 98.0 s with no key (> 90), first key sent, the game entered 7.8 s later (`afterKeyS` 0..30), game time 1000 ms. MapInfo flag: validator |
| R-LOAD-6 | [tested] | `roster/20261126-203936`: failures 0, the map entered by itself (`map_builder.patch_mapinfo`, `test_test_map_clears_it`) |
| R-LOAD-7 | [build] | `expand_map.expand_document_header`; `check_document_header` in the validator. `DocumentHeaderTest`: round trip, only the five fields change, player names kept |
| AC-LOAD-1, AC-LOAD-3 | [operator] | Not checked |

## 2. Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | The game shows the name, descriptions and tip of `DocumentHeader`. A new `GameStrings.txt` with the old `DocumentHeader` showed the old text. | operator 2026-11-26; staged map of that run |
| F2 | `DocumentHeader` version 8: `H2CS`, version, at 0x2C the u32 count of dependencies (C strings), the u32 count of strings, then per string u16 key length, key, locale reversed (`SUne` = enUS), u16 value length, value. The strings end the file. The source holds 172. | `read_document_header`, `test_read_round_trip` |
| F3 | MapInfo flag `0x02` is the wait for a key. A changed flag needs a new check value. | `loadwait/20261126-203204`; `test_on_and_off` |
| F4 | `roster/20261126-203544` failed: no bank within the 60 s launch window. The rerun `roster/20261126-203936` passed. The roster map's flag was off in both. The cause is not known. | runs |

## 3. Design

- Source text: the five fields in `src/SCOBA.SC2Map/<locale>.SC2Data/LocalizedData/GameStrings.txt`, 13 locales.
- Build (`scripts/expand_map.py`):
  - `expand_mapinfo` sets the wait flag;
  - `expand_document_header` writes the five fields of every locale into `DocumentHeader`.
- Test maps (`testkit/map_builder.patch_mapinfo`) clear the flag, except `loadwait`.
- Validator (`loading_screen.check`): text, translations, bindings, `DocumentHeader`, flag, check value.

## 4. Runs

| Run | Result |
| --- | --- |
| `loadwait/20261126-203204` | failures 0 |
| `roster/20261126-203544` | FAIL: no roster test bank produced (F4) |
| `roster/20261126-203936` | failures 0 |

Build stamp of these runs: `04c0c150339e-f67c488649676c4e`.
