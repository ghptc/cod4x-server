/* Bot fill policy. No game objects or map lifetime state are stored here. */
#ifndef SV_BOT_POLICY_H
#define SV_BOT_POLICY_H
typedef enum { BOT_FILL_ACTIVE, BOT_FILL_PAUSED_EMPTY, BOT_FILL_PAUSED_HUMANS } bot_fill_state_t;
static inline bot_fill_state_t BotFill_Pause(int humans) {
    return humans ? BOT_FILL_PAUSED_HUMANS : BOT_FILL_PAUSED_EMPTY;
}
static inline bot_fill_state_t BotFill_Join(bot_fill_state_t state) {
    return state == BOT_FILL_PAUSED_EMPTY ? BOT_FILL_PAUSED_HUMANS : state;
}
static inline bot_fill_state_t BotFill_Leave(bot_fill_state_t state, int remaining) {
    return state == BOT_FILL_PAUSED_HUMANS && remaining == 0 ? BOT_FILL_ACTIVE : state;
}
static inline int BotFill_Target(int humans, int capacity, int bot_limit) {
    int free = (capacity < 12 ? capacity : 12) - humans;
    if (free < 0) free = 0;
    if (free > 12) free = 12;
    return free < bot_limit ? free : bot_limit;
}
/* Bounded decimal parsing, including zero; rejects signs, suffixes and overflow. */
static inline int BotControl_Count(const char *text, int *value) {
    int count = 0;
    if (!text || !*text) return 0;
    for (; *text; ++text) {
        if (*text < '0' || *text > '9') return 0;
        count = count * 10 + *text - '0';
        if (count > 12) return 0;
    }
    *value = count;
    return 1;
}
#endif
