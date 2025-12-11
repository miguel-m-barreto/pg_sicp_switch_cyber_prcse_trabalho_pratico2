import type { NextConfig } from "next";

// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig : NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "www.pingodoce.pt",
      },
      {
        protocol: "https",
        hostname: "www.auchan.pt",
      },
    ],
  },
};

module.exports = nextConfig;
