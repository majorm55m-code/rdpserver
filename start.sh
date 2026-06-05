#!/bin/bash

# تشغيل خدمات النظام
service dbus start
service xrdp start

# الاتصال بـ Tailscale
tailscale up --authkey "$TAILSCALE_AUTHKEY" --accept-routes --hostname "railway-rdp-$(date +%s)"

# عرض معلومات الاتصال
echo "=========================================="
echo "Tailscale IP: $(tailscale ip -4)"
echo "Hostname: $(tailscale status --json | python3 -c "import sys,json; print(json.load(sys.stdin)['Self']['HostName'])")"
echo "Username: railwayuser"
echo "Password: railwaypass"
echo "=========================================="

# إبقاء الحاوية تعمل
tail -f /var/log/xrdp.log
