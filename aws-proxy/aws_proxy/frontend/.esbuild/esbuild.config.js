/* eslint-disable global-require */

const esbuild = require('esbuild');
const path = require('path');
 
const SvgrPlugin = require('esbuild-plugin-svgr');
const CopyPlugin = require('esbuild-plugin-copy').default;
const CleanPlugin = require('esbuild-plugin-clean').default;
const { NodeModulesPolyfillPlugin } = require('@esbuild-plugins/node-modules-polyfill');

const packageJson = require('../package.json');
const HtmlPlugin = require('./plugins/html');
const { writeFileSync } = require('fs');

const CURRENT_ENV = process.env.NODE_ENV || 'development.local';
const BUILD_PATH = path.join(__dirname, '..', '..', 'server', 'static');

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
  target: 'es2020',
  metafile: true,
  // splitting: true,
  // set in case file loader is added below
  plugins: [
    CleanPlugin({
      patterns: [`${BUILD_PATH}/*`, `!${BUILD_PATH}/index.html`],
      sync: true,
      verbose: false,
      options: {
        force: true
      }
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
    writeFileSync(path.join(BUILD_PATH, '__init__.py'),'')
    console.log('done building');
  } catch (e) {
    console.error(e);
    process.exit(1);
  }
};

module.exports = { build };
