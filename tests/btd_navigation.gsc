// Disposable native qualification fixture. Never packaged in a server image.
main()
{
    marker = tablelookup("waypoints/PeZBOT_WP_4.csv", 0, 4928, 1);
    println("BTD_NAV_MARKER value=[" + marker + "] length=" + marker.size);
    wait 4;
    if (getdvar("btd_nav_scenario") == "idle")
    {
        setdvar("btd_nav_nodes", level.waypointcount);
        setdvar("btd_nav_map", getdvar("mapname"));
        return;
    }
    setdvar("btd_nav_nodes", level.waypointcount);
    setdvar("btd_nav_phase", "spawn_links");
    if (level.waypointcount < 2) { fail("nodes"); return; }
    linked_spawns = 0;
    max_spawn_link = 0;
    for (i = 0; i < level.zomspawns.size; i++)
    {
        origin = level.zomspawns[i].origin;
        if (!isdefined(supported_floor(origin))) { fail("spawn_floor"); return; }
        closest_link = 1000000;
        for (j = 0; j < level.waypointcount; j++)
        {
            node = level.waypoints[j].origin;
            separation = distance(origin, node);
            if (separation > 256 || separation >= closest_link) continue;
            trace = bullettrace(origin + (0, 0, 30), node + (0, 0, 30), false, undefined);
            if (trace["fraction"] >= 1) closest_link = separation;
        }
        if (closest_link > 256) { fail("spawn_visibility"); return; }
        linked_spawns++;
        if (closest_link > max_spawn_link) max_spawn_link = closest_link;
    }
    if (linked_spawns != 25) { fail("spawn_count"); return; }
    setdvar("btd_nav_linked_spawns", linked_spawns);
    setdvar("btd_nav_max_spawn_link", max_spawn_link);
    setdvar("btd_nav_phase", "spawn_respawn");
    player = addtestclient("NavigationFixture");
    player.pers["isBot"] = true;
    wait 1;
    player maps\mp\gametypes\_globallogic::menuAllies();
    wait 1;
    player maps\mp\gametypes\_globallogic::menuClass("specops_mp,0");
    if (!player await_spawn()) { fail("spawn"); return; }
    guardian = addtestclient("RespawnWitness");
    guardian.pers["isBot"] = true;
    wait 1;
    guardian maps\mp\gametypes\_globallogic::menuAllies();
    wait 1;
    guardian maps\mp\gametypes\_globallogic::menuClass("specops_mp,0");
    if (!guardian await_spawn()) { fail("witness_spawn"); return; }
    wait 1;
    player suicide();
    wait 2;
    if (!player await_spawn()) { fail("respawn"); return; }
    setdvar("btd_nav_respawn", "passed");
    kick(guardian getentitynumber());
    player.maxhealth = 100000;
    player.health = 100000;
    player.btd_nav_fixture = true;
    level.btd_nav_damage_callback = level.callbackPlayerDamage;
    level.callbackPlayerDamage = ::observe_player_damage;
    weapons = player getweaponslistprimaries();
    if (!weapons.size) { fail("loadout"); return; }
    player.btd_nav_weapon = weapons[0];
    player botstop();
    player freezecontrols(true);
    // Use authored nodes and collision-supported ground, never invented positions.
    setdvar("btd_nav_phase", "camping");
    highest = undefined;
    lowest = 1000000;
    for (i = 0; i < level.waypointcount; i++)
    {
        floor = supported_floor(level.waypoints[i].origin);
        if (!isdefined(floor)) continue;
        if (!isdefined(highest) || floor[2] > highest[2]) highest = floor;
        if (floor[2] < lowest) lowest = floor[2];
    }
    if (!isdefined(highest)) { fail("floor"); return; }
    player setorigin(highest + (0, 0, 1));
    wait 2;
    settled = player.origin;
    hp = player.health;
    setdvar("btd_nav_elevation", settled[2] - lowest);
    if (distance2d(settled, highest) > 16 || settled[2] < highest[2] - 8 ||
        settled[2] > highest[2] + 8 || settled[2] - lowest < 128)
    { fail("elevated_position"); return; }
    if (isdefined(player.campingtime)) { fail("camp_timer"); return; }
    triggers = getentarray("trigger_radius", "classname");
    for (i = 0; i < triggers.size; i++)
        if (isdefined(triggers[i].goto)) { fail("camp_trigger"); return; }
    wait 6;
    if (distance(player.origin, settled) > 8 || player.health != hp ||
        isdefined(player.campingtime)) { fail("camping"); return; }
    setdvar("btd_nav_camping", "passed");
    if (getdvarint("btd_anticamp") != 0) { fail("classic_policy"); return; }

    setdvar("btd_nav_phase", "chase");
    destination = undefined;
    for (i = 0; i < level.waypointcount; i++)
    {
        floor = supported_floor(level.waypoints[i].origin);
        if (!isdefined(floor)) continue;
        d = distance(level.zomspawns[0].origin, floor);
        if (d < 500 || d > 1800) continue;
        trace = bullettrace(level.zomspawns[0].origin + (0, 0, 30),
            floor + (0, 0, 30), false, undefined);
        if (trace["fraction"] >= 1) continue;
        destination = floor;
        break;
    }
    if (!isdefined(destination)) { fail("obstacle_pair"); return; }
    player setorigin(destination + (0, 0, 1));
    wait 1;
    setdvar("btd_nav_player_position", player.origin);
    zombies = [];
    for (i = 0; i < 600; i++)
    {
        zombies = getentarray("zom", "targetname");
        if (zombies.size > 0 && isdefined(zombies[0].health)) break;
        wait 0.1;
    }
    if (!zombies.size) { fail("zombie_spawn"); return; }
    target = zombies[0];
    level.btd_nav_tracked = target;
    start = target.origin;
    initial = distance(start, player.origin);
    trace = bullettrace(start + (0, 0, 30), player.origin + (0, 0, 30), false, target);
    if (trace["fraction"] >= 1 || initial < 400) { fail("obstacle_start"); return; }
    setdvar("btd_nav_blocked_direct_path", "passed");
    setdvar("btd_nav_initial_distance", initial);
    moved = 0;
    closest = initial;
    usedwaypoint = false;
    previous = start;
    route_length = 0;
    previous_wp = -1;
    waypoint_changes = 0;
    for (i = 0; i < 900; i++)
    {
        if (!isdefined(target)) { fail("tracked_zombie_lost"); return; }
        step = distance(previous, target.origin);
        if (step > 100) { fail("navigation_jump"); return; }
        segment = bullettrace(previous + (0, 0, 30), target.origin + (0, 0, 30), false, target);
        if (segment["fraction"] < 1) { fail("navigation_wall_crossing"); return; }
        if (i % 20 == 0)
            println("BTD_NAV_SAMPLE tick=" + i + " pos=" + target.origin + " step=" + step +
                " trace=" + segment["fraction"] + " wp=" + target.currentStaticWp);
        route_length += step;
        previous = target.origin;
        displacement = distance(start, target.origin);
        if (displacement > moved) moved = displacement;
        separation = distance(target.origin, player.origin);
        if (separation < closest) closest = separation;
        if (isdefined(target.currentStaticWp) && target.currentStaticWp >= 0)
        {
            usedwaypoint = true;
            if (target.currentStaticWp != previous_wp)
            {
                waypoint_changes++;
                previous_wp = target.currentStaticWp;
            }
        }
        if (getdvar("btd_nav_melee") == "passed" && moved > 256 &&
            closest < initial - 200 && waypoint_changes >= 2 && route_length > initial * 1.05) break;
        wait 0.1;
    }
    setdvar("btd_nav_displacement", moved);
    setdvar("btd_nav_closest_distance", closest);
    setdvar("btd_nav_used_waypoint", usedwaypoint);
    setdvar("btd_nav_route_length", route_length);
    setdvar("btd_nav_waypoint_changes", waypoint_changes);
    if (getdvar("btd_nav_melee") != "passed" || moved <= 256 ||
        closest >= initial - 200 || waypoint_changes < 2 || route_length <= initial * 1.05) { fail("chase"); return; }
    setdvar("btd_nav_chase", "passed");
    setdvar("btd_nav_phase", "native_fire_wave");
    player freezecontrols(false);
    player botstop();
    level.btd_nav_bullet_hits = 0;
    initial_kills = player.kills;
    for (i = 0; i < 1200; i++)
    {
        if (level.currentwave >= 2) break;
        zombies = getentarray("zom", "targetname");
        nearest = undefined;
        nearest_distance = 1000000;
        for (j = 0; j < zombies.size; j++)
        {
            zombie = zombies[j];
            if (!isdefined(zombie.health) || zombie.health <= 0) continue;
            if (!isdefined(zombie.btd_nav_observed))
            {
                zombie.btd_nav_observed = true;
                zombie thread observe_zombie_damage(player);
            }
            separation = distance(zombie.origin, player.origin);
            if (separation < nearest_distance)
            {
                nearest_distance = separation;
                nearest = zombie;
            }
        }
        if (!isdefined(nearest))
        {
            player botaction("-fire");
            wait 0.1;
            continue;
        }
        // A stationary client can overlap melee attackers and spend its normal
        // ammunition firing through nearby geometry. Walk to a collision-visible
        // authored node, using native player input, instead of moving entities.
        if (nearest_distance < 140 && (!isdefined(player.btd_nav_retreat) ||
            distance2d(player.origin, player.btd_nav_retreat) < 40))
        {
            retreat = undefined;
            for (k = 0; k < level.waypointcount; k++)
            {
                candidate = level.waypoints[k].origin;
                separation = distance(player.origin, candidate);
                if (separation < 200 || separation > 450 ||
                    candidate[2] > player.origin[2] + 80 || candidate[2] < player.origin[2] - 80)
                    continue;
                if (distance(candidate, nearest.origin) < nearest_distance + 150) continue;
                clear = bullettrace(player.origin + (0, 0, 40), candidate + (0, 0, 40), false, player);
                if (clear["fraction"] < 1) continue;
                retreat = candidate;
                break;
            }
            if (isdefined(retreat))
            {
                player.btd_nav_retreat = retreat;
                player botmoveto(retreat);
                println("BTD_NAV_NATIVE_PLAYER_MOVE destination=" + retreat);
            }
        }
        weapon = player.btd_nav_weapon;
        player botweapon(weapon);
        player botlookat(nearest.origin + (0, 0, 35), 0.1);
        if (i % 50 == 0)
            println("BTD_NAV_FIRE tick=" + i + " weapon=" + weapon + " ammo=" +
                player getweaponammoclip(weapon) + " stock=" + player getweaponammostock(weapon) +
                " kills=" + (player.kills - initial_kills) + " zombies=" + zombies.size +
                " targetpos=" + nearest.origin + " targethp=" + nearest.health +
                " wp=" + nearest.currentStaticWp + " playerpos=" + player.origin);
        if (player getweaponammoclip(weapon) <= 0)
        {
            player botaction("-fire");
            player botaction("+reload");
            wait 2;
            player botaction("-reload");
        }
        else player botaction("+fire");
        wait 0.1;
    }
    player botstop();
    setdvar("btd_nav_bullet_hits", level.btd_nav_bullet_hits);
    setdvar("btd_nav_bullet_kills", player.kills - initial_kills);
    if (level.currentwave < 2 || level.btd_nav_bullet_hits < 1 || player.kills - initial_kills < 5) { fail("native_wave"); return; }
    setdvar("btd_nav_wave", "passed");
    setdvar("btd_nav_result", "passed");
}

await_spawn()
{
    for (i = 0; i < 200; i++)
    {
        if (isalive(self) && self.sessionstate == "playing") return true;
        wait 0.1;
    }
    return false;
}

supported_floor(point)
{
    trace = bullettrace(point + (0, 0, 32), point - (0, 0, 80), false, undefined);
    if (trace["fraction"] >= 1) return undefined;
    return trace["position"];
}

observe_zombie_damage(player)
{
    for (;;)
    {
        self waittill("damage", amount, attacker, direction, point, means);
        if (isdefined(attacker) && attacker == player && amount > 0 &&
            (means == "MOD_RIFLE_BULLET" || means == "MOD_PISTOL_BULLET"))
            level.btd_nav_bullet_hits++;
    }
}

observe_player_damage(inflictor, attacker, amount, flags, means, weapon, point, direction, hitloc, offset)
{
    before = self.health;
    self [[level.btd_nav_damage_callback]](inflictor, attacker, amount, flags,
        means, weapon, point, direction, hitloc, offset);
    if (isdefined(self.btd_nav_fixture) && self.health < before &&
        isdefined(inflictor) && isdefined(level.btd_nav_tracked) &&
        inflictor == level.btd_nav_tracked && means == "MOD_MELEE")
        setdvar("btd_nav_melee", "passed");
}

fail(reason)
{
    setdvar("btd_nav_result", "failed_" + reason);
}
