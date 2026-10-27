// Disposable observer and synthetic human input driver; never packaged.
main()
{
    wait 5;
    level.btd_allies_test_hits = 0;
    level.btd_allies_test_melee = 0;
    level.btd_allies_test_human_hits = 0;
    level.btd_allies_test_human_damage = 0;
    level.btd_allies_test_original_damage = level.callbackPlayerDamage;
    level.callbackPlayerDamage = ::observe_player_damage;
    level thread observer();
    level thread requests();
    level thread ended();
    setdvar("btd_allies_test_ready", "1");
}

observer()
{
    for (;;)
    {
        players = getentarray("player", "classname");
        for (i = 0; i < players.size; i++)
        {
            player = players[i];
            if (player.isbot && isdefined(player.btd_ally) && isalive(player))
            {
                weapon = player getcurrentweapon();
                clip = player getweaponammoclip(weapon);
                target = player btd_allies::target_zombie();
                if (isdefined(target))
                {
                    player.btd_allies_test_target = target getentitynumber();
                    player.btd_allies_test_target_time = gettime();
                }
                if (isdefined(player.btd_allies_test_last_weapon) && player.btd_allies_test_last_weapon == weapon &&
                    clip < player.btd_allies_test_last_clip && isdefined(player.btd_allies_test_target_time) &&
                    gettime() - player.btd_allies_test_target_time < 1000)
                    println("BTD_ALLIES_NATIVE_SHOT slot=" + player getentitynumber() + " weapon=" + weapon +
                        " before=" + player.btd_allies_test_last_clip + " after=" + clip + " target=" + player.btd_allies_test_target);
                player.btd_allies_test_last_weapon = weapon;
                player.btd_allies_test_last_clip = clip;
            }
            if (!player.isbot && !isdefined(player.btd_allies_test_human))
            {
                player.btd_allies_test_human = true;
                player thread synthetic_human();
            }
        }
        zombies = getentarray("zom", "targetname");
        for (i = 0; i < zombies.size; i++)
        {
            if (!isdefined(zombies[i].btd_allies_test_observed))
            {
                zombies[i].btd_allies_test_observed = true;
                zombies[i] thread observe_zombie_damage();
            }
        }
        wait 0.05;
    }
}

synthetic_human()
{
    self endon("disconnect");
    wait 0.5;
    self maps\mp\gametypes\_globallogic::menuAllies();
    wait 0.5;
    self maps\mp\gametypes\_globallogic::menuClass("specops_mp,0");
    for (;;)
    {
        if (!isalive(self) || self.sessionstate != "playing") { wait 0.1; continue; }
        if (getdvar("btd_allies_test_mortal") != "1")
        {
            self.maxhealth = 100000;
            self.health = 100000;
        }
        zombies = getentarray("zom", "targetname");
        nearest = undefined;
        separation = 1000000;
        for (i = 0; i < zombies.size; i++)
        {
            zombie = zombies[i];
            if (!isdefined(zombie.health) || zombie.health <= 0) continue;
            range = distance(self.origin, zombie.origin);
            if (range >= separation) continue;
            trace = bullettrace(self.origin + (0,0,55), zombie.origin + (0,0,35), false, self);
            if (trace["fraction"] < 1 && (!isdefined(trace["entity"]) || trace["entity"] != zombie)) continue;
            nearest = zombie;
            separation = range;
        }
        if (isdefined(nearest)) self setplayerangles(vectortoangles(nearest.origin + (0,0,35) - (self.origin + (0,0,55))));
        setdvar("btd_allies_test_fire_" + self getentitynumber(), isdefined(nearest));
        weapons = self getweaponslistprimaries();
        if (weapons.size) setdvar("btd_allies_test_reload_" + self getentitynumber(), self getweaponammoclip(weapons[0]) == 0);
        wait 0.05;
    }
}

requests()
{
    for (;;)
    {
        request = getdvar("btd_allies_test_request");
        if (request != "")
        {
            setdvar("btd_allies_test_request", "");
            if (request == "all_humans_die")
            {
                players = getentarray("player", "classname");
                for (i = 0; i < players.size; i++)
                    if (!players[i].isbot && isalive(players[i])) players[i] suicide();
            }
            if (request == "protection") protection();
            snapshot(request);
        }
        wait 0.05;
    }
}

protection()
{
    players = getentarray("player", "classname");
    human = undefined;
    for (i = 0; i < players.size; i++)
        if (!players[i].isbot && isalive(players[i])) human = players[i];
    if (!isdefined(human)) return;
    zombies = getentarray("zom", "targetname");
    original = human.origin;
    for (i = 0; i < players.size; i++)
    {
        ally = players[i];
        if (!ally.isbot || !isalive(ally) || !isdefined(ally.btd_ally)) continue;
        for (j = 0; j < zombies.size; j++)
        {
            target = zombies[j];
            if (!isdefined(target.health) || target.health <= 0) continue;
            // Use a real live target and require an unblocked positive control
            // before placing the synthetic human into the native firing ray.
            aim = target.origin + (0,0,32);
            ally setplayerangles(vectortoangles(aim - ally geteye()));
            baseline = ally btd_allies::safe_shot(aim, target);
            if (!baseline) continue;
            forward = anglestoforward(ally getplayerangles());
            human setorigin(ally.origin + forward * 60);
            trace = bullettrace(ally geteye(), ally geteye() + forward * 1000, true, ally);
            blocked = isdefined(trace["entity"]) && trace["entity"] == human;
            guarded = ally btd_allies::safe_shot(aim, target);
            guarded = !guarded;
            human setorigin(original);
            if (blocked && guarded)
            {
                println("BTD_ALLIES_PROTECTION baseline=1 blocked=1 guarded=1");
                return;
            }
        }
    }
    println("BTD_ALLIES_PROTECTION no_clear_live_trial=1");
}

ended()
{
    level waittill("game_ended");
    snapshot("eliminated");
    println("BTD_ALLIES_HUMAN_ELIMINATION ended=1");
}

snapshot(label)
{
    players = getentarray("player", "classname");
    allies = 0; alive = 0; humans = 0; human_alive = 0; kills = 0; human_kills = 0;
    for (i = 0; i < players.size; i++)
    {
        player = players[i];
        if (!player.isbot)
        {
            humans++;
            if (isalive(player) && player.sessionstate == "playing") human_alive++;
            if (isdefined(player.kills)) human_kills += player.kills;
            println("BTD_ALLIES_PLAYER label=" + label + " slot=" + player getentitynumber() +
                " human=1 alive=" + isalive(player) + " state=" + player.sessionstate);
            continue;
        }
        if (!isdefined(player.btd_ally) || !player.btd_ally) continue;
        allies++;
        if (isalive(player) && player.sessionstate == "playing") alive++;
        if (isdefined(player.kills)) kills += player.kills;
        weapon = player getcurrentweapon();
        target = player btd_allies::target_zombie();
        target_number = -1;
        if (isdefined(target)) target_number = target getentitynumber();
        println("BTD_ALLIES_PLAYER label=" + label + " slot=" + player getentitynumber() +
            " human=0 alive=" + isalive(player) + " state=" + player.sessionstate + " skill=" + player.btd_ally_skill + " origin=" + player.origin +
            " weapon=" + weapon + " clip=" + player getweaponammoclip(weapon) + " target=" + target_number);
    }
    wave = 0;
    if (isdefined(level.currentwave)) wave = level.currentwave;
    canjoin = false;
    if (isdefined(level.canjoin)) canjoin = level.canjoin == "yes";
    total = 0;
    if (isdefined(level.totalzomsinwave)) total = level.totalzomsinwave;
    println("BTD_ALLIES_SNAPSHOT label=" + label + " allies=" + allies + " alive=" + alive +
        " humans=" + humans + " human_alive=" + human_alive + " kills=" + kills + " human_kills=" + human_kills + " wave=" + wave +
        " canjoin=" + canjoin + " total=" + total + " hits=" + level.btd_allies_test_hits + " melee=" + level.btd_allies_test_melee +
        " human_hits=" + level.btd_allies_test_human_hits + " human_damage=" + level.btd_allies_test_human_damage);
}

observe_zombie_damage()
{
    self endon("death");
    for (;;)
    {
        self waittill("damage", amount, attacker, direction, point, means);
        if (!isdefined(attacker) || !isplayer(attacker) || amount <= 0) continue;
        if (means != "MOD_RIFLE_BULLET" && means != "MOD_PISTOL_BULLET") continue;
        if (attacker.isbot && isdefined(attacker.btd_ally) && attacker.btd_ally)
        {
            level.btd_allies_test_hits++;
            println("BTD_ALLIES_NATIVE_HIT slot=" + attacker getentitynumber() + " skill=" + attacker.btd_ally_skill + " amount=" + amount);
        }
        else if (!attacker.isbot) level.btd_allies_test_human_hits++;
    }
}

observe_player_damage(inflictor, attacker, amount, flags, means, weapon, point, direction, hitloc, offset)
{
    before = self.health;
    self [[level.btd_allies_test_original_damage]](inflictor, attacker, amount, flags, means, weapon, point, direction, hitloc, offset);
    if (!isdefined(self) || !isdefined(self.health)) return;
    if (self.isbot && isdefined(self.btd_ally) && self.btd_ally && self.health < before &&
        isdefined(inflictor) && isdefined(inflictor.targetname) && inflictor.targetname == "zom" && means == "MOD_MELEE")
        level.btd_allies_test_melee++;
    if (!self.isbot && self.health < before && isdefined(attacker) && isplayer(attacker) && attacker.isbot)
        level.btd_allies_test_human_damage++;
}
