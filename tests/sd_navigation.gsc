// Test-only no-teleport navigation observation. Combat disabled to isolate objectives.
init()
{
    level endon("game_ended");
    wait 1;
    setdvar("bots_play_fire", 0);
    ticks = 0;
    planted = false;
    level thread record_defused();
    for (;;)
    {
        wait 0.05;
        // Remove combat perception only in this fixture so enemies cannot hold
        // each other in an endless firefight while firing is disabled.
        players = getentarray("player", "classname");
        for (i = 0; i < players.size; i++)
            if (isdefined(players[i].bot))
            {
                players[i].bot_model_fix = undefined;
                players[i].bot.targets = [];
                players[i].bot.target = undefined;
                players[i].bot.prio_objective = true;
            }
        ticks++;
        if (ticks % 20 == 0 && isdefined(level.sdbomb) && isdefined(level.sdbomb.carrier))
        {
            carrier = level.sdbomb.carrier;
            touching = 0;
            for (i = 0; i < level.bombzones.size; i++)
                if (carrier istouching(level.bombzones[i].trigger)) touching++;
            logprint("SD_NAV carrier=" + carrier getentitynumber() + " origin=" + carrier.origin + " touching=" + touching + " goal=" + carrier.bot.script_goal + "\n");
        }
        if (isdefined(level.bombplanted) && level.bombplanted && !planted)
        {
            planted = true;
            setdvar("sd_navigation_plants", getdvarint("sd_navigation_plants") + 1);
        }

    }
}

record_defused()
{
    level endon("game_ended");
    level waittill("bomb_defused");
    setdvar("sd_navigation_defuses", getdvarint("sd_navigation_defuses") + 1);
}
