import urllib3

from homeassistant.generate import *

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules()

    write_healthcheck(working_dir=join(DIR_ROOT, "src/main/resources/data"))
    write_certificates(working_dir=join(DIR_ROOT, "src/main/resources/data"))

    conf_path = abspath(join(DIR_ROOT, "src/main/resources/data/nginx.conf"))
    with open(conf_path, 'w') as conf_file:
        conf_file.write("""
#######################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
#######################################################################################
user nginx;
worker_processes 1;
pid /var/run/nginx.pid;

error_log /dev/stdout warn;

events {
  worker_connections  1024;
}

http {

  #access_log off;
  log_format custom escape=none '$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"\n$request_body\n';
  access_log /dev/stdout custom;

  server_tokens off;

  client_body_buffer_size 25k;
  client_header_buffer_size 25k;
  client_max_body_size 25k;
  large_client_header_buffers 2 25k;

  gzip on;
  gzip_vary on;
  gzip_proxied any;
  gzip_comp_level 6;
  gzip_min_length 1100;
  gzip_buffers 16 8k;
  gzip_http_version 1.1;
  gzip_types
    application/atom+xml
    application/geo+json
    application/javascript
    application/x-javascript
    application/json
    application/ld+json
    application/manifest+json
    application/rdf+xml
    application/rss+xml
    application/xhtml+xml
    application/xml
    font/eot
    font/otf
    font/ttf
    image/svg+xml
    text/css
    text/javascript
    text/plain
    text/xml;

  # add_header X-Frame-Options "SAMEORIGIN" always;
  # add_header X-Content-Type-Options "nosniff" always;
  # add_header X-XSS-Protection "1; mode=block" always;
  # add_header Referrer-Policy "no-referrer-when-downgrade" always;
  # add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

  # proxy_set_header X-Forwarded-Proto $scheme;
  # proxy_set_header X-Forwarded-Host $host;
  # proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  # proxy_hide_header X-Powered-By;
  # proxy_buffering off;

  # limit_req_zone $binary_remote_addr zone=perip:10m rate=10r/s;
  # limit_req zone=perip burst=20 nodelay;

  # HTTP WS upgrade
  map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
  }

  # HTTP to HTTPS redirect
  server {
    listen ${NGINX_PORT_INTERNAL_HTTP} default_server;
    server_name _;
    return 301 https://$host$request_uri;
  }

  # HTTPS server
  server {
    listen ${NGINX_PORT_INTERNAL_HTTPS} ssl ipv6only=off;
    server_name *.janeandgraham.com;
    ssl_certificate /etc/nginx/certificate.pem;
    ssl_certificate_key /etc/nginx/.key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;    
    # ssl_prefer_server_ciphers on;
    # ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:...';
    # ssl_session_cache shared:SSL:10m;
    # ssl_session_timeout 10m;    
  }

  # Remote domain redirect
  server {
    listen ${NGINX_PORT_INTERNAL_HTTPS};
    server_name janeandgraham.com;
    return 301 https://home.janeandgraham.com$request_uri;
  }

  # Local server for [nginx] and domain [nginx}.janeandgraham.com]
  server {
    listen ${NGINX_PORT_INTERNAL_HTTPS};
    server_name nginx.janeandgraham.com nginx.local.janeandgraham.com;
    location = /health {
      root /usr/share/nginx/html;
      try_files /health.txt =404;
      access_log off;
      add_header Content-Type text/plain;
    }
    location / {
      root /usr/share/nginx/html;
      autoindex on;
    }
    # location ~ /\.(git|env|ht) {
    #   deny all;
    #   access_log off;
    #   log_not_found off;
    # }
  }


      """.strip() + "\n\n")
        for name in modules:
            ip_key = "{}_IP".format(name.upper())
            port_key = "{}_HTTP_PORT".format(name.upper())
            port_value = modules[name][1][port_key] if port_key in modules[name][1] else ""
            host_public_key = "{}_HOST_PUBLIC".format(name.upper())
            ws_context_key = "{}_HTTP_WS_CONTEXT".format(name.upper())
            scheme_key = "{}_HTTP_SCHEME".format(name.upper())
            scheme_value = modules[name][1][scheme_key] if scheme_key in modules[name][1] else "http://"
            console_context_key = "{}_HTTP_CONSOLE_CONTEXT".format(name.upper())
            console_context_value = modules[name][1][console_context_key] if console_context_key in modules[name][1] else ""
            nginx_port_key = "NGINX_PORT_INTERNAL_HTTPS"
            nginx_port_value = modules["nginx"][1][nginx_port_key]
            if port_key in modules[name][1] and name != "nginx":
                server_names = [name]
                if host_public_key in modules[name][1]:
                    server_names.append(modules[name][1][host_public_key])
                for server_name in server_names:
                    conf_file.write("  " + """
  # {} server for [{}] and domain [{}.janeandgraham.com]
  map $host ${}_url {{ default {}${}:{}; }}
  server {{
    listen {};
    server_name {}.janeandgraham.com;
    proxy_buffering off;
    location / {{
      proxy_http_version 1.1;
      proxy_pass ${}_url{};
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
              """.format(
                        "Remote" if name != server_name else "Local",
                        name,
                        server_name,
                        name,
                        scheme_value,
                        ip_key,
                        port_value,
                        nginx_port_value,
                        server_name,
                        name,
                        console_context_value,
                    ).strip() + "\n")
                    if ws_context_key in modules[name][1]:
                        conf_file.write("    " + """
    location {} {{
      proxy_http_version 1.1;
      proxy_pass ${}_url{};
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
    }}
                """.format(
                            modules[name][1][ws_context_key],
                            name,
                            modules[name][1][ws_context_key],
                        ).strip() + "\n")
                    conf_file.write("  " + """
  }
              """.strip() + "\n\n")
        conf_file.write("""
}
      """.strip() + "\n")
        print("Build generate script [nginx] entity metadata persisted to [{}]".format(conf_path))
