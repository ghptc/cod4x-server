// Local qualification fixture only; never installed by prepare.py.
check(condition, label)
{
    if (!condition)
    {
        logprint("GAMEPLAY_TEST FAIL " + label + "\n");
        setdvar("gameplay_test_failed", 1);
    }
    else
        logprint("GAMEPLAY_TEST PASS " + label + "\n");
}

player_fixture(bot, team, class_type)
{
    player = spawnstruct();
    player.isbot = bot;
    player.pers["team"] = team;
    player.pers["class"] = class_type;
    player.team = team;
    player.class = class_type;
    return player;
}

class_limits()
{
    players = level.players;
    server_dvars = level.serverDvars;
    limit = getdvarint("class_sniper_limit");
    level.serverDvars = [];
    setdvar("class_sniper_limit", 1);
    human = player_fixture(false, "allies", "assault");
    other = player_fixture(false, "allies", "assault");
    bot = player_fixture(true, "allies", "sniper");
    level.players = [];
    level.players[0] = human;
    level.players[1] = other;
    level.players[2] = bot;
    check(human maps\mp\gametypes\_promod::verifyClassChoice("allies", "sniper"), "bot-does-not-reserve-human-slot");
    human.pers["class"] = "sniper";
    check(!other maps\mp\gametypes\_promod::verifyClassChoice("allies", "sniper"), "second-human-rejected");
    other maps\mp\gametypes\_promod::setClassChoice("sniper");
    check(other.pers["class"] == "assault", "reservation-guard-rejects-second-human");
    check(human maps\mp\gametypes\_promod::verifyClassChoice("allies", "sniper"), "holder-keeps-slot");
    check(bot maps\mp\gametypes\_promod::verifyClassChoice("allies", "sniper"), "bot-sniper-with-human-slot-full");
    maps\mp\gametypes\_promod::updateClassAvailability("allies");
    check(game["allies_sniper_count"] == 1, "human-only-availability");
    // Team changes clear the old reservation even if the spawned class is stale.
    human.pers["team"] = "axis";
    maps\mp\gametypes\_promod::updateClassAvailability("allies");
    maps\mp\gametypes\_promod::updateClassAvailability("axis");
    check(game["allies_sniper_count"] == 0 && game["axis_sniper_count"] == 1, "team-switch-accounting");
    check(other maps\mp\gametypes\_promod::verifyClassChoice("allies", "sniper"), "old-team-slot-released");
    other.pers["class"] = "sniper";
    other.class = undefined;
    check(!other maps\mp\gametypes\_promod::verifyClassChoice("axis", "sniper"), "new-team-full-rejected");
    maps\mp\gametypes\_promod::updateClassAvailability("allies");
    check(game["allies_sniper_count"] == 1, "round-reservation-survives-unspawned-class");
    level.players[2] = undefined;
    maps\mp\gametypes\_promod::updateClassAvailability("allies");
    check(game["allies_sniper_count"] == 1, "bot-removal-no-human-accounting-change");
    other.pers["class"] = undefined;
    maps\mp\gametypes\_promod::updateClassAvailability("allies");
    check(game["allies_sniper_count"] == 0, "human-class-cleared-releases-slot");
    setdvar("class_sniper_limit", 0);
    check(!bot maps\mp\gametypes\_promod::verifyClassChoice("allies", "sniper"), "disabled-class-respected");
    setdvar("class_sniper_limit", limit);
    level.players = players;
    level.serverDvars = server_dvars;
    maps\mp\gametypes\_promod::updateClassAvailability("allies");
    maps\mp\gametypes\_promod::updateClassAvailability("axis");
}

weapon_classes()
{
    player = player_fixture(true, "allies", "assault");
    classes = strtok("assault,specops,demolitions,sniper", ",");
    counts = [];
    counts[0] = 7; counts[1] = 3; counts[2] = 2; counts[3] = 2;
    for (i = 0; i < classes.size; i++)
    {
        weapons = player maps\mp\bots\promod_ai::allowed_weapons(classes[i], "loadout_primary");
        check(weapons.size == counts[i], "primary-pool-" + classes[i]);
        weapons = player maps\mp\bots\promod_ai::allowed_weapons(classes[i], "loadout_secondary");
        check(weapons.size == 5, "pistol-pool-" + classes[i]);
    }
    allowed = getdvarint("weap_allow_m40a3");
    setdvar("weap_allow_m40a3", 0);
    weapons = player maps\mp\bots\promod_ai::allowed_weapons("sniper", "loadout_primary");
    check(weapons.size == 1 && weapons[0] == "remington700", "disabled-weapon-excluded");
    setdvar("weap_allow_m40a3", allowed);
}

weapon_inventory()
{
    if (!getdvarint("gameplay_test_inventory") || getdvarint("gameplay_test_inventory_done")) return;
    // Readiness precedes the first actual spawn; wait for a live inventory owner.
    for (attempt = 0; attempt < 100; attempt++)
    {
        entities = getentarray("player", "classname");
        live = false;
        for (n = 0; n < entities.size; n++)
            if (entities[n].isbot && isalive(entities[n])) live = true;
        if (live) break;
        wait 0.1;
    }
    setdvar("gameplay_test_inventory_done", 1);
    bots = getentarray("player", "classname");
    bot = undefined;
    seen = [];
    for (i = 0; i < bots.size; i++)
    {
        slot = bots[i] getentitynumber();
        check(!isdefined(seen[slot]), "unique-player-slot-" + slot);
        seen[slot] = true;
        if (bots[i].isbot && isalive(bots[i])) bot = bots[i];
    }
    check(isdefined(bot), "live-bot-for-inventory");
    if (!isdefined(bot)) return;
    classes = strtok("assault,specops,demolitions,sniper", ",");
    for (i = 0; i < classes.size; i++)
    {
        cls = classes[i];
        weapons = bot maps\mp\bots\promod_ai::allowed_weapons(cls, "loadout_primary");
        for (j = 0; j < weapons.size; j++)
        {
            bot maps\mp\gametypes\_promod::setClassChoice(cls);
            bot.pers[cls]["loadout_primary"] = weapons[j];
            bot.pers[cls]["loadout_primary_attachment"] = "none";
            bot maps\mp\gametypes\_class::giveLoadout(bot.pers["team"], cls);
            inventory = bot getweaponslistprimaries();
            found = false;
            for (k = 0; k < inventory.size; k++)
                if (inventory[k] == weapons[j] + "_mp") found = true;
            check(found, "native-inventory-" + weapons[j]);
        }
    }
    sidearms = bot maps\mp\bots\promod_ai::allowed_weapons("sniper", "loadout_secondary");
    for (i = 0; i < sidearms.size; i++)
    {
        bot.pers["sniper"]["loadout_secondary"] = sidearms[i];
        bot.pers["sniper"]["loadout_secondary_attachment"] = "none";
        bot maps\mp\gametypes\_class::giveLoadout(bot.pers["team"], "sniper");
        inventory = bot getweaponslistprimaries();
        found = false;
        for (k = 0; k < inventory.size; k++)
            if (inventory[k] == sidearms[i] + "_mp") found = true;
        check(found, "native-sidearm-inventory-" + sidearms[i]);
    }
    bot maps\mp\bots\promod_ai::choose_loadout();
    bot maps\mp\gametypes\_class::giveLoadout(bot.pers["team"], bot.pers["class"]);
    maps\mp\gametypes\_promod::updateClassAvailability("allies");
    maps\mp\gametypes\_promod::updateClassAvailability("axis");
    check(game["allies_sniper_count"] == 0 && game["axis_sniper_count"] == 0, "bot-inventory-no-human-slots-consumed");
}

init()
{
    wait 3;
    class_limits();
    weapon_classes();
    weapon_inventory();
    logprint("GAMEPLAY_TEST class-and-weapon-checks-complete\n");
    if (!getdvarint("gameplay_test_rotation"))
        return;
    stage = getdvarint("gameplay_test_stage");
    current = getdvar("mapname");
    if (stage == 0)
    {
        setdvar("gameplay_test_previous_map", current);
        setdvar("gameplay_test_stage", 1);
        game["roundsplayed"] = 0;
    }
    else if (stage == 1)
    {
        check(current == getdvar("gameplay_test_previous_map"), "sd-round-keeps-map");
        setdvar("gameplay_test_stage", 2);
        game["roundsplayed"] = 2;
    }
    else if (stage == 2)
    {
        check(current != getdvar("gameplay_test_previous_map"), "completed-match-advances-map");
        target = "mp_strike";
        if (current == target) target = "mp_backlot";
        // The native callvote harness tests the ballot -> this cvar transition.
        setdvar("g_votedMapName", target);
        setdvar("gameplay_test_vote_map", target);
        setdvar("gameplay_test_stage", 3);
        game["roundsplayed"] = 2;
    }
    else if (stage == 3)
    {
        check(current == getdvar("gameplay_test_vote_map"), "voted-next-map-consumed");
        check(getdvar("g_votedMapName") == "", "voted-map-cleared");
        setdvar("gameplay_test_previous_map", current);
        setdvar("gameplay_test_stage", 4);
        game["roundsplayed"] = 2;
    }
    else
    {
        check(current != getdvar("gameplay_test_previous_map"), "rotation-resumes-without-repeat");
        setdvar("gameplay_test_stage", 5);
        return;
    }
    // Exercise the actual terminal Promod routine; do not replace its callbacks.
    game["state"] = "playing";
    level.roundlimit = 2;
    level.scorelimit = 0;
    level.displayRoundEndText = false;
    level.roundEndDelay = 0;
    level.postRoundTime = 0;
    level.forcedEnd = false;
    maps\mp\gametypes\_globallogic::endGame(undefined, game["strings"]["time_limit_reached"]);
}
