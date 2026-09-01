FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD wget --spider -q http://127.0.0.1:3000 || exit 1

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]
