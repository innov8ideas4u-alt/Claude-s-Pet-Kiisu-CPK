"""
concat_for_notebooklm.py — bundle the CFC corpus into NotebookLM-sized sources.

NotebookLM caps at 100 sources per notebook. The corpus has 821 files (mostly
tiny C headers). This script reads NOTEBOOKLM_GROUPING_PLAN.md's three-notebook
split and produces concatenated blobs in:

    notebooklm/cfc/_upload/notebook1_firmware_side/
    notebooklm/cfc/_upload/notebook2_host_side/
    notebooklm/cfc/_upload/notebook3_design_context/

Each output file has clear === FILE: <path> === separators so NotebookLM's
retrieval keeps structural context.

Run from anywhere on the Windows box:
    python D:\\Dev\\Projects\\Claude-s-Pet-Kiisu-CPK\\notebooklm\\cfc\\_meta\\concat_for_notebooklm.py
"""

from pathlib import Path
import shutil

import os, sys
# Detect environment — Windows uses D:\..., WSL/Linux uses /mnt/d/...
if sys.platform == "win32":
    CORPUS = Path(r"D:\Dev\Projects\Claude-s-Pet-Kiisu-CPK\notebooklm\cfc")
else:
    CORPUS = Path("/mnt/d/Dev/Projects/Claude-s-Pet-Kiisu-CPK/notebooklm/cfc")
OUT = CORPUS / "_upload"

# A "bundle" is one output file. Each bundle has:
#   - a destination filename
#   - a list of (label, source_path_or_glob) entries
# source_path is relative to CORPUS. Globs allowed.
NOTEBOOKS = {
    "notebook1_firmware_side": [
        ("01_rpc_service_all.txt",          ["tight/momentum-rpc-service/**/*"]),
        ("02_rpc_app_h_canonical.txt",      ["tight/momentum-rpc-service/rpc_app.h",
                                             "tight/momentum-rpc-service/rpc_app.c",
                                             "tight/momentum-rpc-service/rpc_app_error_codes.h"]),
        ("03_protobuf_schemas.txt",         ["tight/flipperzero-protobuf/**/*"]),
        ("04_protobuf_momentum_fork.txt",   ["tight/momentum-flipperzero-protobuf/**/*"]),
        ("05_api_symbols_nfc.csv",          ["tight/momentum-api-symbols/nfc_symbols.csv"]),
        ("06_api_symbols_subghz.csv",       ["tight/momentum-api-symbols/subghz_symbols.csv"]),
        ("07_api_symbols_infrared.csv",     ["tight/momentum-api-symbols/infrared_symbols.csv"]),
        ("08_api_symbols_gpio.csv",         ["tight/momentum-api-symbols/gpio_symbols.csv"]),
        ("09_api_symbols_lfrfid.csv",       ["tight/momentum-api-symbols/lfrfid_symbols.csv"]),
        ("10_api_symbols_plugin_rpc.csv",   ["tight/momentum-api-symbols/plugin_and_rpc_symbols.csv"]),
        ("11_furi_hal_headers_all.txt",     ["tight/furi-hal-headers/*.h"]),
        ("12_lib_nfc_headers.txt",          ["tight/lib-nfc/*.h"]),
        ("13_lib_subghz_headers.txt",       ["tight/lib-subghz/*.h"]),
        ("14_lib_infrared_headers.txt",     ["tight/lib-infrared/*.h"]),
        ("15_lib_flipper_application.txt",  ["tight/lib-flipper-application/**/*.h",
                                             "tight/lib-flipper-application/**/*.c"]),
        ("16_lib_mjs_public_headers.txt",   ["tight/lib-mjs-public-headers/*.h"]),
        ("17_js_app_core.txt",              ["tight/momentum-js-app-modules/js_app.c",
                                             "tight/momentum-js-app-modules/js_app_i.h",
                                             "tight/momentum-js-app-modules/js_modules.c",
                                             "tight/momentum-js-app-modules/js_modules.h",
                                             "tight/momentum-js-app-modules/js_thread.c",
                                             "tight/momentum-js-app-modules/js_thread.h",
                                             "tight/momentum-js-app-modules/js_thread_i.h",
                                             "tight/momentum-js-app-modules/js_value.c",
                                             "tight/momentum-js-app-modules/js_value.h",
                                             "tight/momentum-js-app-modules/application.fam"]),
        ("18_js_module_serial.txt",         ["tight/momentum-js-app-modules/modules/js_serial.c"]),
        ("19_js_module_gpio.txt",           ["tight/momentum-js-app-modules/modules/js_gpio.c"]),
        ("20_js_module_subghz.txt",         ["tight/momentum-js-app-modules/modules/js_subghz/**/*"]),
        ("21_js_module_infrared.txt",       ["tight/momentum-js-app-modules/modules/js_infrared/**/*"]),
        ("22_js_module_i2c.txt",            ["tight/momentum-js-app-modules/modules/js_i2c.c"]),
        ("23_js_module_spi.txt",            ["tight/momentum-js-app-modules/modules/js_spi.c"]),
        ("24_js_module_storage.txt",        ["tight/momentum-js-app-modules/modules/js_storage.c"]),
        ("25_js_module_notification.txt",   ["tight/momentum-js-app-modules/modules/js_notification.c"]),
        ("26_js_module_badusb.txt",         ["tight/momentum-js-app-modules/modules/js_badusb.c"]),
        ("27_js_module_blebeacon.txt",      ["tight/momentum-js-app-modules/modules/js_blebeacon.c"]),
        ("28_js_module_flipper.txt",        ["tight/momentum-js-app-modules/modules/js_flipper.c",
                                             "tight/momentum-js-app-modules/modules/js_flipper.h"]),
        ("29_js_module_math.txt",           ["tight/momentum-js-app-modules/modules/js_math.c"]),
        ("30_js_module_tests.txt",          ["tight/momentum-js-app-modules/modules/js_tests.c",
                                             "tight/momentum-js-app-modules/modules/js_tests.h"]),
        ("31_js_module_event_loop.txt",     ["tight/momentum-js-app-modules/modules/js_event_loop/**/*"]),
        ("32_js_module_gui.txt",            ["tight/momentum-js-app-modules/modules/js_gui/**/*"]),
        ("33_js_module_usbdisk.txt",        ["tight/momentum-js-app-modules/modules/js_usbdisk/**/*"]),
        ("34_js_module_vgm.txt",            ["tight/momentum-js-app-modules/modules/js_vgm/**/*"]),
        ("35_js_app_plugin_api.txt",        ["tight/momentum-js-app-modules/plugin_api/**/*"]),
        ("36_js_app_views.txt",             ["tight/momentum-js-app-modules/views/**/*"]),
        ("37_in_tree_nfc_app_rpc.c",        ["medium/in-tree-app-rpc-callers/nfc_app_rpc_excerpts.c"]),
        ("38_in_tree_subghz_rpc.c",         ["medium/in-tree-app-rpc-callers/subghz_rpc_excerpts.c"]),
        ("39_in_tree_infrared_rpc.c",       ["medium/in-tree-app-rpc-callers/infrared_app_rpc_excerpts.c"]),
        ("40_in_tree_lfrfid_rpc.c",         ["medium/in-tree-app-rpc-callers/lfrfid_rpc_excerpts.c"]),
        ("41_in_tree_ibutton_rpc.c",        ["medium/in-tree-app-rpc-callers/ibutton_rpc_excerpts.c"]),
        ("42_data_exchange_handler.txt",    ["medium/in-tree-app-rpc-callers/_rpc_app_c_data_exchange_handler.txt"]),
        ("43_cross_firmware_diffs.txt",     ["medium/cross-firmware-rpc-diffs/*.txt"]),
    ],
    "notebook2_host_side": [
        ("01_official_python_bindings.txt",          ["medium/host-clients/flipperzero_protobuf_py/**/*.py",
                                                       "medium/host-clients/flipperzero_protobuf_py/**/*.md"]),
        ("02_official_python_flipper_app.py",        ["medium/host-clients/flipperzero_protobuf_py/flipperzero_protobuf/flipper_app.py"]),
        ("03_official_python_flipperCmd.py",         ["medium/host-clients/flipperzero_protobuf_py/flipperzero_protobuf/flipperCmd/flipperCmd.py"]),
        ("04_pyflipper.txt",                         ["medium/host-clients/pyflipper/**/*"]),
        ("05_rust_flipper_rpc.txt",                  ["medium/host-clients/flipper-rpc-rust/**/*"]),
        ("06_go_flipper.txt",                        ["medium/host-clients/go-flipper/**/*"]),
        ("07_qflipper_rpc_cpp.txt",                  ["medium/host-clients/qflipper-rpc-bits/**/*"]),
        ("08_expansion_protocol_doc.txt",            ["wide/flipper-developer-docs/expansion_protocol.txt"]),
        ("09_app_catalog_rules.txt",                 ["medium/app-catalog-rules/**/*"]),
        ("10_fbs_bt_serial_alt_pattern.txt",         ["medium/maybe-hello-world-fbs/**/*"]),
    ],
    "notebook3_design_context": [
        ("01_momentum_dev_docs_top_level.txt",       ["wide/momentum-docs/*.md"]),
        ("02_momentum_js_docs.txt",                  ["wide/momentum-docs/js/**/*"]),
        ("03_momentum_file_formats.txt",             ["wide/momentum-docs/file_formats/**/*"]),
        ("04_flipper_dev_portal_docs.txt",           ["wide/flipper-developer-docs/*.txt"]),
        ("05_external_docs_OFW_Momentum_Unleashed.txt", ["wide/external-docs/*.md"]),
        ("06_jamison_wiki_furi_furi_hal.txt",        ["wide/jamison-wiki/FURI.md",
                                                       "wide/jamison-wiki/Message-Queue.md",
                                                       "wide/jamison-wiki/Bus-resources.md"]),
        ("07_jamison_wiki_javascript_all.txt",       ["wide/jamison-wiki/JavaScript*.md",
                                                       "wide/jamison-wiki/Modules.md"]),
        ("08_jamison_wiki_capabilities.txt",         ["wide/jamison-wiki/Sub-GHz.md",
                                                       "wide/jamison-wiki/Infrared.md",
                                                       "wide/jamison-wiki/GPIO-Signals.md",
                                                       "wide/jamison-wiki/Analog-Input.md"]),
        ("09_jamison_wiki_build_and_debug.txt",      ["wide/jamison-wiki/UFBT.md",
                                                       "wide/jamison-wiki/Debugging.md",
                                                       "wide/jamison-wiki/Customize-Firmware.md",
                                                       "wide/jamison-wiki/Install-Firmware-and-Apps.md"]),
        ("10_jamison_wiki_misc.txt",                 ["wide/jamison-wiki/Home.md",
                                                       "wide/jamison-wiki/User-Interface.md",
                                                       "wide/jamison-wiki/FlipperZero-Game-Engine*.md"]),
        ("11_jamison_worked_examples.txt",           ["medium/jamisonderek-worked-examples/**/*"]),
        ("12_jamison_sao_custom_js_module.txt",      ["medium/jamisonderek-sao/**/*"]),
        ("13_official_good_faps.txt",                ["medium/official-good-faps/**/*"]),
        ("14_fap_boilerplates.txt",                  ["medium/fap-boilerplates/**/*"]),
        ("15_ufbt_docs.txt",                         ["medium/ufbt-docs/**/*"]),
        ("16_awesome_flipperzero_index.txt",         ["wide/awesome-flipperzero/**/*"]),
        ("17_community_fap_catalog_lists.txt",       ["wide/community-fap-catalogs/**/*"]),
        ("18_DOLPHINTANK_01_brief.md",               ["../.dolphintank/01-brief.md"]),
        ("19_DOLPHINTANK_02_state.md",               ["../.dolphintank/02-state.md"]),
        ("20_DOLPHINTANK_03_active.md",              ["../.dolphintank/03-active.md"]),
        ("21_DOLPHINTANK_04_decisions.md",           ["../.dolphintank/04-decisions.md"]),
        ("22_DOLPHINTANK_05_dont_rebuild.md",        ["../.dolphintank/05-dont-rebuild.md"]),
        ("23_DAY8_FAP_VISION.md",                    ["../docs/decisions/DAY8_FAP_VISION.md"]),
        ("24_RECON_LOG.md",                          ["_meta/RECON_LOG.md"]),
        ("25_NOTEBOOKLM_GROUPING_PLAN.md",           ["_meta/NOTEBOOKLM_GROUPING_PLAN.md"]),
        ("26_MANIFEST.md",                           ["_meta/MANIFEST.md"]),
    ],
}


def resolve_globs(base: Path, patterns: list[str]) -> list[Path]:
    files = []
    for pat in patterns:
        pat = pat.replace("\\", "/")
        if "*" in pat:
            try:
                matches = sorted(base.glob(pat))
                files.extend(m for m in matches if m.is_file())
            except (ValueError, OSError):
                pass
        else:
            p = (base / pat).resolve()
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(sorted(x for x in p.rglob("*") if x.is_file()))
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def concat_bundle(out_path: Path, files: list[Path], corpus_root: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8", errors="replace") as outfp:
        outfp.write(f"# Bundle: {out_path.name}\n")
        outfp.write(f"# {len(files)} files concatenated for NotebookLM ingestion\n\n")
        for f in files:
            try:
                rel = f.relative_to(corpus_root)
            except ValueError:
                rel = f
            outfp.write(f"\n\n=== FILE: {rel} ===\n\n")
            try:
                outfp.write(f.read_text(encoding="utf-8", errors="replace"))
                written += 1
            except Exception as e:
                outfp.write(f"[error reading: {e}]")
    return written


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    summary = []
    for notebook, bundles in NOTEBOOKS.items():
        nb_dir = OUT / notebook
        nb_total_files = 0
        nb_total_bundles = 0
        for out_name, patterns in bundles:
            files = resolve_globs(CORPUS, patterns)
            if not files:
                summary.append(f"  [SKIP empty] {notebook}/{out_name}")
                continue
            n = concat_bundle(nb_dir / out_name, files, CORPUS)
            size_kb = (nb_dir / out_name).stat().st_size // 1024
            summary.append(f"  {notebook}/{out_name}: {n} files -> {size_kb} KB")
            nb_total_files += n
            nb_total_bundles += 1
        summary.append(f"=> {notebook}: {nb_total_bundles} bundles holding {nb_total_files} files")
    print("\n".join(summary))
    print(f"\nOutput root: {OUT}")


if __name__ == "__main__":
    main()
