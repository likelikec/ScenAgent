FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app

# 设置默认后端地址（可通过 --build-arg 覆盖）
# 注意：127.0.0.1 在容器内指向容器自身，不适用于容器化部署
# 容器化部署时请使用：--build-arg VITE_API_BASE_URL=http://host.docker.internal:8000
# 或根据实际网络配置设置正确的后端地址
ARG VITE_API_BASE_URL=http://127.0.0.1:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
