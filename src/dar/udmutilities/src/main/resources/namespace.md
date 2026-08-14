# DNS namespace

Every name under `janeandgraham.com`, what resolves it, and what it reaches. Generated artifacts are noted
per row — none of these names is hand-maintained except the Cloudflare records.

**The infix is the meaning, and the one rule worth remembering is: no infix means the internet can reach it.**

| Pattern | Example | DNS source | Resolves to | TLS certificate | Reachable from |
|---|---|---|---|---|---|
| apex | `janeandgraham.com` | Cloudflare public (DDNS `A`, unproxied) | WAN IP → UDM → nginx | LE `janeandgraham.com` | internet — 301 to `home` |
| `<public>` | `home.janeandgraham.com` | Cloudflare public | WAN → nginx vhost, `allow all` | LE `*.janeandgraham.com` | internet (Home Assistant) |
| `<resource>` | `prices.janeandgraham.com` | Cloudflare public (proxied CNAME) | Cloudflare edge → tunnel → the `.data` vhost | **Cloudflare Universal SSL** | internet, behind Access |
| `<module>.proxy` | `wrangle.proxy.janeandgraham.com` | LAN dnsmasq | nginx vhost, LAN-restricted | LE `*.proxy.janeandgraham.com` | LAN |
| `<resource>.data` | `prices.data.janeandgraham.com` | LAN dnsmasq | nginx API vhost, LAN-restricted | LE `*.data.janeandgraham.com` | LAN |
| `<module>.local` | `wrangle.local.janeandgraham.com` | LAN dnsmasq | the service host **directly**, bypassing nginx | LE `*.local.janeandgraham.com` | LAN |
| `<host>.local` | `macmini-meg.local.janeandgraham.com` | LAN dnsmasq | the machine (`10.0.2.18`) | LE `*.local.janeandgraham.com` | LAN |
| `<host>` | `macmini-meg` | LAN dnsmasq (DHCP reservation) | the machine (`10.0.2.18`) | — | LAN, ssh and `deploy.sh` |

## Why the shapes differ

**Depth is the public/private boundary, and it is not arbitrary.** Cloudflare's Universal SSL covers the root
domain and *first-level* subdomains only, so anything published through the tunnel must be flat — the edge has
no certificate for a second-level name and the TLS handshake fails before Access is even consulted. Every LAN
pattern is second-level and served by the Let's Encrypt certificate we own, where a wildcard per infix costs
nothing but a SAN.

This is also why `.proxy` exists. Before it, a flat name meant *either* public (`home`, `prices`) or LAN (every
module vhost), so the name told you nothing about exposure, and any future API resource could silently collide
with a module of the same name — split-horizon DNS would then serve two different services on one name, LAN and
internet, with no error anywhere.

`.proxy` and `.local` both mean LAN; they differ in whether nginx is in the path. `.proxy` goes through the
reverse proxy (TLS termination, security headers, rate limiting, the `allow`/`deny` source restriction);
`.local` goes straight to the service host and is what modules use to reach each other (`*_SERVICE_PROD`).

## Where each name is generated

| Name | Written by |
|---|---|
| `<module>.proxy`, `<module>.local`, `<host>.local`, `<host>` | `src/dar/udmutilities` → `dhcp.dhcpServers-aliases.conf` (this module) |
| `<resource>.data` | `src/dar/udmutilities` (CNAME) + `src/meg/nginx` (vhost) |
| `<module>.proxy` vhosts, `home`, apex redirect | `src/meg/nginx` → `nginx.conf` |
| `<resource>` (flat, public) | Cloudflare dashboard route + `src/may/cloudflare` ingress |
| certificate SANs | `src/may/letsencrypt` → `dnsrobocert/config.yml` |

Changing a name means editing the relevant `generate.py`, never the generated file. Both nginx and dnsmasq are
rebuilt wholesale, so a retired name disappears rather than lingering.

## Adding a name

- **A module UI** — declare `<MODULE>_HTTP_PORT` in the module's `.env_all`; the `.proxy` vhost and CNAME follow.
- **An API resource** — declare `<MODULE>_HTTP_API_<RESOURCE>_CONTEXT`; the `.data` vhost and CNAME follow.
- **Public via the port-forward** — add `<MODULE>_HOST_PUBLIC=<label>`, which yields a flat, `allow all` vhost.
  Prefer the tunnel instead; this widens the perimeter.
- **Public via the tunnel** — add the resource to `CLOUDFLARE_RESOURCES` in `src/may/cloudflare`, then create the
  route and an Access application with a **Service Auth** policy.

A new infix needs a matching wildcard SAN in `src/may/letsencrypt` before anything will resolve without a
certificate warning.
