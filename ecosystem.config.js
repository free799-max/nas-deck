module.exports = {
  apps: [
    {
      name: "nas-deck-backend",
      cwd: "/home/free/code/nas-deck",
      script: "./start-backend.sh",
      autorestart: true,
      max_restarts: 5,
      min_uptime: "10s",
    },
    {
      name: "nas-deck-frontend",
      cwd: "/home/free/code/nas-deck/frontend",
      script: "npm",
      args: "run dev",
      autorestart: true,
      max_restarts: 5,
      min_uptime: "10s",
    },
  ],
};
