FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV USER=user
ENV PASSWORD=@ROblox2011
ENV TAILSCALE_AUTH_KEY=tskey-auth-kt8X5WKUQH11CNTRL-ziKogjF8wvCgNGyj3jnxvCqc6tVUB8dQ5

RUN apt-get update && apt-get install -y \
    xfce4 xfce4-goodies xrdp dbus-x11 \
    wget curl net-tools iproute2 \
    && apt-get clean

RUN useradd -m -s /bin/bash $USER && \
    echo "$USER:$PASSWORD" | chpasswd && \
    usermod -aG sudo $USER && \
    echo "xfce4-session" > /home/$USER/.xsession && \
    chown $USER:$USER /home/$USER/.xsession

RUN sed -i 's/#Port=3389/Port=3389/' /etc/xrdp/xrdp.ini && \
    sed -i 's/max_bpp=32/max_bpp=24/' /etc/xrdp/xrdp.ini && \
    sed -i 's/xserverbpp=24/xserverbpp=24/' /etc/xrdp/xrdp.ini

RUN curl -fsSL https://tailscale.com/install.sh | sh

COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 3389

CMD ["/start.sh"]
