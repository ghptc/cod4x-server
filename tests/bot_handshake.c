/* Local handshake regression fixture; never a fake internet-list player. */
#include <arpa/inet.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
int main(int argc, char **argv)
{
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in address = {.sin_family = AF_INET, .sin_port = htons(28971)};
    struct timeval timeout = {.tv_sec = 2};
    char reply[2048], packet[2048], challenge[64];
    const char *password = argc > 1 ? argv[1] : "";
    int protocol = argc > 3 ? atoi(argv[3]) : 21;
    struct sockaddr_in local = {.sin_family = AF_INET};
    assert(fd >= 0);
    assert(inet_pton(AF_INET, "127.0.0.1", &address.sin_addr) == 1);
    assert(inet_pton(AF_INET, argc > 2 ? argv[2] : "127.0.0.2", &local.sin_addr) == 1);
    assert(bind(fd, (struct sockaddr *)&local, sizeof(local)) == 0);
    assert(setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) == 0);
    assert(connect(fd, (struct sockaddr *)&address, sizeof(address)) == 0);
    const char request[] = "\xff\xff\xff\xffgetchallenge 123456";
    assert(send(fd, request, sizeof(request)-1, 0) > 0);
    int n = recv(fd, reply, sizeof(reply)-1, 0);
    assert(n > 4); reply[n] = 0;
    assert(sscanf(reply + 4, "challengeResponse %63s", challenge) == 1);
    /* Quotation marks are literal protocol delimiters, without backslash escapes. */
    snprintf(packet, sizeof(packet), "\xff\xff\xff\xff" "connect \"\\protocol\\%d\\challenge\\%s\\qport\\24444\\name\\HandshakeFixture\\rate\\25000\\snaps\\20\\password\\%s\"", protocol, challenge, password);
    assert(send(fd, packet, strlen(packet), 0) > 0);
    n = recv(fd, reply, sizeof(reply)-1, 0);
    assert(n > 4); reply[n] = 0;
    printf("HANDSHAKE_REPLY %s\n", reply + 4);
    int accepted = strncmp(reply + 4, "connectResponse", 15) == 0;
    close(fd);
    return accepted ? 0 : 2;
}
