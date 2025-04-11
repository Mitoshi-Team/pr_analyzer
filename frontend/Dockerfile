# Используем официальный образ Node.js
FROM node:20

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем package.json и package-lock.json
COPY package*.json ./

# Устанавливаем зависимости
RUN npm install

# Копируем весь код фронтенда
COPY . .

# Запускаем Vite в режиме разработки
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]