module.exports = {
  apps: [
    {
      name: "email-engine-ui",
      script: "node_modules/.bin/next",
      args: "start --port 3110",
      cwd: "C:\\Users\\User\\projects\\ai-email-engine\\frontend",
      env: {
        NODE_ENV: "production",
        PORT: 3110,
      },
    },
  ],
};
