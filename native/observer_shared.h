#pragma once
#include <stdint.h>
enum { BTC_OBSERVER_RING = 8192, BTC_OBSERVER_MAGIC = 0x53435442 };
struct BtcObserverFrame { uint32_t tick; unsigned char pads[36]; };
struct BtcObserverHeader {
    uint32_t magic, version, serial, mode, error, closed;
    uint32_t seed, rules, options[2], first, next, read, scores[2], read_serial;
    char names[2][64];
};
struct BtcObserverShared { BtcObserverHeader header; BtcObserverFrame frames[BTC_OBSERVER_RING]; };
static_assert(sizeof(BtcObserverFrame)==40,"Observer frame ABI");
static_assert(sizeof(BtcObserverHeader)==192,"Observer header ABI");
