/** @type {import('next').NextConfig} */

const isProduction = process.env.NODE_ENV === "production";

const nextConfig = {
    basePath: isProduction ? "/BookWebsite" : '',
    output: "export",
    distDir: "dist",
    images: {
        unoptimized: true,
    },
};

export default nextConfig;
