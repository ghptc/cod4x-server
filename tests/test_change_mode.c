/* Exercise the actual nonmutating handler; no deployment boundary is linked. */
#include "../src/sv_cmds.c"
#undef assert
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>

static int power, argc, reads;
static const char *argument, *game;
static char response[1024];
int Cmd_Argc(void) { return argc; }
char *Cmd_Argv(int n) { return (char *)(n == 1 ? argument : "change_mode"); }
int Cmd_GetInvokerPower(void) { return power; }
const char *Cvar_VariableStringBuffer(const char *name, char *buffer, int size)
{
    assert(!strcmp(name, "fs_game")); ++reads;
    snprintf(buffer, size, "%s", game);
    return buffer;
}
void Com_Printf(conChannel_t channel, const char *format, ...)
{
    va_list args;
    (void)channel;
    va_start(args, format);
    vsnprintf(response, sizeof(response), format, args);
    va_end(args);
}
static void call(int count, const char *mode)
{
    argc = count; argument = mode; response[0] = '\0'; reads = 0;
    SV_ChangeMode_f();
}
int main(void)
{
    game = "mods/pml220";
    for (power = 0; power < 100; ++power) {
        call(1, ""); assert(strstr(response, "power 100") && !reads);
        call(2, "zombies"); assert(strstr(response, "power 100") && !reads);
    }
    power = 100;
    call(1, ""); assert(strstr(response, game) && strstr(response, "targets: none") && reads == 1);
    game = ""; call(1, ""); assert(strstr(response, "Current fs_game: main"));
    const char *valid[] = {"zombies", "promod", "hardcore", "unknown", "mode-2"};
    for (unsigned i = 0; i < sizeof(valid)/sizeof(*valid); ++i) {
        call(2, valid[i]); assert(strstr(response, "unavailable") && strstr(response, "Runtime unchanged") && !reads);
    }
    const char *invalid[] = {"", "Zombies", "../zombies", "/tmp/zombies", "mods/zombies", "https://example.invalid",
        "zombies;quit", "zombies\nquit", "zombies\rquit", "zombies\\quit", "$(id)", "`id`", "zombies mode", "-zombies",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};
    for (unsigned i = 0; i < sizeof(invalid)/sizeof(*invalid); ++i) {
        call(2, invalid[i]); assert(strstr(response, "Invalid mode") && !reads);
    }
    call(3, "zombies"); assert(strstr(response, "Usage:") && !reads);
    puts("change_mode: elevated permission, status, invalid input and unavailable targets passed");
}
