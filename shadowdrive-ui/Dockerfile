FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install packages
RUN npm install

# Copy source files
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Run Vite dev server with host and port options
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
