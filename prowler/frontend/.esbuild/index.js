const { build } = require('./esbuild.config');

(async () => {
  if (process.argv.includes('--watch')) {
    await build({ watch: true });
  } else {
    await build();
  }
})();
