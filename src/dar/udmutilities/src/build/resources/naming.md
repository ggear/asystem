# Naming

| Namespace              | Example                               | Resolved By   | Resolves To             | Secured By                          | Reachable From |
|------------------------|---------------------------------------|---------------|-------------------------|-------------------------------------|----------------|
| Public Root Domain     | `janeandgraham.com`                   | Cloudflare    | `nginx` fwd to `home`   | ASystem Certificate                 | Internet       |
| Public Home Domain     | `home.janeandgraham.com`              | Cloudflare    | `nginx` vhost           | ASystem Certificate                 | Internet       |
| Public Data Domain     | `prices.janeandgraham.com`            | Cloudflare    | tunnel to `.data` vhost | Cloudflare Certificate/Access Token | Internet       |
| Private Module Domain  | `wrangle.proxy.janeandgraham.com`     | LAN (dnsmasq) | `nginx` vhost           | ASystem Certificate                 | LAN            |
| Private Data Domain    | `prices.data.janeandgraham.com`       | LAN (dnsmasq) | `nginx` API vhost       | ASystem Certificate                 | LAN            |
| Private Service Domain | `wrangle.local.janeandgraham.com`     | LAN (dnsmasq) | Service Host IP         | ASystem Certificate                 | LAN            |
| Private Host Domain    | `macmini-meg.local.janeandgraham.com` | LAN (dnsmasq) | Host IP                 | ASystem Certificate                 | LAN            |
| Private Host Name      | `macmini-meg`                         | LAN (DHCP)    | Host IP                 | SSH Keys                            | LAN            |
