import glob
import os
import sys
from os.path import *

import pandas as pd
import urllib3

urllib3.disable_warnings()
pd.options.mode.chained_assignment = None

DIR_ROOT = os.path.abspath("{}/../../../..".format(os.path.dirname(os.path.realpath(__file__))))
for dir_module in glob.glob("{}/../../*/*".format(DIR_ROOT)):
    if dir_module.endswith("homeassistant"):
      sys.path.insert(0, "{}/src/build/python".format(dir_module))

from homeassistant.generate import load_env
from homeassistant.generate import load_modules

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules()

    conf_path = abspath(join(DIR_ROOT, "src/main/resources/config/nginx.conf"))
    with open(conf_path, 'w') as conf_file:
      conf_file.write("""
#######################################################################################
# WARNING: This file is written to by the build process, any manual edits will be lost!
#######################################################################################
user nginx;
worker_processes 1;
pid /var/run/nginx.pid;
error_log /var/log/nginx/error.log warn;

events {
  worker_connections  1024;
}

http {

  access_log on;
  server_tokens off;

  client_body_buffer_size 5k;
  client_header_buffer_size 5k;
  client_max_body_size 5k;
  large_client_header_buffers 2 5k;

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

  # HTTP WS upgrade
  map $http_upgrade $connection_upgrade {
    default upgrade;
    ''    close;
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
    return 301 https://$host$request_uri;
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
    server_name nginx.janeandgraham.com;
    location / {
    root /usr/share/nginx/html;
    autoindex on;
    }
  }
      """.strip() + "\n\n")
      for name in modules:
        ip_key = "{}_IP".format(name.upper())
        port_key = "{}_HTTP_PORT".format(name.upper())
        host_public_key = "{}_HOST_PUBLIC".format(name.upper())
        ws_context_key = "{}_HTTP_WS_CONTEXT".format(name.upper())
        console_context_key = "{}_HTTP_CONSOLE_CONTEXT".format(name.upper())
        if port_key in modules[name][1] and name != "nginx":
            server_names = [name]
            if host_public_key in modules[name][1]:
              server_names.append(modules[name][1][host_public_key])
            for server_name in server_names:
              conf_file.write("  " + """
  # {} server for [{}] and domain [{}.janeandgraham.com]
  map $host ${}_url {{ default http://${{{}}}:{}; }}
  server {{
    listen {};
    server_name {}.janeandgraham.com;
    proxy_buffering off;
    location / {{
    proxy_http_version 1.1;
    proxy_pass ${}_url{};
    proxy_set_header Host $host;
    }}
              """.format(
                "Remote" if name != server_name else "Local",
                name,
                server_name,
                name,
                ip_key,
                modules[name][1][port_key],
                modules["nginx"][1]["NGINX_PORT_INTERNAL_HTTPS"],
                server_name,
                name,
                modules[name][1][console_context_key] if console_context_key in modules[name][1] else "",
              ).strip() + "\n")
              if ws_context_key in modules[name][1]:
                conf_file.write("    " + """
    location {} {{
    proxy_http_version 1.1;
    proxy_pass ${}_url{};
    proxy_set_header Host $host;
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
