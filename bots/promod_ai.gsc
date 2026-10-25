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
        if (players[i].isbot)
            players[i] thread attach();
    setdvar("bot_ai_ready", 1);
    logprint("PMBOT READY map=" + getdvar("mapname") + " waypoints=" + level.waypointcount + "\n");
}

on_connect()
{
    level endon("game_ended");
    for (;;)
    {
        level waittill("connected", player);
        if (player.isbot)
            player thread attach();
    }
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
    self.pers["bots"]["skill"]["aim_time"] = 0.25;
    self.pers["bots"]["skill"]["init_react_time"] = 300;
    self.pers["bots"]["skill"]["reaction_time"] = 300;
    self.pers["bots"]["skill"]["fov"] = 0;
    self.pers["bots"]["behavior"]["nade"] = 0;
    self.pers["bots"]["behavior"]["jump"] = 0;
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
    self maps\mp\gametypes\_promod::setClassChoice("assault");
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
