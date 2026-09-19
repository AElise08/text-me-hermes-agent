FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-ef0019372ff8bca593611b31ebd2e08f9f1458ff@sha256:a8a2f97ad78b8192d80a984dce81d3bf5a9a883d18cb7b677704913a09b56aee
COPY runtime/SOUL.md /var/lib/hermes/SOUL.md
COPY LICENSE NOTICE /usr/share/doc/matriz/
COPY skills/matriz/ /opt/hermes/skills/matriz/
COPY scripts/ /opt/matriz/scripts/
COPY templates/ /opt/matriz/templates/
COPY fonts/ /opt/matriz/fonts/
RUN chown -R root:root /opt/matriz && chmod 0755 /opt/matriz/scripts/*.py && chmod 0644 /var/lib/hermes/SOUL.md

COPY image/s6-overlay/ /etc/s6-overlay/
COPY --chmod=0755 image/cont-init.d/20-matriz-seed /etc/cont-init.d/20-matriz-seed
COPY --chmod=0755 image/cont-init.d/25-connector-token /etc/cont-init.d/25-connector-token
