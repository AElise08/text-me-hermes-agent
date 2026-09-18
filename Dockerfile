FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-51f83158a70a383f03a4d03dbd8b6ea102cf0361@sha256:253d7ed3409effa7fa59113d93b4b79bb731d8264cdaf4cd60294924d0110a2e
COPY runtime/SOUL.md /var/lib/hermes/SOUL.md
COPY LICENSE NOTICE /usr/share/doc/matriz/
COPY skills/matriz/ /opt/hermes/skills/matriz/
COPY scripts/ /opt/matriz/scripts/
COPY templates/ /opt/matriz/templates/
COPY fonts/ /opt/matriz/fonts/
RUN chown -R root:root /opt/matriz && chmod 0755 /opt/matriz/scripts/*.py && chmod 0644 /var/lib/hermes/SOUL.md

COPY vendor/client.pin /opt/plow/agent-index-client.pin
RUN set -eu; \
    sha="$(sed -n 's/^sha=//p' /opt/plow/agent-index-client.pin)"; \
    want="$(sed -n 's/^sha256=//p' /opt/plow/agent-index-client.pin)"; \
    path="$(sed -n 's/^path=//p' /opt/plow/agent-index-client.pin)"; \
    curl -fsS --max-time 60 -o /opt/plow/agent-index-client.py "https://raw.githubusercontent.com/plow-pbc/agent-index-client/${sha}/${path}"; \
    got="$(sha256sum /opt/plow/agent-index-client.py | cut -d' ' -f1)"; \
    [ "$got" = "$want" ]; chmod 0644 /opt/plow/agent-index-client.py
COPY image/s6-overlay/ /etc/s6-overlay/
COPY --chmod=0755 image/cont-init.d/20-matriz-seed /etc/cont-init.d/20-matriz-seed
COPY --chmod=0755 image/cont-init.d/25-connector-token /etc/cont-init.d/25-connector-token
