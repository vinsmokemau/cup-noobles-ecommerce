# syntax=docker/dockerfile:1
# Local development image (T1.6). T20.2 adds the production build.
FROM node:22-slim

RUN npm install --global pnpm@12.6.0

WORKDIR /app

COPY .npmrc package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# The DS packages are private (S8). The token is a build secret: it exists only
# in this RUN, and the .npmrc line written here holds a reference, not the
# token, and is removed before the layer is committed (§4.5).
RUN --mount=type=secret,id=node_auth_token,env=NODE_AUTH_TOKEN \
    echo '//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}' >> ~/.npmrc \
    && pnpm install --frozen-lockfile --ignore-scripts \
    && rm ~/.npmrc

COPY . .

EXPOSE 3000
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
