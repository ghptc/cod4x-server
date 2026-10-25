/* Local namespace-only rejection test for a real administration command. */
#include <arpa/inet.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
int main(void)
{
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in server = {.sin_family = AF_INET, .sin_port = htons(28971)};
    struct timeval timeout = {.tv_sec = 2};
    char reply[2048];
    const char request[] = "\xff\xff\xff\xff" "rcon invalid-test-password mute 0 all\n";
    assert(fd >= 0 && inet_pton(AF_INET, "127.0.0.1", &server.sin_addr) == 1);
    assert(setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) == 0);
    assert(sendto(fd, request, sizeof(request)-1, 0, (struct sockaddr *)&server, sizeof(server)) > 0);
    int length = recv(fd, reply, sizeof(reply)-1, 0);
    assert(length > 4); reply[length] = 0;
    assert(strstr(reply + 4, "Bad rcon"));
    close(fd);
    puts("ADMIN_RCON denied");
    return 0;
}
