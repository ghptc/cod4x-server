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
static inline int BotFill_Target(int humans, int capacity) {
    int limit = capacity < 12 ? capacity : 12;
    return humans < limit ? limit - humans : 0;
}
#endif
