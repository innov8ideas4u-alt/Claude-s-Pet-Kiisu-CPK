/*
 * CPK Companion FAP (CFC) — Phase 2 skeleton
 *
 * Implements:
 *   - AppDataExchange callback (rpc_app.h)
 *   - 16-byte CFC frame header + msgpack payload (spec §4)
 *   - State machine: IDLE / ASSEMBLING (spec §6.2)
 *   - Unified callback flow: confirm → validate → assemble → dispatch → send (spec §6.3)
 *   - 5s ASSEMBLING timer (spec §4.3)
 *   - Opcodes: PING / META_CAPABILITIES / META_VERSION / RESET / ERROR (spec §5)
 *
 * Reference for entry-point signature and "RPC <hex>" args parsing:
 *   notebooklm/cfc/medium/official-good-faps/weather_station/weather_station_app.c
 *   notebooklm/cfc/_upload/notebook1_firmware_side/01_rpc_service_all.txt:783
 */

#include <furi.h>
#include <furi_hal.h>
#include <rpc/rpc_app.h>
#include <lib/cmp/cmp.h>

/* Phase 3 Cook 3 — real Momentum NFC. API surface verified against the local
 * Momentum mirror (commit d3ba597) and the f7 api_symbols export table. The
 * reference CLI scanner/dump code is GPL; this is original MIT code that reuses
 * only the public API pattern (alloc -> scan -> poll -> get_uid -> free). */
#include <nfc/nfc.h>
#include <nfc/nfc_scanner.h>
#include <nfc/nfc_poller.h>
#include <nfc/nfc_device.h>
#include <nfc/protocols/nfc_protocol.h>
#include <nfc/protocols/iso14443_3a/iso14443_3a_poller.h>
#include <notification/notification.h>
#include <notification/notification_messages.h>

/* Phase 3 Cook 1 (Sub-GHz vertical) — decoded-stream RX worker. The SECOND CFC
 * capture vertical, structural twin of the NFC worker above: only the capture
 * engine changes (NFC scanner -> Sub-GHz receiver). Every symbol below is
 * exported in targets/f7/api_symbols.csv and confirmed against the Momentum
 * mirror d3ba597; this is original MIT code reusing only the public
 * alloc -> configure -> rx-callback -> free API pattern (AGPL hygiene §10).
 *
 * Extraction is a DIRECT-FIELD read of the decoder's embedded SubGhzBlockGeneric
 * (v2 PATCH P0): NO subghz_block_generic_serialize, no FlipperFormat, no preset.
 * The concrete decoder struct (SubGhzProtocolDecoderPrinceton) is private to
 * princeton.c, so we mirror the universal fixed-code prefix {base; decoder;
 * generic;} — all three sub-structs ARE public+complete (base.h / decoder.h /
 * generic.h) so the compiler computes byte-identical offsets to the real struct.
 * The prefix is confirmed identical across Princeton/Came/Holtek in the mirror. */
#include <lib/subghz/environment.h>
#include <lib/subghz/receiver.h>
#include <lib/subghz/subghz_worker.h>
#include <lib/subghz/subghz_protocol_registry.h>
#include <lib/subghz/devices/devices.h>
#include <lib/subghz/devices/preset.h>
#include <lib/subghz/devices/cc1101_int/cc1101_int_interconnect.h>
#include <lib/subghz/blocks/decoder.h>
#include <lib/subghz/blocks/generic.h>
#include <lib/subghz/protocols/base.h>
/* NB: per-protocol headers (protocols/princeton.h) are NOT shipped in the ufbt
 * SDK — only base.h / public_api.h / raw.h are. We don't need princeton.h: the
 * concrete decoder struct is opaque either way (we use the CfcSubghzDecoderHead
 * mirror), and the only other thing it exposed was the protocol name string,
 * defined below as the stable registry fact CFC_SUBGHZ_PRINCETON_NAME. */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define TAG "CFC"

#define CFC_MAGIC                 0x4346u
#define CFC_VERSION               0x01u
#define CFC_HEADER_SIZE           16u
#define CFC_MAX_FRAGMENT_PAYLOAD  884u
#define CFC_MAX_TRANSACTION       8192u
#define CFC_ASSEMBLING_TIMEOUT_MS 5000u

#define CFC_OP_PING               0x00u
#define CFC_OP_META_CAPABILITIES  0x01u
#define CFC_OP_META_VERSION       0x02u
#define CFC_OP_RESET              0xFEu
#define CFC_OP_ERROR              0xFFu

/* Phase 3 Cook 2 — NFC subscription opcodes (spec §6.1) */
#define CFC_OP_NFC_SUBSCRIBE_CAPTURE 0x40u
#define CFC_OP_NFC_UNSUBSCRIBE       0x41u
#define CFC_OP_NFC_EVENT             0x42u /* broadcast (command_id == 0) */

/* Phase 3 Cook 3.2 — NFC diagnostic broadcast op_code (the live-fire reroute).
 * Cook 3.1's detect-cb / poll diagnostics only reached the SERIAL console
 * (FURI_LOG); the live-fire harness drains the RPC BROADCAST channel and never
 * saw them. This op_code carries the same detect/poll signal as a real broadcast
 * the harness CAN read — on a SEPARATE op_code from CFC_OP_NFC_EVENT (0x42) so it
 * routes to a distinct host subscription buffer and can never pollute the
 * real-event assertions (_check_real_event asserts on 0x42 only). Emitted from
 * the MAIN thread (worker -> worker_out_diag queue -> main drain -> broadcast),
 * never from the worker, and through the same tx_mutex-guarded send path as 0x42.
 * NB: 0x4F sits inside the spec's doc-reserved 0x40-0x4F "GPIO Phase 4" range
 * (DAY8_FAP_PHASE1_SPEC.md §, opcode table) but NO GPIO op is implemented and
 * GPIO is host->FAP whereas this is a FAP->host broadcast; if Phase 4 GPIO ever
 * lands it must avoid 0x4F (or this diag op moves). See COOK 3.2 cook log. */
#define CFC_OP_NFC_DIAG              0x4Fu /* broadcast (command_id == 0) */

/* Phase 3 Cook 1 (Sub-GHz vertical) — opcodes, the 0x5x twin of the NFC 0x4x
 * block (spec §3). 0x52 EVENT is the decoded-stream broadcast lane; 0x5F DIAG is
 * the live-fire reroute seam (twin of NFC 0x4F) so a silent live-fire can be
 * triaged in ONE run instead of blind (the Cook 3.1 failure mode). */
#define CFC_OP_SUBGHZ_SUBSCRIBE_CAPTURE 0x50u /* host -> FAP: arm the RX worker */
#define CFC_OP_SUBGHZ_UNSUBSCRIBE       0x51u /* host -> FAP: disarm the worker */
#define CFC_OP_SUBGHZ_EVENT             0x52u /* broadcast: decoded fixed-code hit */
#define CFC_OP_SUBGHZ_DIAG              0x5Fu /* broadcast: per-decode diagnostic */

#define CFC_ERR_BAD_FRAME         1
#define CFC_ERR_BAD_FRAGMENT      2
#define CFC_ERR_PAYLOAD_TOO_LARGE 3
#define CFC_ERR_OUT_OF_MEMORY     4
#define CFC_ERR_BUSY              5
#define CFC_ERR_BAD_PAYLOAD       6
#define CFC_ERR_UNKNOWN_OPCODE    7
#define CFC_ERR_INTERNAL          99

/* Phase 3 Cook 2 — subscription error codes (spec §6.2). Distinct from the
 * assembling-state CFC_ERR_BUSY (== 5) above. */
#define CFC_ERR_SUB_BUSY          0x10 /* Q2 exclusive: already subscribed/armed */
#define CFC_ERR_NOT_SUBSCRIBED    0x11
#define CFC_ERR_WORKER_BUSY       0x12

#define CFC_RESPONSE_SCRATCH      1024u

/* Phase 3 Cook 2/3 — worker / broadcast tunables (spec §5.4, §5.5, §13.4) */
#define CFC_WORKER_STACK_SIZE        2048u   /* §5.4: NFC-class worker (scan/poll
                                              * callbacks run on NFC-internal
                                              * threads, not this stack) */
#define CFC_WORKER_IN_DEPTH          8u      /* main -> worker control events */
#define CFC_WORKER_OUT_DEPTH         16u     /* worker -> main results */
#define CFC_WORKER_IDLE_TIMEOUT_MS   300000u /* §5.5/Q6: 5-min idle failsafe */
#define CFC_MAIN_POLL_MS             100u    /* main-loop drain/idle tick */
#define CFC_BROADCAST_TXN_BIT        0x80000000u /* M3: broadcast txn namespace */

/* Phase 3 Cook 3 — real NFC scan/poll tunables.
 * Continuous capture keeps ONE greedy scanner alive until a detection actually
 * fires (mirrors nfc_cli_scanner.c's begin/wait/end), instead of tearing the
 * scanner down on a short timer. The wait loops in CFC_SCAN_POLL_MS slices so a
 * disarm/stop is honored promptly, but the scanner is NOT freed just because no
 * card has arrived — first-detection latency (scanner startup + field power-up +
 * card response) can exceed any short fixed window, so a timed teardown would
 * destroy the scanner right before its detect callback fires (Cook 3.1 bug). The
 * scanner is stopped+freed ONLY when a detection needs the HAL for a poll; after
 * the poll we re-arm a fresh scanner, so tapping N cards needs no re-subscribe. */
#define CFC_SCAN_POLL_MS             200u    /* disarm-check slice while scanning */
#define CFC_POLL_TIMEOUT_MS          1000u   /* poller read timeout per card */
#define CFC_WORKER_FLAG_DETECTED     (1UL << 0) /* scanner cb -> worker thread */

/* Phase 3 Cook 3.2 — diagnostic broadcast plumbing.
 * worker_out_diag is a SECOND worker->main queue (parallel to worker_out) that
 * carries CfcWorkerDiag events. Keeping it separate from CfcWorkerResult means
 * the real-event struct + 0x42 msgpack shape are byte-for-byte unchanged. */
#define CFC_WORKER_DIAG_DEPTH        8u      /* worker -> main diag events */
/* poll_failed reason codes (mapped to strings on the main thread, §Cook 3.2) */
#define CFC_DIAG_REASON_NONE         0u
#define CFC_DIAG_REASON_TIMEOUT      1u /* poll_sem timed out — no poller event */
#define CFC_DIAG_REASON_POLLER_ERR   2u /* poller signalled Iso14443_3a Error */
#define CFC_DIAG_REASON_NO_UID       3u /* poll ok but device UID empty/null */

/* Phase 3 Cook 1 (Sub-GHz vertical) — capture/worker tunables.
 * One frequency, one modulation, decodable-only, Princeton-allowlisted (spec §2). */
#define CFC_SUBGHZ_FREQUENCY         433920000u /* 433.92 MHz, the live-fire dial */
#define CFC_SUBGHZ_EVENT_QUEUE_DEPTH 16u        /* P4: worker(rx-cb) -> main events */
#define CFC_SUBGHZ_DIAG_QUEUE_DEPTH  8u         /* worker(rx-cb) -> main diagnostics */
#define CFC_SUBGHZ_MIN_BITS          8u         /* P4/G5: <8 bits is noise */
#define CFC_SUBGHZ_MAX_BITS          64u        /* P4/G5: largest fixed-code key */
#define CFC_SUBGHZ_PROTOCOL_MAXLEN   24u        /* copied protocol name buffer */
#define CFC_SUBGHZ_IDLE_TIMEOUT_MS   300000u    /* 5-min idle auto-disarm (charge) */
/* The allowlisted protocol's registry name (== SUBGHZ_PROTOCOL_PRINCETON_NAME in
 * princeton.h, which the SDK doesn't ship). Defined locally as the stable fact. */
#define CFC_SUBGHZ_PRINCETON_NAME    "Princeton"

typedef enum {
    CfcStateIdle,
    CfcStateAssembling,
} CfcState;

/* Sub-GHz worker lifecycle state (G6 — enum, not bool). Guards subscribe/
 * unsubscribe churn and makes teardown state-guarded (G7): a charge-suppress
 * exit / worker_stop fires ONLY if the matching enter / start happened. */
typedef enum {
    CfcSubghzStateIdle,     /* not armed; HAL released */
    CfcSubghzStateStarting, /* mid bring-up (transient; goto-cleanup target, G4) */
    CfcSubghzStateRunning,  /* armed: charge suppressed, async RX live, worker up */
    CfcSubghzStateStopping, /* mid teardown (transient) */
} CfcSubghzState;

/* ------- Phase 3 Cook 2: worker thread (spec §5.1-§5.3) ------- */

typedef enum {
    CfcWorkerEventTypeStop,
    CfcWorkerEventTypeNfcArm,
    CfcWorkerEventTypeNfcDisarm,
} CfcWorkerEventType;

typedef struct {
    CfcWorkerEventType type;
} CfcWorkerEvent;

/* Worker -> main capture result. Cook 3: every field is now REAL — uid/uid_len/
 * protocol come from a live NFC read, timestamp_ms + overflow_since_last as
 * before. Passed BY VALUE through the queue — never a pointer to worker stack
 * or NFC-owned memory (UAF: scanner/poller buffers die after their callbacks). */
typedef struct {
    uint8_t uid[8];
    size_t uid_len;
    NfcProtocol protocol;         /* REAL: detected/polled protocol (Iso14443_3a) */
    uint32_t timestamp_ms;        /* REAL: furi_get_tick() at capture */
    uint32_t overflow_since_last; /* REAL: worker_out drops since last delivered */
} CfcWorkerResult;

/* Phase 3 Cook 3.2 — worker -> main diagnostic event. Passed BY VALUE through
 * worker_out_diag (no pointers into worker/NFC memory). The worker emits one of
 * these at each diagnostic point (detection observed; poll succeeded; poll
 * failed); the MAIN thread drains them and broadcasts each on CFC_OP_NFC_DIAG so
 * the live-fire harness can read detect-vs-poll without the serial console. */
typedef enum {
    CfcDiagDetect,     /* scanner detect callback fired (worker observed the flag) */
    CfcDiagPollOk,     /* Iso14443_3a poll read a UID */
    CfcDiagPollFailed, /* Iso14443_3a poll failed (see reason) */
} CfcDiagEvent;

typedef struct {
    CfcDiagEvent event;
    NfcProtocol protocol;    /* CfcDiagDetect: first detected protocol (iff count>0) */
    uint32_t protocol_count; /* CfcDiagDetect: number of protocols detected */
    uint32_t uid_len;        /* CfcDiagPollOk: UID length read */
    uint8_t reason;          /* CfcDiagPollFailed: CFC_DIAG_REASON_* */
} CfcWorkerDiag;

/* Worker NFC state. ALL of it (Nfc/poller/device/sem + the detected[] cache) is
 * touched only by the worker thread and the NFC-internal callback threads it
 * spawns; the main thread never reaches in here. thread_id lets the scanner
 * callback (on an NFC-internal thread) wake the worker via a thread flag. */
typedef struct {
    FuriThread* thread;
    FuriMessageQueue* worker_in;       /* main -> worker (CfcWorkerEvent) */
    FuriMessageQueue* worker_out;      /* worker -> main (CfcWorkerResult) */
    FuriMessageQueue* worker_out_diag; /* worker -> main (CfcWorkerDiag), Cook 3.2 */

    FuriThreadId thread_id;       /* worker's own id (scanner cb -> flag target) */
    Nfc* nfc;                     /* HAL claim, held for the whole armed session */
    NfcDevice* nfc_device;        /* receives polled card data */
    NfcScanner* scanner;          /* greedy scanner; alive from arm until a poll */
    NfcPoller* poller;            /* transient: alive only during one poll */
    FuriSemaphore* poll_sem;      /* poller-done signal (cb -> worker) */
    bool poll_ok;                 /* poll result; synced via poll_sem */
    size_t detected_num;          /* protocols from the last scanner detection */
    NfcProtocol detected[NfcProtocolNum];
} CfcWorker;

/* ------- Phase 3 Cook 1: Sub-GHz worker (decoded-stream RX) ------- */

/* Mirror of the universal fixed-code decoder prefix. The concrete
 * SubGhzProtocolDecoderPrinceton is opaque in princeton.h (body private to
 * princeton.c), so the spec's literal cast won't compile. We re-declare the prefix
 * — base + decoder + generic, in struct order — and dereference ONLY after the
 * protocol-name allowlist gate (P0). NOTE the generic sub-struct below is pinned to
 * the FIRMWARE layout, not the SDK's (see the comment on CfcMtmGeneric). */
/* Momentum's SubGhzBlockGeneric is WIDER than the stock ufbt SDK's generic.h:
 * Momentum inserts `data_2` (uint64) right after `data`, plus `cnt_2`/`seed` at the
 * end. The SDK header this FAP compiles against therefore places data_count_bit at
 * offset 20, but the firmware ACTUALLY on the device keeps it at offset 28. Casting
 * through the SDK's SubGhzBlockGeneric read data_count_bit from inside the firmware's
 * unused `data_2` => always 0 (live-fire fingerprint: protocol=Princeton, bits=0,
 * accepted=false). `data` (the key) is at offset 8 in BOTH, so only the bit count was
 * wrong. Pin the cast to the FIRMWARE's real layout (mirror d3ba597). CPK targets
 * Momentum mntm-dev ONLY, so this is correct; revisit if the firmware family changes.
 * GENERAL LESSON: the ufbt SDK headers are stock/upstream and do NOT reflect Momentum's
 * struct extensions — never trust an SDK struct's field offsets for a private cast. */
typedef struct {
    const char* protocol_name;
    uint64_t data;
    uint64_t data_2;         /* Momentum-only; absent from stock SDK generic.h */
    uint32_t serial;
    uint16_t data_count_bit; /* firmware offset 28 (SDK header wrongly puts it at 20) */
    uint8_t btn;
    uint32_t cnt;
    uint8_t cnt_2;           /* Momentum-only */
    uint32_t seed;           /* Momentum-only */
} CfcMtmGeneric;

typedef struct {
    SubGhzProtocolDecoderBase base;
    SubGhzBlockDecoder decoder;
    CfcMtmGeneric generic; /* firmware-accurate layout, NOT the SDK's SubGhzBlockGeneric */
} CfcSubghzDecoderHead;

/* rx-callback -> main decoded result. Passed BY VALUE through the queue; the
 * decoder_base pointer is valid ONLY inside the rx callback (runs on the SubGhz
 * worker thread), same UAF discipline as the NFC UID. protocol[] is an OWNED copy
 * of the registry's static name string (copy-by-value, zero lifetime assumption). */
typedef struct {
    char protocol[CFC_SUBGHZ_PROTOCOL_MAXLEN]; /* e.g. "Princeton" */
    uint32_t bits;                             /* generic.data_count_bit */
    uint64_t key;                              /* generic.data (uint64) */
    uint32_t frequency;                        /* CFC_SUBGHZ_FREQUENCY (const) */
    uint32_t timestamp_ms;                     /* furi_get_tick() at decode (P6) */
} CfcSubghzResult;

/* rx-callback -> main diagnostic (0x5F seam). Emitted on EVERY decode the
 * receiver completes, BEFORE the allowlist/G5 gate, so a silent live-fire is
 * triaged in one run: no diag at all => receiver decoded nothing (RF/preset/
 * freq/wiring); diag with protocol != Princeton => decoding something else;
 * diag Princeton + accepted=false => G5 dropped it; accepted=true => should have
 * broadcast. Passed BY VALUE; best-effort (dropped silently on a full queue). */
typedef struct {
    char protocol[CFC_SUBGHZ_PROTOCOL_MAXLEN];
    uint32_t bits;     /* 0 for non-allowlisted (never cast a foreign prefix) */
    bool accepted;     /* passed allowlist AND G5 (key!=0 && bits in [8,64]) */
} CfcSubghzDiag;

/* Sub-GHz worker state. The SubGhzWorker IS the background decode thread (it owns
 * its own FuriThread), so — unlike the NFC CfcWorker — there is NO custom polling
 * thread here. The receiver rx callback fires synchronously on that worker thread
 * and copies primitives into `events` (P1); the MAIN thread drains + builds the
 * msgpack + broadcasts. Allocated ONCE at app start; fields RESET (never realloc)
 * on re-subscribe (G6). `device` is the const registry handle (init once, G2). */
typedef struct {
    SubGhzEnvironment* environment; /* registry holder (no keystore — fixed-code) */
    SubGhzReceiver* receiver;       /* runs the decoders; our rx cb hangs off it */
    SubGhzWorker* worker;           /* the decode thread (start on arm, stop on disarm) */
    const SubGhzDevice* device;     /* CC1101 internal; resolved once after init */
    bool devices_inited;            /* G2: subghz_devices_init called once */
    FuriMessageQueue* events;       /* rx cb -> main (CfcSubghzResult), depth 16 */
    FuriMessageQueue* diag;         /* rx cb -> main (CfcSubghzDiag), depth 8 */
    uint32_t drops;                 /* P4: running count of events-queue drop-on-full */
    CfcSubghzState state;           /* G6/G7 lifecycle guard */
} CfcSubghzWorker;

typedef struct {
    RpcAppSystem* rpc_app;
    FuriMessageQueue* exit_queue;
    FuriMutex* mutex;
    FuriTimer* assemble_timer;

    /* Cook 3 single-writer wire mutex (MUST-DO #1). RPC responses are sent from
     * the RPC callback thread; NFC broadcasts are drained+sent from the main
     * thread. Two senders. This mutex is held from the FIRST to the LAST
     * fragment of ANY message so the two can never interleave on the wire. */
    FuriMutex* tx_mutex;

    CfcState state;
    uint8_t op_code;
    uint32_t transaction_id;
    uint32_t payload_length;
    uint16_t fragment_total;
    uint16_t fragments_received;
    uint8_t* assemble_buffer;
    size_t assemble_pos;

    /* Phase 3 Cook 2/3 — NFC subscription / worker (all MAIN-THREAD-ONLY fields) */
    CfcWorker worker;
    bool nfc_subscribed;            /* subscription active? (BUSY + idle checks) */
    uint32_t worker_arm_ms;         /* tick at last arm — 5-min idle failsafe */
    uint32_t broadcast_txn_counter; /* next broadcast txn sequence (high-bit set) */
    bool first_tap_pending;         /* beep on the first tap after each subscribe */
    NotificationApp* notifications; /* RECORD_NOTIFICATION (gate f beep) */

    /* Phase 3 Cook 1 — Sub-GHz vertical (additive; independent of NFC above).
     * The two verticals can be armed concurrently: each pairs its own
     * charge-suppress enter/exit (the firmware counter is ref-counted) and its
     * own worker, so they compose without interference (P3). subghz_lock guards
     * the arm/disarm/idle critical sections against the one cross-thread race:
     * unsubscribe (RPC-callback thread) vs the idle failsafe (main thread). */
    CfcSubghzWorker subghz;
    bool subghz_subscribed;     /* subscription active? (BUSY + idle checks) */
    uint32_t subghz_arm_ms;     /* tick at last arm — 5-min idle failsafe */
    FuriMutex* subghz_lock;     /* serialize arm/disarm/idle transitions */
} CfcContext;

typedef struct {
    const uint8_t* data;
    size_t pos;
    size_t cap;
} CfcReadBuf;

typedef struct {
    uint8_t* data;
    size_t pos;
    size_t cap;
} CfcWriteBuf;

/* ------- cmp glue ------- */

static bool cfc_cmp_reader(cmp_ctx_t* ctx, void* data, size_t limit) {
    CfcReadBuf* b = (CfcReadBuf*)ctx->buf;
    if(b->pos + limit > b->cap) return false;
    memcpy(data, b->data + b->pos, limit);
    b->pos += limit;
    return true;
}

static bool cfc_cmp_skipper(cmp_ctx_t* ctx, size_t count) {
    CfcReadBuf* b = (CfcReadBuf*)ctx->buf;
    if(b->pos + count > b->cap) return false;
    b->pos += count;
    return true;
}

static size_t cfc_cmp_writer(cmp_ctx_t* ctx, const void* data, size_t count) {
    CfcWriteBuf* b = (CfcWriteBuf*)ctx->buf;
    if(b->pos + count > b->cap) return 0;
    memcpy(b->data + b->pos, data, count);
    b->pos += count;
    return count;
}

/* ------- header pack/unpack ------- */

static void cfc_write_header(
    uint8_t* out,
    uint8_t op_code,
    uint32_t transaction_id,
    uint16_t fragment_index,
    uint16_t fragment_total,
    uint32_t payload_length) {
    out[0] = (uint8_t)(CFC_MAGIC & 0xFF);
    out[1] = (uint8_t)((CFC_MAGIC >> 8) & 0xFF);
    out[2] = CFC_VERSION;
    out[3] = op_code;
    out[4] = (uint8_t)(transaction_id & 0xFF);
    out[5] = (uint8_t)((transaction_id >> 8) & 0xFF);
    out[6] = (uint8_t)((transaction_id >> 16) & 0xFF);
    out[7] = (uint8_t)((transaction_id >> 24) & 0xFF);
    out[8] = (uint8_t)(fragment_index & 0xFF);
    out[9] = (uint8_t)((fragment_index >> 8) & 0xFF);
    out[10] = (uint8_t)(fragment_total & 0xFF);
    out[11] = (uint8_t)((fragment_total >> 8) & 0xFF);
    out[12] = (uint8_t)(payload_length & 0xFF);
    out[13] = (uint8_t)((payload_length >> 8) & 0xFF);
    out[14] = (uint8_t)((payload_length >> 16) & 0xFF);
    out[15] = (uint8_t)((payload_length >> 24) & 0xFF);
}

typedef struct {
    uint16_t magic;
    uint8_t version;
    uint8_t op_code;
    uint32_t transaction_id;
    uint16_t fragment_index;
    uint16_t fragment_total;
    uint32_t payload_length;
} CfcHeader;

static bool cfc_parse_header(const uint8_t* in, size_t in_len, CfcHeader* hdr) {
    if(in_len < CFC_HEADER_SIZE) return false;
    hdr->magic = (uint16_t)in[0] | ((uint16_t)in[1] << 8);
    hdr->version = in[2];
    hdr->op_code = in[3];
    hdr->transaction_id = (uint32_t)in[4] | ((uint32_t)in[5] << 8) | ((uint32_t)in[6] << 16) |
                          ((uint32_t)in[7] << 24);
    hdr->fragment_index = (uint16_t)in[8] | ((uint16_t)in[9] << 8);
    hdr->fragment_total = (uint16_t)in[10] | ((uint16_t)in[11] << 8);
    hdr->payload_length = (uint32_t)in[12] | ((uint32_t)in[13] << 8) | ((uint32_t)in[14] << 16) |
                          ((uint32_t)in[15] << 24);
    return true;
}

/* ------- send helpers ------- */

static void cfc_assemble_reset(CfcContext* cfc) {
    if(cfc->assemble_buffer) {
        free(cfc->assemble_buffer);
        cfc->assemble_buffer = NULL;
    }
    cfc->assemble_pos = 0;
    cfc->state = CfcStateIdle;
    cfc->op_code = 0;
    cfc->transaction_id = 0;
    cfc->payload_length = 0;
    cfc->fragment_total = 0;
    cfc->fragments_received = 0;
    furi_timer_stop(cfc->assemble_timer);
}

/* Raw wire write — NO locking. Callers MUST hold cfc->tx_mutex across the whole
 * message (all fragments). This is the ONLY place that touches the wire. */
static inline void cfc_wire_write_raw(CfcContext* cfc, const uint8_t* buf, size_t len) {
    rpc_system_app_exchange_data(cfc->rpc_app, buf, len);
}

/* Single-fragment message. Acquires tx_mutex for the (one) frame. */
static void cfc_send_response_frame(
    CfcContext* cfc,
    uint8_t op_code,
    uint32_t transaction_id,
    const uint8_t* payload,
    size_t payload_len) {
    if(payload_len > CFC_MAX_FRAGMENT_PAYLOAD) {
        FURI_LOG_E(TAG, "send: payload %zu > 884; dropping", payload_len);
        return;
    }
    uint8_t buf[CFC_HEADER_SIZE + CFC_MAX_FRAGMENT_PAYLOAD];
    cfc_write_header(buf, op_code, transaction_id, 0, 1, (uint32_t)payload_len);
    if(payload && payload_len) {
        memcpy(buf + CFC_HEADER_SIZE, payload, payload_len);
    }
    furi_mutex_acquire(cfc->tx_mutex, FuriWaitForever);
    cfc_wire_write_raw(cfc, buf, CFC_HEADER_SIZE + payload_len);
    furi_mutex_release(cfc->tx_mutex);
}

/**
 * Send a response that may exceed CFC_MAX_FRAGMENT_PAYLOAD (884 bytes)
 * by fragmenting into multiple frames per spec §6.4. Each fragment carries
 * the same op_code, transaction_id, and total payload_length; only
 * frag_idx changes across frames.
 *
 * Caller owns the payload buffer; this function does not free it.
 * Inter-frame furi_delay_ms(1) yield per spec §6.4 — gives the firmware
 * RPC scheduler breathing room between fragments.
 *
 * No return value: rpc_system_app_exchange_data is void per
 * docs/decisions/DAY8_FAP_PHASE1_SPEC.md §6.4. Transport-level failures
 * are detected host-side via timeout.
 *
 * Cook 3: tx_mutex is acquired ONCE and held across every fragment (including
 * the inter-frame delay) so a concurrent NFC broadcast on the main thread can
 * never slip between two fragments of this response. Does NOT call
 * cfc_send_response_frame (that would re-acquire the non-recursive mutex).
 */
static void cfc_send_response_multi(
    CfcContext* cfc,
    uint8_t op_code,
    uint32_t transaction_id,
    const uint8_t* payload,
    size_t payload_len) {
    if(payload_len > CFC_MAX_TRANSACTION) {
        FURI_LOG_E(TAG, "send_multi: payload %zu > CFC_MAX_TRANSACTION; dropping", payload_len);
        return;
    }

    uint32_t total_frags = (payload_len <= CFC_MAX_FRAGMENT_PAYLOAD)
                               ? 1u
                               : (payload_len + CFC_MAX_FRAGMENT_PAYLOAD - 1) /
                                     CFC_MAX_FRAGMENT_PAYLOAD;
    uint8_t buf[CFC_HEADER_SIZE + CFC_MAX_FRAGMENT_PAYLOAD];

    furi_mutex_acquire(cfc->tx_mutex, FuriWaitForever);
    for(uint32_t frag_idx = 0; frag_idx < total_frags; frag_idx++) {
        size_t offset = frag_idx * CFC_MAX_FRAGMENT_PAYLOAD;
        size_t this_frag_len = (payload_len - offset > CFC_MAX_FRAGMENT_PAYLOAD)
                                   ? CFC_MAX_FRAGMENT_PAYLOAD
                                   : (payload_len - offset);

        cfc_write_header(buf, op_code, transaction_id, frag_idx, total_frags, (uint32_t)payload_len);
        if(this_frag_len) {
            memcpy(buf + CFC_HEADER_SIZE, payload + offset, this_frag_len);
        }
        cfc_wire_write_raw(cfc, buf, CFC_HEADER_SIZE + this_frag_len);

        // Inter-frame yield per spec §6.4. Gives the RPC scheduler time
        // to drain its outbound queue before we push the next fragment.
        if(frag_idx + 1 < total_frags) {
            furi_delay_ms(1);
        }
    }
    furi_mutex_release(cfc->tx_mutex);
}

static void cfc_send_error(CfcContext* cfc, uint32_t transaction_id, int code, const char* message) {
    uint8_t payload[64];
    CfcWriteBuf wb = {.data = payload, .pos = 0, .cap = sizeof(payload)};
    cmp_ctx_t cmp;
    cmp_init(&cmp, &wb, NULL, NULL, cfc_cmp_writer);
    if(!cmp_write_map(&cmp, 2)) return;
    if(!cmp_write_str(&cmp, "code", 4)) return;
    if(!cmp_write_integer(&cmp, code)) return;
    if(!cmp_write_str(&cmp, "message", 7)) return;
    if(!cmp_write_str(&cmp, message, (uint32_t)strlen(message))) return;
    cfc_send_response_frame(cfc, CFC_OP_ERROR, transaction_id, payload, wb.pos);
}

static void cfc_send_status_ok(CfcContext* cfc, uint32_t transaction_id, uint8_t op_code) {
    uint8_t payload[32];
    CfcWriteBuf wb = {.data = payload, .pos = 0, .cap = sizeof(payload)};
    cmp_ctx_t cmp;
    cmp_init(&cmp, &wb, NULL, NULL, cfc_cmp_writer);
    if(!cmp_write_map(&cmp, 1)) return;
    if(!cmp_write_str(&cmp, "status", 6)) return;
    if(!cmp_write_str(&cmp, "ok", 2)) return;
    cfc_send_response_frame(cfc, op_code, transaction_id, payload, wb.pos);
}

/* ------- Phase 3 Cook 3: real NFC worker thread + broadcast plumbing (§5, §18) ------- */

/*
 * Scanner detection callback. Runs on an NFC-INTERNAL thread, NOT the worker.
 * The protocols[] array is only valid for the duration of this call — COPY it
 * immediately into worker-owned storage, then wake the worker via a thread flag
 * (the in-tree nfc_cli_scanner.c pattern). Keep it minimal: copy + signal.
 */
static void cfc_scanner_detect_cb(NfcScannerEvent event, void* context) {
    CfcWorker* w = (CfcWorker*)context;
    if(event.type != NfcScannerEventTypeDetected) return;
    size_t n = event.data.protocol_num;
    if(n > NfcProtocolNum) n = NfcProtocolNum;
    w->detected_num = n;
    memcpy(w->detected, event.data.protocols, n * sizeof(NfcProtocol));
    /* HALT disambiguation: proves the detect callback fired (vs a poll-side fail). */
    FURI_LOG_I(TAG, "scan detect cb: %u protocol(s)", (unsigned)n);
    furi_thread_flags_set(w->thread_id, CFC_WORKER_FLAG_DETECTED);
}

/*
 * Iso14443_3a poller callback. Runs on an NFC-INTERNAL thread. On Ready, stash
 * the read data into our NfcDevice and stop; on Error, flag failure and stop.
 * The semaphore release establishes a happens-before edge to the worker thread,
 * which then reads poll_ok + the device UID safely. Original MIT reimplementation
 * of the nfc_cli_dump_iso14443_3a.c API pattern.
 */
static NfcCommand cfc_iso14443_3a_poller_cb(NfcGenericEvent event, void* context) {
    furi_assert(event.protocol == NfcProtocolIso14443_3a);
    CfcWorker* w = (CfcWorker*)context;
    const Iso14443_3aPollerEvent* ev = event.event_data;

    NfcCommand command = NfcCommandContinue;
    if(ev->type == Iso14443_3aPollerEventTypeReady) {
        nfc_device_set_data(w->nfc_device, NfcProtocolIso14443_3a, nfc_poller_get_data(w->poller));
        w->poll_ok = true;
        command = NfcCommandStop;
    } else if(ev->type == Iso14443_3aPollerEventTypeError) {
        w->poll_ok = false;
        command = NfcCommandStop;
    }
    if(command == NfcCommandStop) furi_semaphore_release(w->poll_sem);
    return command;
}

/* Claim the NFC HAL + alloc the per-session NFC objects. Worker thread only. */
static bool cfc_worker_nfc_start(CfcWorker* w) {
    w->nfc = nfc_alloc(); /* exclusively claims the NFC HAL */
    if(!w->nfc) {
        FURI_LOG_E(TAG, "nfc_alloc failed");
        return false;
    }
    w->nfc_device = nfc_device_alloc();
    w->poll_sem = furi_semaphore_alloc(1, 0);
    w->scanner = NULL;
    w->poller = NULL;
    w->detected_num = 0;
    return true;
}

/*
 * Begin a continuous greedy scan: clear any stale detect flag, then alloc + start
 * ONE scanner that stays alive until a detection fires (or we disarm). Mirrors
 * nfc_cli_scanner_begin_scan. Worker thread only. Unlike a per-cycle teardown,
 * this scanner is given unbounded time to fire its detect callback. */
static void cfc_worker_scan_begin(CfcWorker* w) {
    furi_thread_flags_clear(CFC_WORKER_FLAG_DETECTED);
    w->detected_num = 0;
    w->scanner = nfc_scanner_alloc(w->nfc);
    nfc_scanner_start(w->scanner, cfc_scanner_detect_cb, w);
}

/*
 * Stop + free the live scanner so the HAL is free for a poll (or on disarm).
 * nfc_scanner_stop is synchronous — no detect callback can fire after it returns.
 * NULL-safe + idempotent. Worker thread only. */
static void cfc_worker_scan_end(CfcWorker* w) {
    if(w->scanner) {
        nfc_scanner_stop(w->scanner);
        nfc_scanner_free(w->scanner);
        w->scanner = NULL;
    }
}

/* Release everything cfc_worker_nfc_start claimed. Worker thread only.
 * nfc_free() releases the HAL — without it NFC is dead until reboot. Each guard
 * is NULL-safe so this is idempotent (the thread exit path calls it again). */
static void cfc_worker_nfc_stop(CfcWorker* w) {
    cfc_worker_scan_end(w); /* kill a live scanner first (HAL still claimed) */
    if(w->poller) {
        nfc_poller_stop(w->poller);
        nfc_poller_free(w->poller);
        w->poller = NULL;
    }
    if(w->poll_sem) {
        furi_semaphore_free(w->poll_sem);
        w->poll_sem = NULL;
    }
    if(w->nfc_device) {
        nfc_device_free(w->nfc_device);
        w->nfc_device = NULL;
    }
    if(w->nfc) {
        nfc_free(w->nfc); /* releases the HAL */
        w->nfc = NULL;
    }
    w->detected_num = 0;
}

/*
 * Poll a detected Iso14443_3a card and fill out->uid. Alloc poller, start, block
 * on poll_sem until the callback signals, read the UID and COPY it (the poller/
 * device buffers are NFC-owned, not ours to keep). Returns false on timeout or
 * read error. Worker thread only.
 */
static bool cfc_worker_poll_iso14443_3a(CfcWorker* w, CfcWorkerResult* out, uint8_t* fail_reason) {
    w->poll_ok = false;
    *fail_reason = CFC_DIAG_REASON_NONE; /* Cook 3.2: distinguish the failure mode */
    w->poller = nfc_poller_alloc(w->nfc, NfcProtocolIso14443_3a);
    nfc_poller_start(w->poller, cfc_iso14443_3a_poller_cb, w);

    FuriStatus s = furi_semaphore_acquire(w->poll_sem, CFC_POLL_TIMEOUT_MS);

    nfc_poller_stop(w->poller);
    nfc_poller_free(w->poller);
    w->poller = NULL;

    if(s != FuriStatusOk) {
        *fail_reason = CFC_DIAG_REASON_TIMEOUT;
        return false;
    }
    if(!w->poll_ok) {
        *fail_reason = CFC_DIAG_REASON_POLLER_ERR;
        return false;
    }

    size_t uid_len = 0;
    const uint8_t* uid = nfc_device_get_uid(w->nfc_device, &uid_len);
    if(!uid || uid_len == 0) {
        *fail_reason = CFC_DIAG_REASON_NO_UID;
        return false;
    }
    if(uid_len > sizeof(out->uid)) uid_len = sizeof(out->uid);

    memcpy(out->uid, uid, uid_len); /* COPY now — uid points into device memory */
    out->uid_len = uid_len;
    out->protocol = NfcProtocolIso14443_3a;
    out->timestamp_ms = furi_get_tick();
    return true;
}

/*
 * Cook 3.2 — post a diagnostic to the main thread (NON-BLOCKING, worker only).
 * The worker NEVER writes the wire (Q3); it enqueues a by-value CfcWorkerDiag and
 * the MAIN thread drains + broadcasts it on CFC_OP_NFC_DIAG. A full diag queue
 * just drops the event (0 timeout) — diagnostics must never stall the worker or
 * perturb the real capture path.
 */
static void cfc_worker_emit_diag(CfcWorker* w, const CfcWorkerDiag* d) {
    furi_message_queue_put(w->worker_out_diag, d, 0);
}

/*
 * Worker thread (spec §5.2, §18). Real NFC hardware work runs HERE, off the RPC
 * callback context. The worker NEVER touches the wire (Q3) — it only enqueues
 * results to worker_out; the MAIN thread drains and broadcasts them.
 *
 * Lifecycle: idle (blocked on worker_in) -> Arm claims the HAL and starts ONE
 * greedy scanner -> the loop waits in CFC_SCAN_POLL_MS slices for a detection,
 * servicing pending control each slice; on a detection it stops the scanner,
 * polls+emits an Iso14443_3a card, then re-arms a fresh scanner -> Disarm/Stop
 * stops the scanner and releases the HAL. The scanner is NOT torn down on a
 * timeout, so a card tapped any time after arm is caught (the Cook 3.1 fix);
 * control latency while armed is <= CFC_SCAN_POLL_MS, inside the 5s budget.
 * Continuous capture (tap N cards, no re-subscribe) IS the re-arm after each poll.
 *
 * Backpressure (arena review): worker_out put is NON-BLOCKING (0 timeout). On a
 * full queue the event is dropped + counted; the count rides out on the next
 * delivered event's overflow_since_last.
 */
static int32_t cfc_worker_thread(void* context) {
    CfcWorker* w = (CfcWorker*)context;
    w->thread_id = furi_thread_get_current_id();
    bool armed = false;
    uint32_t pending_overflow = 0;

    while(true) {
        if(!armed) {
            /* Idle: block until a control event arrives. */
            CfcWorkerEvent ev;
            FuriStatus s = furi_message_queue_get(w->worker_in, &ev, FuriWaitForever);
            if(s != FuriStatusOk) continue;
            if(ev.type == CfcWorkerEventTypeStop) break;
            if(ev.type == CfcWorkerEventTypeNfcArm) {
                if(cfc_worker_nfc_start(w)) {
                    cfc_worker_scan_begin(w); /* one live scanner for this session */
                    armed = true;
                    pending_overflow = 0;
                }
            }
            /* Disarm while idle: nothing to do. */
            continue;
        }

        /* Armed: ONE scanner is live (begun at arm / re-armed after each poll).
         * Wait a short slice for a detection — the scanner is NOT torn down on
         * timeout, so it has unbounded time to fire. We only loop back to
         * re-check the disarm/stop signal. */
        uint32_t flags =
            furi_thread_flags_wait(CFC_WORKER_FLAG_DETECTED, FuriFlagWaitAny, CFC_SCAN_POLL_MS);
        bool detected = !(flags & FuriFlagError) && (flags & CFC_WORKER_FLAG_DETECTED);

        /* Service pending control WITHOUT blocking, so disarm/stop are honored
         * within CFC_SCAN_POLL_MS even while waiting for a card. */
        bool stop = false;
        bool disarm = false;
        CfcWorkerEvent ev;
        while(furi_message_queue_get(w->worker_in, &ev, 0) == FuriStatusOk) {
            if(ev.type == CfcWorkerEventTypeStop) {
                stop = true;
            } else if(ev.type == CfcWorkerEventTypeNfcDisarm) {
                disarm = true;
            }
            /* extra Arm while armed: ignore */
        }
        if(stop || disarm) {
            cfc_worker_nfc_stop(w); /* stops the live scanner + releases the HAL */
            armed = false;
            if(stop) break;
            continue;
        }

        if(detected) {
            /* Cook 3.2 DIAG: the detect callback fired. Emit BEFORE the poll so the
             * operator's terminal shows detection happened even if the poll then
             * fails/hangs. Carries the first detected protocol + the count. */
            CfcWorkerDiag detect_diag = {
                .event = CfcDiagDetect,
                .protocol = (w->detected_num > 0) ? w->detected[0] : NfcProtocolIso14443_3a,
                .protocol_count = (uint32_t)w->detected_num,
            };
            cfc_worker_emit_diag(w, &detect_diag);

            /* The poll needs the HAL the scanner holds — stop the scanner first. */
            cfc_worker_scan_end(w);
            for(size_t i = 0; i < w->detected_num; i++) {
                /* Cook 3.3: accept the whole ISO14443-3A family, not just a bare
                 * Iso14443_3a leaf. The scanner reports the MOST-SPECIFIC protocol
                 * (nfc_scanner_filter_detected_protocols strips the Iso14443_3a base
                 * once a child is detected), so an NTAG/Ultralight card arrives as
                 * NfcProtocolMfUltralight, a bank card as Iso14443_4a/EMV, etc. —
                 * never as bare Iso14443_3a. Every one of them is activated by the
                 * SAME 3a anti-collision and exposes its UID at the 3a transport
                 * layer, so the single existing Iso14443_3a poll reads the UID
                 * regardless of the higher layer (verified against Momentum
                 * nfc_protocol.c tree + nfc_scanner.c; nfc_protocol_has_parent is
                 * exported in targets/f7/api_symbols.csv). Bare 3a cards still match
                 * via the == arm, so the Cook 3 Iso14443_3a path is unchanged. */
                if(w->detected[i] != NfcProtocolIso14443_3a &&
                   !nfc_protocol_has_parent(w->detected[i], NfcProtocolIso14443_3a))
                    continue;
                CfcWorkerResult result = {0};
                uint8_t fail_reason = CFC_DIAG_REASON_NONE;
                bool poll_ok = cfc_worker_poll_iso14443_3a(w, &result, &fail_reason);
                /* HALT disambiguation: detect fired (logged above) → poll outcome. */
                FURI_LOG_I(TAG, "poll iso14443_3a: %s", poll_ok ? "ok" : "FAILED");
                /* Cook 3.2 DIAG: poll outcome, with uid_len (ok) or reason (failed). */
                CfcWorkerDiag poll_diag = {0};
                if(poll_ok) {
                    poll_diag.event = CfcDiagPollOk;
                    poll_diag.uid_len = (uint32_t)result.uid_len;
                } else {
                    poll_diag.event = CfcDiagPollFailed;
                    poll_diag.reason = fail_reason;
                }
                cfc_worker_emit_diag(w, &poll_diag);
                if(poll_ok) {
                    result.overflow_since_last = pending_overflow;
                    /* NON-BLOCKING put — never stall the worker on a full queue. */
                    if(furi_message_queue_put(w->worker_out, &result, 0) == FuriStatusOk) {
                        pending_overflow = 0;
                    } else {
                        pending_overflow++; /* dropped; reported on next delivery */
                    }
                }
                break; /* One 3a-family card per detection: the UID is read at the
                          shared 3a transport layer, so a single poll covers any of
                          NTAG/Ultralight, MfClassic, Iso14443_4a, EMV, ... — poll
                          once, then re-arm the scanner for the next tap. */
            }
            /* Re-arm a fresh scanner and resume the wait — continuous capture
             * (tap N cards without re-subscribing). */
            cfc_worker_scan_begin(w);
        }
    }

    /* Safety net: release the HAL if we exit while still holding it. Idempotent. */
    cfc_worker_nfc_stop(w);
    return 0;
}

/*
 * Encode + send one NFC_EVENT broadcast (spec §6.4 payload). Runs on the MAIN
 * thread only. Payload map: uid(bin) / type(str) / rssi(nil) / timestamp_ms /
 * overflow_since_last. Cook 3: uid + type are now REAL — type is the firmware's
 * own protocol name (e.g. "ISO14443-3A"). rssi stays nil (no RSSI source in the
 * poller API). Msgpack keys are unchanged from Cook 2, so host + mJS are untouched.
 */
static void cfc_send_nfc_event(CfcContext* cfc, uint32_t txn, const CfcWorkerResult* r) {
    uint8_t payload[128];
    CfcWriteBuf wb = {.data = payload, .pos = 0, .cap = sizeof(payload)};
    cmp_ctx_t cmp;
    cmp_init(&cmp, &wb, NULL, NULL, cfc_cmp_writer);

    const char* type_name = nfc_device_get_protocol_name(r->protocol);
    if(!type_name) type_name = "unknown";
    uint32_t type_len = (uint32_t)strlen(type_name);

    if(!cmp_write_map(&cmp, 5)) return;
    if(!cmp_write_str(&cmp, "uid", 3)) return;
    if(!cmp_write_bin(&cmp, r->uid, (uint32_t)r->uid_len)) return;
    if(!cmp_write_str(&cmp, "type", 4)) return;
    if(!cmp_write_str(&cmp, type_name, type_len)) return;
    if(!cmp_write_str(&cmp, "rssi", 4)) return;
    if(!cmp_write_nil(&cmp)) return;
    if(!cmp_write_str(&cmp, "timestamp_ms", 12)) return;
    if(!cmp_write_uinteger(&cmp, r->timestamp_ms)) return;
    if(!cmp_write_str(&cmp, "overflow_since_last", 19)) return;
    if(!cmp_write_uinteger(&cmp, r->overflow_since_last)) return;

    cfc_send_response_frame(cfc, CFC_OP_NFC_EVENT, txn, payload, wb.pos);
}

/*
 * Cook 3.2 — encode + send one NFC_DIAG broadcast (the live-fire reroute). MAIN
 * thread only, through cfc_send_response_frame so it rides the SAME tx_mutex
 * single-writer discipline as the real 0x42 event (it is a new message TYPE, not
 * a new writer thread). Distinct op_code (0x4F) → distinct host subscription
 * buffer → can never reach _check_real_event (which asserts on 0x42 only).
 *
 * Payload (msgpack map), per diag event:
 *   detect_cb:   {"event":"detect_cb","protocol":"<name|unknown>","protocol_count":N}
 *   poll_ok:     {"event":"poll_ok","uid_len":N}
 *   poll_failed: {"event":"poll_failed","reason":"timeout|poller_error|no_uid|unknown"}
 */
static void cfc_send_nfc_diag(CfcContext* cfc, uint32_t txn, const CfcWorkerDiag* d) {
    uint8_t payload[96];
    CfcWriteBuf wb = {.data = payload, .pos = 0, .cap = sizeof(payload)};
    cmp_ctx_t cmp;
    cmp_init(&cmp, &wb, NULL, NULL, cfc_cmp_writer);

    switch(d->event) {
    case CfcDiagDetect: {
        const char* pname =
            (d->protocol_count > 0) ? nfc_device_get_protocol_name(d->protocol) : NULL;
        if(!pname) pname = "unknown";
        if(!cmp_write_map(&cmp, 3)) return;
        if(!cmp_write_str(&cmp, "event", 5)) return;
        if(!cmp_write_str(&cmp, "detect_cb", 9)) return;
        if(!cmp_write_str(&cmp, "protocol", 8)) return;
        if(!cmp_write_str(&cmp, pname, (uint32_t)strlen(pname))) return;
        if(!cmp_write_str(&cmp, "protocol_count", 14)) return;
        if(!cmp_write_uinteger(&cmp, d->protocol_count)) return;
        break;
    }
    case CfcDiagPollOk:
        if(!cmp_write_map(&cmp, 2)) return;
        if(!cmp_write_str(&cmp, "event", 5)) return;
        if(!cmp_write_str(&cmp, "poll_ok", 7)) return;
        if(!cmp_write_str(&cmp, "uid_len", 7)) return;
        if(!cmp_write_uinteger(&cmp, d->uid_len)) return;
        break;
    case CfcDiagPollFailed: {
        const char* reason;
        switch(d->reason) {
        case CFC_DIAG_REASON_TIMEOUT:
            reason = "timeout";
            break;
        case CFC_DIAG_REASON_POLLER_ERR:
            reason = "poller_error";
            break;
        case CFC_DIAG_REASON_NO_UID:
            reason = "no_uid";
            break;
        default:
            reason = "unknown";
            break;
        }
        if(!cmp_write_map(&cmp, 2)) return;
        if(!cmp_write_str(&cmp, "event", 5)) return;
        if(!cmp_write_str(&cmp, "poll_failed", 11)) return;
        if(!cmp_write_str(&cmp, "reason", 6)) return;
        if(!cmp_write_str(&cmp, reason, (uint32_t)strlen(reason))) return;
        break;
    }
    default:
        return;
    }

    cfc_send_response_frame(cfc, CFC_OP_NFC_DIAG, txn, payload, wb.pos);
}

/*
 * Drain worker_out and broadcast each result (spec §5.3). MAIN thread only —
 * the worker never calls rpc_system_app_exchange_data (Q3). Broadcast txns get
 * the high bit SET (M3 namespace partition) so they can never collide with a
 * host-allocated request txn on the host side.
 *
 * Cook 3: the wire is now strictly safe — cfc_send_nfc_event sends under
 * tx_mutex, held first-to-last fragment, so a broadcast cannot interleave with
 * an RPC response emitted concurrently from the RPC-callback thread.
 *
 * On the FIRST tap after each subscribe we fire notification.success() (gate f):
 * the device beeps + the screen wakes, so a real tap is visible in a classroom.
 */
static void cfc_drain_worker_results(CfcContext* cfc) {
    CfcWorkerResult result;
    while(furi_message_queue_get(cfc->worker.worker_out, &result, 0) == FuriStatusOk) {
        uint32_t txn = CFC_BROADCAST_TXN_BIT | (cfc->broadcast_txn_counter++ & 0x7FFFFFFFu);
        // PHASE4-UI-HOOK: per-event UI reaction fires here
        cfc_send_nfc_event(cfc, txn, &result);

        if(cfc->first_tap_pending) {
            cfc->first_tap_pending = false;
            if(cfc->notifications) {
                notification_message(cfc->notifications, &sequence_success);
            }
        }
    }
}

/*
 * Cook 3.2 — drain worker_out_diag and broadcast each diagnostic on
 * CFC_OP_NFC_DIAG. MAIN thread only (the worker never writes the wire). Shares
 * the broadcast txn namespace + counter with cfc_drain_worker_results (both run
 * on the main thread, serialized by the main loop), so every diag txn has the M3
 * high bit SET — required for the host reader to route it to a subscription
 * buffer (a broadcast on a high-bit-CLEAR txn is dropped as an M3 violation).
 * Drained BEFORE the real results each tick so a detect_cb tends to surface a
 * moment ahead of its event; the two streams are separate host buffers anyway.
 */
static void cfc_drain_worker_diag(CfcContext* cfc) {
    CfcWorkerDiag d;
    while(furi_message_queue_get(cfc->worker.worker_out_diag, &d, 0) == FuriStatusOk) {
        uint32_t txn = CFC_BROADCAST_TXN_BIT | (cfc->broadcast_txn_counter++ & 0x7FFFFFFFu);
        cfc_send_nfc_diag(cfc, txn, &d);
    }
}

/*
 * 5-minute idle failsafe (spec §5.5 / Q6). If a subscription has been armed for
 * >5 min with no host activity, disarm the worker and clear the subscription so
 * a client that walked away stops the (mock) NFC work. MAIN thread only.
 */
static void cfc_check_idle_timeout(CfcContext* cfc) {
    if(!cfc->nfc_subscribed) return;
    uint32_t now = furi_get_tick();
    if((now - cfc->worker_arm_ms) > furi_ms_to_ticks(CFC_WORKER_IDLE_TIMEOUT_MS)) {
        FURI_LOG_I(TAG, "NFC idle >5min — auto-disarm failsafe");
        CfcWorkerEvent ev = {.type = CfcWorkerEventTypeNfcDisarm};
        furi_message_queue_put(cfc->worker.worker_in, &ev, 100);
        cfc->nfc_subscribed = false;
    }
}

/* ------- Phase 3 Cook 1: Sub-GHz decoded-stream RX worker (§5, §7, P0-P6) ------- */

/*
 * Receiver rx callback — fires SYNCHRONOUSLY on the SubGhz worker thread when a
 * protocol fully decodes (receiver.c). decoder_base is valid ONLY inside this
 * call: copy by value, NEVER retain the pointer (same UAF rule as the NFC UID).
 *
 * Extraction is a DIRECT-FIELD read (P0): gate on the protocol NAME first
 * (Princeton allowlist), and only THEN cast to the fixed-code prefix to read the
 * embedded generic block. Casting before the gate would read `generic` at a
 * struct offset that differs per protocol — the exact reason the allowlist
 * exists. NO serialize, NO FlipperFormat, NO preset. The callback does the
 * minimum and queues primitives; the MAIN thread builds msgpack + broadcasts (P1).
 */
static void cfc_subghz_rx_cb(
    SubGhzReceiver* receiver,
    SubGhzProtocolDecoderBase* decoder_base,
    void* context) {
    UNUSED(receiver);
    CfcSubghzWorker* w = (CfcSubghzWorker*)context;
    if(!decoder_base || !decoder_base->protocol || !decoder_base->protocol->name) return;

    const char* name = decoder_base->protocol->name; /* universal (all protocols) */
    bool is_princeton = (strcmp(name, CFC_SUBGHZ_PRINCETON_NAME) == 0);

    uint32_t bits = 0;
    uint64_t key = 0;
    if(is_princeton) {
        /* P0: allowlist passed -> safe to read the embedded generic directly. */
        const CfcSubghzDecoderHead* head = (const CfcSubghzDecoderHead*)decoder_base;
        key = head->generic.data;
        bits = (uint32_t)head->generic.data_count_bit;
    }

    /* G5 frame validation: a plausible fixed-code key, before anything is queued. */
    bool accepted =
        is_princeton && key != 0 && bits >= CFC_SUBGHZ_MIN_BITS && bits <= CFC_SUBGHZ_MAX_BITS;

    /* 0x5F diag seam — emit on EVERY decode, BEFORE the gate, best-effort. Lets a
     * silent live-fire self-triage in one run. bits is 0 for non-allowlisted
     * (we never cast a foreign struct prefix). */
    CfcSubghzDiag d = {0};
    strncpy(d.protocol, name, sizeof(d.protocol) - 1);
    d.bits = bits;
    d.accepted = accepted;
    furi_message_queue_put(w->diag, &d, 0); /* drop silently on full */

    if(!accepted) return;

    /* P1: copy primitives only — no msgpack here. */
    CfcSubghzResult r = {0};
    strncpy(r.protocol, name, sizeof(r.protocol) - 1);
    r.bits = bits;
    r.key = key;
    r.frequency = CFC_SUBGHZ_FREQUENCY;
    r.timestamp_ms = furi_get_tick(); /* ticks == ms on Momentum (configTICK_RATE_HZ=1000), P6 */

    /* G1: NON-BLOCKING put; drop + count on a full queue. NEVER FuriWaitForever —
     * a full queue + worker_stop's thread-join would hard-deadlock -> reboot. */
    if(furi_message_queue_put(w->events, &r, 0) != FuriStatusOk) {
        w->drops++;
    }
}

/*
 * App-start (HEAVY, one-time): alloc env + receiver + worker + queues, wire the
 * decode pipeline, devices_init ONCE (G2) and resolve the CC1101 handle. NO HAL
 * claim — begin()/the radio is deferred to arm so the radio is released whenever
 * no one is subscribed. Mirrors subghz_txrx_alloc's ordering. Main thread only.
 */
static void cfc_subghz_app_start(CfcSubghzWorker* w) {
    w->state = CfcSubghzStateIdle;
    w->drops = 0;

    w->environment = subghz_environment_alloc();
    /* Fixed-code only: set the registry, NO keystore load (P0/§5.1). */
    subghz_environment_set_protocol_registry(w->environment, (void*)&subghz_protocol_registry);

    w->receiver = subghz_receiver_alloc_init(w->environment);
    subghz_receiver_set_filter(w->receiver, SubGhzProtocolFlag_Decodable);
    subghz_receiver_set_rx_callback(w->receiver, cfc_subghz_rx_cb, w);

    w->worker = subghz_worker_alloc();
    subghz_worker_set_overrun_callback(w->worker, (SubGhzWorkerOverrunCallback)subghz_receiver_reset);
    subghz_worker_set_pair_callback(w->worker, (SubGhzWorkerPairCallback)subghz_receiver_decode);
    subghz_worker_set_context(w->worker, w->receiver);

    w->events = furi_message_queue_alloc(CFC_SUBGHZ_EVENT_QUEUE_DEPTH, sizeof(CfcSubghzResult));
    w->diag = furi_message_queue_alloc(CFC_SUBGHZ_DIAG_QUEUE_DEPTH, sizeof(CfcSubghzDiag));

    /* G2: devices_init ONCE. Resolve the internal CC1101 now; begin() (the actual
     * HAL/SPI claim) is paired with arm/disarm so it never latches when idle. */
    subghz_devices_init();
    w->devices_inited = true;
    w->device = subghz_devices_get_by_name(SUBGHZ_DEVICE_CC1101_INT_NAME);
    if(!w->device) FURI_LOG_E(TAG, "subghz: CC1101 internal device not found");
}

/*
 * Arm (LIGHT subscribe, §7 + P2). Claims the radio and starts the decode chain.
 * begin()<->end() is paired with arm<->disarm (NOT app-start/exit) so a second
 * subscribe can never double-begin (the spec's §7 placement of begin in Subscribe
 * with end only in App-exit would double-claim on re-subscribe — corrected here
 * to the mirror-canonical pairing, subghz_txrx radio_device_set/power_off).
 *
 * The setup sequence is mirror-verified (weather_station / subghz_txrx); the
 * spec's §5.1 omitted subghz_devices_start_async_rx (THE capture link) and named
 * a non-existent subghz_worker_set_context_to_pair / subghz_devices_set_idle —
 * all corrected from source. Every failure after charge-suppress-enter unwinds
 * through `fail:` so the charge-suppress can never latch (G4). Returns true iff
 * fully armed (state == RUNNING). Main thread; holds subghz_lock at the call site.
 */
static int cfc_subghz_arm(CfcSubghzWorker* w) {
    if(!w->device) {
        FURI_LOG_E(TAG, "subghz arm: no device");
        return 1;
    }
    if(!subghz_devices_is_frequency_valid(w->device, CFC_SUBGHZ_FREQUENCY)) {
        FURI_LOG_E(TAG, "subghz arm: 433.92 invalid");
        return 2;
    }

    w->state = CfcSubghzStateStarting;
    w->drops = 0;                       /* G6: reset per-subscribe, never realloc */
    subghz_receiver_reset(w->receiver); /* clear any stale partial decode */

    /* ROOT-CAUSE FIX (live-fire): the INTERNAL CC1101 has interconnect->begin == NULL,
     * so subghz_devices_begin() returns false BY DESIGN (begin is the power-on
     * handshake for EXTERNAL radios only: extended_range / amp_and_leds / region
     * bypass). The internal radio needs no begin — its bring-up is the
     * reset/load_preset/set_frequency/set_rx sequence below, and its teardown is
     * subghz_devices_end (furi_hal_subghz_shutdown). So we CALL begin for external-
     * device forward-compat but DO NOT gate arm on its return. All calls after this
     * point are void (no failure signal), so there is no early-return path and thus
     * no in-arm charge-suppress unwind needed (G4); disarm pairs the exit (G7). */
    subghz_devices_begin(w->device);

    subghz_devices_reset(w->device);
    subghz_devices_idle(w->device);
    subghz_devices_load_preset(w->device, FuriHalSubGhzPresetOok650Async, NULL);
    subghz_devices_set_frequency(w->device, CFC_SUBGHZ_FREQUENCY);
    subghz_devices_flush_rx(w->device);

    furi_hal_power_suppress_charge_enter(); /* paired with disarm's exit (G7) */

    subghz_devices_set_rx(w->device);
    /* THE capture link (mirror-confirmed; absent from the spec's §5.1): the device
     * pushes captured level/duration pairs into the worker via the worker's own
     * callback, and the worker thread feeds them to the receiver's pair callback
     * (subghz_receiver_decode). Without this the worker gets zero data and nothing
     * ever decodes. */
    subghz_devices_start_async_rx(w->device, subghz_worker_rx_callback, w->worker);

    subghz_worker_start(w->worker);

    w->state = CfcSubghzStateRunning;
    return 0;
}

/*
 * Disarm (LIGHT unsubscribe). State-guarded (G7): no-op unless RUNNING, so an
 * exit-after-unsubscribe or a double-disarm can never double-exit charge-suppress
 * or stop an unstarted worker. worker_stop joins the decode thread FIRST (no rx
 * callback fires after it returns), then the device stops pushing durations
 * (mirror order, subghz_txrx_rx_end). end() releases the HAL/SPI (G3). Main thread;
 * holds subghz_lock at the call site (except the post-RPC-detach app-exit path).
 */
static void cfc_subghz_disarm(CfcSubghzWorker* w) {
    if(w->state != CfcSubghzStateRunning) return; /* G7 */
    w->state = CfcSubghzStateStopping;

    if(subghz_worker_is_running(w->worker)) subghz_worker_stop(w->worker);
    subghz_devices_stop_async_rx(w->device);
    subghz_devices_idle(w->device);
    furi_hal_power_suppress_charge_exit(); /* G7: paired with arm's enter */
    subghz_devices_sleep(w->device);
    subghz_devices_end(w->device); /* release HAL/SPI (paired with begin) */

    w->state = CfcSubghzStateIdle;
}

/*
 * App-exit teardown. Guarded disarm covers exit-while-subscribed (G3): the main
 * loop has ended and RPC is detached, so this is the sole teardown — no race with
 * unsubscribe. receiver_free BEFORE env_free (spec §5.3.2, STANDS post-P0): each
 * decoder slot was alloc'd against the environment, so freeing env first could
 * dangle a decoder that retained it. Main thread only.
 */
static void cfc_subghz_app_exit(CfcSubghzWorker* w) {
    cfc_subghz_disarm(w); /* no-op unless RUNNING */

    if(w->devices_inited) {
        subghz_devices_deinit();
        w->devices_inited = false;
    }
    if(w->worker) {
        subghz_worker_free(w->worker);
        w->worker = NULL;
    }
    if(w->receiver) { /* BEFORE env */
        subghz_receiver_free(w->receiver);
        w->receiver = NULL;
    }
    if(w->environment) {
        subghz_environment_free(w->environment);
        w->environment = NULL;
    }
    if(w->events) {
        furi_message_queue_free(w->events);
        w->events = NULL;
    }
    if(w->diag) {
        furi_message_queue_free(w->diag);
        w->diag = NULL;
    }
}

/*
 * Encode + send one SUBGHZ_EVENT (0x52) broadcast. MAIN thread only, through
 * cfc_send_response_frame so it rides the same tx_mutex single-writer wire
 * discipline as every other message. Payload map (spec §4 / P0 / P4):
 *   protocol(str) bits(u32) key(u64) frequency(u32) timestamp_ms(u32) drops(u32)
 * key is a uint64 — high-bit keys (> INT64_MAX) are valid and must round-trip.
 */
static void cfc_send_subghz_event(
    CfcContext* cfc,
    uint32_t txn,
    const CfcSubghzResult* r,
    uint32_t drops) {
    uint8_t payload[128];
    CfcWriteBuf wb = {.data = payload, .pos = 0, .cap = sizeof(payload)};
    cmp_ctx_t cmp;
    cmp_init(&cmp, &wb, NULL, NULL, cfc_cmp_writer);

    uint32_t name_len = (uint32_t)strlen(r->protocol); /* always NUL-terminated (zero-init) */

    if(!cmp_write_map(&cmp, 6)) return;
    if(!cmp_write_str(&cmp, "protocol", 8)) return;
    if(!cmp_write_str(&cmp, r->protocol, name_len)) return;
    if(!cmp_write_str(&cmp, "bits", 4)) return;
    if(!cmp_write_uinteger(&cmp, r->bits)) return;
    if(!cmp_write_str(&cmp, "key", 3)) return;
    if(!cmp_write_uinteger(&cmp, r->key)) return; /* uint64, P6 */
    if(!cmp_write_str(&cmp, "frequency", 9)) return;
    if(!cmp_write_uinteger(&cmp, r->frequency)) return;
    if(!cmp_write_str(&cmp, "timestamp_ms", 12)) return;
    if(!cmp_write_uinteger(&cmp, r->timestamp_ms)) return;
    if(!cmp_write_str(&cmp, "drops", 5)) return;
    if(!cmp_write_uinteger(&cmp, drops)) return;

    cfc_send_response_frame(cfc, CFC_OP_SUBGHZ_EVENT, txn, payload, wb.pos);
}

/*
 * Encode + send one SUBGHZ_DIAG (0x5F) broadcast. MAIN thread only, same wire
 * discipline. Payload: {event:"decode", protocol:<name>, bits:N, accepted:bool}.
 */
static void cfc_send_subghz_diag(CfcContext* cfc, uint32_t txn, const CfcSubghzDiag* d) {
    uint8_t payload[96];
    CfcWriteBuf wb = {.data = payload, .pos = 0, .cap = sizeof(payload)};
    cmp_ctx_t cmp;
    cmp_init(&cmp, &wb, NULL, NULL, cfc_cmp_writer);

    uint32_t name_len = (uint32_t)strlen(d->protocol);
    if(!cmp_write_map(&cmp, 4)) return;
    if(!cmp_write_str(&cmp, "event", 5)) return;
    if(!cmp_write_str(&cmp, "decode", 6)) return;
    if(!cmp_write_str(&cmp, "protocol", 8)) return;
    if(!cmp_write_str(&cmp, d->protocol, name_len)) return;
    if(!cmp_write_str(&cmp, "bits", 4)) return;
    if(!cmp_write_uinteger(&cmp, d->bits)) return;
    if(!cmp_write_str(&cmp, "accepted", 8)) return;
    if(!cmp_write_bool(&cmp, d->accepted)) return;

    cfc_send_response_frame(cfc, CFC_OP_SUBGHZ_DIAG, txn, payload, wb.pos);
}

/*
 * Drain the rx-callback -> main result queue and broadcast each on 0x52. MAIN
 * thread only (the worker never touches the wire). Broadcast txns get the M3
 * high bit SET so the host reader routes them to the 0x52 subscription buffer.
 * Each event carries the running `drops` count so the host distinguishes "no
 * signal" from "dropped everything" (P4).
 */
static void cfc_drain_subghz_events(CfcContext* cfc) {
    CfcSubghzResult r;
    while(furi_message_queue_get(cfc->subghz.events, &r, 0) == FuriStatusOk) {
        uint32_t txn = CFC_BROADCAST_TXN_BIT | (cfc->broadcast_txn_counter++ & 0x7FFFFFFFu);
        cfc_send_subghz_event(cfc, txn, &r, cfc->subghz.drops);
    }
}

/* Drain the rx-callback -> main diag queue and broadcast each on 0x5F. MAIN
 * thread only; same M3 high-bit txn namespace + shared counter. */
static void cfc_drain_subghz_diag(CfcContext* cfc) {
    CfcSubghzDiag d;
    while(furi_message_queue_get(cfc->subghz.diag, &d, 0) == FuriStatusOk) {
        uint32_t txn = CFC_BROADCAST_TXN_BIT | (cfc->broadcast_txn_counter++ & 0x7FFFFFFFu);
        cfc_send_subghz_diag(cfc, txn, &d);
    }
}

/*
 * 5-minute idle failsafe (parity with the NFC §5.5 path). If a subscription has
 * been armed >5 min with no host churn, disarm so a client that walked away stops
 * holding the radio + charge-suppress (battery won't charge while suppressed).
 * MAIN thread; the subghz_lock closes the one real race — a concurrent
 * unsubscribe on the RPC-callback thread — so disarm runs exactly once.
 */
static void cfc_check_subghz_idle_timeout(CfcContext* cfc) {
    if(!cfc->subghz_subscribed) return;
    if((furi_get_tick() - cfc->subghz_arm_ms) <= furi_ms_to_ticks(CFC_SUBGHZ_IDLE_TIMEOUT_MS))
        return;

    furi_mutex_acquire(cfc->subghz_lock, FuriWaitForever);
    if(cfc->subghz_subscribed &&
       (furi_get_tick() - cfc->subghz_arm_ms) > furi_ms_to_ticks(CFC_SUBGHZ_IDLE_TIMEOUT_MS)) {
        FURI_LOG_I(TAG, "subghz idle >5min — auto-disarm failsafe");
        cfc_subghz_disarm(&cfc->subghz);
        cfc->subghz_subscribed = false;
    }
    furi_mutex_release(cfc->subghz_lock);
}

/* ------- handlers ------- */

static void cfc_handle_ping(CfcContext* cfc, uint32_t txn, const uint8_t* msgpack, size_t mp_len) {
    /* Parse incoming map, find key "echo", snapshot its value bytes, re-emit. */
    CfcReadBuf rb = {.data = msgpack, .pos = 0, .cap = mp_len};
    cmp_ctx_t cmp;
    cmp_init(&cmp, &rb, cfc_cmp_reader, cfc_cmp_skipper, NULL);

    uint32_t map_size = 0;
    if(!cmp_read_map(&cmp, &map_size)) {
        cfc_send_error(cfc, txn, CFC_ERR_BAD_PAYLOAD, "expected map");
        return;
    }

    size_t echo_start = 0;
    size_t echo_end = 0;
    bool found_echo = false;
    for(uint32_t i = 0; i < map_size; i++) {
        /* read key as string */
        cmp_object_t key_obj;
        if(!cmp_read_object(&cmp, &key_obj)) {
            cfc_send_error(cfc, txn, CFC_ERR_BAD_PAYLOAD, "bad key");
            return;
        }
        bool key_is_echo = false;
        if(cmp_object_is_str(&key_obj)) {
            uint32_t key_size = key_obj.as.str_size;
            if(key_size == 4 && rb.pos + 4 <= rb.cap) {
                if(memcmp(rb.data + rb.pos, "echo", 4) == 0) {
                    key_is_echo = true;
                }
            }
            /* advance past key string bytes */
            if(rb.pos + key_size > rb.cap) {
                cfc_send_error(cfc, txn, CFC_ERR_BAD_PAYLOAD, "bad key length");
                return;
            }
            rb.pos += key_size;
        } else {
            /* non-string key: skip it */
        }
        /* snapshot value byte range and skip */
        size_t val_start = rb.pos;
        if(!cmp_skip_object_no_limit(&cmp)) {
            cfc_send_error(cfc, txn, CFC_ERR_BAD_PAYLOAD, "bad value");
            return;
        }
        size_t val_end = rb.pos;
        if(key_is_echo && !found_echo) {
            echo_start = val_start;
            echo_end = val_end;
            found_echo = true;
        }
    }

    /* Build response: {status: "ok", echo: <verbatim>} (or {status: "ok"} if no echo key).
     * v8.3: allocate output buffer on heap, sized for inbound echo + msgpack map overhead.
     * Map overhead: fixmap(1B) + "status"(7B) + "ok"(3B) + "echo"(5B) + str-prefix(≤5B) = ~21B.
     * Pad to 64B for safety. */
    size_t echo_len = found_echo ? (echo_end - echo_start) : 0;
    size_t out_capacity = echo_len + 64;
    if(out_capacity > CFC_MAX_TRANSACTION) {
        cfc_send_error(cfc, txn, CFC_ERR_BAD_PAYLOAD, "ping echo exceeds CFC_MAX_TRANSACTION");
        return;
    }

    uint8_t* response = malloc(out_capacity);
    if(!response) {
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping malloc failed");
        return;
    }

    CfcWriteBuf wb = {.data = response, .pos = 0, .cap = out_capacity};
    cmp_ctx_t out;
    cmp_init(&out, &wb, NULL, NULL, cfc_cmp_writer);

    uint32_t out_size = found_echo ? 2 : 1;
    if(!cmp_write_map(&out, out_size)) {
        free(response);
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc map");
        return;
    }
    if(!cmp_write_str(&out, "status", 6) || !cmp_write_str(&out, "ok", 2)) {
        free(response);
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc status");
        return;
    }
    if(found_echo) {
        if(!cmp_write_str(&out, "echo", 4)) {
            free(response);
            cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc echo key");
            return;
        }
        // Direct memcpy of the verbatim msgpack-encoded echo value.
        // Buffer already sized to fit; no overflow check needed.
        size_t verbatim_len = echo_end - echo_start;
        memcpy(wb.data + wb.pos, msgpack + echo_start, verbatim_len);
        wb.pos += verbatim_len;
    }

    cfc_send_response_multi(cfc, CFC_OP_PING, txn, response, wb.pos);
    free(response);
}

static void cfc_handle_meta_capabilities(CfcContext* cfc, uint32_t txn) {
    uint8_t response[64];
    CfcWriteBuf wb = {.data = response, .pos = 0, .cap = sizeof(response)};
    cmp_ctx_t out;
    cmp_init(&out, &wb, NULL, NULL, cfc_cmp_writer);

    if(!cmp_write_map(&out, 2)) return;
    if(!cmp_write_str(&out, "status", 6)) return;
    if(!cmp_write_str(&out, "ok", 2)) return;
    if(!cmp_write_str(&out, "opcodes", 7)) return;
    if(!cmp_write_array(&out, 5)) return;
    cmp_write_integer(&out, CFC_OP_PING);
    cmp_write_integer(&out, CFC_OP_META_CAPABILITIES);
    cmp_write_integer(&out, CFC_OP_META_VERSION);
    cmp_write_integer(&out, CFC_OP_RESET);
    cmp_write_integer(&out, CFC_OP_ERROR);
    cfc_send_response_frame(cfc, CFC_OP_META_CAPABILITIES, txn, response, wb.pos);
}

static void cfc_handle_meta_version(CfcContext* cfc, uint32_t txn) {
    uint8_t response[128];
    CfcWriteBuf wb = {.data = response, .pos = 0, .cap = sizeof(response)};
    cmp_ctx_t out;
    cmp_init(&out, &wb, NULL, NULL, cfc_cmp_writer);

    if(!cmp_write_map(&out, 5)) return;
    if(!cmp_write_str(&out, "status", 6)) return;
    if(!cmp_write_str(&out, "ok", 2)) return;
    if(!cmp_write_str(&out, "cfc_version", 11)) return;
    if(!cmp_write_str(&out, "0.1", 3)) return;
    if(!cmp_write_str(&out, "firmware", 8)) return;
    if(!cmp_write_str(&out, "mntm-dev", 8)) return;
    if(!cmp_write_str(&out, "schema_major", 12)) return;
    if(!cmp_write_integer(&out, 1)) return;
    if(!cmp_write_str(&out, "schema_minor", 12)) return;
    if(!cmp_write_integer(&out, 0)) return;
    cfc_send_response_frame(cfc, CFC_OP_META_VERSION, txn, response, wb.pos);
}

/* ------- dispatch ------- */

static void cfc_dispatch(CfcContext* cfc, uint8_t op_code, uint32_t txn, const uint8_t* mp, size_t mp_len) {
    switch(op_code) {
    case CFC_OP_PING:
        cfc_handle_ping(cfc, txn, mp, mp_len);
        break;
    case CFC_OP_META_CAPABILITIES:
        cfc_handle_meta_capabilities(cfc, txn);
        break;
    case CFC_OP_META_VERSION:
        cfc_handle_meta_version(cfc, txn);
        break;
    case CFC_OP_RESET:
        /* RESET in IDLE is a no-op confirmation; in ASSEMBLING the caller below clears the buffer. */
        cfc_send_status_ok(cfc, txn, CFC_OP_RESET);
        break;
    case CFC_OP_NFC_SUBSCRIBE_CAPTURE: {
        /* Q2 exclusive (spec §3): a second subscribe while armed is BUSY. */
        if(cfc->nfc_subscribed) {
            cfc_send_error(cfc, txn, CFC_ERR_SUB_BUSY, "already subscribed");
            break;
        }
        /* Q1 ack-timing race fix (spec §13.2): ack FIRST, yield ~20ms so the ack
         * is on the wire, THEN arm the worker — so no broadcast can reach the
         * host before the subscribe ack does. */
        cfc_send_status_ok(cfc, txn, CFC_OP_NFC_SUBSCRIBE_CAPTURE);
        furi_delay_ms(20);
        CfcWorkerEvent arm = {.type = CfcWorkerEventTypeNfcArm};
        if(furi_message_queue_put(cfc->worker.worker_in, &arm, 100) == FuriStatusOk) {
            cfc->nfc_subscribed = true;
            cfc->worker_arm_ms = furi_get_tick();
            cfc->first_tap_pending = true; /* beep on the first real tap (gate f) */
        } else {
            /* Ack already sent OK but the worker couldn't be signalled. Leave
             * nfc_subscribed false so the host's next subscribe retries. */
            FURI_LOG_E(TAG, "subscribe: worker_in full, arm dropped");
        }
        break;
    }
    case CFC_OP_NFC_UNSUBSCRIBE: {
        if(!cfc->nfc_subscribed) {
            cfc_send_error(cfc, txn, CFC_ERR_NOT_SUBSCRIBED, "not subscribed");
            break;
        }
        CfcWorkerEvent disarm = {.type = CfcWorkerEventTypeNfcDisarm};
        furi_message_queue_put(cfc->worker.worker_in, &disarm, 100);
        cfc->nfc_subscribed = false;
        cfc_send_status_ok(cfc, txn, CFC_OP_NFC_UNSUBSCRIBE);
        break;
    }
    case CFC_OP_SUBGHZ_SUBSCRIBE_CAPTURE: {
        furi_mutex_acquire(cfc->subghz_lock, FuriWaitForever);
        if(cfc->subghz_subscribed) {
            furi_mutex_release(cfc->subghz_lock);
            cfc_send_error(cfc, txn, CFC_ERR_SUB_BUSY, "already subscribed");
            break;
        }
        /* Sub-GHz arm is SYNCHRONOUS hardware bring-up (unlike NFC's async worker
         * arm), so we report accurate status: arm first, ack on success / error on
         * failure. No Q1 ack-race — the host registers its 0x52 buffer BEFORE
         * sending this arm, and 0x52 broadcasts are deferred to the main-loop
         * drain, so an event can never beat the ack onto the wire. */
        int arm_rc = cfc_subghz_arm(&cfc->subghz);
        if(arm_rc == 0) {
            cfc->subghz_subscribed = true;
            cfc->subghz_arm_ms = furi_get_tick();
        }
        furi_mutex_release(cfc->subghz_lock);
        if(arm_rc == 0) {
            cfc_send_status_ok(cfc, txn, CFC_OP_SUBGHZ_SUBSCRIBE_CAPTURE);
        } else {
            const char* arm_msg = (arm_rc == 1) ? "arm fail: no CC1101 device" :
                                  (arm_rc == 2) ? "arm fail: 433.92 freq invalid" :
                                  (arm_rc == 3) ? "arm fail: devices_begin (HAL claim)" :
                                                  "arm fail: unknown";
            cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, arm_msg);
        }
        break;
    }
    case CFC_OP_SUBGHZ_UNSUBSCRIBE: {
        furi_mutex_acquire(cfc->subghz_lock, FuriWaitForever);
        if(!cfc->subghz_subscribed) {
            furi_mutex_release(cfc->subghz_lock);
            cfc_send_error(cfc, txn, CFC_ERR_NOT_SUBSCRIBED, "not subscribed");
            break;
        }
        cfc_subghz_disarm(&cfc->subghz); /* synchronous: joins the decode thread */
        cfc->subghz_subscribed = false;
        furi_mutex_release(cfc->subghz_lock);
        cfc_send_status_ok(cfc, txn, CFC_OP_SUBGHZ_UNSUBSCRIBE);
        break;
    }
    default:
        cfc_send_error(cfc, txn, CFC_ERR_UNKNOWN_OPCODE, "unknown opcode");
        break;
    }
}

/* ------- assemble timer ------- */

static void cfc_on_assemble_timeout(void* context) {
    CfcContext* cfc = (CfcContext*)context;
    furi_mutex_acquire(cfc->mutex, FuriWaitForever);
    if(cfc->state == CfcStateAssembling) {
        FURI_LOG_I(TAG, "assemble timeout for txn=%lu; dropping", (unsigned long)cfc->transaction_id);
        cfc_assemble_reset(cfc);
    }
    furi_mutex_release(cfc->mutex);
}

/* ------- RPC callback ------- */

static void cfc_rpc_callback(const RpcAppSystemEvent* event, void* context) {
    CfcContext* cfc = (CfcContext*)context;

    if(event->type == RpcAppEventTypeSessionClose) {
        FURI_LOG_I(TAG, "session close");
        uint32_t exit_signal = 1;
        furi_message_queue_put(cfc->exit_queue, &exit_signal, 0);
        return;
    }

    if(event->type == RpcAppEventTypeAppExit) {
        FURI_LOG_I(TAG, "app exit request");
        rpc_system_app_confirm(cfc->rpc_app, true);
        uint32_t exit_signal = 1;
        furi_message_queue_put(cfc->exit_queue, &exit_signal, 0);
        return;
    }

    if(event->type != RpcAppEventTypeDataExchange) {
        return;
    }

    /* Confirm BEFORE doing application work (spec §6.3 step 3) */
    rpc_system_app_confirm(cfc->rpc_app, true);

    const uint8_t* in = event->data.bytes.ptr;
    size_t in_len = event->data.bytes.size;

    if(in_len < CFC_HEADER_SIZE) {
        cfc_send_error(cfc, 0, CFC_ERR_BAD_FRAME, "frame < 16");
        return;
    }

    CfcHeader hdr;
    cfc_parse_header(in, in_len, &hdr);

    /* Magic + version validation */
    if(hdr.magic != CFC_MAGIC || hdr.version != CFC_VERSION) {
        cfc_send_error(cfc, hdr.transaction_id, CFC_ERR_BAD_FRAME, "magic/version");
        return;
    }

    /* Payload size guard (§4.3) */
    if(hdr.payload_length > CFC_MAX_TRANSACTION) {
        cfc_send_error(cfc, hdr.transaction_id, CFC_ERR_PAYLOAD_TOO_LARGE, "payload > 8192");
        return;
    }

    /* Fragment-shape validation */
    if(hdr.fragment_total < 1 || hdr.fragment_index >= hdr.fragment_total) {
        cfc_send_error(cfc, hdr.transaction_id, CFC_ERR_BAD_FRAGMENT, "fragment shape");
        return;
    }

    size_t fragment_data_len = in_len - CFC_HEADER_SIZE;

    furi_mutex_acquire(cfc->mutex, FuriWaitForever);

    /* IDLE: first-fragment-only */
    if(cfc->state == CfcStateIdle) {
        if(hdr.fragment_index != 0) {
            furi_mutex_release(cfc->mutex);
            cfc_send_error(cfc, hdr.transaction_id, CFC_ERR_BAD_FRAGMENT, "orphan fragment");
            return;
        }

        /* Per-frame size validation (§4.3 security check) */
        if(fragment_data_len > hdr.payload_length) {
            furi_mutex_release(cfc->mutex);
            cfc_send_error(cfc, hdr.transaction_id, CFC_ERR_BAD_FRAGMENT, "frame > payload_length");
            return;
        }

        if(hdr.fragment_total == 1) {
            /* Single-fragment transaction — dispatch immediately */
            if(fragment_data_len != hdr.payload_length) {
                furi_mutex_release(cfc->mutex);
                cfc_send_error(cfc, hdr.transaction_id, CFC_ERR_BAD_FRAGMENT, "len mismatch");
                return;
            }
            /* RESET special-case: works in IDLE too (§6.2 RESET acceptance) */
            uint32_t txn = hdr.transaction_id;
            uint8_t op = hdr.op_code;
            uint8_t* tmp = NULL;
            const uint8_t* mp_ptr = NULL;
            size_t mp_len = fragment_data_len;
            if(mp_len > 0) {
                tmp = (uint8_t*)malloc(mp_len);
                if(!tmp) {
                    furi_mutex_release(cfc->mutex);
                    cfc_send_error(cfc, txn, CFC_ERR_OUT_OF_MEMORY, "malloc");
                    return;
                }
                memcpy(tmp, in + CFC_HEADER_SIZE, mp_len);
                mp_ptr = tmp;
            }
            furi_mutex_release(cfc->mutex);
            cfc_dispatch(cfc, op, txn, mp_ptr, mp_len);
            if(tmp) free(tmp);
            return;
        }

        /* Multi-fragment: allocate assemble buffer */
        cfc->assemble_buffer = (uint8_t*)malloc(hdr.payload_length);
        if(!cfc->assemble_buffer) {
            furi_mutex_release(cfc->mutex);
            cfc_send_error(cfc, hdr.transaction_id, CFC_ERR_OUT_OF_MEMORY, "malloc");
            return;
        }
        cfc->state = CfcStateAssembling;
        cfc->op_code = hdr.op_code;
        cfc->transaction_id = hdr.transaction_id;
        cfc->payload_length = hdr.payload_length;
        cfc->fragment_total = hdr.fragment_total;
        cfc->fragments_received = 1;
        cfc->assemble_pos = 0;

        memcpy(cfc->assemble_buffer + cfc->assemble_pos, in + CFC_HEADER_SIZE, fragment_data_len);
        cfc->assemble_pos += fragment_data_len;

        furi_timer_start(cfc->assemble_timer, furi_ms_to_ticks(CFC_ASSEMBLING_TIMEOUT_MS));
        furi_mutex_release(cfc->mutex);
        return;
    }

    /* ASSEMBLING branch */
    /* RESET is special: even with a different transaction_id, RESET clears
     * ASSEMBLING state and returns IDLE. Single-fragment only. (§6.2 RESET acceptance) */
    if(hdr.op_code == CFC_OP_RESET && hdr.fragment_total == 1 && hdr.fragment_index == 0) {
        uint32_t reset_txn = hdr.transaction_id;
        cfc_assemble_reset(cfc);
        furi_mutex_release(cfc->mutex);
        cfc_send_status_ok(cfc, reset_txn, CFC_OP_RESET);
        return;
    }

    if(hdr.transaction_id != cfc->transaction_id) {
        /* Different txn while assembling → BUSY, but DO NOT corrupt in-flight buffer */
        uint32_t other_txn = hdr.transaction_id;
        furi_mutex_release(cfc->mutex);
        cfc_send_error(cfc, other_txn, CFC_ERR_BUSY, "busy");
        return;
    }

    /* Same txn — validate consistency */
    if(hdr.payload_length != cfc->payload_length || hdr.fragment_total != cfc->fragment_total) {
        uint32_t txn = cfc->transaction_id;
        cfc_assemble_reset(cfc);
        furi_mutex_release(cfc->mutex);
        cfc_send_error(cfc, txn, CFC_ERR_BAD_FRAGMENT, "payload_length/total inconsistent");
        return;
    }

    if(hdr.fragment_index != cfc->fragments_received) {
        uint32_t txn = cfc->transaction_id;
        cfc_assemble_reset(cfc);
        furi_mutex_release(cfc->mutex);
        cfc_send_error(cfc, txn, CFC_ERR_BAD_FRAGMENT, "fragment out of order");
        return;
    }

    /* Per-frame size validation */
    size_t remaining = cfc->payload_length - cfc->assemble_pos;
    if(fragment_data_len > remaining) {
        uint32_t txn = cfc->transaction_id;
        cfc_assemble_reset(cfc);
        furi_mutex_release(cfc->mutex);
        cfc_send_error(cfc, txn, CFC_ERR_BAD_FRAGMENT, "frame > remaining");
        return;
    }

    memcpy(cfc->assemble_buffer + cfc->assemble_pos, in + CFC_HEADER_SIZE, fragment_data_len);
    cfc->assemble_pos += fragment_data_len;
    cfc->fragments_received++;

    if(cfc->fragments_received == cfc->fragment_total) {
        /* Final fragment — dispatch */
        if(cfc->assemble_pos != cfc->payload_length) {
            uint32_t txn = cfc->transaction_id;
            cfc_assemble_reset(cfc);
            furi_mutex_release(cfc->mutex);
            cfc_send_error(cfc, txn, CFC_ERR_BAD_FRAGMENT, "total != payload_length");
            return;
        }
        uint32_t txn = cfc->transaction_id;
        uint8_t op = cfc->op_code;
        uint8_t* buf = cfc->assemble_buffer;
        size_t len = cfc->assemble_pos;
        /* Detach buffer so dispatch handlers can read it after we release the mutex */
        cfc->assemble_buffer = NULL;
        cfc->assemble_pos = 0;
        cfc->state = CfcStateIdle;
        cfc->op_code = 0;
        cfc->transaction_id = 0;
        cfc->payload_length = 0;
        cfc->fragment_total = 0;
        cfc->fragments_received = 0;
        furi_timer_stop(cfc->assemble_timer);
        furi_mutex_release(cfc->mutex);
        cfc_dispatch(cfc, op, txn, buf, len);
        free(buf);
        return;
    }

    /* Restart timeout, keep assembling */
    furi_timer_start(cfc->assemble_timer, furi_ms_to_ticks(CFC_ASSEMBLING_TIMEOUT_MS));
    furi_mutex_release(cfc->mutex);
}

/* ------- entry point ------- */

int32_t cfc_app_main(void* p) {
    /* p is a const char* args string. When launched via app_start("cfc","RPC"), firmware
     * rewrites it to "RPC %08lX" where the hex value is the pointer to the RpcAppSystem. */
    const char* args = (const char*)p;
    if(!args || strncmp(args, "RPC ", 4) != 0) {
        FURI_LOG_E(TAG, "must be launched in RPC mode (args='%s')", args ? args : "(null)");
        return -1;
    }

    uintptr_t rpc_app_ptr = 0;
    if(sscanf(args + 4, "%lx", (unsigned long*)&rpc_app_ptr) != 1 || rpc_app_ptr == 0) {
        FURI_LOG_E(TAG, "bad RPC args: '%s'", args);
        return -1;
    }

    CfcContext cfc = {0};
    cfc.rpc_app = (RpcAppSystem*)rpc_app_ptr;
    cfc.state = CfcStateIdle;
    cfc.mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    cfc.tx_mutex = furi_mutex_alloc(FuriMutexTypeNormal); /* Cook 3 single-writer wire */
    cfc.exit_queue = furi_message_queue_alloc(2, sizeof(uint32_t));
    cfc.assemble_timer = furi_timer_alloc(cfc_on_assemble_timeout, FuriTimerTypeOnce, &cfc);
    cfc.notifications = furi_record_open(RECORD_NOTIFICATION); /* gate f beep */

    /* Phase 3 Cook 2/3: start the worker thread BEFORE accepting RPC traffic so a
     * subscribe arriving immediately after send_started has a worker to arm. The
     * worker's NFC fields are zero-initialised by `= {0}` (NULL until Arm). */
    cfc.worker.worker_in = furi_message_queue_alloc(CFC_WORKER_IN_DEPTH, sizeof(CfcWorkerEvent));
    cfc.worker.worker_out =
        furi_message_queue_alloc(CFC_WORKER_OUT_DEPTH, sizeof(CfcWorkerResult));
    cfc.worker.worker_out_diag = /* Cook 3.2: worker -> main diagnostics */
        furi_message_queue_alloc(CFC_WORKER_DIAG_DEPTH, sizeof(CfcWorkerDiag));
    cfc.worker.thread =
        furi_thread_alloc_ex("CfcWorker", CFC_WORKER_STACK_SIZE, cfc_worker_thread, &cfc.worker);
    furi_thread_start(cfc.worker.thread);

    /* Phase 3 Cook 1 — Sub-GHz vertical: HEAVY one-time setup (env/receiver/
     * worker/queues/devices_init). No HAL claim until the first subscribe. The
     * subghz_lock guards the arm/disarm/idle critical sections. */
    cfc.subghz_lock = furi_mutex_alloc(FuriMutexTypeNormal);
    cfc_subghz_app_start(&cfc.subghz);

    rpc_system_app_set_callback(cfc.rpc_app, cfc_rpc_callback, &cfc);
    rpc_system_app_send_started(cfc.rpc_app);

    FURI_LOG_I(TAG, "CFC started (rpc_app=%p)", (void*)cfc.rpc_app);

    /* Main loop: wait for an exit signal, but wake every CFC_MAIN_POLL_MS to do
     * main-thread periodic work — drain the worker's results onto the wire
     * (§5.3) and run the 5-min idle failsafe (§5.5). ONLY this thread sends
     * broadcasts; the worker never touches the wire (Q3). */
    uint32_t signal = 0;
    while(true) {
        FuriStatus s = furi_message_queue_get(cfc.exit_queue, &signal, CFC_MAIN_POLL_MS);
        if(s == FuriStatusOk) {
            break; /* session close / app exit */
        }
        cfc_drain_worker_diag(&cfc); /* Cook 3.2: broadcast diagnostics (0x4F) */
        cfc_drain_worker_results(&cfc);
        cfc_check_idle_timeout(&cfc);
        /* Phase 3 Cook 1 — Sub-GHz: drain diag (0x5F) before events (0x52) so a
         * decode diagnostic tends to surface a tick ahead of its event. */
        cfc_drain_subghz_diag(&cfc);
        cfc_drain_subghz_events(&cfc);
        cfc_check_subghz_idle_timeout(&cfc);
    }

    FURI_LOG_I(TAG, "CFC exiting");

    rpc_system_app_set_callback(cfc.rpc_app, NULL, NULL);
    rpc_system_app_send_exited(cfc.rpc_app);

    /* Worker shutdown (spec §5.6): signal stop, join, then free thread + queues.
     * Stop implicitly disarms (the worker exits its loop). */
    {
        CfcWorkerEvent stop = {.type = CfcWorkerEventTypeStop};
        furi_message_queue_put(cfc.worker.worker_in, &stop, FuriWaitForever);
        furi_thread_join(cfc.worker.thread);
        furi_thread_free(cfc.worker.thread);
        furi_message_queue_free(cfc.worker.worker_in);
        furi_message_queue_free(cfc.worker.worker_out);
        furi_message_queue_free(cfc.worker.worker_out_diag); /* Cook 3.2 */
    }

    /* Phase 3 Cook 1 — Sub-GHz teardown: guarded disarm (covers exit-while-armed,
     * G3/G7) + devices_deinit + free env/receiver/worker/queues (receiver BEFORE
     * env, §5.3.2). RPC is already detached, so no unsubscribe can race this. */
    cfc_subghz_app_exit(&cfc.subghz);
    furi_mutex_free(cfc.subghz_lock);

    /* Worker is joined and the RPC callback detached, so no further sends can
     * occur — safe to drop the wire mutex and the notification record. */
    furi_record_close(RECORD_NOTIFICATION);
    cfc.notifications = NULL;

    furi_timer_stop(cfc.assemble_timer);
    furi_timer_free(cfc.assemble_timer);
    furi_message_queue_free(cfc.exit_queue);
    furi_mutex_free(cfc.mutex);
    furi_mutex_free(cfc.tx_mutex);
    if(cfc.assemble_buffer) free(cfc.assemble_buffer);

    return 0;
}
