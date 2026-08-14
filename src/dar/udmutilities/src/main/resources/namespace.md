# DNS namespace

| Type             | Example | DNS Source | Resolves To | TLS Certificate | Reachable From |
|------------------|---|---|---|---|---|
| Public Root Domain | `janeandgraham.com` | Cloudflare public (DDNS `A`, unproxied) | WAN IP → UDM → nginx, 301 to `home` | `janeandgraham.com` | Internet |
| Public Home Domain | `home.janeandgraham.com` | Cloudflare public | WAN → nginx vhost, `allow all` | `*.janeandgraham.com` | Internet |
| Public Resource Domain | `prices.janeandgraham.com` | Cloudflare public (proxied CNAME) | Cloudflare edge → tunnel → the `.data` vhost | Cloudflare Universal SSL | Internet via Cloudflare Access |
| Private Module   | `wrangle.proxy.janeandgraham.com` | LAN dnsmasq | nginx vhost, LAN-restricted | `*.proxy.janeandgraham.com` | LAN |
| Private Resource | `prices.data.janeandgraham.com` | LAN dnsmasq | nginx API vhost, LAN-restricted | `*.data.janeandgraham.com` | LAN |
| `<module>.local` | `wrangle.local.janeandgraham.com` | LAN dnsmasq | the service host directly, bypassing nginx | `*.local.janeandgraham.com` | LAN |
| `<host>.local`   | `macmini-meg.local.janeandgraham.com` | LAN dnsmasq | the machine (`10.0.2.18`) | `*.local.janeandgraham.com` | LAN |
| `<host>`         | `macmini-meg` | LAN dnsmasq (DHCP reservation) | the machine (`10.0.2.18`) | — | LAN |
