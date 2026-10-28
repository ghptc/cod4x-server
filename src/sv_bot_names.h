/* Bounded Bot Warfare botnames.txt parsing. AGPL-3.0-or-later. */
#ifndef SV_BOT_NAMES_H
#define SV_BOT_NAMES_H
#include <stddef.h>
#define BOT_NAMES_BYTES 8192
#define BOT_NAME_BYTES 32
/* Only plain ASCII display names: no colors, controls or userinfo delimiters.
 * Reject overlong lines instead of truncating two distinct names into one. */
static int BotName_Next(const char **cursor, const char *end, char name[BOT_NAME_BYTES])
{
    while (*cursor < end) {
        const char *start = *cursor, *stop;
        size_t length, i;
        int valid = 1;
        while (*cursor < end && **cursor != '\n') ++*cursor;
        stop = *cursor;
        if (*cursor < end) ++*cursor;
        if (stop > start && stop[-1] == '\r') --stop;
        while (start < stop && *start == ' ') ++start;
        while (stop > start && stop[-1] == ' ') --stop;
        length = (size_t)(stop - start);
        if (!length || length >= BOT_NAME_BYTES) continue;
        for (i = 0; i < length; ++i) {
            unsigned char c = (unsigned char)start[i];
            if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                  (c >= '0' && c <= '9') || c == ' ' || c == '.' || c == '-')) valid = 0;
        }
        if (!valid) continue;
        for (i = 0; i < length; ++i) name[i] = start[i];
        name[length] = 0;
        return 1;
    }
    return 0;
}
#endif
