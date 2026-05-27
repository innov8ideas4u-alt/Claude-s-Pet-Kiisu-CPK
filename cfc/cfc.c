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

#define CFC_ERR_BAD_FRAME         1
#define CFC_ERR_BAD_FRAGMENT      2
#define CFC_ERR_PAYLOAD_TOO_LARGE 3
#define CFC_ERR_OUT_OF_MEMORY     4
#define CFC_ERR_BUSY              5
#define CFC_ERR_BAD_PAYLOAD       6
#define CFC_ERR_UNKNOWN_OPCODE    7
#define CFC_ERR_INTERNAL          99

#define CFC_RESPONSE_SCRATCH      1024u

typedef enum {
    CfcStateIdle,
    CfcStateAssembling,
} CfcState;

typedef struct {
    RpcAppSystem* rpc_app;
    FuriMessageQueue* exit_queue;
    FuriMutex* mutex;
    FuriTimer* assemble_timer;

    CfcState state;
    uint8_t op_code;
    uint32_t transaction_id;
    uint32_t payload_length;
    uint16_t fragment_total;
    uint16_t fragments_received;
    uint8_t* assemble_buffer;
    size_t assemble_pos;
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
    rpc_system_app_exchange_data(cfc->rpc_app, buf, CFC_HEADER_SIZE + payload_len);
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

    /* Build response: {status: "ok", echo: <verbatim>} (or {status: "ok"} if no echo key) */
    uint8_t response[CFC_MAX_FRAGMENT_PAYLOAD];
    CfcWriteBuf wb = {.data = response, .pos = 0, .cap = sizeof(response)};
    cmp_ctx_t out;
    cmp_init(&out, &wb, NULL, NULL, cfc_cmp_writer);

    uint32_t out_size = found_echo ? 2 : 1;
    if(!cmp_write_map(&out, out_size)) {
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc map");
        return;
    }
    if(!cmp_write_str(&out, "status", 6) || !cmp_write_str(&out, "ok", 2)) {
        cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc status");
        return;
    }
    if(found_echo) {
        if(!cmp_write_str(&out, "echo", 4)) {
            cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping enc echo key");
            return;
        }
        size_t verbatim_len = echo_end - echo_start;
        if(wb.pos + verbatim_len > wb.cap) {
            cfc_send_error(cfc, txn, CFC_ERR_INTERNAL, "ping echo too large");
            return;
        }
        memcpy(wb.data + wb.pos, msgpack + echo_start, verbatim_len);
        wb.pos += verbatim_len;
    }

    cfc_send_response_frame(cfc, CFC_OP_PING, txn, response, wb.pos);
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
    cfc.exit_queue = furi_message_queue_alloc(2, sizeof(uint32_t));
    cfc.assemble_timer = furi_timer_alloc(cfc_on_assemble_timeout, FuriTimerTypeOnce, &cfc);

    rpc_system_app_set_callback(cfc.rpc_app, cfc_rpc_callback, &cfc);
    rpc_system_app_send_started(cfc.rpc_app);

    FURI_LOG_I(TAG, "CFC started (rpc_app=%p)", (void*)cfc.rpc_app);

    uint32_t signal = 0;
    furi_message_queue_get(cfc.exit_queue, &signal, FuriWaitForever);

    FURI_LOG_I(TAG, "CFC exiting");

    rpc_system_app_set_callback(cfc.rpc_app, NULL, NULL);
    rpc_system_app_send_exited(cfc.rpc_app);

    furi_timer_stop(cfc.assemble_timer);
    furi_timer_free(cfc.assemble_timer);
    furi_message_queue_free(cfc.exit_queue);
    furi_mutex_free(cfc.mutex);
    if(cfc.assemble_buffer) free(cfc.assemble_buffer);

    return 0;
}
