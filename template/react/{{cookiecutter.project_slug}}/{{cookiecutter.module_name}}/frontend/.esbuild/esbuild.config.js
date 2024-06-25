/* eslint-disable global-require */

const esbuild = require('esbuild');
const path = require('path');
 
const SvgrPlugin = require('esbuild-plugin-svgr');
const CopyPlugin = require('esbuild-plugin-copy').default;
const CleanPlugin = require('esbuild-plugin-clean').default;
const { NodeModulesPolyfillPlugin } = require('@esbuild-plugins/node-modules-polyfill');

const packageJson = require('../package.json');
const HtmlPlugin = require('./plugins/html');

const CURRENT_ENV = process.env.NODE_ENV || 'development.local';
const BUILD_PATH = path.join(__dirname, '..', 'build');
const WEB_LOCATION_PREFIX = process.env.WEB_LOCATION_PREFIX;

// Load .env.* file depending on the active environment
require('dotenv').config({ path: `.env.${CURRENT_ENV}` });

const BUILD_CONFIG = {
  entryPoints: [
    path.join(__dirname, '..', 'src', 'index.tsx'),
    path.join(__dirname, '..', 'src', 'index.html'),
  ],
  assetNames: '[name]-[hash]',
  entryNames: '[name]-[hash]',
  outdir: BUILD_PATH,
  bundle: true,
  minify: !CURRENT_ENV.includes('development.local'),
  sourcemap: true,
  target: 'es2015',
  metafile: true,
  // splitting: true,
  // set in case file loader is added below
  plugins: [
    CleanPlugin({
      patterns: [`${BUILD_PATH}/*`, `!${BUILD_PATH}/index.html`],
      sync: true,
      verbose: false
    }),
    SvgrPlugin({
      prettier: false,
      svgo: false,
      svgoConfig: {
        plugins: [{ removeViewBox: false }],
      },
      titleProp: true,
      ref: true,
    }),
    CopyPlugin({
      copyOnStart: true,
      // https://github.com/LinbuduLab/nx-plugins/issues/57
      assets: [
        {
          from: ['./public/*'],
          to: ['./'],
        },
      ],
    }),
    NodeModulesPolyfillPlugin(),
    HtmlPlugin({
      prefix: WEB_LOCATION_PREFIX,
      filename: path.join(BUILD_PATH, 'index.html'),
      env: true,
    }),
  ],
  inject: [path.join(__dirname, 'esbuild.shims.js')],
  define: {
    // Define replacements for env vars starting with `REACT_APP_`
    ...Object.entries(process.env).reduce(
      (memo, [name, value]) => name.startsWith('REACT_APP_') ?
        { ...memo, [`process.env.${name}`]: JSON.stringify(value) } :
        memo,
      {},
    ),
    'process.cwd': 'dummyProcessCwd',
    'process.env.PUBLIC_URL': '""', // empty for now to point to the root
    'process.env.BASE_PATH': '"/"',
    'process.env.NODE_ENV': JSON.stringify(CURRENT_ENV),
    global: 'window',
  },
  external: [
    ...Object.keys(packageJson.devDependencies || {}),
  ],
  loader: {
    '.md': 'text',
    '.gif': 'dataurl',
  }
};

const build = async (overrides = {}) => {
  try {
    await esbuild.build({ ...BUILD_CONFIG, ...overrides });
    console.log('done building');
  } catch (e) {
    console.error(e);
    process.exit(1);
  }
};

module.exports = { build };
