FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# تثبيت XRDP + Xfce + Tailscale
RUN apt-get update && apt-get install -y \
    xfce4 \
    xfce4-goodies \
    xrdp \
    xorgxrdp \
    dbus-x11 \
    net-tools \
    curl \
    wget \
    sudo \
    && apt-get clean

# تثبيت Tailscale
RUN curl -fsSL https://tailscale.com/install.sh | sh

# إنشاء مستخدم
RUN useradd -m -s /bin/bash railwayuser && \
    echo "railwayuser:railwaypass" | chpasswd && \
    usermod -aG sudo railwayuser

# تكوين XRDP
RUN echo "xfce4-session" > /home/railwayuser/.xsession && \
    chown railwayuser:railwayuser /home/railwayuser/.xsession

# سكربت التشغيل
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 3389

CMD ["/start.sh"]
