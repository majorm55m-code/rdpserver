#!/bin/bash
set -e

service dbus start
service xrdp start || true

# تشغيل Tailscale في userspace mode
tailscaled --tun=userspace-networking --statedir=/var/lib/tailscale &
TAILSCALED_PID=$!

sleep 5

# الاتصال بـ Tailscale بالمفتاح المباشر
tailscale up --authkey="tskey-auth-kt8X5WKUQH11CNTRL-ziKogjF8wvCgNGyj3jnxvCqc6tVUB8dQ5" --hostname=railway-rdp --ssh

sleep 3

# إعادة توجيه RDP عبر Tailscale Serve
tailscale serve --bg --tcp 3389 tcp://localhost:3389

IP=$(tailscale ip -4 2>/dev/null || echo "connecting...")
echo "============================================"
echo "     LINUX RDP IS READY"
echo "============================================"
echo "  Tailscale IP : $IP"
echo "  Username     : $USER"
echo "  Password     : $PASSWORD"
echo "  RDP Port     : 3389"
echo "============================================"

wait $TAILSCALED_PID
