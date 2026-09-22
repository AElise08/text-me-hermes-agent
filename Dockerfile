FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-67021a7029e33e80bcb27899be6515a5a0e9b37b@sha256:0c3892e93c1a001c61fb7106396e0a4b7e0219008184fd90719caa84a3390ff0
# Cloud deployments run without compose.yml; keep usage reporting enabled.
ENV AGENT_ID=text-me

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
