const { build, serve } = require('./esbuild.config');

(async () => {
  if (process.argv.includes('--serve')) {
    await serve();
  } else if (process.argv.includes('--watch')) {
    await build({ watch: true });
  } else {
    await build();
  }
})();
