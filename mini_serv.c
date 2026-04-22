#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdio.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/select.h>

/* ===== copied from main.c ===== */
int	extract_message(char **buf, char **msg)
{
	char	*newbuf;
	int	i;

	*msg = 0;
	if (*buf == 0)
		return (0);
	i = 0;
	while ((*buf)[i])
	{
		if ((*buf)[i] == '\n')
		{
			newbuf = calloc(1, sizeof(*newbuf) * (strlen(*buf + i + 1) + 1));
			if (newbuf == 0)
				return (-1);
			strcpy(newbuf, *buf + i + 1);
			*msg = *buf;
			(*msg)[i + 1] = 0;
			*buf = newbuf;
			return (1);
		}
		i++;
	}
	return (0);
}

char	*str_join(char *buf, char *add)
{
	char	*newbuf;
	int	len;

	if (buf == 0)
		len = 0;
	else
		len = strlen(buf);
	newbuf = malloc(sizeof(*newbuf) * (len + strlen(add) + 1));
	if (newbuf == 0)
		return (0);
	newbuf[0] = 0;
	if (buf != 0)
		strcat(newbuf, buf);
	free(buf);
	strcat(newbuf, add);
	return (newbuf);
}
/* ===== end main.c helpers ===== */

int	sockfd, maxfd, gid;
int	ids[65536];
char	*bufs[65536];
fd_set	afds, rfds, wfds;
char	buf_w[200000], buf_r[200000];

void	fatal(void)
{
	write(2, "Fatal error\n", 12);
	exit(1);
}

void	send_all(int except)
{
	for (int fd = 0; fd <= maxfd; fd++)
		if (FD_ISSET(fd, &wfds) && fd != except)
			send(fd, buf_w, strlen(buf_w), MSG_NOSIGNAL);
}

void	add_client(void)
{
	int cfd = accept(sockfd, NULL, NULL);
	if (cfd < 0)
		return;
	if (cfd > maxfd)
		maxfd = cfd;
	ids[cfd] = gid++;
	bufs[cfd] = NULL;
	FD_SET(cfd, &afds);
	sprintf(buf_w, "server: client %d just arrived\n", ids[cfd]);
	send_all(cfd);
}

void	rm_client(int fd)
{
	sprintf(buf_w, "server: client %d just left\n", ids[fd]);
	send_all(fd);
	free(bufs[fd]);
	bufs[fd] = NULL;
	FD_CLR(fd, &afds);
	close(fd);
}

void	read_client(int fd)
{
	int r = recv(fd, buf_r, sizeof(buf_r) - 1, 0);
	if (r <= 0)
	{
		rm_client(fd);
		return;
	}
	buf_r[r] = 0;
	bufs[fd] = str_join(bufs[fd], buf_r);
	if (!bufs[fd])
		fatal();
	char *msg;
	while (extract_message(&bufs[fd], &msg) > 0)
	{
		sprintf(buf_w, "client %d: %s", ids[fd], msg);
		send_all(fd);
		free(msg);
	}
}

int	main(int ac, char **av)
{
	if (ac != 2)
	{
		write(2, "Wrong number of arguments\n", 26);
		exit(1);
	}
	sockfd = socket(AF_INET, SOCK_STREAM, 0);
	if (sockfd < 0)
		fatal();
	struct sockaddr_in addr;
	bzero(&addr, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_addr.s_addr = htonl(2130706433); // 127.0.0.1
	addr.sin_port = htons(atoi(av[1]));
	if (bind(sockfd, (const struct sockaddr *)&addr, sizeof(addr)) < 0)
		fatal();
	if (listen(sockfd, 128) < 0)
		fatal();
	FD_ZERO(&afds);
	FD_SET(sockfd, &afds);
	maxfd = sockfd;
	while (1)
	{
		rfds = wfds = afds;
		if (select(maxfd + 1, &rfds, &wfds, NULL, NULL) < 0)
			continue;
		for (int fd = 0; fd <= maxfd; fd++)
		{
			if (!FD_ISSET(fd, &rfds))
				continue;
			if (fd == sockfd)
				add_client();
			else
				read_client(fd);
			break;
		}
	}
	return 0;
}
