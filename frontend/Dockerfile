FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app

# 设置默认后端地址（可通过 --build-arg 覆盖）
# 留空时，前端会按当前页面主机自动推导：
# - 本地开发 5173 -> 后端 8003
# - Docker/云端页面 3000 -> 后端 9000
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
