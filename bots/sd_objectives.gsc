// Promod-specific glue for the derived Bot Warfare S&D routines.
// Mod asset terms and attribution: docs/third-party-bots.md.

start()
{
    self endon("disconnect");
    self endon("death");
    self endon("promod_ai_reset");
    level endon("game_ended");
    self waittill("bot_spawned");
    if (!getdvarint("bot_sd_objectives") || !self.isbot)
        return;
    if (getdvarint("bot_debug")) logprint("PMBOT SD_START slot=" + self getentitynumber() + "\n");
    self.bot_lock_goal = false;
    self thread cleanup_on_death();
    self thread cleanup_on_reset();
    self thread bot_sd_attackers();
    self thread bot_sd_defenders();
}

cleanup_on_death()
{
    self endon("disconnect");
    self endon("promod_ai_reset");
    level endon("game_ended");
    self waittill("death");
    self notify("bot_use");
    self BotBuiltinBotAction("-activate");
}

cleanup_on_reset()
{
    self endon("disconnect");
    self endon("death");
    level endon("game_ended");
    self waittill("promod_ai_reset");
    self notify("bot_use");
    self notify("new_goal");
    self BotBuiltinBotAction("-activate");
}

carries_bomb()
{
    return isdefined(level.sdbomb) && isdefined(self.carryobject) &&
        self.carryobject == level.sdbomb;
}

objective_goal(origin, radius)
{
    if (getdvarint("bot_debug")) logprint("PMBOT SD_GOAL slot=" + self getentitynumber() + " origin=" + origin + "\n");
    self SetScriptGoal(origin, radius);
    self thread goal_deadline(level.bombplanted);
}

goal_deadline(planted)
{
    self endon("disconnect");
    self endon("death");
    self endon("promod_ai_reset");
    self endon("new_goal");
    self endon("goal");
    self endon("bad_path");
    level endon("game_ended");
    deadline = gettime() + 45000;
    while (gettime() < deadline && getdvarint("bot_sd_objectives") &&
        !level.gameended && planted == level.bombplanted)
        wait 0.1;
    self notify("bad_path");
}

wait_stop_move()
{
    deadline = gettime() + 2000;
    while (gettime() < deadline && (!self isonground() || lengthsquared(self getvelocity()) > 1))
        wait 0.05;
}

hold_objective_use(duration)
{
    if (getdvarint("bot_debug")) logprint("PMBOT SD_USE slot=" + self getentitynumber() + "\n");
    planted = level.bombplanted;
    deadline = gettime() + int(duration * 1000);
    while (gettime() < deadline && getdvarint("bot_sd_objectives") &&
        !level.gameended && planted == level.bombplanted &&
        !level.bombdefused && !level.bombexploded && !self HasThreat())
    {
        // Short renewable native input leases: interruption cannot leave use held.
        // The native game object validates contact, team and ownership every tick.
        self thread BotPressUse(0.1);
        wait 0.05;
    }
    self notify("bot_use");
    self BotBuiltinBotAction("-activate");
}
