# Naming

| Namespace              | Example                               | Resolved By | Resolves To           | Secured By            | Reachable From |
|------------------------|---------------------------------------|-------------|-----------------------|-----------------------|----------------|
| Public Root Domain     | `janeandgraham.com`                   | Cloudflare  | `nginx` fwd to `home` | ASystem Cert          | Internet       |
| Public Home Domain     | `home.janeandgraham.com`              | Cloudflare  | `nginx` Host          | ASystem Cert          | Internet       |
| Public Data Domain     | `prices.janeandgraham.com`            | Cloudflare  | tunnel to Data Host   | Cloudflare Cert/Token | Internet       |
| Private Module Domain  | `wrangle.proxy.janeandgraham.com`     | LAN         | `nginx` Host          | ASystem Cert          | LAN            |
| Private Data Domain    | `prices.data.janeandgraham.com`       | LAN         | `nginx` Data Host     | ASystem Cert          | LAN            |
| Private Service Domain | `wrangle.local.janeandgraham.com`     | LAN         | Service Host          | ASystem Cert          | LAN            |
| Private Host Domain    | `macmini-meg.local.janeandgraham.com` | LAN         | Host                  | ASystem Cert          | LAN            |
| Private Host Name      | `macmini-meg`                         | LAN         | Host                  | SSH Keys              | LAN            |
