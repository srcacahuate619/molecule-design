/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack: (config) => {
    // paper.js (ketcher-core dep) has conditional require() for Node-only
    // modules (jsdom, canvas). In the browser `self` is already `window`,
    // so those branches are never taken at runtime.
    // Tell webpack to NOT parse paper.js, avoiding unresolvable requires.
    //
    // molstar/build/viewer also uses dynamic require() calls and pre-compiled
    // CSS that is incompatible with webpack static analysis — add to noParse.
    config.module.noParse = [
      ...(config.module.noParse || []),
      /paper[\\/]dist[\\/]/,
      /molstar[\\/]build[\\/]/,
    ];

    // Exclude molstar's pre-compiled CSS from Next.js css-loader pipeline
    // It's loaded manually via a <style> tag in AdvancedMolstarViewer
    config.module.rules = config.module.rules.map((rule) => {
      if (rule.oneOf) {
        rule.oneOf = rule.oneOf.map((one) => {
          if (one.test && one.test.toString().includes("css")) {
            return {
              ...one,
              exclude: [
                ...(one.exclude ? (Array.isArray(one.exclude) ? one.exclude : [one.exclude]) : []),
                /molstar[\\/]build[\\/]/,
              ],
            };
          }
          return one;
        });
      }
      return rule;
    });

    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      path: false,
      canvas: false,
    };

    config.resolve.alias = {
      ...config.resolve.alias,
      "pdfjs-dist/build/pdf.worker.mjs": false,
      "pdfjs-dist/build/pdf.worker.min.mjs": false,
    };

    return config;
  },
};

module.exports = nextConfig;
