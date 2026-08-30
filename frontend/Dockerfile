# =============================================================================
# Nexus frontend image: plain nginx serving the static HTML/CSS/vanilla-JS
# app. No build step — there is nothing to compile (no React/Vue/bundler),
# which is the whole point of the mandated vanilla stack.
# =============================================================================
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html

# Don't ship the Dockerfile/nginx.conf themselves into the served root.
RUN rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/nginx.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -qO- http://localhost/healthz || exit 1
