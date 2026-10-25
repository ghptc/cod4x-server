// CoD4x Promod administration, 2026-10-25. AGPL-3.0-or-later.
// Reuse installed Promod methods; do not replace its callbacks or class rules.
set_team(team)
{
    self endon("disconnect");
    level endon("game_ended");
    // Console commands run outside G_RunFrame's animation context. Yield first.
    wait 0.05;
    if (team == "allies")
        self maps\mp\gametypes\_globallogic::menuAllies();
    else if (team == "axis")
        self maps\mp\gametypes\_globallogic::menuAxis();
    else if (team == "spectator")
        self maps\mp\gametypes\_globallogic::menuSpectator();
    else
        return;
    if (isdefined(self.isbot) && self.isbot && team != "spectator" && self.pers["team"] == team)
    {
        // Humans keep Promod's class menu; bots reuse its validated assault path.
        self maps\mp\gametypes\_promod::initClassLoadouts();
        self maps\mp\gametypes\_promod::setClassChoice("assault");
        self maps\mp\gametypes\_promod::menuAcceptClass(undefined);
        if (isdefined(self.pers["class"]))
            logprint("ADMIN_BOT_CLASS slot=" + self getentitynumber() + " class=" + self.pers["class"] + "\n");
    }
    logprint("ADMIN_TEAM slot=" + self getentitynumber() + " requested=" + team + " team=" + self.pers["team"] + "\n");
}
