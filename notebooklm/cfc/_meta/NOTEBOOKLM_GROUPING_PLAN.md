# NotebookLM grouping plan for CFC corpus

## Budget
- AI Pro plan: **100 sources / notebook**
- We can use **multiple notebooks** if helpful (Victor will load whichever the question needs)

## Recommendation: THREE specialized notebooks

Multi-notebook beats one-big-notebook because:
1. Each notebook's retrieval is scoped to a coherent topic
2. We can ask different load-bearing questions in each
3. The corpus contains both DOCS (prose) and CODE (function signatures, structs) — NotebookLM does worse when these mix at the same retrieval rank

---

## Notebook 1: "CFC Firmware-Side Reference" (~60 sources)

**Purpose:** Answer questions about what C code the CFC FAP/FAL writes — function names, structs, build system, capability APIs.

**Contents:**
| Group | Source count | Path |
|---|---|---|
| Momentum RPC service (the whole thing) | 14 | `tight/momentum-rpc-service/` |
| Momentum JS app source incl. all 14 modules | ~30 (collapse subdirs) | `tight/momentum-js-app-modules/` — bundle by module: `modules/js_subghz/*` as ONE source, etc. |
| Protobuf schemas (.proto + .options) | 1 | `tight/flipperzero-protobuf/` — concatenate all into one |
| API symbols filtered per domain | 5 | `tight/momentum-api-symbols/{nfc,subghz,infrared,gpio,lfrfid,plugin}_symbols.csv` |
| Furi HAL headers | ~5 (concatenate by domain) | `tight/furi-hal-headers/` |
| lib-nfc public headers | 1 | concat `tight/lib-nfc/*.h` |
| lib-subghz public headers | 1 | concat `tight/lib-subghz/*.h` |
| lib-infrared public headers | 1 | concat `tight/lib-infrared/*.h` |
| lib-flipper-application incl. plugin system | 1 | concat `tight/lib-flipper-application/*` |
| mjs public headers | 1 | concat `tight/lib-mjs-public-headers/*.h` |
| In-tree app callers (5 main apps' RPC excerpts) | 5 | `medium/in-tree-app-rpc-callers/` |
| Cross-firmware diffs | 1 | `medium/cross-firmware-rpc-diffs/` (concat) |

**Load-bearing questions:**
- "Show me the exact RPC handler call sequence for `RpcAppEventTypeDataExchange`"
- "What's the minimum C code to read a MIFARE Classic UID using `furi_hal_nfc_*` directly?"
- "How does `js_subghz` register its methods? Show the JS_ASSIGN_MULTI pattern."
- "Which furi_hal_subghz_* functions are exported (`+`) vs unavailable (`-`)?"
- "What does the FAP application manifest (`.fam`) need to declare for an RPC-using app?"

---

## Notebook 2: "CFC Host-Side Reference" (~25 sources)

**Purpose:** Answer questions about Python/Rust/Go/C++ host code that drives RPC and AppDataExchange.

**Contents:**
| Group | Source count | Path |
|---|---|---|
| flipperzero_protobuf_py incl. `rpc_app_data_exchange_send/recv` | 1 (concat into one file) | `medium/host-clients/flipperzero_protobuf_py/` |
| flipper-rpc Rust src | 1 (concat) | `medium/host-clients/flipper-rpc-rust/` |
| go-flipper | 1 (concat) | `medium/host-clients/go-flipper/` |
| pyFlipper | 1 (concat) | `medium/host-clients/pyflipper/` |
| qFlipper RPC bits | 1 (concat) | `medium/host-clients/qflipper-rpc-bits/` |
| Protobuf compiled .pb.h/.pb.c reference | 1 | from qflipper `messages/` subdir |
| Expansion protocol doc | 1 | `wide/flipper-developer-docs/expansion_protocol.txt` |
| Application catalog rules | ~5 | `medium/app-catalog-rules/` |

**Load-bearing questions:**
- "Show me exact bytes on the wire for a host → FAP `DataExchangeRequest`"
- "What's the maximum payload size per `DataExchangeRequest`? How do we chunk?"
- "How does qFlipper handle response timeouts on RPC requests?"
- "Can multiple sessions write to the same FAP via AppDataExchange concurrently?"

---

## Notebook 3: "CFC Design Context" (~25 sources)

**Purpose:** High-level FAP architecture knowledge — patterns, anti-patterns, ecosystem context.

**Contents:**
| Group | Source count | Path |
|---|---|---|
| All Momentum dev docs | ~10 | `wide/momentum-docs/` (incl. js subdir, file_formats subdir) |
| Flipper developer.flipper.net docs (clean text) | 11 | `wide/flipper-developer-docs/*.txt` |
| External-docs (Momentum/OFW/Unleashed README, fbt, etc.) | ~5 | `wide/external-docs/` |
| jamisonderek wiki pages (22 community deep-dives) | bundle as ~5 (concat by domain) | `wide/jamison-wiki/` |
| awesome-flipperzero index | 1 | `wide/awesome-flipperzero/README.md` |
| Community FAP catalogs | 2 | `wide/community-fap-catalogs/` |
| jamisonderek SAO (custom JS module example, in the wild) | 1 (concat) | `medium/jamisonderek-sao/` |
| fbs (BT serial hijack alt-pattern) | 1 (concat) | `medium/maybe-hello-world-fbs/` |
| FAP boilerplates (catalog + leedave) | 2 (concat each) | `medium/fap-boilerplates/` |
| ufbt docs | 1 (concat) | `medium/ufbt-docs/` |
| jamisonderek worked-example FAPs (7 domains) | 7 | `medium/jamisonderek-worked-examples/` |
| Official good-faps reference (weather, nfc_magic, mass_storage, etc.) | 6 | `medium/official-good-faps/` |
| DolphinTank state files | 5 | `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\.dolphintank\` |
| CPK's own DAY8_FAP_VISION.md | 1 | `D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\docs\decisions\DAY8_FAP_VISION.md` |

**Load-bearing questions:**
- "How does our DAY8_FAP_VISION align with what other FAPs do? Where does it diverge?"
- "What FAP categories does the application catalog accept? Where would CFC fit?"
- "Which design alternative does the community lean on for capabilities Momentum's stock JS doesn't expose: button-press automation, fork-rebuild, AppDataExchange, or custom JS modules?"
- "What does jamisonderek's SAO teach us about packaging a JS module with example scripts?"

---

## Pre-upload concatenation script

Many of the 800+ files are tiny C headers or single-method modules. NotebookLM gives one source per upload, so we batch-concatenate by group with clear separators before upload. Suggested script: `concat_for_notebooklm.py` in `_meta/`.

Pattern:
```
=== FILE: applications/services/rpc/rpc.h ===
[file content]

=== FILE: applications/services/rpc/rpc_app.h ===
[file content]
...
```

This gives NotebookLM enough structural context to know where each fragment came from while staying within source-count limits.

---

## Sources NOT going into NotebookLM

These get loaded into **AnythingLLM specialists** instead, where retrieval over code is better than NotebookLM's prose-bias:
- Full Momentum-Apps + Xtreme-Apps source (513MB + 269MB — too big anyway; we only kept the indexes)
- All `.options` field-level wire constraints — those go inline in the Phase 1 spec, not searched

---

## After upload: what each notebook produces

- **Notebook 1** → feeds the API/struct sections of `DAY8_FAP_PHASE1_SPEC.md` ("what we'll call")
- **Notebook 2** → feeds the host-transport sections ("what CPK sends/receives")
- **Notebook 3** → feeds the design-rationale + architecture-choice sections ("why this shape, what others did")
