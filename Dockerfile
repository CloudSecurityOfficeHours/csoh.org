FROM nginx:alpine

# Copy custom nginx config that mirrors .htaccess security rules
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy site files
COPY . /usr/share/nginx/html/

# Remove files that should not be served
RUN rm -rf /usr/share/nginx/html/.git \
           /usr/share/nginx/html/.github \
           /usr/share/nginx/html/.claude \
           /usr/share/nginx/html/__pycache__ \
           /usr/share/nginx/html/tools \
           /usr/share/nginx/html/Dockerfile \
           /usr/share/nginx/html/docker-compose.yml \
           /usr/share/nginx/html/nginx.conf \
           /usr/share/nginx/html/.gitignore \
           /usr/share/nginx/html/.htaccess \
           /usr/share/nginx/html/.dockerignore

# Remove sensitive file types (scripts, markdown docs, backups)
RUN find /usr/share/nginx/html -name '*.py' -delete && \
    find /usr/share/nginx/html -name '*.pyc' -delete && \
    find /usr/share/nginx/html -name '*.md' -delete && \
    find /usr/share/nginx/html -name '*.sh' -delete && \
    find /usr/share/nginx/html -name '*.bak' -delete && \
    find /usr/share/nginx/html -name '*.log' -delete

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
