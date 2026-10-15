#pragma once
#include <stdint.h>
struct RisingUser { uint32_t id, flags; char name[65]; };
struct RisingState {
    uint32_t connected, self_id, host_id, count, chat_count, capacity;
    char title[97], address[129], notice[257], key[65];
    RisingUser users[32];
    char chat[64][385];
    char invite[385];
};
struct RisingCommand {
    uint32_t op, target, port, capacity;
    char name[65], title[97], address[129], key[65], text[385];
};
struct RisingShared {
    uint32_t magic, version;
    volatile uint32_t state_seq, command_seq, ack_seq;
    RisingState state;
    RisingCommand command;
};
static_assert(sizeof(RisingUser) == 76, "Room user ABI");
static_assert(sizeof(RisingState) == 28032, "Room state ABI");
static_assert(sizeof(RisingCommand) == 760, "Room command ABI");
static_assert(sizeof(RisingShared) == 28812, "Room shared ABI");
