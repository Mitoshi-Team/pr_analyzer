# Этап сборки (build stage)
FROM node:16-alpine as build-stage

# Установка рабочей директории
WORKDIR /app

# Копирование package.json и package-lock.json (если существует)
COPY package*.json ./

# Установка зависимостей
RUN npm install

# Копирование исходного кода проекта
COPY . .

# Сборка проекта для продакшн
RUN npm run build

# Этап запуска (production stage)
FROM nginx:stable-alpine as production-stage

# Копирование собранного проекта из стадии сборки в директорию nginx
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Копирование кастомной nginx конфигурации
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открываем порт 80
EXPOSE 80

# Запуск nginx
CMD ["nginx", "-g", "daemon off;"]