// Promod AI integration, 2026-10-25. Experimental, not production certified.
// Bot Warfare: INeedGames/INeedBots, PeZBOT team and contributors.
// Integration mod assets: PModEPL; see docs/bots.md and docs/third-party-bots.md.
#include maps\mp\bots\_bot_utility;

init()
{
    setdvar("bot_ai_ready", 0);
    if (!getdvarint("bot_enable") || getdvar("g_gametype") != "sd" || getdvarint("sv_pure") != 1)
        return;
    wait 0.2;
    if (getdvarint("bot_debug"))
        setdvar("g_no_script_spam", 0);
    setdvar("bots_main_firstIsHost", 0);
    setdvar("bots_main_GUIDs", "");
    setdvar("bots_main_menu", 0);
    setdvar("bots_manage_fill", 0);
    setdvar("bots_manage_add", 0);
    setdvar("bots_play_move", 1);
    setdvar("bots_play_fire", 1);
    setdvar("bots_play_aim", 1);
    setdvar("bots_play_ads", 1);
    setdvar("bots_play_knife", 0);
    setdvar("bots_play_nade", 0);
    setdvar("bots_play_obj", 0);
    setdvar("bots_play_killstreak", 0);
    setdvar("bots_play_jumpdrop", 0);
    maps\mp\bots\adapter::init();
    // Constants from pinned _bot::init, without its callback or population hooks.
    level.bots_smokelist = List();
    level.bots_minsprintdistance = 315 * 315;
    level.bots_mingrenadedistance = 256 * 256;
    level.bots_maxgrenadedistance = 1024 * 1024;
    level.bots_maxknifedistance = 128 * 128;
    level.bots_goaldistance = 27.5 * 27.5;
    level.bots_noadsdistance = 200 * 200;
    level.bots_maxshotgundistance = 500 * 500;
    level.bots_listendist = 100;
    level.smokeradius = 255;
    level.bots_fullautoguns = [];
    level.bots_fullautoguns["ak47"] = true;
    level.bots_fullautoguns["ak74u"] = true;
    level.bots_fullautoguns["mp5"] = true;
    load_waypoints();
    if (level.waypointcount <= 0)
    {
        logprint("PMBOT BLOCKED no waypoints for " + getdvar("mapname") + "\n");
        return;
    }
    level thread on_connect();
    level thread on_round_end();
    players = getentarray("player", "classname");
    for (i = 0; i < players.size; i++)
    {
        players[i] thread watch_player();
        if (players[i].isbot)
            players[i] thread attach();
    }
    setdvar("bot_ai_ready", 1);
    logprint("PMBOT READY map=" + getdvar("mapname") + " waypoints=" + level.waypointcount + "\n");
}

on_connect()
{
    level endon("game_ended");
    for (;;)
    {
        level waittill("connected", player);
        player thread watch_player();
        if (player.isbot)
            player thread attach();
    }
}

// Perception metadata is required for human opponents too, not only AI entities.
watch_player()
{
    if (isdefined(self.promod_ai_watched))
        return;
    self.promod_ai_watched = true;
    self thread player_model_ready();
    self thread watch_grenades();
}

player_model_ready()
{
    self endon("disconnect");
    level endon("game_ended");
    if (!isalive(self) || self.sessionstate != "playing")
        self waittill("spawned_player");
    wait 0.05;
    self.bot_model_fix = true;
}

// Reuse Bot Warfare's smoke registration without its admin/callback initializer.
watch_grenades()
{
    self endon("disconnect");
    level endon("game_ended");
    for (;;)
    {
        self waittill("grenade_fire", grenade, weapon);
        if (!isdefined(grenade))
            continue;
        grenade.name = weapon;
        if (weapon == "smoke_grenade_mp")
            grenade thread register_smoke();
    }
}

register_smoke()
{
    level endon("game_ended");
    smoke = spawnstruct();
    smoke.origin = self getorigin();
    smoke.state = "moving";
    smoke.grenade = self;
    level.bots_smokelist ListAdd(smoke);
    smoke thread track_smoke();
}

track_smoke()
{
    level endon("game_ended");
    while (isdefined(self.grenade))
    {
        self.origin = self.grenade getorigin();
        wait 0.05;
    }
    self.state = "smoking";
    wait 11.5;
    level.bots_smokelist ListRemove(self);
}

on_round_end()
{
    level waittill("game_ended");
    setdvar("bot_ai_ready", 0);
}

attach()
{
    self endon("disconnect");
    if (isdefined(self.promod_ai_attached))
        return;
    self.promod_ai_attached = true;
    self notify("promod_ai_reset");
    self.promod_ai_core_spawned = undefined;
    self maps\mp\bots\_bot_internal::added();
    self thread difficulty_control();
    self maps\mp\bots\_bot_internal::connected();
    self thread model_ready();
    self thread weapon_selection();
    if (getdvarint("bot_debug"))
    {
        self thread observe();
        self thread observe_fire();
    }
    // Promod emits connected before all per-player initialization finishes.
    wait 1;
    self maps\mp\gametypes\_promod::initClassLoadouts();
    if (self.pers["team"] != "allies" && self.pers["team"] != "axis")
        self maps\mp\gametypes\_globallogic::menuAutoAssign();
    if (!self choose_loadout())
    {
        bot_trace("PMBOT NO_ALLOWED_LOADOUT slot=" + self getentitynumber());
        return;
    }
    self maps\mp\gametypes\_promod::menuAcceptClass(undefined);
    wait 0.2;
    // Reconnect during round restart may have spawned before attachment.
    if (isalive(self) && self.sessionstate == "playing" && !isdefined(self.bot_model_fix))
    {
        wait 0.05;
        self.bot_model_fix = true;
    }
    if (isalive(self) && self.sessionstate == "playing" && !isdefined(self.promod_ai_core_spawned))
    {
        self.promod_ai_core_spawned = true;
        self thread maps\mp\bots\_bot_internal::onWeaponChange();
        self thread maps\mp\bots\_bot_internal::onLastStand();
        self thread maps\mp\bots\_bot_internal::reload_watch();
        self thread maps\mp\bots\_bot_internal::sprint_watch();
        self thread maps\mp\bots\_bot_internal::spawned();
    }
    bot_trace("PMBOT CLASS slot=" + self getentitynumber() + " team=" + self.pers["team"] + " class=" + self.pers["class"]);
}

// Let Promod validate each candidate against the active mode before reserving it.
allowed_weapons(class_type, loadout_type)
{
    if (loadout_type == "loadout_primary")
        candidates = strtok("m16,ak47,m4,g3,g36c,m14,mp44,mp5,uzi,ak74u,winchester1200,m1014,m40a3,remington700", ",");
    else
        candidates = strtok("beretta,colt45,usp,deserteagle,deserteaglegold", ",");
    allowed = [];
    for (i = 0; i < candidates.size; i++)
        if (maps\mp\gametypes\_promod::validClass(class_type, candidates[i], loadout_type) &&
            self maps\mp\gametypes\_promod::verifyWeaponChoice(candidates[i], class_type))
            allowed[allowed.size] = candidates[i];
    return allowed;
}

choose_loadout()
{
    classes = strtok("assault,specops,demolitions,sniper", ",");
    allowed_classes = [];
    for (i = 0; i < classes.size; i++)
    {
        weapons = self allowed_weapons(classes[i], "loadout_primary");
        if (weapons.size && self maps\mp\gametypes\_promod::verifyClassChoice(self.pers["team"], classes[i]))
            allowed_classes[allowed_classes.size] = classes[i];
    }
    if (!allowed_classes.size)
        return false;
    class_type = allowed_classes[randomint(allowed_classes.size)];
    self maps\mp\gametypes\_promod::setClassChoice(class_type);
    primaries = self allowed_weapons(class_type, "loadout_primary");
    secondaries = self allowed_weapons(class_type, "loadout_secondary");
    self.pers[class_type]["loadout_primary"] = primaries[randomint(primaries.size)];
    self.pers[class_type]["loadout_primary_attachment"] = "none";
    if (!maps\mp\gametypes\_promod::validClass(class_type, "none", "loadout_primary_attachment") &&
        self.pers[class_type]["loadout_primary"] != "mp44" &&
        maps\mp\gametypes\_promod::validClass(class_type, "silencer", "loadout_primary_attachment"))
        self.pers[class_type]["loadout_primary_attachment"] = "silencer";
    self.pers[class_type]["loadout_secondary"] = "none";
    if (secondaries.size)
        self.pers[class_type]["loadout_secondary"] = secondaries[randomint(secondaries.size)];
    self.pers[class_type]["loadout_secondary_attachment"] = "none";
    if (!maps\mp\gametypes\_promod::validClass(class_type, "none", "loadout_secondary_attachment") &&
        maps\mp\gametypes\_promod::validClass(class_type, "silencer", "loadout_secondary_attachment"))
        self.pers[class_type]["loadout_secondary_attachment"] = "silencer";
    bot_trace("PMBOT LOADOUT slot=" + self getentitynumber() + " class=" + class_type +
        " primary=" + self.pers[class_type]["loadout_primary"] +
        " secondary=" + self.pers[class_type]["loadout_secondary"]);
    return true;
}

// Reuse the pinned seven Bot Warfare profiles without its stock gametype/admin callbacks.
difficulty_control()
{
    self endon("disconnect");
    self endon("promod_ai_reset");
    level endon("game_ended");
    previous = undefined;
    for (;;)
    {
        mode = getdvarint("bot_skill");
        if (!isdefined(previous) || previous != mode)
        {
            if (mode == -1)
            {
                self maps\mp\bots\difficulty::reset_profile();
                self.pers["bots"]["skill"]["aim_time"] = 0.25;
                self.pers["bots"]["skill"]["init_react_time"] = 300;
                self.pers["bots"]["skill"]["reaction_time"] = 300;
                self.pers["bots"]["skill"]["fov"] = 0;
            }
            else
            {
                self maps\mp\bots\difficulty::set_diff();
                self maps\mp\bots\difficulty::apply_profile();
            }
            self.pers["bots"]["behavior"]["nade"] = 0;
            self.pers["bots"]["behavior"]["jump"] = 0;
            previous = mode;
            bot_trace("PMBOT SKILL slot=" + self getentitynumber() + " mode=" + mode + " base=" + self.pers["bots"]["skill"]["base"] + " aim=" + self.pers["bots"]["skill"]["aim_time"]);
        }
        wait 0.5;
    }
}

// Upstream _bot::doPlayerModelFix, kept outside its callback/admin initializer.
model_ready()
{
    self endon("disconnect");
    self endon("promod_ai_reset");
    level endon("game_ended");
    self waittill("spawned_player");
    wait 0.05;
    self.bot_model_fix = true;
    self.promod_ai_core_spawned = true;
}

// Synchronize native bot input with an existing primary; never give new weapons.
weapon_selection()
{
    self endon("disconnect");
    self endon("promod_ai_reset");
    level endon("game_ended");
    for (;;)
    {
        wait 0.2;
        if (!isalive(self) || self.sessionstate != "playing")
            continue;
        if (self getcurrentweapon() != "none")
            continue;
        weapons = self getweaponslistprimaries();
        if (weapons.size > 0)
        {
            self botweapon(weapons[0]);
            bot_trace("PMBOT WEAPON_SELECT slot=" + self getentitynumber() + " weapon=" + weapons[0]);
        }
    }
}

observe_fire()
{
    self endon("disconnect");
    self endon("promod_ai_reset");
    level endon("game_ended");
    for (;;)
    {
        self waittill("weapon_fired");
        bot_trace("PMBOT FIRE slot=" + self getentitynumber() + " weapon=" + self getcurrentweapon());
    }
}

observe()
{
    self endon("disconnect");
    self endon("promod_ai_reset");
    level endon("game_ended");
    for (;;)
    {
        wait 1;
        enemy = -1;
        if (isdefined(self.bot.target) && isdefined(self.bot.target.entity))
            enemy = self.bot.target.entity getentitynumber();
        bot_trace("PMBOT SAMPLE slot=" + self getentitynumber() + " state=" + self.sessionstate + " pos=" + self.origin + " angles=" + self getplayerangles() + " hp=" + self.health + " weapon=" + self getcurrentweapon() + " ammo=" + self getammocount(self getcurrentweapon()) + " enemy=" + enemy + " wp=" + self.bot.next_wp);
    }
}

// Debug evidence uses the existing game log without changing Promod callbacks.
bot_trace(message)
{
    if (getdvarint("bot_debug"))
        logprint(message + "\n");
}
