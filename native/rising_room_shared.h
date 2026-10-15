#pragma once
#include <stdint.h>
struct RisingUser { uint32_t id, flags; char name[65]; };
struct RisingMatch {
    uint32_t id, round, p1, p2, winner, status, score1, score2, confirmations, bots;
    char name1[65], name2[65], code[8];
};
struct RisingTournament {
    uint32_t status, ft, characters, enrolled, self_enrolled, role, current, champion, count, revision, mode;
    char id[65], title[97], champion_name[65], roster[257];
    RisingMatch matches[31];
};
struct RisingState {
    uint32_t connected, self_id, host_id, count, chat_count, capacity;
    char title[97], address[129], notice[257], key[65];
    RisingUser users[32];
    char chat[64][385];
    char invite[385];
    RisingTournament tournament;
};
struct RisingCommand {
    uint32_t op, target, port, capacity;
    char name[65], title[97], address[129], key[65], text[385];
    uint32_t ft, characters, score1, score2;
    char tournament_id[65];
};
struct RisingShared {
    uint32_t magic, version;
    volatile uint32_t state_seq, command_seq, ack_seq;
    RisingState state;
    RisingCommand command;
};
static_assert(sizeof(RisingUser) == 76, "Room user ABI");
static_assert(sizeof(RisingMatch) == 180, "Room match ABI");
static_assert(sizeof(RisingTournament) == 6108, "Tournament ABI");
static_assert(sizeof(RisingState) == 34140, "Room state ABI");
static_assert(sizeof(RisingCommand) == 844, "Room command ABI");
static_assert(sizeof(RisingShared) == 35004, "Room shared ABI");
