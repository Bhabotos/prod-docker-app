# Static frontend served by unprivileged nginx (runs as a non-root user).
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
# Dashboard (index.html + js/ + dashboard.css) and the original items demo (items.html + app.js + style.css).
COPY index.html items.html style.css dashboard.css app.js /usr/share/nginx/html/
COPY js/ /usr/share/nginx/html/js/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8080/healthz || exit 1
