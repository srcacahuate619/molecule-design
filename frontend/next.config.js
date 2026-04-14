/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // paper.js (ketcher-core dep) has conditional require() for Node-only
    // modules (jsdom, canvas). In the browser `self` is already `window`,
    // so those branches are never taken at runtime.
    // Tell webpack to NOT parse paper.js, avoiding unresolvable requires.
    config.module.noParse = [
      ...(config.module.noParse || []),
      /paper[\\/]dist[\\/]/,
    ];

    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      path: false,
      canvas: false,
    };

    return config;
  },
};

module.exports = nextConfig;
