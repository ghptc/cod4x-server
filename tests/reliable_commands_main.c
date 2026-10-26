/* Scenario assertions operate on real client_t and serialized message bytes. */
static int readlong(const byte *data) { int value; memcpy(&value, data, 4); return value; }
static int readshort(const byte *data) { unsigned short value; memcpy(&value, data, 2); return value; }
static void add(client_t *client, char opcode, int n, int type) {
    char command[64]; snprintf(command, sizeof(command), "%c %d", opcode, n);
    SV_AddServerCommand(client, type, command);
}
static void verify_commands(msg_t *msg, int first, int last, char opcode) {
    int offset = 0;
    for (int seq = first; seq <= last; ++seq) {
        assert(msg->data[offset++] == svc_serverCommand);
        assert(readlong(msg->data + offset) == seq); offset += 4;
        char expected[64]; snprintf(expected, sizeof(expected), "%c %d", opcode, seq);
        assert(!strcmp((char *)msg->data + offset, expected)); offset += strlen(expected) + 1;
    }
    assert(offset == msg->cursize && !msg->overflowed);
}
int main(int argc, char **argv) {
    assert(argc == 2);
    client_t *client = svs.clients;
    client->state = CS_ACTIVE; client->netchan.remoteAddress.type = NA_IP;
    sv_maxclients->integer = 2; sv_fps->integer = 20; sv_maxDownloadRate->integer = 128;
    sv_allowDownload->integer = 1; sv_pure->integer = 1;
    byte data[65536], saved[65536]; msg_t msg;
    if (!strcmp(argv[1], "retransmit")) {
        /* Progressively acknowledge packets: sent text must survive unsent compaction. */
        for (int batch = 0; batch < 50; ++batch) {
            int start = client->reliableSequence + 1;
            for (int i = 0; i < 10; ++i) add(client, 'x', start + i, 1);
            MSG_Init(&msg, data, sizeof(data)); SV_UpdateServerCommandsToClient(client, &msg);
            verify_commands(&msg, start, start + 9, 'x');
            int length = msg.cursize; memcpy(saved, data, length);
            svs.time += 60000; /* Arbitrarily long wait alone must not discard commands. */
            MSG_Init(&msg, data, sizeof(data)); SV_UpdateServerCommandsToClient(client, &msg);
            assert(msg.cursize == length && !memcmp(data, saved, length));
            client->reliableAcknowledge = client->reliableSequence;
            MSG_Init(&msg, data, sizeof(data)); SV_UpdateServerCommandsToClient(client, &msg);
            assert(msg.cursize == 0);
        }
        assert(!drops && client->reliableSequence == 500);
    } else if (!strcmp(argv[1], "compact")) {
        add(client, 'a', 1, 1);
        MSG_Init(&msg, data, sizeof(data)); SV_UpdateServerCommandsToClient(client, &msg);
        add(client, 'a', 2, 1); add(client, 'a', 3, 1);
        assert(client->reliableSequence == 2 && client->reliableSent == 1);
        assert(!strcmp(client->reliableCommands[1].command, "a 1"));
        assert(!strcmp(client->reliableCommands[2].command, "a 3"));
        add(client, 'x', 4, 0); assert(client->reliableSequence == 3);
        client->state = CS_PRIMED;
        add(client, 'x', 5, 0); assert(client->reliableSequence == 2);
        add(client, 'x', 6, 1); assert(client->reliableSequence == 3);
        assert(!strcmp(client->reliableCommands[1].command, "a 1"));
        assert(!strcmp(client->reliableCommands[2].command, "a 3"));
        assert(!strcmp(client->reliableCommands[3].command, "x 6"));
    } else if (!strcmp(argv[1], "overflow")) {
        /* No acknowledgments: 128 unique critical commands fit; 129 requests a drop. */
        for (int i = 1; i <= MAX_RELIABLE_COMMANDS; ++i) add(client, 'x', i, 1);
        assert(!drops && client->reliableSequence == MAX_RELIABLE_COMMANDS);
        add(client, 'x', MAX_RELIABLE_COMMANDS + 1, 1);
        assert(drops == 1 && oob == 1);
        assert(strstr(client->reliableCommands[client->reliableSequence & (MAX_RELIABLE_COMMANDS-1)].command,
                      "EXE_SERVERCOMMANDOVERFLOW"));
    } else if (!strcmp(argv[1], "recover")) {
        for (int i = 1; i <= 20; ++i) add(client, 'x', i, 1);
        MSG_Init(&msg, data, 40); SV_UpdateServerCommandsToClientRecover(client, &msg);
        int first_end = client->reliableSent;
        assert(first_end > 0 && first_end < 20 && client->reliableSequence == 20);
        verify_commands(&msg, 1, first_end, 'x');
        client->reliableAcknowledge = first_end;
        MSG_Init(&msg, data, sizeof(data)); SV_UpdateServerCommandsToClientRecover(client, &msg);
        verify_commands(&msg, first_end + 1, 20, 'x'); assert(client->reliableSent == 20);
    } else if (!strcmp(argv[1], "download")) {
        for (int i = 0; i < (int)sizeof(fixture); ++i) fixture[i] = (byte)(i * 31);
        add(client, 'x', 1, 1);
        reliableCommands_t original = client->reliableCommands[1];
        strcpy(client->downloadName, "mods/fixture/test.iwd");
        SV_WriteDownloadToClient(client);
        assert(transport_calls == 1 && transport[8] == DLSUBCMD_FILEINIT);
        assert(readlong(transport + 9) == (int)sizeof(fixture));
        client->downloadEOF = qfalse; client->downloadXmitBlock = 1;
        client->downloadNumBytes = sizeof(fixture);
        int received = 0;
        for (int frames = 0; frames < 1000; ++frames) {
            svs.time += 50; SV_WriteDownloadToClient(client);
            assert(transport[8] == DLSUBCMD_SERVERDL);
            int length = readshort(transport + 13);
            assert(readlong(transport + 9) == received);
            assert(readlong(transport) == transport_len - 4 && transport_len == length + 15);
            if (!length) break;
            assert(!memcmp(transport + 15, fixture + received, length)); received += length;
        }
        assert(received == (int)sizeof(fixture) && client->downloadEOF);
        assert(client->reliableSequence == 1 && client->reliableSent == 0 && client->reliableAcknowledge == 0);
        assert(!memcmp(&original, &client->reliableCommands[1], sizeof(original)));
    } else if (!strcmp(argv[1], "backpressure")) {
        strcpy(client->downloadName, "mods/fixture/test.iwd"); client->download = 1;
        client->downloadNumBytes = sizeof(fixture); client->downloadXmitBlock = 1;
        buffered = 20001; SV_WriteDownloadToClient(client); assert(!transport_calls && filepos == 0);
        buffered = 0; send_window = 1000000;
        SV_WriteDownloadToClient(client); assert(readshort(transport + 13) == (128 * 1024) / 20);
        svs.clients[1].state = CS_CONNECTED; svs.clients[1].downloadXmitBlock = 1;
        SV_WriteDownloadToClient(client); assert(readshort(transport + 13) == (128 * 1024) / 2 / 20);
    } else if (!strcmp(argv[1], "done")) {
        strcpy(client->downloadName, "mods/fixture/test.iwd"); client->download = 1;
        client->downloadXmitBlock = 1; client->wwwDl_var01 = 1;
        SV_DoneDownload_f(client);
        assert(closed == 1 && refreshed == 1 && refreshed_client == client && !client->downloadXmitBlock);
    } else { assert(!"unknown scenario"); }
    puts(argv[1]); return 0;
}
