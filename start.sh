#!/bin/bash

service dbus start
service xrdp start

# تشغيل Tailscale بالمفتاح المباشر
tailscale up --authkey="tskey-auth-kt8X5WKUQH11CNTRL-ziKogjF8wvCgNGyj3jnxvCqc6tVUB8dQ5" --hostname=railway-rdp

IP=$(tailscale ip -4)

echo "============================================"
echo "     LINUX RDP IS READY"
echo "============================================"
echo "  Tailscale IP : $IP"
echo "  Username     : $USER"
echo "  Password     : $PASSWORD"
echo "  RDP Port     : 3389"
echo "============================================"

tail -f /dev/null
