// Disposable qualification fixture; not installed by prepare.py.
init()
{
    for (;;)
    {
        wait 0.05;
        request = getdvar("integration_request");
        if (request == "") continue;
        setdvar("integration_request", "");
        if (request == "reset_human")
        {
            // A fixture converts an existing bot entity to a synthetic human.
            // Actual humans enter the original Ready Up loop at connect time.
            players = getentarray("player", "classname");
            for (i = 0; i < players.size; i++)
                if (!players[i].isbot)
                {
                    players[i] notify("promod_ai_reset");
                }
        }
        if (request == "recorded")
        {
            players = getentarray("player", "classname");
            for (i = 0; i < players.size; i++)
                if (!players[i].isbot)
                {
                    // Recording UI requires a real graphical client.
                    players[i].pers["record_reminder_done"] = true;
                    players[i].inrecmenu = undefined;
                }
        }
        if (request == "bots_mark_ready")
        {
            players = getentarray("player", "classname");
            for (i = 0; i < players.size; i++)
                if (players[i].isbot) { players[i].ready = true; players[i].update = true; }
        }
        if (request == "short_match")
        {
            // Accelerate the actual S&D completion condition, retaining death,
            // scoring, round-end, match-end and ExitLevel implementations.
            level.roundlimit = 2;
            level.scorelimit = 0;
            // Accelerated administrative suicides can precede grenade tracking.
            // Satisfy that unrelated original death-handler field in this fixture.
            players = getentarray("player", "classname");
            for (i = 0; i < players.size; i++)
                if (!isdefined(players[i].throwingGrenade)) players[i].throwingGrenade = false;
        }
        if (request == "team_reset")
        {
            players = getentarray("player", "classname");
            for (i = 0; i < players.size; i++)
                if (players[i].isbot)
                {
                    players[i].integration_team = players[i].pers["team"];
                    players[i].pers["team"] = "spectator";
                }
        }
        if (request == "team_restore")
        {
            players = getentarray("player", "classname");
            for (i = 0; i < players.size; i++)
                if (players[i].isbot) players[i].pers["team"] = players[i].integration_team;
        }
        if (request == "human_spectator" || request == "human_switch" || request == "human_restore")
        {
            players = getentarray("player", "classname");
            for (i = 0; i < players.size; i++)
                if (!players[i].isbot)
                {
                    if (request == "human_spectator")
                    {
                        players[i].integration_team = players[i].pers["team"];
                        players[i] maps\mp\gametypes\_globallogic::menuSpectator();
                    }
                    else
                    {
                        team = players[i].integration_team;
                        if (request == "human_switch")
                        {
                            team = "axis";
                            if (players[i].pers["team"] == "axis") team = "allies";
                        }
                        if (team == "axis") players[i] maps\mp\gametypes\_globallogic::menuAxis();
                        else players[i] maps\mp\gametypes\_globallogic::menuAllies();
                    }
                }
        }
        bots = 0; bot_ready = 0; humans = 0; human_ready = 0;
        players = getentarray("player", "classname");
        for (i = 0; i < players.size; i++)
        {
            player = players[i];
            ready = isdefined(player.ready) && player.ready;
            if (player.isbot) { bots++; if (ready) bot_ready++; }
            else { humans++; if (ready) human_ready++; }
        }
        over = isdefined(level.ready_up_over) && level.ready_up_over;
        phase = "unset";
        if (isdefined(game["state"])) phase = game["state"];
        rounds = -1;
        if (isdefined(game["roundsplayed"])) rounds = game["roundsplayed"];
        eligible = 0; pending = 0;
        if (isdefined(level.readyup_humans)) eligible = level.readyup_humans;
        if (isdefined(level.not_ready_count)) pending = level.not_ready_count;
        message = "PROMOD_RUNTIME " + request + " map=" + getdvar("mapname") +
            " over=" + int(over) + " bots=" + bots + " bot_ready=" + bot_ready +
            " humans=" + humans + " human_ready=" + human_ready +
            " phase=" + phase + " rounds=" + rounds +
            " eligible=" + eligible + " pending=" + pending +
            " rdyup=" + int(isdefined(level.rdyup) && level.rdyup);
        logprint(message + "\n");
        setdvar("integration_snapshot", message);
    }
}
