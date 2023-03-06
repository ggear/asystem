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

  map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
  }

  server {
    listen ${NGINX_PORT_EXTERNAL_HTTP} default_server;
    server_name _;
    return 301 https://$host$request_uri;
  }

  server {
    listen ${NGINX_PORT_EXTERNAL_HTTPS} ssl ipv6only=off;
    server_name *.janeandgraham.com;
    ssl_certificate /etc/nginx/certificate.pem;
    ssl_certificate_key /etc/nginx/.key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    return 301 https://$host$request_uri;
  }

  server {
    listen ${NGINX_PORT_EXTERNAL_HTTPS};
    server_name janeandgraham.com;
    ssl_certificate /etc/nginx/certificate.pem;
    ssl_certificate_key /etc/nginx/.key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    return 301 https://home.janeandgraham.com$request_uri;
  }

  server {
     listen ${NGINX_HOST}:80;
     server_name ${NGINX_HOST};
     location / {
       root /usr/share/nginx/html;
       autoindex on;
     }
  }

  server {
    listen ${NGINX_PORT_INTERNAL_HTTP} default_server;
    server_name _;
    location / {
      root /usr/share/nginx/html;
      autoindex on;
    }
  }

  server {
    listen ${NGINX_PORT_INTERNAL_HTTPS} ssl ipv6only=off;
    server_name ${NGINX_HOST}.janeandgraham.com;
    ssl_certificate /etc/nginx/certificate.pem;
    ssl_certificate_key /etc/nginx/.key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
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
            if port_key in modules[name][1]:
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
    ssl_certificate /etc/nginx/certificate.pem;
    ssl_certificate_key /etc/nginx/.key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    proxy_buffering off;
    location / {{
      proxy_http_version 1.1;
      proxy_pass ${}_url{};
      proxy_set_header Host $host;
    }}
                    """.format(
                        "Public" if name != server_name else "Private",
                        name,
                        server_name,
                        name,
                        ip_key,
                        modules[name][1][port_key],
                        modules["nginx"][1]["NGINX_PORT_EXTERNAL_HTTPS"],
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
