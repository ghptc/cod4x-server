// Allied native clients for Before the Dawn. Original integration, AGPL-3.0-or-later.
// Vendor zombie navigation remains authoritative and is only read here.
init()
{
    setdvar("bot_ai_ready", 0);
    if (!getdvarint("btd_allies_enable") || getdvar("g_gametype") != "war" || getdvarint("sv_pure") != 1)
        return;
    level endon("game_ended");
    level.btd_ally_sequence = 0;
    while (!isdefined(level.waypointcount) || level.waypointcount < 1) wait 0.1;
    // Register before enabling native creation, so no connect notification is lost.
    level thread connections();
    level thread ended();
    setdvar("bot_ai_ready", 1);
    players = getentarray("player", "classname");
    for (i = 0; i < players.size; i++)
        if (players[i].isbot) players[i] thread attach();
}

ended()
{
    level waittill("game_ended");
    setdvar("bot_ai_ready", 0);
    players = getentarray("player", "classname");
    for (i = 0; i < players.size; i++)
        if (players[i].isbot) players[i] botstop();
}

connections()
{
    level endon("game_ended");
    for (;;)
    {
        level waittill("connected", player);
        if (isdefined(player) && player.isbot) player thread attach();
    }
}

human_players()
{
    result = [];
    players = getentarray("player", "classname");
    for (i = 0; i < players.size; i++)
        if (!players[i].isbot) result[result.size] = players[i];
    return result;
}

attach()
{
    self endon("disconnect");
    level endon("game_ended");
    if (isdefined(self.btd_ally_attached)) return;
    self.btd_ally_attached = true;
    self.btd_ally = true;
    // Cycle 3 easy / 2 medium; never modify vendor zombie difficulty.
    self.btd_ally_skill = "easy";
    if (level.btd_ally_sequence % 5 >= 3) self.btd_ally_skill = "medium";
    level.btd_ally_sequence++;
    self.pers["isBot"] = true;
    wait 1;
    self maps\mp\gametypes\_globallogic::menuAllies();
    wait 0.2;
    // Vendor validates class and grants its normal weapons/ammunition.
    self maps\mp\gametypes\_globallogic::menuClass("specops_mp,0");
    self thread think();
}

think()
{
    self endon("disconnect");
    level endon("game_ended");
    previous = undefined;
    acquired = 0;
    next_shot = 0;
    next_route = 0;
    for (;;)
    {
        self botaction("-fire");
        if (!getdvarint("btd_allies_enable") || !isalive(self) || self.sessionstate != "playing")
        {
            self botstop();
            previous = undefined;
            wait 0.2;
            continue;
        }
        target = self target_zombie();
        now = gettime();
        reaction = 1400;
        interval = 1000;
        error = 65;
        if (self.btd_ally_skill == "medium")
        {
            reaction = 900;
            interval = 700;
            error = 40;
        }
        if (!isdefined(target) || !isdefined(previous) || target != previous)
        {
            acquired = now;
            previous = target;
        }
        if (now >= next_route)
        {
            self follow_human();
            next_route = now + 1000;
        }
        if (isdefined(target))
        {
            aim = target.origin + (randomfloatrange(0 - error, error), randomfloatrange(0 - error, error), 32);
            self botlookat(aim, 0.3);
            weapon = self select_weapon();
            self botweapon(weapon);
            if (self getweaponammoclip(weapon) <= 0)
            {
                self botaction("+reload");
                wait 2;
                self botaction("-reload");
            }
            else if (now - acquired >= reaction && now >= next_shot)
            {
                // Let the native turn finish before any firing pulse: do not
                // sweep fire across players while turning toward a zombie.
                wait 0.35;
                if (self safe_shot(aim, target))
                {
                    self botaction("+fire");
                    wait 0.1;
                    self botaction("-fire");
                }
                next_shot = gettime() + interval;
            }
        }
        wait 0.1;
    }
}

target_zombie()
{
    zombies = getentarray("zom", "targetname");
    best = undefined;
    range = 900;
    for (i = 0; i < zombies.size; i++)
    {
        zombie = zombies[i];
        if (!isdefined(zombie.health) || zombie.health <= 0) continue;
        separation = distance(self.origin, zombie.origin);
        if (separation >= range) continue;
        trace = bullettrace(self geteye(), zombie.origin + (0, 0, 32), true, self);
        // Script-model damage surfaces may not be returned as the trace entity.
        // A clear segment to the zombie is also visible; player blockers remain solid.
        if (trace["fraction"] == 1 || (isdefined(trace["entity"]) && trace["entity"] == zombie))
        {
            best = zombie;
            range = separation;
        }
    }
    return best;
}

safe_shot(aim, target)
{
    if (!isalive(self) || self.sessionstate != "playing" || !getdvarint("btd_allies_enable")) return false;
    // Trace with player collision: never intentionally fire through a human.
    trace = bullettrace(self geteye(), aim, true, self);
    if (isdefined(trace["entity"]) && isplayer(trace["entity"])) return false;
    // Native aim interpolation may still be turning from the previous target.
    direction = anglestoforward(self getplayerangles());
    actual = bullettrace(self geteye(), self geteye() + direction * 1000, true, self);
    if (isdefined(actual["entity"]) && isplayer(actual["entity"])) return false;
    return isdefined(target) && isdefined(target.health) && target.health > 0;
}

follow_human()
{
    humans = human_players();
    leader = undefined;
    range = 999999;
    for (i = 0; i < humans.size; i++)
    {
        if (!isalive(humans[i]) || humans[i].sessionstate != "playing") continue;
        separation = distance(self.origin, humans[i].origin);
        if (separation < range) { leader = humans[i]; range = separation; }
    }
    if (!isdefined(leader) || range < 220) { self stop_movement(); return; }
    trace = bullettrace(self.origin + (0, 0, 40), leader.origin + (0, 0, 40), false, self);
    if (trace["fraction"] == 1) { self botmoveto(leader.origin); return; }
    start = self nearest_node(self.origin, true);
    goal = self nearest_node(leader.origin, false);
    if (start < 0 || goal < 0) { self stop_movement(); return; }
    // Local BFS arrays, no writes to the vendor graph or its search metadata.
    queue = []; parent = []; queue[0] = start; parent[start] = start;
    for (head = 0; head < queue.size && !isdefined(parent[goal]); head++)
    {
        node = queue[head];
        children = level.waypoints[node].children;
        for (j = 0; j < children.size; j++)
        {
            child = children[j];
            if (child < 0 || child >= level.waypointcount || isdefined(parent[child])) continue;
            parent[child] = node;
            queue[queue.size] = child;
        }
    }
    if (!isdefined(parent[goal])) { self stop_movement(); return; }
    next = goal;
    while (parent[next] != start && parent[next] != next) next = parent[next];
    destination = level.waypoints[next].origin;
    if (distance(self.origin, level.waypoints[start].origin) > 70) destination = level.waypoints[start].origin;
    self botmoveto(destination);
}

select_weapon()
{
    weapon = self getcurrentweapon();
    if (weapon == "none" || weapon == "" || weapon == "defaultweapon_mp" ||
        (self getweaponammoclip(weapon) <= 0 && self getweaponammostock(weapon) <= 0))
    {
        owned = self getweaponslistprimaries();
        for (i = 0; i < owned.size; i++)
        {
            candidate = owned[i];
            if (self getweaponammoclip(candidate) > 0 || self getweaponammostock(candidate) > 0)
                return candidate;
        }
    }
    return weapon;
}

stop_movement()
{
    weapon = self select_weapon();
    self botstop();
    self botweapon(weapon);
}

nearest_node(origin, visible)
{
    best = -1; range = 999999;
    for (i = 0; i < level.waypointcount; i++)
    {
        candidate = level.waypoints[i].origin;
        separation = distance(origin, candidate);
        if (separation >= range) continue;
        if (visible)
        {
            trace = bullettrace(origin + (0, 0, 40), candidate + (0, 0, 40), false, self);
            if (trace["fraction"] < 1) continue;
        }
        best = i; range = separation;
    }
    return best;
}
