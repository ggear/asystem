# DNS namespace

| Type                   | Example | DNS Source                       | Resolves To | TLS Certificate                | Reachable From               |
|------------------------|---|----------------------------------|---|--------------------------------|------------------------------|
| Public Root Domain     | `janeandgraham.com` | Cloudflare      | WAN IP → UDM → nginx, 301 to `home` | ASystem `janeandgraham.com`    | Internet                     |
| Public Home Domain     | `home.janeandgraham.com` | Cloudflare                 | WAN → nginx vhost, `allow all` | ASystem  `*.janeandgraham.com` | Internet                     |
| Public Resource Domain | `prices.janeandgraham.com` | Cloudflare   | Cloudflare edge → tunnel → the `.data` vhost | Cloudflare Universal SSL       | Internet (Cloudflare Access) |
| Private Module Domain  | `wrangle.proxy.janeandgraham.com` | LAN                              | nginx vhost, LAN-restricted | ASystem `*.proxy.janeandgraham.com`    | LAN                          |
| Private Resource Domain | `prices.data.janeandgraham.com` | LAN                              | nginx API vhost, LAN-restricted | ASystem `*.data.janeandgraham.com`     | LAN                          |
| Private Service Domain | `wrangle.local.janeandgraham.com` | LAN                              | the service host directly, bypassing nginx | ASystem `*.local.janeandgraham.com`    | LAN                          |
| Private Host Domain    | `macmini-meg.local.janeandgraham.com` | LAN                              | the machine (`10.0.2.18`) | ASystem `*.local.janeandgraham.com`    | LAN                          |
| Private Host Name      | `macmini-meg` | LAN (DHCP reservation)           | the machine (`10.0.2.18`) | —                              | LAN                          |
