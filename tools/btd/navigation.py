#!/usr/bin/env python3
"""Validate private Killhouse waypoint tables without redistributing map data.

This proves parsing and graph structure, not engine collision clearance or gameplay.
The original stringtable has no angle column; angles are not invented here.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import re

MAP = 'mp_killhouse'
OFFSET = 4827
COUNT = 101
BROKEN_TERMINATOR = 'end '
TERMINATOR = 'end'
NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?')
MAX_NATIVE_FLOAT = 3.4028234663852886e38


def vector(value):
    """Parse exactly three finite numeric coordinates, failing on missing fields."""
    tokens = [item for item in value.split(' ') if item] if isinstance(value, str) else value
    if not isinstance(tokens, (list, tuple)) or len(tokens) != 3:
        raise ValueError('Expected exactly three coordinates')
    if any(isinstance(item, bool) or
           (isinstance(item, str) and not NUMBER.fullmatch(item)) for item in tokens):
        raise ValueError('Invalid numeric coordinate')
    try:
        result = tuple(float(item) for item in tokens)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid numeric coordinate') from exc
    if not all(math.isfinite(item) and abs(item) <= MAX_NATIVE_FLOAT for item in result):
        raise ValueError('Coordinates must be finite native floats')
    return result


def validate_rows(rows, *, offset=OFFSET, count=COUNT, spawns=None,
                  max_spawn_distance=None):
    """Validate only this map's exact keys, preserving unrelated table content.

    `rows` is a CSV reader or sequence of four string cells per row. Caller must
    supply an already corrected terminal marker; the validator does not repair
    or skip malformed graph entries. Optional spawns are index-to-XYZ mappings.
    A nearest-node association is geometric proximity, not a collision trace.
    """
    if count < 1 or offset < 0:
        raise ValueError('Invalid graph bounds')
    wanted = {str(offset + index) for index in range(count + 1)}
    selected = {}
    for row in rows:
        if not row or row[0] not in wanted:
            continue
        if len(row) != 4:
            raise ValueError('Expected four waypoint columns')
        if row[0] in selected:
            raise ValueError('Duplicate waypoint key: ' + row[0])
        selected[row[0]] = row
    if set(selected) != wanted:
        raise ValueError('Missing waypoint keys: ' + ', '.join(sorted(wanted - set(selected))))
    terminal = selected[str(offset + count)]
    if terminal[1:] != [TERMINATOR, '0', '0']:
        raise ValueError('Invalid map terminal marker')
    origins, children = [], []
    for index in range(count):
        row = selected[str(offset + index)]
        origins.append(vector(row[1]))
        tokens = [item for item in row[2].split(' ') if item]
        if not tokens or any(not re.fullmatch(r'[0-9]+', item) for item in tokens):
            raise ValueError('Invalid child index syntax')
        linked = [int(item) for item in tokens]
        if len(set(linked)) != len(linked):
            raise ValueError('Duplicate child index')
        if any(item < 0 or item >= count or item == index for item in linked):
            raise ValueError('Out-of-range or self child index')
        if row[3] != 'stand':
            raise ValueError('Unexpected Killhouse waypoint type')
        children.append(linked)
    if len(set(origins)) != count:
        raise ValueError('Duplicate waypoint origin')
    for index, linked in enumerate(children):
        if any(index not in children[other] for other in linked):
            raise ValueError('Nonreciprocal child edge')
    seen, todo = {0}, [0]
    while todo:
        for other in children[todo.pop()]:
            if other not in seen:
                seen.add(other)
                todo.append(other)
    if len(seen) != count:
        raise ValueError('Disconnected waypoint graph')
    report = {'map': MAP, 'offset': offset, 'nodes': count,
              'directed_edges': sum(map(len, children)), 'connected': True,
              'reciprocal': True, 'angle_column': False,
              'bounds': [[min(v[i] for v in origins), max(v[i] for v in origins)]
                         for i in range(3)],
              'geometry_qualified': False, 'gameplay_qualified': False}
    if max_spawn_distance is not None and (not math.isfinite(max_spawn_distance) or max_spawn_distance <= 0):
        raise ValueError('Invalid maximum spawn distance')
    if spawns is not None:
        if set(spawns) != set(range(25)):
            raise ValueError('Expected all 25 distinct vendor spawn indices')
        associations = []
        for index in range(25):
            origin = vector(spawns[index])
            nearest = min(range(count), key=lambda n: math.dist(origin, origins[n]))
            distance = math.dist(origin, origins[nearest])
            if max_spawn_distance is not None and distance > max_spawn_distance:
                raise ValueError('Spawn exceeds specified nearest-node distance')
            associations.append({'spawn': index, 'node': nearest, 'distance': distance})
        report['spawn_associations'] = associations
        report['spawn_distance_max'] = max(item['distance'] for item in associations)
    return report


def spawn_points(source):
    """Read only the original Killhouse branch from a private pinned GSC input."""
    marker = 'else if(getDvar("mapname") == "mp_killhouse")'
    if source.count(marker) != 1:
        raise ValueError('Missing or ambiguous Killhouse spawn branch')
    branch = source.split(marker, 1)[1].split('// Overgrown', 1)[0]
    matches = re.findall(r'zomspawnpoint\[(\d+)\]\s*=\s*\(([^)]+)\);', branch)
    result = {}
    for index, raw in matches:
        index = int(index)
        if index in result:
            raise ValueError('Duplicate spawn index')
        result[index] = vector(raw.split(','))
    if set(result) != set(range(25)):
        raise ValueError('Expected all 25 vendor spawn points')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table', type=Path, required=True, help='Private CSV export of waypoint table 4 with the terminal marker corrected')
    parser.add_argument('--spawns', type=Path, help='Private original survival spawn GSC source')
    parser.add_argument('--max-spawn-distance', type=float, help='Optional explicit geometric proximity gate; not proof of collision clearance')
    args = parser.parse_args()
    try:
        spawns = spawn_points(args.spawns.read_text()) if args.spawns else None
        # Stringtable exports may include non-UTF8 cells belonging to other maps.
        # Native lookup also selects by exact global key; those cells stay private.
        with args.table.open(encoding='latin1', newline='') as stream:
            report = validate_rows(csv.reader(stream), spawns=spawns,
                                   max_spawn_distance=args.max_spawn_distance)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Navigation validation failed: {exc}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
