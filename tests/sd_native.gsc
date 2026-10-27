// Test-only native interaction fixture. Never installed by preparation.
// setorigin is fixture arrangement, NOT navigation/gameplay evidence.
#include maps\mp\bots\_bot_utility;
init()
{
    level endon("game_ended");
    wait 1;
    setdvar("sd_test_rounds", getdvarint("sd_test_rounds") + 1);
    setdvar("sd_test_round_reset", int(!level.bombplanted && !level.bombdefused && !level.bombexploded));
    wait 13;
    players = getentarray("player", "classname");
    attacker = undefined;
    defender = undefined;
    for (i = 0; i < players.size; i++)
    {
        player = players[i];
        player notify("promod_ai_reset");
        player botstop();
        if (player.pers["team"] == game["attackers"] && !isdefined(attacker)) attacker = player;
        if (player.pers["team"] == game["defenders"] && !isdefined(defender)) defender = player;
    }
    if (!isdefined(attacker) || !isdefined(defender) || !isdefined(level.sdbomb))
    {
        setdvar("sd_test_result", "missing_players_or_bomb");
        return;
    }
    if (isdefined(level.sdbomb.carrier)) attacker = level.sdbomb.carrier;
    attacker setorigin(level.sdbomb.trigger.origin);
    wait 1;
    if (!isdefined(attacker.carryobject) || attacker.carryobject != level.sdbomb)
    {
        setdvar("sd_test_result", "pickup_failed");
        return;
    }
    setdvar("sd_test_pickup", 1);
    plant = level.bombzones[0];
    attacker fixture_place(plant);
    wait 0.5;
    attacker botaction("+activate");
    wait 1;
    attacker botaction("-activate");
    wait 0.3;
    if (level.bombplanted || attacker.isplanting)
    {
        setdvar("sd_test_result", "plant_interrupt_failed");
        return;
    }
    setdvar("sd_test_plant_interrupted", 1);
    attacker.throwingGrenade = false;
    attacker suicide();
    wait 0.3;
    if (isdefined(level.sdbomb.carrier) || level.bombplanted)
    {
        setdvar("sd_test_result", "death_drop_failed");
        return;
    }
    setdvar("sd_test_death_drop", 1);
    for (i = 0; i < players.size; i++)
        if (players[i].pers["team"] == game["attackers"] && isalive(players[i]))
        { attacker = players[i]; break; }
    if (isdefined(level.sdbomb.carrier)) attacker = level.sdbomb.carrier;
    attacker setorigin(level.sdbomb.trigger.origin);
    wait 0.5;
    if (!isdefined(attacker.carryobject) || attacker.carryobject != level.sdbomb)
    {
        setdvar("sd_test_result", "pickup_failed");
        return;
    }
    attacker fixture_place(plant);
    wait 0.5;
    began = gettime();
    attacker botaction("+activate");
    while (!level.bombplanted && gettime() - began < 10000) wait 0.05;
    attacker botaction("-activate");
    setdvar("sd_test_plant_elapsed", gettime() - began);
    setdvar("sd_test_debug", "planted=" + int(level.bombplanted) + " time=" + (gettime() - began) + " required=" + plant.usetime + " touching=" + int(attacker istouching(plant.trigger)) + " onground=" + int(attacker isonground()));
    if (!level.bombplanted || gettime() - began < plant.usetime - 100)
    {
        setdvar("sd_test_result", "native_plant_failed");
        return;
    }
    setdvar("sd_test_planted", 1);
    wait 0.2;
    defuse = level.defuseobject;
    defender fixture_place(defuse);
    wait 0.5;
    defender botaction("+activate");
    wait 1;
    defender botaction("-activate");
    wait 0.3;
    if (level.bombdefused || defender.isdefusing)
    {
        setdvar("sd_test_result", "defuse_interrupt_failed");
        return;
    }
    setdvar("sd_test_defuse_interrupted", 1);
    defender botaction("+activate");
    wait 1;
    defender.throwingGrenade = false;
    defender suicide();
    wait 0.3;
    if (level.bombdefused)
    {
        setdvar("sd_test_result", "defuse_death_failed");
        return;
    }
    setdvar("sd_test_defuse_death", 1);
    for (i = 0; i < players.size; i++)
        if (players[i].pers["team"] == game["defenders"] && isalive(players[i]))
        { defender = players[i]; break; }
    defender fixture_place(defuse);
    wait 0.5;
    began = gettime();
    level thread record_defuse(defender, defuse, began);
    defender botaction("+activate");
    while (!level.bombdefused && gettime() - began < 12000) wait 0.05;
    defender botaction("-activate");
    setdvar("sd_test_defuse_elapsed", gettime() - began);
    if (!level.bombdefused || gettime() - began < defuse.usetime - 100)
    {
        setdvar("sd_test_result", "native_defuse_failed");
        return;
    }
    setdvar("sd_test_result", "passed");
}

record_defuse(defender, object, began)
{
    level waittill("bomb_defused");
    defender botaction("-activate");
    elapsed = gettime() - began;
    setdvar("sd_test_defuse_elapsed", elapsed);
    if (level.bombdefused && elapsed >= object.usetime - 100)
        setdvar("sd_test_result", "passed");
    else
        setdvar("sd_test_result", "native_defuse_failed");
}

// Find grounded trigger contact for fixture setup without altering native state.
fixture_place(object)
{
    offsets = [];
    offsets[0] = (50,50,0);
    offsets[1] = (0,0,0);
    offsets[2] = (-50,-50,0);
    offsets[3] = (-50,50,0);
    offsets[4] = (50,-50,0);
    for (i = 0; i < offsets.size; i++)
    {
        origin = object.curorigin + offsets[i];
        trace = bullettrace(origin + (0,0,128), origin - (0,0,512), false, self);
        self setorigin(trace["position"] + (0,0,4));
        wait 0.5;
        if (self isonground() && self istouching(object.trigger)) return;
    }
}
