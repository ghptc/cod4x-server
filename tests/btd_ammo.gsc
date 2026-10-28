// Authored disposable fixture: calls the real pinned vendor pickup handler.
main()
{
    wait 4;
    level.grace_time = 120;
    a = survivor("AmmoA");
    b = survivor("AmmoB");
    // Let the vendor wave loop enter its long grace wait before shortening
    // only subsequent pickup cooldown waits in this disposable fixture.
    wait 6;
    level.grace_time = 5;
    a freezecontrols(true);
    b freezecontrols(true);
    a setorigin((500, 500, 100));
    b setorigin((700, 700, 100));
    drop = spawn("trigger_radius", (0, 0, -9000), 0, 120, 120);
    other = spawn("trigger_radius", (0, 0, -9500), 0, 120, 120);
    drop thread btd_general\_ammo_drops::ammodrop();
    other thread btd_general\_ammo_drops::ammodrop();
    wait 0.1;
    weapon = a getcurrentweapon();
    a setweaponammostock(weapon, 0);
    bweapon = b getcurrentweapon();
    b setweaponammostock(bweapon, 0);
    a.health = 50;
    b.health = 60;
    check(!isdefined(a.hasntfullammo), "first_use_uninitialized");
    // Exercise the vendor main loop: it creates the model, HUD and radius
    // trigger in response to the actual inter-wave event. No replacement
    // pickup handler or scripted trigger notification is used here.
    level notify("wave_end");
    wait 0.3;
    models = getentarray("script_model", "classname");
    wave_drops = [];
    for (i = 0; i < models.size; i++)
        if (isdefined(models[i].trigger) && isdefined(models[i].marker))
            wave_drops[wave_drops.size] = models[i];
    check(wave_drops.size == 2, "vendor_wave_created_two_drops");
    if (wave_drops.size != 2) return;
    a setorigin(wave_drops[0].origin);
    b setorigin(wave_drops[1].origin);
    wait 0.3;
    a setorigin((500, 500, 100));
    b setorigin((700, 700, 100));
    check(a getweaponammostock(weapon) > 0 && b getweaponammostock(bweapon) > 0, "two_players_refilled");
    check(a.health == 60 && b.health == 70, "health_increment");
    check(!a.hasntfullammo && !b.hasntfullammo, "cooldown_started");
    a setweaponammostock(weapon, 0);
    other notify("trigger", a);
    wait 0.1;
    check(a.health == 60 && a getweaponammostock(weapon) == 0, "rapid_cross_drop_throttled");
    wait 0.8;
    other notify("trigger", a);
    wait 0.1;
    check(a.health == 70 && a getweaponammostock(weapon) == 0, "false_cooldown_preserved");
    // A dead player must not receive ammo or health.
    b suicide();
    wait 0.1;
    deadhealth = b.health;
    drop notify("trigger", b);
    wait 0.1;
    check(b.health == deadhealth, "dead_player_ignored");
    // Disconnect while both delayed callbacks are pending.
    c = survivor("AmmoDisconnect");
    c freezecontrols(true);
    c setorigin((900, 900, 100));
    drop notify("trigger", c);
    wait 0.1;
    kick(c getentitynumber());
    wait 6;
    check(a.hasntfullammo, "cooldown_expired");
    drop notify("trigger", a);
    wait 0.1;
    check(a getweaponammostock(weapon) > 0, "refill_after_cooldown");
    // Await the normal vendor respawn, then re-enter the same handler.
    for (i = 0; i < 200; i++)
    {
        if (isalive(b) && b.sessionstate == "playing") break;
        wait 0.1;
    }
    check(isalive(b) && b.sessionstate == "playing", "respawn");
    bweapon = b getcurrentweapon();
    b setweaponammostock(bweapon, 0);
    drop notify("trigger", b);
    wait 0.1;
    check(b getweaponammostock(bweapon) > 0, "respawn_refilled");
    d = survivor("AmmoReconnect");
    d freezecontrols(true);
    d setorigin((1100, 1100, 100));
    check(!isdefined(d.hasntfullammo), "new_entity_uninitialized");
    drop notify("trigger", d);
    wait 0.1;
    check(isdefined(d.hasntfullammo) && !d.hasntfullammo, "new_entity_pickup");
    wait 0.8;
    dweapon = d getcurrentweapon();
    d setweaponammostock(dweapon, 0);
    d.hasntfullammo = true;
    d.health = d.maxhealth - 5;
    physical = spawn("trigger_radius", d.origin, 0, 120, 120);
    physical thread btd_general\_ammo_drops::ammodrop();
    wait 0.3;
    check(d getweaponammostock(dweapon) > 0 && d.health == d.maxhealth, "physical_radius_pickup_and_health_cap");
    level notify("wave_start");
    wait 0.1;
    drop delete();
    other delete();
    physical delete();
    if (getdvar("btd_ammo_failed") == "") setdvar("btd_test_result", "ammo_pass");
}

survivor(name)
{
    p = addtestclient(name);
    p.pers["isBot"] = true;
    wait 0.5;
    p maps\mp\gametypes\_globallogic::menuAllies();
    wait 0.5;
    p maps\mp\gametypes\_globallogic::menuClass("specops_mp,0");
    for (i = 0; i < 150; i++)
    {
        if (isalive(p) && p.sessionstate == "playing") return p;
        wait 0.1;
    }
    check(false, "spawn");
    return p;
}

check(ok, name)
{
    if (!ok)
    {
        setdvar("btd_ammo_failed", name);
        setdvar("btd_test_result", "ammo_failed");
        println("AMMO_CHECK_FAILED " + name);
    }
    else println("AMMO_CHECK_PASS " + name);
}
