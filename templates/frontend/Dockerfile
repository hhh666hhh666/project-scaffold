# 用 slim（Debian/glibc）而非 alpine：esbuild 没有 x64-musl 的官方二进制，
# alpine 下 vite build 会报 "You installed esbuild for another platform"。
FROM node:22-slim AS build
WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmmirror.com

# ⚠️ 依赖层必须靠前：npm ci 严格按 package-lock.json 装（锁文件要入库）。
COPY package.json package-lock.json ./
RUN npm ci --registry="$NPM_REGISTRY" --no-audit --no-fund

COPY . .

# 版本与构建信息在构建期注入（值由发布流水线从 git tag 算出，vite.config.ts 再 define 成常量）。
# ⚠️ 必须声明在 npm ci 那一层**之后**、npm run build **之前**：ARG 值一变，它之后的层
#    缓存全失效，放到前面会让每次发版都白重装一遍依赖。
ARG APP_VERSION=dev
ARG APP_COMMIT=unknown

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
