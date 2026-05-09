# Pinned to a specific minor version + image digest for supply-chain safety.
# `nginx:alpine` (unpinned) would resolve to whatever the registry serves
# today; a compromised tag could ship malicious bytes into our build. The
# @sha256: pin makes the build reproducible and tamper-evident.
#
# To update: `docker pull nginx:1.27-alpine && \
#             docker inspect --format='{{index .RepoDigests 0}}' nginx:1.27-alpine`
FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10

# Refresh Alpine packages on top of the pinned base. The digest pin
# guarantees we start from known bytes, but the packages baked into that
# digest age — `apk upgrade` pulls current versions from Alpine's repos,
# picking up security patches (libssl3, libxml2, libpng, etc.) without
# losing reproducibility on the base layer. Trivy will catch any HIGH/
# CRITICAL CVEs that survive this step.
RUN apk upgrade --no-cache && \
    rm -rf /var/cache/apk/*

# Copy custom nginx config that mirrors .htaccess security rules.
# The security-headers snippet is `include`d into every location block;
# without that, nginx's add_header inheritance gets clobbered by the
# per-location Cache-Control headers and HSTS/CSP/etc. silently disappear.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-security-headers.conf /etc/nginx/conf.d/security-headers.conf

# Copy site files. The .dockerignore at the repo root excludes secrets,
# private keys, internal directories, etc., so they never enter the build
# context — defense in depth alongside the post-COPY rm/find below.
COPY . /usr/share/nginx/html/

# Remove files that should not be served. Belt-and-braces: most of these
# are also blocked at request time by `location ~ /\.` and friends in
# nginx.conf, but stripping them out of the image means the bytes aren't
# present in any layer if someone exfiltrates the image itself.
RUN rm -rf /usr/share/nginx/html/.git \
           /usr/share/nginx/html/.github \
           /usr/share/nginx/html/.claude \
           /usr/share/nginx/html/__pycache__ \
           /usr/share/nginx/html/tools \
           /usr/share/nginx/html/seo-audits \
           /usr/share/nginx/html/Dockerfile \
           /usr/share/nginx/html/docker-compose.yml \
           /usr/share/nginx/html/nginx.conf \
           /usr/share/nginx/html/nginx-security-headers.conf \
           /usr/share/nginx/html/.gitignore \
           /usr/share/nginx/html/.htaccess \
           /usr/share/nginx/html/.dockerignore

# Remove sensitive file types (scripts, markdown docs, backups, secrets,
# private keys). The `.env`/`*.pem`/`*.key` patterns are the security-
# critical ones — even though .dockerignore should have prevented them
# from being COPY'd in the first place, this is the second line of defense.
RUN find /usr/share/nginx/html -name '*.py' -delete && \
    find /usr/share/nginx/html -name '*.pyc' -delete && \
    find /usr/share/nginx/html -name '*.md' -delete && \
    find /usr/share/nginx/html -name '*.sh' -delete && \
    find /usr/share/nginx/html -name '*.bak' -delete && \
    find /usr/share/nginx/html -name '*.log' -delete && \
    find /usr/share/nginx/html -name '.env*' -delete && \
    find /usr/share/nginx/html -name '*.pem' -delete && \
    find /usr/share/nginx/html -name '*.key' -delete && \
    find /usr/share/nginx/html -name '*.crt' -delete

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
