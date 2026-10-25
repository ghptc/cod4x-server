#include <assert.h>
#include <stdio.h>
#include "../src/sv_bot_policy.h"
int main(void)
{
    bot_fill_state_t state = BotFill_Pause(0);
    assert(state == BOT_FILL_PAUSED_EMPTY);
    /* Map changes have no policy transition: empty pause stays empty. */
    assert(BotFill_Leave(state, 0) == BOT_FILL_PAUSED_EMPTY);
    state = BotFill_Join(state);
    assert(state == BOT_FILL_PAUSED_HUMANS);
    assert(BotFill_Leave(state, 1) == BOT_FILL_PAUSED_HUMANS);
    assert(BotFill_Leave(state, 0) == BOT_FILL_ACTIVE);
    state = BotFill_Pause(2);
    assert(BotFill_Leave(state, 1) == BOT_FILL_PAUSED_HUMANS);
    assert(BotFill_Leave(state, 0) == BOT_FILL_ACTIVE);
    assert(BotFill_Target(0, 12, 12) == 12);
    assert(BotFill_Target(1, 12, 12) == 11);
    assert(BotFill_Target(12, 12, 12) == 0);
    assert(BotFill_Target(13, 12, 12) == 0);
    assert(BotFill_Target(0, 8, 12) == 8);
    assert(BotFill_Target(0, 64, 12) == 12);
    assert(BotFill_Target(4, 64, 12) == 8);
    assert(BotFill_Target(13, 64, 12) == 0);
    assert(BotFill_Target(0, 12, 0) == 0);
    assert(BotFill_Target(2, 12, 4) == 4);
    assert(BotFill_Target(11, 12, 4) == 1);
    int count;
    assert(BotControl_Count("0", &count) && count == 0);
    assert(BotControl_Count("12", &count) && count == 12);
    const char *invalid[] = {"", "-1", "+1", "13", "2x", "1;quit", "99999999999999999"};
    for (unsigned i = 0; i < sizeof(invalid)/sizeof(*invalid); ++i)
        assert(!BotControl_Count(invalid[i], &count));
    puts("bot policy: pause, empty guard, last-human resume and capacity passed");
    return 0;
}
