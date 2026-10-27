// Disposable fixture only. Never packaged in a runtime image.
main()
{
    if (getdvar("btd_test_scenario") == "idle") return;
    wait 4;
    if (getdvar("btd_test_scenario") == "expression")
    {
        fixture = spawn("script_model", (0, 0, 0));
        // The regression runner substitutes the actual pinned condition here.
        if (BTD_TEST_CONDITION) setdvar("btd_test_result", "unexpected");
        setdvar("btd_test_result", "expression_pass");
        return;
    }
    player = addtestclient("DeathRegression");
    player.pers["isBot"] = true;
    wait 1;
    player maps\mp\gametypes\_globallogic::menuAllies();
    wait 1;
    player maps\mp\gametypes\_globallogic::menuClass("specops_mp,0");
    for (i = 0; i < 150; i++)
    {
        if (isalive(player) && player.sessionstate == "playing") break;
        wait 0.1;
    }
    if (!isalive(player) || player.sessionstate != "playing")
    {
        setdvar("btd_test_result", "spawn_failed");
        return;
    }
    setdvar("btd_test_result", "spawned");
    if (getdvar("btd_test_scenario") == "classic")
    {
        player classic();
        return;
    }
    wait 1;
    player suicide();
    wait 2;
    setdvar("btd_test_result", "death_callback_survived");
    if (getdvar("btd_test_scenario") != "lifecycle") return;
    for (i = 0; i < 200; i++)
    {
        if (isalive(player) && player.sessionstate == "playing") break;
        wait 0.1;
    }
    if (!isalive(player) || player.sessionstate != "playing")
    {
        setdvar("btd_test_result", "respawn_failed"); return;
    }
    setdvar("btd_test_respawn", "passed");
    player.maxhealth = 100000;
    player.health = 100000;
    seen_spawn = false;
    // Exercise the vendor wave loop with accelerated fixture CFG values.
    // Damage notifications enter the vendor zombie health/death handler.
    for (i = 0; i < 1800; i++)
    {
        zombies = getentarray("zom", "targetname");
        for (j = 0; j < zombies.size; j++)
        {
            if (isdefined(zombies[j].health) && zombies[j].health > 0)
            {
                seen_spawn = true;
                zombies[j] notify("damage", 100000, player, (1,0,0), zombies[j].origin,
                    "MOD_RIFLE_BULLET", "zombie", "tag_origin", "tag_origin", 0);
            }
        }
        if (seen_spawn && level.currentwave >= 2) break;
        wait 0.05;
    }
    if (!seen_spawn) { setdvar("btd_test_result", "zombie_spawn_failed"); return; }
    setdvar("btd_test_zombie_spawn", "passed");
    if (level.currentwave < 2) { setdvar("btd_test_result", "wave_failed"); return; }
    setdvar("btd_test_wave", "passed");
    kick(player getentitynumber());
    setdvar("btd_test_result", "lifecycle_pass");
}

classic()
{
    // Run the shipped dispatchers. Zero must suppress both independent systems.
    self btd_general\_anti_camp_time::main();
    if (isdefined(self.campingtime))
    {
        setdvar("btd_test_result", "classic_timer_enabled");
        return;
    }
    triggers = getentarray("trigger_radius", "classname");
    for (i = 0; i < triggers.size; i++)
    {
        if (isdefined(triggers[i].goto))
        {
            setdvar("btd_test_result", "classic_teleport_enabled");
            return;
        }
    }
    self freezecontrols(true);
    // Crash's helicopter is one of the vendor's explicitly blocked positions.
    self setorigin((996, 584, 322));
    wait 2;
    start = self.origin;
    setdvar("btd_test_classic_height", start[2]);
    if (start[2] < 230 || distance2d(start, (996, 584, 322)) > 35)
    {
        setdvar("btd_test_result", "classic_position_failed");
        return;
    }
    health = self.health;
    level.status = "play";
    // More than twice the accelerated camping timeout; no zombies spawn yet.
    wait 6;
    if (!isalive(self) || self.sessionstate != "playing" || self.health < health ||
        isdefined(self.campingtime))
    {
        setdvar("btd_test_result", "classic_camping_failed");
        return;
    }
    if (distance(start, self.origin) > 8)
    {
        setdvar("btd_test_result", "classic_position_failed");
        return;
    }
    if (getdvar("btd_msg2") != "^7Server admins are ^4pitta")
    {
        setdvar("btd_test_result", "classic_message_failed");
        return;
    }
    setdvar("btd_test_result", "classic_pass");
}
