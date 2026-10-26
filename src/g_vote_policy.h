/* Native vote input validation. No console metacharacters or partial map names. */
#ifndef G_VOTE_POLICY_H
#define G_VOTE_POLICY_H
#include <string.h>

static inline int Vote_Identifier(const char *name)
{
    unsigned n = 0;
    for (; *name; ++name, ++n)
        if (!((*name >= 'a' && *name <= 'z') ||
              (*name >= 'A' && *name <= 'Z') ||
              (*name >= '0' && *name <= '9') || *name == '_'))
            return 0;
    return n > 0 && n < 64; /* MAX_QPATH */
}

static inline int Vote_MapInRotation(const char *rotation, const char *map)
{
    const char *key, *value;
    size_t keylen, len;
    if (!Vote_Identifier(map))
        return 0;
    /* Native rotation is a sequence of whitespace-separated key/value pairs.
       Unsupported syntax fails closed rather than broadening the allowlist. */
    while (*rotation)
    {
        rotation += strspn(rotation, " \t\r\n");
        key = rotation;
        keylen = strcspn(rotation, " \t\r\n");
        rotation += keylen;
        rotation += strspn(rotation, " \t\r\n");
        value = rotation;
        len = strcspn(rotation, " \t\r\n");
        rotation += len;
        if (keylen == 3 && !strncmp(key, "map", 3) &&
            strlen(map) == len && !strncmp(value, map, len))
            return 1;
    }
    return 0;
}
#endif
