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
    assert(BotFill_Target(0, 12) == 12);
    assert(BotFill_Target(1, 12) == 11);
    assert(BotFill_Target(12, 12) == 0);
    assert(BotFill_Target(13, 12) == 0);
    assert(BotFill_Target(0, 8) == 8);
    assert(BotFill_Target(0, 64) == 12);
    puts("bot policy: pause, empty guard, last-human resume and capacity passed");
    return 0;
}
