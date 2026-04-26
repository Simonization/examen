#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <netinet/in.h>


fd_set fds, rfds, wfds;
int id[10000];
char *msg[10000];
char wbuf[42], rbuf[1024];
int clients = 0, fd_max = 0;

int extract_message(char **buf, char **msg)
{
    char *newbuf;
    int i;

    *msg = 0;
    if(*buf == 0)
        return 0;
    i = 0;
    while((*buf)[i])
    {
        if((*buf)[i] == '\n')
        {
            newbuf = (char *)calloc(1, sizeof(*newbuf)*(strlen(*buf + i + 1) + 1));
            if(newbuf == 0)
                return -1;
            strcpy(newbuf, *buf + i + 1);
            *msg = *buf;
            (*msg)[i + 1] = 0;
            *buf = newbuf;
            return 1;
        }
        i++;
    }
    return 0;
}

char *str_join(char *buf, char *add)
{
    char *newbuf;
    int len;

    if(buf == 0)
        len = 0;
    else
        len = strlen(buf);

    newbuf = (char *)malloc(sizeof(*newbuf) * (len + strlen(add) + 1));
    if(newbuf == 0)
        return 0;
    newbuf[0] = 0;
    if(buf != 0)
        strcat(newbuf, buf);
    free(buf);
    strcat(newbuf, add);
    return newbuf;
}

void exit_err(char *err)
{
    write(2, err, strlen(err));
    exit(1);
}

void notify(int from, char *msg)
{
    for(int fd = 0; fd <= fd_max; fd++)
    {
        if(FD_ISSET(fd, &wfds) && fd != from)
            send(fd, msg, strlen(msg), 0);
    }
}

void add_client(int fd)
{
    fd_max = fd > fd_max ? fd : fd_max;
    FD_SET(fd, &fds);
    id[fd] = clients++;
    msg[fd] = NULL;
    sprintf(wbuf, "server: client %d just arrived\n", id[fd]);
    notify(fd, wbuf);
}

void remove_client(int fd)
{
    sprintf(wbuf, "server: client %d just left\n", id[fd]);
    notify(fd, wbuf);
    free(msg[fd]);
    msg[fd] = NULL;
    FD_CLR(fd, &fds);
    close(fd);
}

void serve(int fd)
{
    char *str;
    while(extract_message(&msg[fd], &str))
    {
        sprintf(wbuf, "client %d: ",id[fd]);
        notify(fd, wbuf);
        notify(fd, str);
        free(str);
        str = NULL;
    }
}

int main(int ac, char **av)
{
    if(ac != 2)
        exit_err("Wrong number of arguments\n");

    FD_ZERO(&fds);

    int sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if(sockfd < 0)
        exit_err("Fatal error\n");

    fd_max = sockfd;
    FD_SET(sockfd, &fds);

    struct sockaddr_in addr;
    bzero(&addr, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(0x7F000001);
    addr.sin_port = htons(atoi(av[1]));

    if(bind(sockfd, (struct sockaddr *)&addr, sizeof(addr)) || listen(sockfd, 10))
        exit_err("Fatal error\n");

    while(1)
    {
        rfds = wfds = fds;

        if(select(fd_max + 1, &rfds, &wfds, NULL, NULL) < 0)
            exit_err("Fatal error\n");

        for(int fd = 0; fd <= fd_max; fd++)
        {
            if(!FD_ISSET(fd, &rfds))
                continue;

            if(fd == sockfd)
            {
                socklen_t len = sizeof(addr);
                int client = accept(sockfd, (struct sockaddr *)&addr, &len);
                if(client >= 0)
                {
                    add_client(client);
                }
            }
            else
            {
                int r = recv(fd, rbuf, 1024, 0);
                if(r <= 0)
                {
                    remove_client(fd);
                }
                else
                {
                    rbuf[r] = '\0';
                    msg[fd] = str_join(msg[fd], rbuf);
                    serve(fd);
                }
            }
        }
    }
}
